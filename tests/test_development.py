import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.development_baseline import execute, mask_text, plan, prepare_or_run
from scripts.prepare_development import dependence, grouped_records, prepare, sha, write_csv


class DevelopmentTests(unittest.TestCase):
    def fixture(self):
        rows=[]
        texts={'POS':'great moving lovely film','NEG':'dull awful weak plot','NEU':'release date runtime question'}
        for group in range(9):
            for label,text in texts.items():
                rows.append(dict(id=f'{group}_{label}',text_raw=f'{text} posttoken{group}',label=label,
                                 movie_id=f'movie{group%3}',post_id=f'post{group}',post_url=f'https://example.test/{group}',
                                 comment_id=f'comment{group}_{label}',parent_comment_id='',status='LABELED',
                                 validation_issues='',audit_pending=''))
        return rows

    def cfg(self):
        return dict(seed=42,folds=3,models=['nb','lr','svm'],variants=['original','masked'],
                    ngram_max=2,class_weight='balanced',top_features=3)

    def test_post_and_transitive_duplicate_isolation(self):
        rows=self.fixture()
        rows[3]['text_raw']=rows[0]['text_raw']
        # A duplicate bridges two posts, including all other comments in both posts.
        _,_,groups=grouped_records(rows)
        self.assertEqual(groups[rows[1]['id']],groups[rows[5]['id']])
        result=plan(rows,self.cfg())
        self.assertIn(rows[3]['id'],result['omitted_duplicate_ids'])
        validation=[]
        for fold in result['folds']:
            self.assertFalse({groups[r] for r in fold['train_ids']} & {groups[r] for r in fold['validation_ids']})
            validation.extend(fold['validation_ids'])
        self.assertEqual(len(validation),len(set(validation)))
        self.assertEqual(len(validation),26)
        self.assertEqual(plan(list(reversed(rows)),self.cfg())['folds'],result['folds'])

    def test_duplicate_conflict_is_not_silently_dropped(self):
        rows=self.fixture()
        rows[4]['text_raw']=rows[0]['text_raw']
        with self.assertRaisesRegex(ValueError,'conflict'):
            plan(rows,self.cfg())

    def test_near_duplicate_component_and_missing_post_rejected(self):
        rows=self.fixture()
        rows[0]['text_raw']=' '.join('uniquetoken'+str(i) for i in range(80))
        rows[3]['text_raw']=rows[0]['text_raw']+' ending'
        _,pairs,groups=grouped_records(rows)
        self.assertTrue(pairs)
        self.assertEqual(groups[rows[0]['id']],groups[rows[4]['id']])
        rows[0]['post_id']=''
        with self.assertRaisesRegex(ValueError,'provenance'):
            plan(rows,self.cfg())

    def test_mask_literal_boundaries_scope_unicode_and_negation(self):
        aliases=[dict(text='Mưa Đỏ',token='TEN_PHIM'),dict(text='anh Sen',token='TEN_NHAN_VAT',movies=['mua_do']),
                 dict(text='Avatar',token='TEN_PHIM'),dict(text='Avatar 2',token='TEN_PHIM')]
        raw='Mưa Đỏ không dở. Avatar 2 rất hay; Avatarized vẫn thế. anh Sen mai đi xem.'
        got=mask_text(raw,aliases,'mua_do')
        self.assertEqual(got,'TEN_PHIM không dở. TEN_PHIM rất hay; Avatarized vẫn thế. TEN_NHAN_VAT mai đi xem.')
        self.assertIn('anh Sen',mask_text(raw,aliases,'other'))
        self.assertIn('mai đi xem',got)
        import unicodedata
        self.assertEqual(mask_text(unicodedata.normalize('NFD',raw),aliases,'mua_do'),got)

    def test_fixture_all_models_variants_metrics_and_train_only_vocabulary(self):
        from src.baseline.core import model as real_model
        estimators=[]
        def track(*args):
            estimator=real_model(*args)
            estimators.append(estimator)
            return estimator
        rows=self.fixture(); cfg=self.cfg(); split=plan(rows,cfg)
        with patch('scripts.development_baseline.model',side_effect=track):
            results,predictions,coefficients=execute(rows,cfg,split,[])
        self.assertEqual(len(results),6)
        self.assertEqual(len(predictions),27*6)
        self.assertTrue(coefficients)
        for r in results:
            self.assertEqual(len(r['oof']['confusion_matrix']),3)
            self.assertEqual(set(r['oof']['per_class']),{'POS','NEG','NEU'})
        for index,estimator in enumerate(estimators):
            fold=split['folds'][index%3]
            vocab=estimator['vectorizer'].vocabulary_
            for rid in fold['validation_ids']:
                self.assertNotIn('posttoken'+rid.split('_')[0],vocab)

    def test_pending_gate_and_checksum_fail_before_fitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'data';data.mkdir()
            rows=self.fixture()
            write_csv(data/'annotations.csv',rows,list(rows[0]))
            manifest=dict(purpose='exploratory_development_only',independent_test=False,
                          output_sha256={'annotations.csv':sha(data/'annotations.csv')},
                          all_human_review_resolved=False,pending_review_ids=[rows[0]['id']])
            (data/'manifest.json').write_text(json.dumps(manifest))
            (root/'aliases.json').write_text(json.dumps(dict(aliases=[])))
            cfg=self.cfg();cfg.update(dataset=str(data),mask_lexicon=str(root/'aliases.json'))
            (root/'config.json').write_text(json.dumps(cfg))
            with patch('scripts.development_baseline.model') as fit:
                with self.assertRaisesRegex(ValueError,'Human review'):
                    prepare_or_run(root/'config.json',root/'blocked',run=True)
                fit.assert_not_called()
            self.assertFalse((root/'blocked').exists())
            p=prepare_or_run(root/'config.json',root/'plan')
            self.assertFalse(p['models_trained']);self.assertTrue(p['provisional'])
            with (data/'annotations.csv').open('a') as f:f.write('tampered')
            with self.assertRaisesRegex(ValueError,'checksum'):
                prepare_or_run(root/'config.json',root/'tampered')

    def test_descriptive_dependence(self):
        rows=self.fixture()
        self.assertAlmostEqual(dependence(rows)['cramers_v'],0)
        for r in rows:r['movie_id']=r['label']
        self.assertAlmostEqual(dependence(rows)['cramers_v'],1)

    def test_preparation_preserves_existing_human_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.joinpath('human.txt').write_text('keep me')
            with self.assertRaises(FileExistsError):
                prepare(root/'missing_config.json',root)
            self.assertEqual(root.joinpath('human.txt').read_text(),'keep me')

    def test_changed_source_rejected_without_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'human.csv';source.write_text('source changed after audit')
            spec=dict(name='fixture',input=str(source),input_sha256='0'*64)
            cfg=root/'config.json';cfg.write_text(json.dumps(dict(sources=[spec])))
            with self.assertRaisesRegex(ValueError,'Source changed'):
                prepare(cfg,root/'prepared')
            self.assertFalse((root/'prepared').exists())
            self.assertFalse(list(root.glob('.development-*')))


if __name__=='__main__':
    unittest.main()
