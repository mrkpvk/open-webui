"""Exercise the production option validator without initializing application data."""

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

source = Path(__file__).resolve().parents[1] / 'open_webui/routers/benchmarks.py'
tree = ast.parse(source.read_text())
nodes = [
    node
    for node in tree.body
    if (
        isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id in ('DEFAULT_OPTIONS', 'INTEGER_OPTIONS', 'FLOAT_OPTIONS')
            for t in node.targets
        )
    )
    or (isinstance(node, ast.FunctionDef) and node.name in ('effective_options', 'direct_model'))
]
namespace = {'math': math}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
options = namespace['effective_options']


def test_strict_benchmarks_cannot_bypass_webui_presets_or_chained_models():
    def info(base=None, params=None):
        return SimpleNamespace(base_model_id=base, params=SimpleNamespace(model_dump=lambda **kw: params or {}))

    assert namespace['direct_model'](None)
    assert namespace['direct_model'](info())
    assert not namespace['direct_model'](info(base='restricted-base'))
    assert not namespace['direct_model'](info(params={'system': 'Administrator instruction'}))
    assert not namespace['direct_model'](info(params={'num_gpu': 0}))


def test_cpu_and_explicit_zero_values_are_frozen():
    source = {'temperature': 0, 'max_tokens': 8, 'num_gpu': 0, 'stop': ['\n', ' END ']}
    resolved = options(source)
    assert resolved['num_gpu'] == 0 and resolved['temperature'] == 0 and resolved['num_predict'] == 8
    assert resolved['stop'] == ['\n', ' END '] and source['max_tokens'] == 8


@pytest.mark.parametrize(
    'params',
    [
        {'num_gpu': 1},
        {'num_gpu': False},
        {'temperature': float('nan')},
        {'num_thread': 0},
        {'num_predict': -1},
        {'max_tokens': 8, 'num_predict': 16},
        {'seed': 1},
        {'custom_params': {'num_gpu': 1}},
        {'stop': '\n'},
        {'no_repeat_ngram_size': 3},
    ],
)
def test_unsupported_or_unsafe_settings_are_rejected(params):
    with pytest.raises(ValueError):
        options(params)
