"""Pure scheduling and scoring contracts for the isolated benchmark runner."""

import json
import math
import random
from collections import deque
from typing import Any

SCORER_VERSION = '1'
SCHEDULE_VERSION = '1'
MAX_TRIALS = 5000
ORDER_TYPES = {'dataset', 'reverse', 'shuffle_once', 'shuffle_each_repeat'}
SCORER_TYPES = {'exact', 'boolean', 'json_field', 'graph'}


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be an integer from {minimum} to {maximum}')
    return value


def _validate_items(items: list[dict], label: str, maximum: int) -> None:
    if not isinstance(items, list) or not items or len(items) > maximum:
        raise ValueError(f'{label} must contain between 1 and {maximum} items')
    ids = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip():
            raise ValueError(f'Every {label} item must have a nonempty string id')
        ids.append(item['id'])
    if len(set(ids)) != len(ids):
        raise ValueError(f'{label} ids must be unique')


def build_schedule(
    questions: list[dict],
    configurations: list[dict],
    repeats: int,
    order: str,
    order_seed: int,
    seed_mode: str,
    inference_seeds: list[int],
) -> list[dict]:
    """Expand the complete schedule before inference without mutating the input.

    Each repetition presents the same question order to every configuration.
    ``list`` maps one explicit inference seed to each repetition; ``fixed`` uses
    its single seed for every trial. Ordering uses a separate local RNG and never
    consumes inference seeds. Indices are zero based, including repeat_index.
    """
    _validate_items(questions, 'questions', 500)
    _validate_items(configurations, 'configurations', 16)
    _integer(repeats, 'repeats', 1, 100)
    _integer(order_seed, 'order_seed', 0, 2**31 - 1)
    if order not in ORDER_TYPES:
        raise ValueError(f'order must be one of {", ".join(sorted(ORDER_TYPES))}')
    if seed_mode not in {'fixed', 'list'}:
        raise ValueError('seed_mode must be fixed or list')
    if not isinstance(inference_seeds, list):
        raise ValueError('inference_seeds must be a list of integers')
    seed_count = 1 if seed_mode == 'fixed' else repeats
    if len(inference_seeds) != seed_count:
        raise ValueError(f'{seed_mode} seed_mode requires exactly {seed_count} inference seed(s)')
    for seed in inference_seeds:
        _integer(seed, 'inference seed', 0, 2**31 - 1)
    if len(questions) * len(configurations) * repeats > MAX_TRIALS:
        raise ValueError(f'A benchmark may contain at most {MAX_TRIALS} trials')

    rng = random.Random(order_seed)
    original_order = list(range(len(questions)))
    once_order = original_order.copy()
    if order == 'reverse':
        once_order.reverse()
    elif order == 'shuffle_once':
        rng.shuffle(once_order)

    schedule = []
    for repeat_index in range(repeats):
        question_order = once_order.copy()
        if order == 'shuffle_each_repeat':
            question_order = original_order.copy()
            rng.shuffle(question_order)
        seed = inference_seeds[0 if seed_mode == 'fixed' else repeat_index]
        for question_index in question_order:
            for configuration in configurations:
                index = len(schedule)
                schedule.append(
                    {
                        'id': f'trial-{index + 1:06d}',
                        'index': index,
                        'question_id': questions[question_index]['id'],
                        'configuration_id': configuration['id'],
                        'repeat_index': repeat_index,
                        'seed': seed,
                    }
                )
    return schedule


def _json_path(scorer: dict) -> list[str]:
    field = scorer.get('field', scorer.get('path'))
    if not isinstance(field, str) or not field or any(not part for part in field.split('.')):
        raise ValueError('json_field scorer requires a nonempty dotted field path, such as answer or results.0.answer')
    return field.split('.')


def validate_scorer(scorer: dict) -> None:
    """Reject invalid scorer settings before a run is created."""
    if not isinstance(scorer, dict) or scorer.get('type') not in SCORER_TYPES:
        raise ValueError(f'scorer.type must be one of {", ".join(sorted(SCORER_TYPES))}')
    if scorer['type'] == 'exact':
        for option in ('trim', 'case_sensitive'):
            if option in scorer and not isinstance(scorer[option], bool):
                raise ValueError(f'{option} must be a boolean')
    elif scorer['type'] == 'json_field':
        _json_path(scorer)


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().casefold()
        if text in {'true', 'yes', '1'}:
            return True
        if text in {'false', 'no', '0'}:
            return False
    if type(value) is int and value in (0, 1):
        return bool(value)
    raise ValueError('Expected a single boolean answer: true, false, yes, no, 1, or 0')


def _validate_json_value(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if type(value) in (int, float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Expected JSON values must contain finite numbers')
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json_value(item)
        return
    raise ValueError('Expected value must be a valid JSON value')


def directed_reachable(graph: dict) -> bool:
    """Compute directed reachability, including a zero-edge path to oneself."""
    if not isinstance(graph, dict):
        raise ValueError('graph scorer requires question.graph')
    nodes = graph.get('nodes')
    edges = graph.get('edges')
    if not isinstance(nodes, list) or not nodes or any(not isinstance(node, str) or not node for node in nodes):
        raise ValueError('graph.nodes must be a nonempty list of nonempty strings')
    if len(nodes) != len(set(nodes)):
        raise ValueError('graph.nodes must be unique')
    node_set = set(nodes)
    source, target = graph.get('source'), graph.get('target')
    if not isinstance(source, str) or not isinstance(target, str) or source not in node_set or target not in node_set:
        raise ValueError('graph.source and graph.target must identify graph.nodes')
    if not isinstance(edges, list):
        raise ValueError('graph.edges must be a list of [source, target] pairs')
    adjacency = {node: [] for node in nodes}
    for edge in edges:
        if (
            not isinstance(edge, (list, tuple))
            or len(edge) != 2
            or any(not isinstance(node, str) or node not in node_set for node in edge)
        ):
            raise ValueError('Each directed edge must contain two known graph.nodes')
        adjacency[edge[0]].append(edge[1])
    pending = deque([source])
    visited = {source}
    while pending:
        node = pending.popleft()
        if node == target:
            return True
        for neighbour in adjacency[node]:
            if neighbour not in visited:
                visited.add(neighbour)
                pending.append(neighbour)
    return False


def validate_question(question: dict, scorer: dict) -> None:
    """Validate scoring ground truth; graph labels are derived, never trusted."""
    validate_scorer(scorer)
    if not isinstance(question, dict):
        raise ValueError('Question must be an object')
    kind = scorer['type']
    if kind == 'graph':
        directed_reachable(question.get('graph'))
        return
    if 'expected' not in question:
        raise ValueError('Question requires an expected value')
    expected = question['expected']
    if kind == 'exact' and not isinstance(expected, str):
        raise ValueError('exact scorer requires a string expected value')
    elif kind == 'boolean':
        _boolean(expected)
    elif kind == 'json_field':
        _validate_json_value(expected)


def _json_equal(left: Any, right: Any) -> bool:
    # JSON booleans are distinct from numbers, unlike Python's True == 1.
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_json_equal(left[key], right[key]) for key in left)
    return left == right


def score_response(response: str, question: dict, scorer: dict) -> dict:
    """Score one fresh response; malformed answers count as incorrect.

    Invalid scorer/question configurations have no score. A malformed model
    answer has score zero with an explicit error, so omitting parse failures
    cannot inflate reported accuracy.
    """
    result = {
        'score': None,
        'passed': None,
        'error': None,
        'actual': None,
        'expected': None,
        'scorer_version': SCORER_VERSION,
    }
    try:
        validate_question(question, scorer)
    except (ValueError, TypeError) as exc:
        return {**result, 'error': str(exc)}
    kind = scorer['type']
    expected = directed_reachable(question['graph']) if kind == 'graph' else question['expected']
    result['expected'] = expected
    try:
        if not isinstance(response, str):
            raise ValueError('Model response must be text')
        if kind == 'exact':
            actual = response.strip() if scorer.get('trim', True) else response
            expected = expected.strip() if scorer.get('trim', True) else expected
            if not scorer.get('case_sensitive', True):
                actual, expected = actual.casefold(), expected.casefold()
            passed = actual == expected
        elif kind in {'boolean', 'graph'}:
            actual, expected = _boolean(response), _boolean(expected)
            passed = actual == expected
        else:

            def reject_constant(value):
                raise ValueError(f'Invalid JSON constant: {value}')

            actual = json.loads(response, parse_constant=reject_constant)
            for part in _json_path(scorer):
                if isinstance(actual, dict) and part in actual:
                    actual = actual[part]
                elif isinstance(actual, list) and part.isdecimal() and int(part) < len(actual):
                    actual = actual[int(part)]
                else:
                    raise ValueError(f'Response JSON does not contain field {scorer.get("field", scorer.get("path"))}')
            passed = _json_equal(actual, expected)
        return {**result, 'score': float(passed), 'passed': passed, 'actual': actual, 'expected': expected}
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        return {**result, 'score': 0.0, 'passed': False, 'error': str(exc), 'actual': response}
