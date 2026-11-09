"""Regression tests without starting the server, migrations, or reading user config."""

import ast
import copy
import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope='module')
def payload():
    backend = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend))
    # Only environmental initialization is replaced. Parameter handling, merging,
    # message conversion and logit-bias parsing all use the real production code.
    env = types.ModuleType('open_webui.env')
    env.CHAT_STREAM_RESPONSE_CHUNK_MAX_BUFFER_SIZE = 1024
    config = types.ModuleType('open_webui.config')
    config.DEFAULT_RAG_TEMPLATE = ''
    try:
        with patch.dict(sys.modules, {'open_webui.env': env, 'open_webui.config': config}):
            yield importlib.import_module('open_webui.utils.payload')
    finally:
        sys.path.remove(str(backend))


@pytest.fixture(scope='module')
def apply_chat_params(payload):
    # This function lives in the large request middleware. Compile that exact
    # function so testing it cannot initialize databases, tools or model clients.
    path = Path(__file__).resolve().parents[1] / 'open_webui/utils/middleware.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'apply_params_to_form_data'
    )
    namespace = {
        'copy': copy,
        'json': json,
        'deep_update': payload.deep_update,
        'remove_open_webui_params': payload.remove_open_webui_params,
        'apply_model_params_to_body_ollama': payload.apply_model_params_to_body_ollama,
        'convert_logit_bias_input_to_json': importlib.import_module(
            'open_webui.utils.misc'
        ).convert_logit_bias_input_to_json,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['apply_params_to_form_data']


def test_standard_chat_preserves_cpu_zero_seed_and_false_thinking(payload, apply_chat_params):
    request = {
        'model': 'local-model',
        'messages': [{'role': 'user', 'content': 'Answer yes.'}],
        'params': {
            'num_gpu': '0',
            'num_thread': '1',
            'seed': '0',
            'temperature': 0,
            'max_tokens': '8',
            'think': False,
            'no_repeat_ngram_size': 3,
            'min_length': 2,
            'ignore_eos': True,
            'logit_bias': '1:100',
        },
    }
    body = payload.convert_payload_openai_to_ollama(apply_chat_params(request, {'owned_by': 'ollama'}))
    assert body['options'] == {'num_gpu': 0, 'num_thread': 1, 'seed': 0, 'temperature': 0.0, 'num_predict': 8}
    assert body['think'] is False
    assert 'params' not in body
    assert 'num_predict' not in body


def test_custom_params_do_not_reintroduce_ui_flags_or_consume_shared_settings(payload):
    settings = {
        'temperature': 0.7,
        'custom_params': {'num_gpu': '0', 'seed': '0', 'no_repeat_ngram_size': '4', 'min_length': '2'},
    }
    before = copy.deepcopy(settings)
    first = payload.apply_model_params_to_body_ollama(settings, {})
    second = payload.apply_model_params_to_body_ollama(settings, {})
    assert first == second == {'options': {'temperature': 0.7, 'num_gpu': 0, 'seed': 0}}
    assert settings == before


def test_max_tokens_is_an_ollama_option_and_explicit_option_takes_precedence(payload):
    base = {'model': 'local-model', 'messages': [], 'max_tokens': 8}
    assert payload.convert_payload_openai_to_ollama(base)['options'] == {'num_predict': 8}
    base['options'] = {'max_tokens': 16, 'num_gpu': 0}
    assert payload.convert_payload_openai_to_ollama(base)['options'] == {'num_predict': 16, 'num_gpu': 0}
    assert base['options'] == {'max_tokens': 16, 'num_gpu': 0}


def test_openai_keeps_provider_decoding_options_but_not_client_diagnostic(payload, apply_chat_params):
    body = apply_chat_params(
        {'params': {'min_length': 2, 'ignore_eos': True, 'no_repeat_ngram_size': 3, 'logit_bias': '1:-5'}},
        {'owned_by': 'openai'},
    )
    assert body == {'min_length': 2, 'ignore_eos': True, 'logit_bias': {'1': -5}}


def test_direct_model_options_preserve_zero_root_values_and_other_options(payload):
    result = payload.apply_model_params_to_body_ollama(
        {'num_gpu': 0, 'seed': 0, 'keep_alive': '0', 'think': False},
        {'options': {'num_ctx': 2048}},
    )
    assert result == {'options': {'num_ctx': 2048, 'num_gpu': 0, 'seed': 0}, 'keep_alive': 0, 'think': False}


def test_openai_model_settings_are_not_consumed(payload):
    params = {'custom_params': {'seed': '0'}, 'no_repeat_ngram_size': 3}
    before = copy.deepcopy(params)
    assert payload.apply_model_params_to_body_openai(params, {}) == {'seed': 0}
    assert params == before


def test_cli_creates_secret_once_without_starting_server(payload, tmp_path, monkeypatch):
    cli = importlib.import_module('open_webui')
    key_file = tmp_path / 'synthetic-cli-key'
    monkeypatch.setattr(cli, 'KEY_FILE', key_file)
    monkeypatch.delenv('WEBUI_SECRET_KEY', raising=False)
    monkeypatch.setenv('WEBUI_SECRET_KEY_LENGTH', '24')
    monkeypatch.setenv('USE_CUDA_DOCKER', 'false')
    monkeypatch.setenv('FROM_INIT_PY', 'false')
    monkeypatch.setattr(cli.uvicorn, 'run', lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, 'open_webui.main', types.ModuleType('open_webui.main'))
    monkeypatch.setattr(sys.modules['open_webui.env'], 'UVICORN_WORKERS', 1, raising=False)

    cli.serve()
    initial_key = key_file.read_text(encoding='ascii')
    assert len(initial_key) >= 32
    monkeypatch.delenv('WEBUI_SECRET_KEY')
    cli.serve()
    assert key_file.read_text(encoding='ascii') == initial_key
