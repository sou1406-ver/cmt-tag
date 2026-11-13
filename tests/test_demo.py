import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dataset.common import load, seal, sha, write_jsonl
from src.models import demo


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'outputs/canonical/versions/filtered_20261112_final'
        self.source.mkdir(parents=True)
        examples = [('POS', 'excellent acting'), ('NEG', 'terrible script'), ('NEU', 'movie runtime information')]
        rows = []
        for i in range(425):
            label, text = examples[i % 3]
            rows.append(dict(record_id=str(i), text_raw=text, text_minimal=text,
                             human_label=label, human_decisions=[dict(status='LABELED', label=label)]))
        write_jsonl(self.source/'candidate.local.jsonl', rows)
        seal(self.source, dict(kind='FIXTURE'))
        self.output = self.root/'outputs/demo'

    def test_build_roundtrip_and_no_evaluation(self):
        before = sha(self.source/'candidate.local.jsonl')
        with patch('src.models.core.evaluate_gold', side_effect=AssertionError('No gold evaluation')):
            result = demo.build(self.output, self.root)
        self.assertEqual(result['train_records'], 425)
        self.assertFalse(result['gold_data_used'])
        self.assertEqual(sha(self.source/'candidate.local.jsonl'), before)
        model = demo.load_model(self.output)
        self.assertEqual(demo.predict(model, 'excellent acting'), 'POS')
        self.assertFalse(load(self.output/'model_info.json')['metrics_computed'])
        with self.assertRaises(FileExistsError):
            demo.build(self.output, self.root)

    def test_missing_human_labels_refused(self):
        with patch.object(demo, 'read_jsonl', return_value=[]):
            with self.assertRaisesRegex(ValueError, '425'):
                demo.build(self.output, self.root)

    def test_reservation_guard_runs_before_fit(self):
        with patch.object(demo, 'assert_allowed', side_effect=ValueError('reserved')):
            with patch.object(demo, 'gold_model') as factory:
                with self.assertRaisesRegex(ValueError, 'reserved'):
                    demo.build(self.output, self.root)
                factory.assert_not_called()

    def test_tamper_rejected_before_deserialization(self):
        demo.build(self.output, self.root)
        (self.output/'model.joblib').write_bytes(b'tampered')
        with patch.object(demo.joblib, 'load') as loader:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                demo.load_model(self.output)
            loader.assert_not_called()

    def test_blank_and_interactive_exit(self):
        with self.assertRaises(ValueError):
            demo.predict(None, '  ')
        model = unittest.mock.Mock()
        model.predict.return_value = ['NEU']
        lines = iter(['synthetic comment', ''])
        emitted = []
        demo.interactive(model, lambda _: next(lines), emitted.append)
        self.assertIn('Nhan du doan: NEU', emitted)
        model.predict.assert_called_once()
        for error in (EOFError, KeyboardInterrupt):
            with patch.object(model, 'predict') as predict:
                demo.interactive(model, unittest.mock.Mock(side_effect=error), emitted.append)
                predict.assert_not_called()


if __name__ == '__main__':
    unittest.main()
