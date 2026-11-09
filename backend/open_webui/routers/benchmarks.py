"""CPU experiments with immutable inputs and durable, owner-scoped checkpoints."""

import asyncio
import csv
import hashlib
import io
import json
import math
import subprocess
import time
from contextlib import suppress
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from open_webui.env import DATA_DIR, VERSION, WEBUI_BUILD_HASH
from open_webui.models.config import Config
from open_webui.models.users import Users
from open_webui.routers import ollama
from open_webui.utils.auth import get_verified_user
from open_webui.utils.benchmark_core import (
    SCORER_VERSION,
    SCHEDULE_VERSION,
    build_schedule,
    score_response,
    validate_question,
    validate_scorer,
)
from open_webui.utils.benchmark_store import BenchmarkConflict, BenchmarkStore

router = APIRouter()
LEASE_SECONDS = 60
DEFAULT_OPTIONS = {
    'num_gpu': 0,
    'num_thread': 1,
    'num_batch': 512,
    'num_ctx': 2048,
    'num_predict': 128,
    'temperature': 0,
    'top_k': 40,
    'top_p': 0.9,
    'min_p': 0.0,
    'repeat_penalty': 1.0,
    'repeat_last_n': 64,
    'presence_penalty': 0.0,
    'frequency_penalty': 0.0,
}
INTEGER_OPTIONS = {
    'num_gpu': (0, 0),
    'num_thread': (1, 256),
    'num_batch': (1, 4096),
    'num_ctx': (128, 131072),
    'num_predict': (1, 32768),
    'top_k': (0, 10000),
    'repeat_last_n': (-1, 131072),
    'num_keep': (0, 131072),
}
FLOAT_OPTIONS = {
    'temperature': (0, 2),
    'top_p': (0, 1),
    'min_p': (0, 1),
    'typical_p': (0, 1),
    'repeat_penalty': (0, 10),
    'presence_penalty': (-2, 2),
    'frequency_penalty': (-2, 2),
}


class RunForm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=160)
    model_id: str = Field(min_length=1, max_length=256)
    backend_index: int = Field(ge=0, strict=True)
    questions: list[dict] = Field(min_length=1, max_length=500)
    configurations: list[dict] = Field(min_length=1, max_length=16)
    repeats: int = Field(default=3, ge=1, le=100, strict=True)
    order: str = 'dataset'
    order_seed: int = Field(default=0, ge=0, le=2**31 - 1, strict=True)
    seed_mode: str = 'fixed'
    inference_seeds: list[int] = [0]
    scorer: dict = {'type': 'exact'}
    system_prompt: str = Field(default='', max_length=100000)
    timeout_seconds: int = Field(default=600, ge=5, le=3600, strict=True)


def effective_options(params):
    if not isinstance(params, dict):
        raise ValueError('Each configuration needs a params object')
    params = dict(params)
    if 'max_tokens' in params:
        if 'num_predict' in params:
            raise ValueError('Use max_tokens or num_predict, not both')
        params['num_predict'] = params.pop('max_tokens')
    for key, value in params.items():
        if key in INTEGER_OPTIONS:
            low, high = INTEGER_OPTIONS[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key} must be an integer from {low} to {high}')
        elif key in FLOAT_OPTIONS:
            low, high = FLOAT_OPTIONS[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key} must be finite and from {low} to {high}')
        elif key == 'stop':
            if (
                not isinstance(value, list)
                or len(value) > 32
                or any(not isinstance(t, str) or not t or len(t) > 1024 for t in value)
            ):
                raise ValueError('stop must be a list of up to 32 nonempty strings')
        else:
            raise ValueError(f'Unsupported benchmark parameter: {key}. Set inference seeds separately.')
    return {**DEFAULT_OPTIONS, **params, 'num_gpu': 0}


def store(request):
    return request.app.state.benchmark_store


def owned(request, run_id, user):
    try:
        return store(request).get(run_id, user.id)
    except KeyError:
        raise HTTPException(404, 'Benchmark run not found') from None


def fingerprint(url):
    return hashlib.sha256(url.encode()).hexdigest()


def direct_model(info):
    """Presets must not acquire a path that bypasses their configured policy."""
    return info is None or (not info.base_model_id and not info.params.model_dump(exclude_none=True))


def source_revision():
    try:
        root = Path(__file__).resolve().parents[3]
        revision = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, timeout=5, check=True
        )
        dirty = subprocess.run(
            ['git', 'status', '--porcelain'], cwd=root, capture_output=True, text=True, timeout=5, check=True
        )
        return {'app_commit': revision.stdout.strip(), 'app_dirty': bool(dirty.stdout.strip())}
    except (OSError, subprocess.SubprocessError):
        return {'app_commit': None, 'app_dirty': None}


async def connection(request, user, model_id, backend_index):
    if user is None or user.role not in ('admin', 'user'):
        raise HTTPException(403, 'Account is not allowed to run benchmarks')
    available = await ollama.get_ollama_tags(request, user=user)
    model = next((m for m in available['models'] if m['model'] == model_id), None)
    if not model or backend_index not in model.get('urls', []):
        raise HTTPException(403, 'Model is unavailable on this eligible backend')
    info = await ollama.Models.get_model_by_id(model_id)
    await ollama.check_model_access(user, info, ollama.BYPASS_MODEL_ACCESS_CONTROL)
    if not direct_model(info):
        raise HTTPException(
            409, 'Choose a direct Ollama model without WebUI parameter/system presets for strict benchmarking.'
        )
    urls = await Config.get('ollama.base_urls', [])
    if backend_index >= len(urls):
        raise HTTPException(409, 'Ollama backend configuration changed')
    url = urls[backend_index]
    configs = await Config.get('ollama.api_configs', {})
    config = ollama.resolve_api_config(configs, backend_index, url)
    if not config.get('enable', True):
        raise HTTPException(409, 'Ollama backend is disabled')
    provider_model = model_id
    prefix = config.get('prefix_id')
    if prefix and provider_model.startswith(prefix + '.'):
        provider_model = provider_model[len(prefix) + 1 :]
    key = ollama.get_api_key(backend_index, url, configs)

    async def call(path, method='GET', payload=None):
        return await ollama.send_request(
            url + path,
            method,
            payload=json.dumps(payload) if payload is not None else None,
            key=key,
            user=user,
            api_config=config,
            request=request,
        )

    tags = await call('/api/tags')
    actual = next((m for m in (tags or {}).get('models', []) if m.get('model') == provider_model), None)
    if not actual or not actual.get('digest'):
        raise HTTPException(409, 'Selected backend must expose an installed model digest')
    return {'call': call, 'model': provider_model, 'digest': actual['digest'], 'identity': fingerprint(url)}


@router.get('/models')
async def models(request: Request, user=Depends(get_verified_user)):
    result = await ollama.get_ollama_tags(request, user=user)
    eligible = []
    for model in result.get('models', []):
        info = await ollama.Models.get_model_by_id(model['model'])
        if direct_model(info):
            eligible.append(model)
    return {
        'models': [
            {
                'id': m['model'],
                'name': m.get('name', m['model']),
                'digest': m.get('digest'),
                'backends': [{'index': idx, 'name': f'Ollama connection {idx + 1}'} for idx in m.get('urls', [])],
            }
            for m in eligible
        ]
    }


@router.get('/runs')
async def runs(request: Request, user=Depends(get_verified_user)):
    return {'runs': store(request).list(user.id)}


@router.post('/runs')
async def create_run(form: RunForm, request: Request, user=Depends(get_verified_user)):
    data = form.model_dump()
    try:
        validate_scorer(data['scorer'])
        if len(json.dumps(data, allow_nan=False)) > 2_000_000:
            raise ValueError('Experiment input exceeds 2 MB')
        for q in data['questions']:
            if not isinstance(q.get('prompt'), str) or not q['prompt'].strip() or len(q['prompt']) > 100000:
                raise ValueError('Each question needs a nonempty prompt of at most 100,000 characters')
            validate_question(q, data['scorer'])
        for config in data['configurations']:
            config['name'] = str(config.get('name') or config.get('id', ''))[:160]
            config['params'] = effective_options(config.get('params', {}))
        schedule = build_schedule(
            data['questions'],
            data['configurations'],
            data['repeats'],
            data['order'],
            data['order_seed'],
            data['seed_mode'],
            data['inference_seeds'],
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from None
    conn = await connection(request, user, form.model_id, form.backend_index)
    version = await conn['call']('/api/version')
    info = await conn['call']('/api/show', 'POST', {'model': conn['model']})
    data.update(
        schema_version=1,
        scorer_version=SCORER_VERSION,
        schedule_version=SCHEDULE_VERSION,
        schedule=schedule,
        model_digest=conn['digest'],
        backend_identity=conn['identity'],
        ollama_version=(version or {}).get('version'),
        model_template=(info or {}).get('template'),
        model_parameters=(info or {}).get('parameters'),
        model_details=(info or {}).get('details'),
        model_system=(info or {}).get('system'),
        app_version=VERSION,
        app_build=WEBUI_BUILD_HASH,
        device='cpu',
        result_cache=False,
        context='independent',
        kv_cache_policy='engine default',
        dataset_sha256=hashlib.sha256(json.dumps(data['questions'], sort_keys=True).encode()).hexdigest(),
    )
    data.update(await asyncio.to_thread(source_revision))
    return store(request).create(user.id, data)


@router.get('/runs/{run_id}')
async def get_run(run_id: str, request: Request, user=Depends(get_verified_user)):
    return owned(request, run_id, user)


async def execute_run(app, run_id, owner_id, worker):
    db = app.state.benchmark_store
    request = Request(
        {
            'type': 'http',
            'app': app,
            'method': 'POST',
            'path': '/internal/benchmarks',
            'headers': [],
            'query_string': b'',
            'scheme': 'http',
            'server': ('localhost', 80),
        }
    )
    stop_event = asyncio.Event()
    current = None

    async def heartbeat():
        while not stop_event.is_set():
            if db.heartbeat(run_id, worker, LEASE_SECONDS):
                raise asyncio.CancelledError()
            await asyncio.sleep(1)

    beat = asyncio.create_task(heartbeat())
    try:
        run = db.get(run_id, owner_id)
        manifest = run['manifest']
        questions = {q['id']: q for q in manifest['questions']}
        configs = {c['id']: c for c in manifest['configurations']}
        while True:
            if beat.done():
                await beat
            trial = db.next_trial(run_id, worker)
            if trial is None:
                db.finish(run_id, worker, 'completed')
                return
            started = time.monotonic()
            try:
                user = await Users.get_user_by_id(owner_id)
                conn = await connection(request, user, manifest['model_id'], manifest['backend_index'])
                if conn['identity'] != manifest['backend_identity'] or conn['digest'] != manifest['model_digest']:
                    raise RuntimeError('Pinned backend or model digest changed. Create a new experiment.')
                runtime = await conn['call']('/api/version')
                if (runtime or {}).get('version') != manifest['ollama_version']:
                    raise RuntimeError('Ollama runtime version changed. Create a new experiment.')
                options = {**configs[trial['configuration_id']]['params'], 'seed': trial['seed'], 'num_gpu': 0}
                messages = (
                    [{'role': 'system', 'content': manifest['system_prompt']}] if manifest['system_prompt'] else []
                )
                messages.append({'role': 'user', 'content': questions[trial['question_id']]['prompt']})
                payload = {
                    'model': conn['model'],
                    'messages': messages,
                    'options': options,
                    'stream': False,
                    'keep_alive': '5m',
                }
                current = asyncio.create_task(
                    asyncio.wait_for(conn['call']('/api/chat', 'POST', payload), manifest['timeout_seconds'])
                )
                done, _ = await asyncio.wait([current, beat], return_when=asyncio.FIRST_COMPLETED)
                if beat in done:
                    await beat
                answer = await current
                if (
                    not isinstance(answer, dict)
                    or not answer.get('done')
                    or not isinstance(answer.get('message', {}).get('content'), str)
                ):
                    raise RuntimeError('Ollama did not return a completed text response')
                output = answer['message']['content']
                thinking = answer['message'].get('thinking')
                generation = json.dumps({'content': output, 'thinking': thinking}, ensure_ascii=False, sort_keys=True)
                scored = score_response(output, questions[trial['question_id']], manifest['scorer'])
                loaded = await conn['call']('/api/ps')
                evidence = [m for m in (loaded or {}).get('models', []) if m.get('digest') == conn['digest']]
                if not evidence or any(m.get('size_vram') != 0 for m in evidence):
                    raise RuntimeError('CPU execution could not be verified: model telemetry must report size_vram=0')
                result = {
                    'status': 'completed',
                    'output': output,
                    'score': scored['score'],
                    'valid': scored['score'] is not None and scored['error'] is None,
                    'actual': scored['actual'],
                    'expected': scored['expected'],
                    'scorer_error': scored['error'],
                    'effective_request': payload,
                    'device_evidence': evidence,
                    'output_sha256': hashlib.sha256(output.encode()).hexdigest(),
                    'generation_sha256': hashlib.sha256(generation.encode()).hexdigest(),
                    'thinking': thinking,
                    'provider_response': answer,
                    'finish_reason': answer.get('done_reason'),
                    'usage': {key: answer.get(key) for key in ('prompt_eval_count', 'eval_count', 'total_duration')},
                }
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Connection credentials/URLs must not leak through provider exception text.
                error = (
                    exc.detail
                    if isinstance(exc, HTTPException) and exc.status_code in (403, 409)
                    else (str(exc) if isinstance(exc, (RuntimeError, asyncio.TimeoutError)) else type(exc).__name__)
                )
                result = {'status': 'error', 'error': error or 'Inference timed out', 'score': 0, 'valid': False}
            result['elapsed_seconds'] = round(time.monotonic() - started, 4)
            db.checkpoint(run_id, worker, trial, result)
    except asyncio.CancelledError:
        with suppress(BenchmarkConflict):
            db.finish(run_id, worker, 'cancelled', 'Cancelled; resume continues incomplete trials.')
    except Exception:
        with suppress(BenchmarkConflict):
            db.finish(
                run_id, worker, 'failed', 'Worker interrupted. Completed trials are preserved; resume remaining work.'
            )
    finally:
        stop_event.set()
        for task in (beat, current):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
        if app.state.benchmark_tasks.get(run_id) is asyncio.current_task():
            app.state.benchmark_tasks.pop(run_id, None)


@router.post('/runs/{run_id}/{action}')
async def control_run(run_id: str, action: str, request: Request, user=Depends(get_verified_user)):
    run = owned(request, run_id, user)
    if action == 'cancel':
        store(request).cancel(run_id, user.id)
        task = request.app.state.benchmark_tasks.get(run_id)
        if task:
            task.cancel()
    elif action in ('start', 'resume'):
        if (
            run['manifest']['scorer_version'] != SCORER_VERSION
            or run['manifest']['schedule_version'] != SCHEDULE_VERSION
        ):
            raise HTTPException(409, 'Benchmark scoring/schedule version changed. Create a new experiment.')
        worker = str(uuid4())
        try:
            store(request).claim(run_id, user.id, worker, LEASE_SECONDS)
        except BenchmarkConflict as exc:
            raise HTTPException(409, str(exc)) from None
        task = asyncio.create_task(execute_run(request.app, run_id, user.id, worker))
        request.app.state.benchmark_tasks[run_id] = task
    else:
        raise HTTPException(404, 'Unknown benchmark action')
    return owned(request, run_id, user)


@router.get('/runs/{run_id}/export')
async def export_run(run_id: str, request: Request, format: str = 'json', user=Depends(get_verified_user)):
    run = owned(request, run_id, user)
    if format == 'json':
        body, media = json.dumps(run, ensure_ascii=False, indent=2), 'application/json'
    elif format == 'csv':
        output = io.StringIO(newline='')
        fields = [
            'id',
            'question_id',
            'configuration_id',
            'repeat_index',
            'seed',
            'status',
            'output',
            'score',
            'valid',
            'actual',
            'expected',
            'error',
            'scorer_error',
            'elapsed_seconds',
            'attempts',
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for trial in run['trials']:
            # Spreadsheet applications must not execute model output as a formula.
            row = {
                k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v)
                for k, v in trial.items()
            }
            writer.writerow(row)
        body, media = output.getvalue(), 'text/csv'
    else:
        raise HTTPException(422, 'format must be json or csv')
    return Response(
        body, media_type=media, headers={'Content-Disposition': f'attachment; filename="benchmark-{run_id}.{format}"'}
    )


def initialize(app):
    app.state.benchmark_store = BenchmarkStore(DATA_DIR / 'benchmarks.sqlite3')
    app.state.benchmark_tasks = {}


async def shutdown(app):
    tasks = list(app.state.benchmark_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
