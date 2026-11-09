"""Durable benchmark checkpoints, isolated from the application's chat database."""

import json
import hashlib
import sqlite3
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class BenchmarkConflict(ValueError):
    pass


def summarize(trials, configurations):
    def counts(rows):
        completed = [row for row in rows if row['status'] == 'completed']
        scored = [row for row in completed if row.get('score') is not None]
        correct = sum(row.get('score') == 1 for row in scored)
        valid = sum(bool(row.get('valid')) for row in completed)
        errors = sum(row['status'] == 'error' for row in rows)
        return {
            'total': len(rows),
            'finished': len(completed) + errors,
            'completed': len(completed),
            'errors': errors,
            'scoring_errors': sum(bool(row.get('scorer_error')) for row in completed),
            'scored': len(scored),
            'correct': correct,
            'accuracy': correct / len(rows) if rows else None,
            'completed_accuracy': correct / (len(completed) + errors) if completed or errors else None,
            'coverage': (len(completed) + errors) / len(rows) if rows else None,
            'valid': valid,
            'valid_rate': valid / (len(completed) + errors) if completed or errors else None,
        }

    result = counts(trials)
    grouped = defaultdict(list)
    for trial in trials:
        grouped[(trial['question_id'], trial['configuration_id'])].append(trial)
    details = []
    for (question_id, configuration_id), rows in grouped.items():
        outputs = Counter(
            row.get('generation_sha256')
            or hashlib.sha256(
                json.dumps(
                    {'content': row.get('output', ''), 'thinking': row.get('thinking')},
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            for row in rows
            if row['status'] == 'completed'
        )
        answers = Counter(
            json.dumps(row.get('actual'), sort_keys=True)
            for row in rows
            if row['status'] == 'completed' and row.get('valid')
        )
        completed = sum(outputs.values())
        details.append(
            {
                'question_id': question_id,
                'configuration_id': configuration_id,
                **counts(rows),
                'distinct_outputs': len(outputs),
                'identical': len(outputs) == 1 if completed >= 2 else None,
                'modal_count': max(outputs.values()) if outputs else 0,
                'modal_share': max(outputs.values()) / completed if completed else None,
                'valid_answers': sum(answers.values()),
                'distinct_answers': len(answers),
                'answers_agree': len(answers) == 1 if sum(answers.values()) >= 2 else None,
                'all_repeats_finished': all(row['status'] in ('completed', 'error') for row in rows),
            }
        )
    repeated = [group for group in details if group['completed'] >= 2]
    identical = sum(bool(group['identical']) for group in repeated)
    result['consistency'] = {
        'groups': len(details),
        'groups_with_repeats': len(repeated),
        'identical_groups': identical,
        'rate': identical / len(repeated) if repeated else None,
        'answer_groups_with_repeats': sum(group['valid_answers'] >= 2 for group in details),
        'answer_agreement': (
            sum(group['answers_agree'] is True for group in details)
            / sum(group['valid_answers'] >= 2 for group in details)
            if any(group['valid_answers'] >= 2 for group in details)
            else None
        ),
    }
    result['by_configuration'] = [
        {
            'id': config['id'],
            'name': config['name'],
            **counts([trial for trial in trials if trial['configuration_id'] == config['id']]),
        }
        for config in configurations
    ]
    result['by_question_configuration'] = details
    return result


class BenchmarkStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL,
                    status TEXT NOT NULL, manifest TEXT NOT NULL,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0, error TEXT
                );
                CREATE INDEX IF NOT EXISTS benchmark_owner ON benchmark_runs(owner_id, created_at);
                CREATE TABLE IF NOT EXISTS benchmark_trials (
                    run_id TEXT NOT NULL, id TEXT NOT NULL, position INTEGER NOT NULL,
                    status TEXT NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(run_id,id),
                    FOREIGN KEY(run_id) REFERENCES benchmark_runs(id)
                );
                CREATE TABLE IF NOT EXISTS benchmark_lease (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    owner TEXT NOT NULL, run_id TEXT NOT NULL, expires REAL NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _recover(self, db):
        lease = db.execute('SELECT * FROM benchmark_lease WHERE singleton=1').fetchone()
        if lease and lease['expires'] <= time.time():
            self._interrupt(db, lease['run_id'], 'Worker lease expired; resume to retry the incomplete trial.')
            db.execute('DELETE FROM benchmark_lease WHERE singleton=1')

    def _interrupt(self, db, run_id, reason, status='interrupted'):
        for row in db.execute("SELECT * FROM benchmark_trials WHERE run_id=? AND status='running'", (run_id,)):
            result = json.loads(row['result'])
            if result.get('attempt_history'):
                result['attempt_history'][-1].update(status=status, ended_at=time.time(), error=reason)
            result['status'] = 'pending'
            db.execute(
                'UPDATE benchmark_trials SET status=?,result=? WHERE run_id=? AND id=?',
                ('pending', json.dumps(result), run_id, row['id']),
            )
        db.execute(
            "UPDATE benchmark_runs SET status=?,error=?,updated_at=? WHERE id=? AND status='running'",
            (status, reason, time.time(), run_id),
        )

    def _owned(self, db, run_id, owner_id):
        row = db.execute('SELECT * FROM benchmark_runs WHERE id=? AND owner_id=?', (run_id, owner_id)).fetchone()
        if row is None:
            raise KeyError('Benchmark run not found')
        return row

    def create(self, owner_id, manifest):
        run_id, now = str(uuid4()), time.time()
        with self.connection() as db:
            db.execute(
                'INSERT INTO benchmark_runs VALUES(?,?,?,?,?,?,?,?,?)',
                (run_id, owner_id, manifest['name'], 'pending', json.dumps(manifest), now, now, 0, None),
            )
            for trial in manifest['schedule']:
                result = {
                    **trial,
                    'status': 'pending',
                    'attempts': 0,
                    'attempt_history': [],
                    'output': None,
                    'error': None,
                    'score': None,
                    'valid': None,
                    'elapsed_seconds': None,
                }
                db.execute(
                    'INSERT INTO benchmark_trials VALUES(?,?,?,?,?)',
                    (run_id, trial['id'], trial['index'], 'pending', json.dumps(result)),
                )
        return self.get(run_id, owner_id)

    def get(self, run_id, owner_id):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._recover(db)
            row = self._owned(db, run_id, owner_id)
            manifest = json.loads(row['manifest'])
            trials = [
                json.loads(trial['result'])
                for trial in db.execute(
                    'SELECT result FROM benchmark_trials WHERE run_id=? ORDER BY position', (run_id,)
                )
            ]
            summary = summarize(trials, manifest['configurations'])
            return {
                'id': row['id'],
                'name': row['name'],
                'status': row['status'],
                'manifest': manifest,
                'trials': trials,
                'summary': summary,
                'total_trials': len(trials),
                'completed_trials': summary['finished'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'error': row['error'],
            }

    def list(self, owner_id):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._recover(db)
            rows = db.execute(
                """SELECT r.id,r.name,r.status,r.created_at,r.updated_at,r.error,
                COUNT(t.id) AS total_trials,
                SUM(CASE WHEN t.status IN ('completed','error') THEN 1 ELSE 0 END) AS completed_trials
                FROM benchmark_runs r LEFT JOIN benchmark_trials t ON r.id=t.run_id
                WHERE r.owner_id=? GROUP BY r.id ORDER BY r.created_at DESC LIMIT 100""",
                (owner_id,),
            )
            return [{**dict(row), 'summary': {}} for row in rows]

    def claim(self, run_id, owner_id, worker, lease_seconds):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._recover(db)
            row = self._owned(db, run_id, owner_id)
            if row['status'] not in ('pending', 'cancelled', 'interrupted', 'failed'):
                raise BenchmarkConflict('Only pending, cancelled, interrupted or failed runs can start.')
            if db.execute('SELECT 1 FROM benchmark_lease').fetchone():
                raise BenchmarkConflict('Another benchmark is running. Cancel it or wait for it to finish.')
            db.execute('INSERT INTO benchmark_lease VALUES(1,?,?,?)', (worker, run_id, time.time() + lease_seconds))
            db.execute(
                "UPDATE benchmark_runs SET status='running',cancel_requested=0,error=NULL,updated_at=? WHERE id=?",
                (time.time(), run_id),
            )

    def heartbeat(self, run_id, worker, lease_seconds):
        with self.connection() as db:
            changed = db.execute(
                'UPDATE benchmark_lease SET expires=? WHERE run_id=? AND owner=? AND expires>?',
                (time.time() + lease_seconds, run_id, worker, time.time()),
            ).rowcount
            if not changed:
                raise BenchmarkConflict('Benchmark worker no longer owns its lease.')
            row = db.execute('SELECT cancel_requested FROM benchmark_runs WHERE id=?', (run_id,)).fetchone()
            return bool(row['cancel_requested'])

    def next_trial(self, run_id, worker):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._lease(db, run_id, worker)
            row = db.execute(
                "SELECT * FROM benchmark_trials WHERE run_id=? AND status='pending' ORDER BY position LIMIT 1",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            result = json.loads(row['result'])
            result['status'] = 'running'
            result['attempts'] += 1
            result['attempt_history'].append(
                {'attempt': result['attempts'], 'status': 'running', 'started_at': time.time()}
            )
            db.execute(
                "UPDATE benchmark_trials SET status='running',result=? WHERE run_id=? AND id=?",
                (json.dumps(result), run_id, row['id']),
            )
            return result

    def _lease(self, db, run_id, worker):
        lease = db.execute(
            'SELECT 1 FROM benchmark_lease WHERE run_id=? AND owner=? AND expires>?', (run_id, worker, time.time())
        ).fetchone()
        if not lease:
            raise BenchmarkConflict('Benchmark worker lease lost or expired.')

    def checkpoint(self, run_id, worker, trial, result):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._lease(db, run_id, worker)
            trial.update(result)
            trial['attempt_history'][-1].update(status=trial['status'], ended_at=time.time(), error=trial.get('error'))
            db.execute(
                'UPDATE benchmark_trials SET status=?,result=? WHERE run_id=? AND id=? AND status=?',
                (trial['status'], json.dumps(trial), run_id, trial['id'], 'running'),
            )
            db.execute('UPDATE benchmark_runs SET updated_at=? WHERE id=?', (time.time(), run_id))

    def cancel(self, run_id, owner_id):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._recover(db)
            row = self._owned(db, run_id, owner_id)
            if row['status'] == 'running':
                db.execute(
                    'UPDATE benchmark_runs SET cancel_requested=1,updated_at=? WHERE id=?', (time.time(), run_id)
                )
            elif row['status'] != 'completed':
                db.execute(
                    "UPDATE benchmark_runs SET status='cancelled',updated_at=? WHERE id=?", (time.time(), run_id)
                )

    def finish(self, run_id, worker, status, error=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._lease(db, run_id, worker)
            if status != 'completed':
                self._interrupt(db, run_id, error or 'Run cancelled; incomplete trial can be resumed.', status)
            db.execute(
                'UPDATE benchmark_runs SET status=?,error=?,updated_at=? WHERE id=?',
                (status, error, time.time(), run_id),
            )
            db.execute('DELETE FROM benchmark_lease WHERE run_id=? AND owner=?', (run_id, worker))
