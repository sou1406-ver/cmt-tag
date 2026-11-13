import tempfile
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dataset.common import load, seal, sha, write_jsonl
from src.models import demo
from src.models import transformer_demo


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
        for name in demo.MODELS:
            self.assertEqual(demo.predict(demo.load_model(self.output,name), 'excellent acting'), 'POS')
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
        (self.output/'tfidf_char_svm.joblib').write_bytes(b'tampered')
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

    def test_menu_compare_switch_and_invalid_selection(self):
        model=unittest.mock.Mock()
        model.predict.return_value=['NEU']
        lines=iter(['bad','5','synthetic comment','/model','1','another comment',''])
        emitted=[]
        with patch.object(demo,'load_model',return_value=model):
            demo.menu(self.output,lambda _:next(lines),emitted.append)
        self.assertEqual(model.predict.call_count,5)
        self.assertIn('Lua chon khong hop le.',emitted)
        for name in demo.MODELS.values():self.assertIn(name+': NEU',emitted)

    def test_transformer_views_and_label_mapping(self):
        self.assertEqual(transformer_demo.text_view('  movie :))  ','visobert'),'movie :))')
        with patch('pyvi.ViTokenizer.tokenize',return_value='word_segmented') as segment:
            self.assertEqual(transformer_demo.text_view('movie','phobert'),'word_segmented')
            segment.assert_called_once_with('movie')

    def test_missing_transformer_keeps_menu_usable(self):
        model=unittest.mock.Mock()
        model.predict.return_value=['NEU']
        lines=iter(['6','2','synthetic comment',''])
        emitted=[]
        with patch.object(demo,'load_model',return_value=model), patch.object(transformer_demo,'TransformerPredictor',side_effect=ValueError('checkpoint missing')):
            demo.menu(self.output,lambda _:next(lines),emitted.append)
        self.assertTrue(any('checkpoint missing' in message for message in emitted))
        model.predict.assert_called_once()

    @unittest.skipUnless(importlib.util.find_spec('torch'), 'Optional PyTorch runtime not installed')
    def test_transformer_prediction_uses_checkpoint_mapping(self):
        import torch
        predictor=object.__new__(transformer_demo.TransformerPredictor)
        predictor.name='visobert';predictor.info={'config':{'max_length':128}}
        predictor.tokenizer=unittest.mock.Mock(return_value={'input_ids':torch.tensor([[1]])})
        predictor.model=unittest.mock.Mock()
        predictor.model.return_value.logits=torch.tensor([[0.,4.,1.]])
        predictor.model.config.id2label={0:'NEG',1:'POS',2:'NEU'}
        self.assertEqual(predictor.predict(['synthetic comment']),['POS'])

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'), 'Optional Transformer runtime not installed')
    def test_transformer_missing_checkpoint_fails_without_remote_load(self):
        with patch('transformers.AutoModelForSequenceClassification.from_pretrained') as factory:
            with self.assertRaises(FileNotFoundError):
                transformer_demo.TransformerPredictor(self.root/'missing')
            factory.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'), 'Optional Transformer runtime not installed')
    def test_transformer_guard_blocks_before_download(self):
        with patch.object(transformer_demo,'training_rows',side_effect=ValueError('reserved')):
            with patch.object(transformer_demo,'ROOT',self.root), patch('huggingface_hub.HfApi') as api:
                with self.assertRaisesRegex(ValueError,'reserved'):
                    transformer_demo.train('visobert',self.root/'outputs/new')
                api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
