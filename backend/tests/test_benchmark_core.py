"""Pure benchmark contracts: scheduling independence and inspectable scoring."""

import copy
import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / 'open_webui/utils/benchmark_core.py'
_spec = importlib.util.spec_from_file_location('benchmark_core_test_target', _path)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

QUESTIONS = [{'id': f'q{index}', 'prompt': 'Reply yes.', 'expected': 'yes'} for index in range(8)]
CONFIGS = [{'id': 'a', 'params': {'temperature': 0}}, {'id': 'b', 'params': {'temperature': 0.5}}]


def schedule(**changes):
    args = dict(
        questions=QUESTIONS,
        configurations=CONFIGS,
        repeats=3,
        order='dataset',
        order_seed=4,
        seed_mode='fixed',
        inference_seeds=[0],
    )
    return core.build_schedule(**{**args, **changes})


def question_order(trials, repeat_index, configuration_id='a'):
    return [
        trial['question_id']
        for trial in trials
        if trial['repeat_index'] == repeat_index and trial['configuration_id'] == configuration_id
    ]


def test_schedule_expands_full_cross_product_without_mutating_dataset():
    before = copy.deepcopy((QUESTIONS, CONFIGS))
    trials = schedule()
    assert len(trials) == 48
    assert len({trial['id'] for trial in trials}) == 48
    assert [trial['index'] for trial in trials] == list(range(48))
    assert all(trial['seed'] == 0 for trial in trials)
    assert (QUESTIONS, CONFIGS) == before
    assert question_order(trials, 0) == [question['id'] for question in QUESTIONS]
    assert question_order(schedule(order='reverse'), 0) == [question['id'] for question in reversed(QUESTIONS)]


def test_shuffled_order_is_reproducible_shared_and_independent_of_inference_seed():
    once = schedule(order='shuffle_once')
    assert once == schedule(order='shuffle_once')
    assert question_order(once, 0) == question_order(once, 2) == question_order(once, 0, 'b')
    changed_seeds = schedule(order='shuffle_once', seed_mode='list', inference_seeds=[12, 13, 14])
    assert question_order(once, 0) == question_order(changed_seeds, 0)
    assert {trial['seed'] for trial in changed_seeds if trial['repeat_index'] == 2} == {14}
    changed_order = schedule(order='shuffle_once', order_seed=8)
    assert question_order(once, 0) != question_order(changed_order, 0)
    assert {trial['seed'] for trial in changed_order} == {0}


def test_shuffle_each_repeat_uses_new_order_but_is_reproducible():
    trials = schedule(order='shuffle_each_repeat')
    assert trials == schedule(order='shuffle_each_repeat')
    assert question_order(trials, 0) != question_order(trials, 1)
    assert question_order(trials, 1) == question_order(trials, 1, 'b')
    assert set(question_order(trials, 0)) == set(question_order(trials, 1))


@pytest.mark.parametrize(
    'change',
    [
        {'repeats': 0},
        {'seed_mode': 'list', 'inference_seeds': [1, 2]},
        {'seed_mode': 'fixed', 'inference_seeds': [-1]},
        {'order_seed': True},
        {'questions': [{'id': 'same'}, {'id': 'same'}]},
        {'order': 'unknown'},
        {'questions': [{'id': str(index)} for index in range(500)], 'repeats': 100},
    ],
)
def test_invalid_or_oversized_schedules_are_rejected(change):
    with pytest.raises(ValueError):
        schedule(**change)


def test_exact_scoring_options_and_wrong_answers_are_explicit():
    assert core.score_response(' YES\n', {'expected': 'yes'}, {'type': 'exact', 'case_sensitive': False})['passed']
    assert not core.score_response(' YES\n', {'expected': 'yes'}, {'type': 'exact'})['passed']
    assert not core.score_response('yes\n', {'expected': 'yes'}, {'type': 'exact', 'trim': False})['passed']
    invalid = core.score_response('yes', {'expected': 1}, {'type': 'exact'})
    assert invalid['score'] is None and invalid['error']


@pytest.mark.parametrize(
    ('answer', 'expected', 'passed'),
    [
        ('YES', True, True),
        (' false ', 'no', True),
        ('0', True, False),
        ('1', 1, True),
    ],
)
def test_boolean_answers_are_parsed_as_single_tokens(answer, expected, passed):
    result = core.score_response(answer, {'expected': expected}, {'type': 'boolean'})
    assert result['passed'] is passed and result['error'] is None


def test_malformed_model_answers_count_as_incorrect_without_becoming_config_errors():
    for response, scorer in [
        ('I think yes, but no.', {'type': 'boolean'}),
        ('not JSON', {'type': 'json_field', 'field': 'answer'}),
        ('{"other": true}', {'type': 'json_field', 'field': 'answer'}),
        ('{"answer": NaN}', {'type': 'json_field', 'field': 'answer'}),
    ]:
        result = core.score_response(response, {'expected': True}, scorer)
        assert result['score'] == 0 and result['passed'] is False and result['error']


def test_json_field_nested_arrays_and_boolean_number_distinction():
    scorer = {'type': 'json_field', 'field': 'results.0.answer'}
    response = '{"results":[{"answer":{"reachable":true,"path":["a","b"]}}]}'
    assert core.score_response(response, {'expected': {'reachable': True, 'path': ['a', 'b']}}, scorer)['passed']
    assert not core.score_response(response, {'expected': {'reachable': 1, 'path': ['a', 'b']}}, scorer)['passed']
    assert core.score_response('{"answer":null}', {'expected': None}, {'type': 'json_field', 'path': 'answer'})[
        'passed'
    ]


def graph_question(source='a', target='c', expected=None):
    return {
        'graph': {
            'nodes': ['a', 'b', 'c', 'isolated'],
            'edges': [['a', 'b'], ['b', 'a'], ['b', 'c']],
            'source': source,
            'target': target,
        },
        'expected': expected,
    }


def test_directed_reachability_uses_graph_ground_truth_including_cycles_and_zero_length_paths():
    scorer = {'type': 'graph'}
    assert core.score_response('yes', graph_question(expected=False), scorer)['expected'] is True
    assert core.score_response('no', graph_question('c', 'a'), scorer)['passed']
    assert core.score_response('no', graph_question('a', 'isolated'), scorer)['passed']
    assert core.score_response('true', graph_question('isolated', 'isolated'), scorer)['passed']


def test_invalid_graph_and_scorer_configuration_fail_before_execution():
    malformed = graph_question()
    malformed['graph']['edges'].append(['a', 'missing'])
    with pytest.raises(ValueError, match='known graph.nodes'):
        core.validate_question(malformed, {'type': 'graph'})
    with pytest.raises(ValueError):
        core.validate_scorer({'type': 'json_field', 'field': 'a..b'})
    with pytest.raises(ValueError):
        core.validate_scorer({'type': 'exact', 'trim': 'false'})
    result = core.score_response('yes', malformed, {'type': 'graph'})
    assert result['score'] is None and result['passed'] is None and result['error']
