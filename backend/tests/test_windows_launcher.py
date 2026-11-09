"""Exercise the batch launcher with a harmless uvicorn module in a temp folder."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows batch launcher')


@pytest.fixture
def launcher(tmp_path):
    script = tmp_path / 'start_windows.bat'
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'start_windows.bat', script)
    (tmp_path / 'uvicorn.py').write_text(
        'import hashlib,json,os,sys\n'
        'from pathlib import Path\n'
        "key=os.environ.get('WEBUI_SECRET_KEY', '')\n"
        "Path('launch-result.json').write_text(json.dumps({"
        "'args':sys.argv[1:], 'key_length':len(key), "
        "'key_hash':hashlib.sha256(key.encode()).hexdigest()}))\n",
        encoding='utf-8',
    )
    env = {
        **os.environ,
        'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', ''),
        'PYTHONPATH': str(tmp_path),
        'WEBUI_SECRET_KEY': '',
        'WEBUI_JWT_SECRET_KEY': '',
        'WEBUI_SECRET_KEY_FILE': str(tmp_path / 'key with spaces'),
        'WEBUI_SECRET_KEY_LENGTH': '24',
        'WEB_LOADER_ENGINE': '',
        'FORWARDED_ALLOW_IPS': '',
    }

    def run(**overrides):
        result = subprocess.run(
            ['cmd.exe', '/d', '/c', str(script)],
            cwd=tmp_path,
            env={**env, **overrides},
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads((tmp_path / 'launch-result.json').read_text())

    return run, tmp_path / 'key with spaces'


def test_launcher_generates_key_once_and_passes_proxy_setting(launcher):
    run, key_path = launcher
    first = run()
    initial_key = key_path.read_bytes()
    second = run()
    assert len(initial_key) >= 32
    assert first['key_hash'] == second['key_hash'] == hashlib.sha256(initial_key).hexdigest()
    assert key_path.read_bytes() == initial_key
    forwarded_index = first['args'].index('--forwarded-allow-ips')
    assert first['args'][forwarded_index + 1] == '*'


def test_launcher_preserves_explicit_key_with_exclamation_mark(launcher):
    run, key_path = launcher
    synthetic_key = 'synthetic!test!key'
    result = run(WEBUI_SECRET_KEY=synthetic_key)
    assert result['key_hash'] == hashlib.sha256(synthetic_key.encode()).hexdigest()
    assert not key_path.exists()
