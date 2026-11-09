"""Persistence contracts: isolation, lease ownership, recovery and honest metrics."""

import importlib.util
import time
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / 'open_webui/utils/benchmark_store.py'
spec = importlib.util.spec_from_file_location('benchmark_store_target', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def store(tmp_path):
    return module.BenchmarkStore(tmp_path / 'benchmarks.sqlite3')


def manifest():
    return {
        'name': 'Experiment',
        'configurations': [{'id': 'a', 'name': 'CPU'}],
        'schedule': [
            {'id': f'trial-{i}', 'index': i, 'question_id': 'q1', 'configuration_id': 'a', 'repeat_index': i, 'seed': 0}
            for i in range(3)
        ],
    }


def test_owner_isolation_and_frozen_inputs(store):
    saved = store.create('alice', manifest())
    with pytest.raises(KeyError):
        store.get(saved['id'], 'bob')
    assert store.list('bob') == []
    saved['manifest']['name'] = 'Changed in browser'
    assert store.get(saved['id'], 'alice')['manifest']['name'] == 'Experiment'
    assert store.list('alice')[0]['total_trials'] == 3


def test_global_lease_prevents_parallel_benchmarks_and_stale_worker_writes(store):
    first, second = store.create('alice', manifest()), store.create('bob', manifest())
    store.claim(first['id'], 'alice', 'worker1', 60)
    with pytest.raises(module.BenchmarkConflict):
        store.claim(second['id'], 'bob', 'worker2', 60)
    with pytest.raises(module.BenchmarkConflict):
        store.next_trial(first['id'], 'wrong-worker')
    store.finish(first['id'], 'worker1', 'cancelled')
    store.claim(second['id'], 'bob', 'worker2', 60)


def test_cancel_resume_preserves_completed_trials_and_attempt_history(store):
    saved = store.create('alice', manifest())
    store.claim(saved['id'], 'alice', 'worker1', 60)
    first = store.next_trial(saved['id'], 'worker1')
    store.checkpoint(
        saved['id'],
        'worker1',
        first,
        {'status': 'completed', 'output': 'yes', 'actual': True, 'score': 1, 'valid': True},
    )
    second = store.next_trial(saved['id'], 'worker1')
    store.cancel(saved['id'], 'alice')
    assert store.heartbeat(saved['id'], 'worker1', 60)
    store.finish(saved['id'], 'worker1', 'cancelled')
    store.claim(saved['id'], 'alice', 'worker2', 60)
    retried = store.next_trial(saved['id'], 'worker2')
    assert retried['id'] == second['id'] and retried['attempts'] == 2
    assert retried['attempt_history'][0]['status'] == 'cancelled'
    assert store.get(saved['id'], 'alice')['trials'][0]['output'] == 'yes'


def test_expired_lease_recovers_incomplete_trial_without_overwriting_output(store):
    saved = store.create('alice', manifest())
    store.claim(saved['id'], 'alice', 'old', 60)
    trial = store.next_trial(saved['id'], 'old')
    with store.connection() as db:
        db.execute('UPDATE benchmark_lease SET expires=?', (time.time() - 1,))
    with pytest.raises(module.BenchmarkConflict):
        store.heartbeat(saved['id'], 'old', 60)
    recovered = store.get(saved['id'], 'alice')
    assert recovered['status'] == 'interrupted'
    assert recovered['trials'][0]['status'] == 'pending'
    store.claim(saved['id'], 'alice', 'new', 60)
    assert store.next_trial(saved['id'], 'new')['id'] == trial['id']


def test_errors_and_pending_trials_stay_in_accuracy_denominator(store):
    saved = store.create('alice', manifest())
    store.claim(saved['id'], 'alice', 'worker', 60)
    trial = store.next_trial(saved['id'], 'worker')
    store.checkpoint(
        saved['id'],
        'worker',
        trial,
        {'status': 'completed', 'output': 'yes', 'actual': True, 'score': 1, 'valid': True},
    )
    trial = store.next_trial(saved['id'], 'worker')
    store.checkpoint(saved['id'], 'worker', trial, {'status': 'error', 'score': 0, 'valid': False, 'error': 'timeout'})
    summary = store.get(saved['id'], 'alice')['summary']
    assert summary['accuracy'] == 1 / 3
    assert summary['completed_accuracy'] == 1 / 2
    assert summary['valid_rate'] == 1 / 2 and summary['coverage'] == 2 / 3


def test_answer_agreement_and_raw_output_identity_are_distinct():
    rows = [
        {
            'question_id': 'q',
            'configuration_id': 'a',
            'status': 'completed',
            'output': text,
            'actual': True,
            'valid': True,
            'score': 1,
        }
        for text in ('true', 'YES')
    ]
    result = module.summarize(rows, [{'id': 'a', 'name': 'CPU'}])
    assert result['consistency']['answer_agreement'] == 1
    assert result['consistency']['rate'] == 0


def test_reasoning_variability_changes_output_identity_even_when_final_answers_match():
    rows = [
        {
            'question_id': 'q',
            'configuration_id': 'a',
            'status': 'completed',
            'output': 'true',
            'actual': True,
            'valid': True,
            'score': 1,
            'generation_sha256': digest,
        }
        for digest in ('thinking-a', 'thinking-b')
    ]
    summary = module.summarize(rows, [{'id': 'a', 'name': 'CPU'}])
    assert summary['consistency']['answer_agreement'] == 1
    assert summary['consistency']['rate'] == 0
