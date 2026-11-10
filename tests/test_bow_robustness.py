from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.naive_bayes import ComplementNB, MultinomialNB

from scripts.development_baseline import execute
from scripts.import_development_review import import_review
from scripts.prepare_development import grouped_records, load, read_csv, save, sha, write_csv
from src.baseline.bow_robustness import (inputs,make_model,partition_diagnostics,repeated_plans,run,
    seed_summary,transfer_plans,validate_config,validate_plan)
from src.baseline.preprocessing_experiments import score as phase_e_score
from tests import test_development_review as review_fixture


class BowPrimitiveTests(unittest.TestCase):
    def config(self):return load('configs/bow_robustness.json')

    def test_true_counts_ngrams_and_training_only_vocabulary(self):
        cfg=self.config();old_cfg=load('configs/preprocessing_experiments.json')
        for spec in cfg['models'][:4]:
            with self.subTest(model=spec['id']):
                pipeline=make_model(spec,cfg,old_cfg)
                pipeline.fit(['hay hay k','không hay','ngày chiếu'],['POS','NEG','NEU'])
                vec=pipeline['vectorizer'];self.assertIsInstance(vec,CountVectorizer)
                self.assertIsInstance(pipeline['model'],MultinomialNB if spec['model']=='mnb' else ComplementNB)
                self.assertEqual(vec.transform(['hay hay'])[0,vec.vocabulary_['hay']],2)
                self.assertIn('không',vec.vocabulary_);self.assertIn('k',vec.vocabulary_)
                if spec['ngram_max']==2:self.assertIn('không hay',vec.vocabulary_)
                pipeline.predict(['validationzzzzz'])
                self.assertNotIn('validationzzzzz',vec.vocabulary_)

    def test_seed_std_is_over_five_oof_scores_not_fifteen_folds(self):
        seeds=[42,7,21,73,2026]
        results=[dict(seed=s,model_id='x',metrics=dict(macro_f1=v,accuracy=v,per_class={
            label:dict(recall=v) for label in ('POS','NEG','NEU')}),folds=[dict(macro_f1=999)]*3)
            for s,v in zip(seeds,[0.1,0.2,0.3,0.4,0.5])]
        summary=seed_summary(results,['x'],seeds)[0]
        self.assertEqual(summary['n_seeds'],5)
        self.assertAlmostEqual(summary['macro_f1']['mean'],0.3)
        self.assertAlmostEqual(summary['macro_f1']['std'],math.sqrt(0.025))
        with self.assertRaises(ValueError):seed_summary(results+[results[0]],['x'],seeds)

    def test_config_cannot_treat_folds_as_repeats_or_claim_gold_transfer(self):
        for field,value in [('std_ddof',0),('seeds',[42]*5),('input_view','normalized')]:
            cfg=self.config();cfg[field]=value
            with self.assertRaises(ValueError):validate_config(cfg)
        cfg=self.config();cfg['transfer']['independent_test']=True
        with self.assertRaises(ValueError):validate_config(cfg)
        cfg=self.config();cfg['models'][-1].pop('phase_e_run_id')
        with self.assertRaisesRegex(ValueError,'references'):validate_config(cfg)

    def test_spanning_components_and_non_candidate_bridges_stay_intact(self):
        cfg=self.config()['transfer'];rows=[];groups={}
        for prefix,movie in [('m','mua_do'),('o','other')]:
            for index,label in enumerate(['POS','NEG','NEU','POS','NEG','NEU']):
                rid=prefix+str(index);rows.append(dict(id=rid,movie_id=movie,label=label,post_id=rid));groups[rid]=rid
        # An unselected row joins another topic to m0. The whole component is excluded.
        rows.append(dict(id='outside',movie_id='other',label='',post_id='bridge'));groups['outside']=groups['m0']
        ids=[r['id'] for r in rows if r['id']!='outside']
        diagnostics=transfer_plans(rows,ids,groups,cfg)
        for d in diagnostics:
            self.assertIn('m0',d['excluded_candidate_ids'])
            self.assertNotIn('m0',d['train_ids']+d['evaluation_ids'])
            self.assertFalse({groups[r] for r in d['train_ids']} & {groups[r] for r in d['evaluation_ids']})

    def test_transfer_missing_class_is_skipped_without_fabricated_metrics(self):
        cfg=self.config()['transfer']
        rows=[dict(id='a',movie_id='mua_do',label='POS',post_id='a'),
              dict(id='b',movie_id='other',label='NEG',post_id='b')]
        result=transfer_plans(rows,['a','b'],{'a':'a','b':'b'},cfg)
        self.assertTrue(all(d['status']=='skipped' and d['skip_reasons'] for d in result))
        self.assertTrue(all('metrics' not in d for d in result))

    def test_partition_identity_ignores_fold_number_permutations(self):
        first=dict(seed=42,folds=[dict(fold=i,validation_ids=[str(i)]) for i in range(3)])
        second=dict(seed=7,folds=[dict(fold=(i+1)%3,validation_ids=[str(i)]) for i in range(3)])
        result=partition_diagnostics([first,second],{str(i):str(i) for i in range(3)},
                                     {str(i):'mua_do' for i in range(3)},'mua_do')
        self.assertEqual(result['unique_partitions'],1)
        self.assertEqual(result['seeds'][1]['moved_comments_vs_reference'],0)


class BowRunTests(unittest.TestCase):
    def setUp(self):
        helper=review_fixture.DevelopmentReviewTests();helper.setUp();self.addCleanup(helper.doCleanups)
        self.root=helper.root;self.reviewed=self.root/'reviewed'
        import_review(helper.source,helper.csv(helper.decisions()),self.reviewed,'fixture_a')
        self.rows=read_csv(self.reviewed/'annotations.csv');self.by_id={r['id']:r for r in self.rows}
        ids=sorted(r['id'] for r in self.rows if r['status']=='LABELED')
        _,_,self.groups=grouped_records(self.rows)
        folds=[];splitter=StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=42)
        for index,(tr,va) in enumerate(splitter.split(ids,[self.by_id[i]['label'] for i in ids],[self.groups[i] for i in ids])):
            train,valid=[ids[i] for i in tr],[ids[i] for i in va]
            folds.append(dict(fold=index,train_ids=train,validation_ids=valid,
                              train_counts=dict(Counter(self.by_id[i]['label'] for i in train)),
                              validation_counts=dict(Counter(self.by_id[i]['label'] for i in valid))))
        self.locked=dict(seed=42,candidates=len(ids),folds=folds,group_by_id=self.groups,omitted_duplicate_ids=[],
                         dataset_manifest_sha256=sha(self.reviewed/'manifest.json'),provisional=False,
                         independent_test=False,ready_to_run=True)
        self.plan_path=self.root/'old_plan.json';save(self.plan_path,self.locked)
        reference,_,_=execute(self.rows,dict(variants=['original'],models=['nb','lr','svm'],ngram_max=2,
                                           class_weight='balanced',seed=42,top_features=3),self.locked,[])
        save(self.root/'old_reference.json',dict(results=reference));save(self.root/'aliases.json',dict(aliases=[]))
        self.old_cfg=load('configs/preprocessing_experiments.json')
        self.old_cfg.update(dataset=str(self.reviewed),dataset_manifest_sha256=sha(self.reviewed/'manifest.json'),
            locked_plan=str(self.plan_path),locked_plan_sha256=sha(self.plan_path),expected_candidates=len(ids),
            reference_metrics=str(self.root/'old_reference.json'),reference_metrics_sha256=sha(self.root/'old_reference.json'),
            mask_lexicon=str(self.root/'aliases.json'),mask_lexicon_sha256=sha(self.root/'aliases.json'))
        self.phase_root=self.root/'phase_e';self.phase_root.mkdir()
        save(self.phase_root/'experiment_config.json',self.old_cfg);shutil.copyfile(self.plan_path,self.phase_root/'locked_plan.json')
        phase_results=[];phase_predictions=[]
        for kind,feature,run_id in [('lr','word','B0_lr_balanced'),('svm','word','B0_svm_balanced'),('svm','char','B3_svm_balanced')]:
            recipe=dict(feature=feature,light=False,segment=False,teencode=False)
            result,pred=phase_e_score({i:self.by_id[i]['text_raw'] for i in ids},self.by_id,self.locked,recipe,kind,'balanced',self.old_cfg)
            phase_results.append(dict(run_id=run_id,**result));phase_predictions.extend(dict(run_id=run_id,**r) for r in pred)
        save(self.phase_root/'metrics.json',dict(results=phase_results))
        write_csv(self.phase_root/'predictions.csv',phase_predictions,list(phase_predictions[0]))
        from importlib.metadata import version
        save(self.phase_root/'environment.json',dict(packages={p:version(p) for p in ('scikit-learn','numpy','scipy')}))
        save(self.phase_root/'manifest.json',dict(purpose='development_preprocessing_ablation_only',independent_test=False,
            models_trained=True,candidates=len(ids),fixture_only=True,
            output_sha256={p.name:sha(p) for p in self.phase_root.iterdir()}))
        self.cfg=load('configs/bow_robustness.json')
        self.cfg.update(phase_e_root=str(self.phase_root),phase_e_manifest_sha256=sha(self.phase_root/'manifest.json'),
                        phase_e_config_sha256=sha(self.phase_root/'experiment_config.json'),
                        phase_e_metrics_sha256=sha(self.phase_root/'metrics.json'),expected_candidates=len(ids))
        self.cfg['transfer']['movie_id']='movie0'
        self.cfg_path=self.root/'e1.json';save(self.cfg_path,self.cfg)

    def test_complete_run_preserves_reference_and_shares_plans_across_models(self):
        before={p:p.read_bytes() for p in self.phase_root.iterdir()}
        with patch('builtins.print'):manifest=run(self.cfg_path,self.root/'e1')
        self.assertEqual(manifest['fits'],119);self.assertTrue(manifest['fixture_only'])
        self.assertFalse(manifest['independent_test'])
        self.assertTrue(all(p.read_bytes()==payload for p,payload in before.items()))
        root=self.root/'e1';plans=load(root/'repeated_plans.json');self.assertEqual(plans[0]['folds'],self.locked['folds'])
        repeated=load(root/'repeated_results.json');self.assertEqual(len(repeated),35)
        self.assertTrue(all(r['n_seeds']==5 for r in load(root/'seed_summary.json')))
        mapping={p['seed']:{rid:f['fold'] for f in p['folds'] for rid in f['validation_ids']} for p in plans}
        predictions=read_csv(root/'predictions.csv')
        for p in predictions:
            if p['stage'] in ('repeated','original_and_seed_42'):
                self.assertEqual(int(p['fold']),mapping[int(p['seed'])][p['id']])
        self.assertEqual(len(predictions),len(mapping[42])*7*6)
        with self.assertRaises(FileExistsError):run(self.cfg_path,root)
        with self.assertRaisesRegex(ValueError,'outside'):
            run(self.cfg_path,self.phase_root/'do_not_write_here')
        self.assertFalse((self.phase_root/'do_not_write_here').exists())

    def test_plan_detects_components_crossing_folds(self):
        ids=sorted({i for f in self.locked['folds'] for i in f['validation_ids']});groups=deepcopy(self.groups)
        fold=self.locked['folds'][0];groups[fold['train_ids'][0]]=groups[fold['validation_ids'][0]]
        with self.assertRaisesRegex(ValueError,'component leaks'):
            validate_plan(self.locked['folds'],ids,groups,self.by_id)

    def test_all_five_seeds_are_kept_without_searching_for_a_good_seed(self):
        plans=repeated_plans(self.rows,self.locked,self.cfg)
        self.assertEqual([p['seed'] for p in plans],[42,7,21,73,2026])
        for p in plans:
            self.assertEqual(len({i for f in p['folds'] for i in f['validation_ids']}),self.cfg['expected_candidates'])

    def test_changed_phase_e_rejected_before_any_estimator_fit(self):
        with (self.phase_root/'metrics.json').open('a') as f:f.write(' ')
        with patch('src.baseline.bow_robustness.fit_predict') as fit:
            with self.assertRaisesRegex(ValueError,'artifact changed'):run(self.cfg_path,self.root/'changed')
            fit.assert_not_called()
        self.assertFalse((self.root/'changed').exists())


if __name__=='__main__':unittest.main()
