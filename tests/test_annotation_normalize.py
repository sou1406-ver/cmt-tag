import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts.normalize_annotations import FIELDS, normalize_file
from src.annotation.core import import_human
from src.annotation.guidelines import GUIDELINE, GUIDELINE_VERSION
from src.data.importers import digest


class NormalizeAnnotationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def inputs(self, decisions):
        rows = [dict.fromkeys(FIELDS, '') for _ in decisions]
        for index, (row, decision) in enumerate(zip(rows, decisions)):
            row.update(id=f'fixture_{index}', movie_id='fixture_film', text_raw=f'=)) fixture {index}')
            row.update(decision)
        task = dict(dataset_version='fixture', guideline_version=GUIDELINE_VERSION, guideline_sha256=digest(GUIDELINE.read_bytes()),
                    rows=[dict(id=r['id'], text_raw=r['text_raw'], split='train', cohort='random') for r in rows])
        task_path = self.root / 'task.json'
        task_path.write_text(json.dumps(task), encoding='utf-8')
        path = self.root / 'labels.csv'
        self.write_csv(path, rows)
        return path, task_path, rows

    def write_csv(self, path, rows):
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def read_csv(self, path):
        with path.open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))

    def test_five_way_decisions_keep_every_row_and_existing_importer_accepts(self):
        path, task, original = self.inputs([
            dict(label=' pos '), dict(label='NEG'), dict(status='NEU'),
            dict(label='review', review_reason='rev_context'), dict(label='EXCLUDE', reason='Off topic'),
        ])
        before = path.read_bytes()
        out = self.root / 'normalized'
        report = normalize_file(path, task, out)
        self.assertTrue(report['import_ready'])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(report['sentiment_label_counts'], {'POS': 1, 'NEG': 1, 'NEU': 1})
        self.assertEqual([r['id'] for r in self.read_csv(out / 'normalized.csv')], [r['id'] for r in original])
        self.assertEqual(self.read_csv(out / 'original_input.csv'), original)
        self.assertEqual(len(self.read_csv(out / 'review.csv')), 1)
        self.assertEqual(len(self.read_csv(out / 'exclude.csv')), 1)
        events = self.root / 'events.jsonl'
        self.assertEqual(import_human(task, out / 'normalized.csv', events, 'fixture_annotator', True), 5)
        decisions = [json.loads(line)['decision'] for line in events.read_text().splitlines()]
        self.assertEqual([d['status'] for d in decisions], ['LABELED', 'LABELED', 'LABELED', 'REVIEW', 'EXCLUDE'])
        self.assertTrue(all(d['label'] is None for d in decisions[3:]))
        self.assertFalse(report['gold_release_created'])

    def test_missing_and_conflicting_decisions_are_retained_outside_sentiment(self):
        path, task, _ = self.inputs([
            dict(label='POS'), dict(), dict(status='LABELED'),
            dict(status='REVIEW'), dict(status='EXCLUDE', label='NEG'),
        ])
        out = self.root / 'pending'
        report = normalize_file(path, task, out)
        self.assertFalse(report['import_ready'])
        self.assertEqual(len(self.read_csv(out / 'normalized.csv')), 5)
        self.assertEqual(len(self.read_csv(out / 'sentiment_candidates.csv')), 1)
        self.assertEqual(len(self.read_csv(out / 'pending.csv')), 2)
        self.assertEqual(len(self.read_csv(out / 'review.csv')), 1)
        self.assertEqual(len(self.read_csv(out / 'exclude.csv')), 1)
        self.assertEqual({i['code'] for i in report['issues']},
                         {'MISSING_DECISION', 'MISSING_SENTIMENT_LABEL', 'MISSING_REVIEW_REASON', 'NON_SENTIMENT_STATE_HAS_LABEL'})

    def test_whitespace_restore_requires_opt_in_and_never_fixes_changed_words(self):
        path, task, rows = self.inputs([dict(label='POS'), dict(label='NEG')])
        rows[0]['text_raw'] += ' '
        rows[1]['text_raw'] += ' new words'
        self.write_csv(path, rows)
        report = normalize_file(path, task, self.root / 'strict')
        self.assertEqual(len(report['issues']), 2)
        report = normalize_file(path, task, self.root / 'whitespace', restore_task_whitespace=True)
        self.assertEqual(report['sentiment_candidates'], 1)
        self.assertEqual(report['issues'][0]['id'], 'fixture_1')
        self.assertEqual(self.read_csv(self.root / 'whitespace' / 'original_input.csv'), rows)
        self.assertEqual([a['action'] for a in report['actions']].count('RESTORE_TASK_WHITESPACE'), 1)

    def test_user_corrections_join_by_id_and_conflicts_or_overwrites_fail(self):
        path, task, rows = self.inputs([dict(), dict(status='REVIEW')])
        self.write_csv(path, list(reversed(rows)))
        overrides = self.root / 'overrides.json'
        overrides.write_text(json.dumps(dict(rows=[
            dict(id='fixture_0', expected=dict(label=''), set=dict(label='NEU'), evidence='User confirmation'),
            dict(id='fixture_1', expected=dict(review_reason=''), set=dict(review_reason='REV_CONTEXT'), evidence='User confirmation'),
        ])), encoding='utf-8')
        out = self.root / 'corrected'
        report = normalize_file(path, task, out, overrides)
        self.assertTrue(report['import_ready'])
        normalized = {r['id']: r for r in self.read_csv(out / 'normalized.csv')}
        self.assertEqual(normalized['fixture_0']['label'], 'NEU')
        self.assertEqual(normalized['fixture_1']['review_reason'], 'REV_CONTEXT')
        with self.assertRaises(FileExistsError):
            normalize_file(path, task, out, overrides)
        rows[0]['label'] = 'POS'
        self.write_csv(path, rows)
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            normalize_file(path, task, self.root / 'conflict', overrides)

    def test_missing_or_duplicate_task_ids_are_not_dropped_or_guessed(self):
        path, task, rows = self.inputs([dict(label='POS'), dict(label='NEG')])
        rows[1]['id'] = rows[0]['id']
        self.write_csv(path, rows)
        with self.assertRaisesRegex(ValueError, 'exactly the task IDs once'):
            normalize_file(path, task, self.root / 'bad')
        self.assertFalse((self.root / 'bad').exists())


if __name__ == '__main__':
    unittest.main()
