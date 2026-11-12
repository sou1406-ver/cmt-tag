"""Development views and train-only vectorization, using fixtures only."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import zipfile
import unittest

from src.preprocessing import preprocess
from src.preprocessing.model import (ModelOptions, ModelText, model_view, text_model,
                                     normalize_teencode, reduce_elongation)
from src.models.preprocessing_cv import estimator, fit_fold, fold_plan, TOKEN_PATTERN


class ModelPreprocessingTests(unittest.TestCase):
    def row(self, text='An Bình phim hay', **extra):
        return dict(record_id='a', source_dataset='facebook', text_raw=text,
                    text_minimal=preprocess(text), comment_id='11', post_id='10', **extra)

    def test_minimal_and_source_are_unchanged(self):
        row = self.row(); before = deepcopy(row)
        model_view(row); text_model(row['text_minimal'])
        self.assertEqual(row, before)
        self.assertEqual(preprocess('  KO :D hayyy!!!  '), 'KO :D hayyy!!!')

    def test_no_metadata_no_name_guess(self):
        for text in ['An Bình phim hay', 'Mưa Đỏ rất hay', 'Mong Đạo Diễn làm tốt hơn']:
            result = model_view(self.row(text))
            self.assertEqual(result['text_view'], text)
            self.assertEqual(result['view_method'], 'RAW')

    def observation(self):
        return dict(text_raw='An Bình phim hay', text_without_mentions=' phim hay',
                    mention_count=1, text_extraction_version='dom_text_v2', post_id='10', comment_id='11')

    def test_aggregate_dom_is_rule_match_never_verified(self):
        v = model_view(self.row(), self.observation())
        self.assertEqual(v['text_view'], 'phim hay')
        self.assertEqual(v['view_method'], 'DOM_RULE_MATCH')
        self.assertIn('NOT_NODE_VERIFIED', v['reason'])

    def test_invalid_dom_fallback(self):
        for key, value in [('mention_count', 0), ('mention_count', True), ('text_extraction_version','v1'),
                           ('comment_id', '12'), ('text_raw','Mưa Đỏ phim hay'),
                           ('text_without_mentions','phim không hay'), ('text_without_mentions','')]:
            obs = self.observation(); obs[key] = value
            self.assertEqual(model_view(self.row(), obs)['text_view'], self.row()['text_minimal'])

    def test_legacy_never_uses_dom(self):
        row = self.row(); row['source_dataset'] = 'legacy_29k_unverified'
        self.assertEqual(model_view(row, self.observation())['reason'], 'LEGACY_NO_DOM_POLICY')

    def test_negation_preserved(self):
        for text, expected in [('không hay','không'),('chưa tốt','chưa'),('ko ổn','không')]:
            self.assertIn(expected, text_model(text))

    def test_teencode_whole_tokens_and_ambiguous_forms(self):
        self.assertEqual(normalize_teencode('ko k0 khong hok hông khum đc cx'),
                         'không không không không không không được cũng')
        self.assertEqual(normalize_teencode('k koko dc cg mk mik mng j z v ng'),
                         'k koko dc cg mk mik mng j z v ng')
        self.assertEqual(normalize_teencode('mn ơi mn xem mn abc'), 'mọi người ơi mọi người xem mn abc')

    def test_elongation_letters_only(self):
        self.assertEqual(reduce_elongation('hayyy đẹpppp !!! 333 😭😭😭'), 'hay đẹp !!! 333 😭😭😭')

    def test_emoticons_emoji_kept_literally(self):
        for symbol in [':))', ':):)', '=))', ':v', ':(', ':D', '-_-', '^^', '<3',
                       '😭', '😂', '👨‍👩‍👧‍👦', '👍🏽', '🇻🇳', '1️⃣']:
            with self.subTest(symbol=symbol):
                out = text_model('PHIM hayyy ' + symbol)
                self.assertIn(symbol, out)
                self.assertIn(symbol, out.split())

    def test_punctuation_is_kept_as_tokens(self):
        out = text_model('PHIM hay!!! không?', ModelOptions(segment=False))
        self.assertEqual(out, 'phim hay ! ! ! không ?')

    def test_pyvi_and_no_pyvi_control(self):
        self.assertEqual(text_model('diễn xuất không hay'), 'diễn_xuất không hay')
        self.assertEqual(text_model('diễn xuất không hay', ModelOptions(segment=False)), 'diễn xuất không hay')

    def test_repeated_application_guard_and_safe_steps(self):
        value = text_model('KO hayyy :))')
        self.assertIsInstance(value, ModelText)
        with self.assertRaises(ValueError): text_model(value)
        self.assertEqual(normalize_teencode(normalize_teencode('ko đc')), normalize_teencode('ko đc'))
        self.assertEqual(reduce_elongation(reduce_elongation('hayyy')), reduce_elongation('hayyy'))

    def test_one_character_and_emoticon_features(self):
        for name in ['bow_complement_nb','tfidf_word_svm']:
            vec = estimator(name, 1).named_steps['vectorizer']
            self.assertEqual(vec.token_pattern, TOKEN_PATTERN)
            self.assertFalse(vec.lowercase)
            tokens = vec.build_analyzer()('k :)) không')
            self.assertIn('k', tokens); self.assertIn(':))', tokens)

    def test_vectorizer_never_fits_validation(self):
        p = estimator('bow_complement_nb', 1)
        fit_fold(p, ['hay tích_cực','dở tiêu_cực','validation_only_word'], ['POS','NEG','NEU'], [0,1], [2])
        self.assertNotIn('validation_only_word', p.named_steps['vectorizer'].vocabulary_)
        with self.assertRaises(ValueError): fit_fold(p, ['a'], ['POS'], [0], [0])

    def test_group_folds_and_legacy_records(self):
        rows = [dict(record_id=str(i), source_dataset='facebook', post_id=str(100+i//3),
                     post_url='https://www.facebook.com/p/posts/'+str(100+i//3), human_label=['POS','NEG','NEU'][i%3]) for i in range(30)]
        rows += [dict(record_id='l'+str(i), source_dataset='legacy_29k_unverified', post_id='', human_label='NEG') for i in range(5)]
        plan, groups = fold_plan(rows, seeds=(1,2))
        self.assertEqual(plan, fold_plan(rows, seeds=(1,2))[0])
        self.assertEqual(len(set(groups[-5:])), 5)
        for split in plan:
            self.assertFalse({groups[i] for i in split['train']} & {groups[i] for i in split['validation']})
        rows[0]['post_id'] = 'bad'
        with self.assertRaises(ValueError): fold_plan(rows)

    def test_no_gold_api_dependency(self):
        from src.models import preprocessing_cv
        source = Path(preprocessing_cv.__file__).read_text(encoding='utf-8')
        self.assertNotIn('evaluate_gold(', source)
        self.assertNotIn('locked_gold.local.jsonl', source)
        self.assertNotIn('gold_test.xlsx', source)

    def test_pinned_jsonl_and_zip_dom_observations(self):
        from src.models.preprocessing_cv import source_observations
        with TemporaryDirectory() as tmp:
            root = Path(tmp); payload = (json.dumps(self.observation())+'\n').encode()
            (root/'source.jsonl').write_bytes(payload)
            with zipfile.ZipFile(root/'archive.zip','w') as z: z.writestr('source.jsonl',payload)
            for ref in ['source.jsonl','archive.zip!source.jsonl']:
                row = dict(self.row(), source_file=ref, source_row=1,
                           source_sha256=hashlib.sha256(payload).hexdigest())
                obs, hashes = source_observations([row], root)
                self.assertEqual(obs['a']['mention_count'], 1)
                self.assertEqual(model_view(row,obs['a'])['view_method'],'DOM_RULE_MATCH')
                row['source_sha256'] = 'invalid'
                with self.assertRaises(ValueError): source_observations([row], root)

    def test_snapshot_hashes_opaque_gold_without_parsing(self):
        from src.models.preprocessing_cv import snapshot
        with TemporaryDirectory() as tmp:
            root = Path(tmp); filtered = root/'filtered'; filtered.mkdir()
            (filtered/'protected_inputs.local.json').write_text('{}',encoding='utf-8')
            (root/'outputs/gold').mkdir(parents=True)
            gold = root/'outputs/gold/opaque.xlsx'; gold.write_bytes(b'not a spreadsheet or JSON')
            before = snapshot(root,filtered)
            self.assertEqual(before,snapshot(root,filtered))
            gold.write_bytes(b'changed')
            self.assertNotEqual(before,snapshot(root,filtered))
            self.assertFalse((root/'data/evaluation_usage').exists())


if __name__ == '__main__': unittest.main()
