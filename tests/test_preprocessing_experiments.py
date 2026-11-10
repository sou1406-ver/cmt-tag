from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import unicodedata

from scripts.development_baseline import execute, mask_text
from scripts.import_development_review import import_review
from scripts.prepare_development import grouped_records, load, read_csv, save, sha
from src.baseline.preprocessing_experiments import (collisions, estimator, offline_network,
    prepare_views, read_locked, run, validate_config)
from src.preprocessing.vietnamese import VietnamesePreprocessor
from tests import test_development_review as review_fixture


class VietnamesePreprocessingTests(unittest.TestCase):
    def config(self):return load('configs/preprocessing_experiments.json')['preprocessing']

    def test_raw_view_is_exact_and_light_preserves_accents_negation_intensifiers(self):
        processor=VietnamesePreprocessor(self.config())
        raw=unicodedata.normalize('NFD','Phim KHÔNG hay\n chưa tốt chẳng ổn chả thích đừng xem vl vch')
        self.assertEqual(processor.transform(raw).text,raw)
        result=processor.transform(raw,light=True)
        self.assertEqual(result.text,'phim không hay chưa tốt chẳng ổn chả thích đừng xem vl vch')
        self.assertTrue(any(s['step']=='unicode_nfc' and s['changed'] for s in result.steps))

    def test_teencode_is_optional_bounded_and_does_not_rewrite_price_units(self):
        processor=VietnamesePreprocessor(self.config())
        raw='ko ko khum đc k 4k 100 k kịch bản không chưa vl vch'
        self.assertEqual(processor.transform(raw,light=True).text,raw)
        result=processor.transform(raw,light=True,teencode=True)
        self.assertEqual(result.text,'không không không được không 4k 100 k kịch bản không chưa vl vch')
        self.assertEqual(result.counts['teencode_ko'],2)
        self.assertEqual(result.counts['k_after_number_preserved'],1)

    def test_emoji_and_emoticons_have_literal_neutral_distinct_tokens(self):
        processor=VietnamesePreprocessor(self.config())
        result=processor.transform('😭 😂 ❤️ 👍🏽 👩‍💻 🇻🇳 1️⃣ :))) =)) :( :D <3',light=True)
        self.assertEqual(result.counts['emoji_occurrences'],7)
        self.assertEqual(result.counts['emot_occurrences'],5)
        self.assertIn('emoji_u1f62d',result.text);self.assertIn('emoji_u1f602',result.text)
        self.assertIn('emot_u3a_u29_u29_u29',result.text)
        self.assertNotIn('positive',result.text);self.assertNotIn('negative',result.text)

    def test_segmenter_protects_symbol_and_entity_tokens(self):
        calls=[]
        def segment(value):
            calls.append(value)
            return value.replace('diễn xuất','diễn_xuất').replace('kịch bản','kịch_bản')
        processor=VietnamesePreprocessor(self.config(),segmenter=segment)
        result=processor.transform('TEN_PHIM không dở 😭 :))) diễn xuất và kịch bản',light=True,segment=True)
        self.assertIn('diễn_xuất',result.text);self.assertIn('kịch_bản',result.text)
        self.assertIn('không',result.text);self.assertIn('ten_phim',result.text)
        self.assertIn('emoji_u1f62d',result.text)
        self.assertTrue(all('emoji_' not in c and 'ten_phim' not in c and 'emot_' not in c for c in calls))

    def test_config_cannot_silently_remove_negation_or_expand_intensifiers(self):
        for field,value in [('teencode_map',{'không':''}),('intensifier_map',{'vl':'vãi'}),('emoji','sentiment')]:
            cfg=self.config();cfg[field]=value
            with self.assertRaises(ValueError):VietnamesePreprocessor(cfg)
        with self.assertRaises(ValueError):VietnamesePreprocessor(self.config()).transform('phim',segment=True)

    def test_offline_guard_blocks_network_and_restores_socket_api(self):
        connect=socket.socket.connect
        with offline_network():
            with self.assertRaisesRegex(RuntimeError,'offline'):socket.create_connection(('127.0.0.1',9))
        self.assertIs(socket.socket.connect,connect)

    def test_changed_counts_are_per_comment_and_occurrences_are_per_token(self):
        processor=VietnamesePreprocessor(self.config())
        rows=[dict(id='one',movie_id='x',text_raw='ko ko'),dict(id='two',movie_id='x',text_raw='không')]
        recipe=dict(feature='union',light=True,segment=False,teencode=True)
        _,stats,_=prepare_views(rows,recipe,processor)
        self.assertEqual(stats['changed_comments']['teencode'],1)
        self.assertEqual(stats['occurrences']['teencode_ko'],2)

    def test_postprocess_collisions_are_reported_without_moving_folds(self):
        locked=dict(folds=[dict(fold=0,validation_ids=['a']),dict(fold=1,validation_ids=['b'])])
        before=deepcopy(locked)
        self.assertEqual(len(collisions({'a':'không hay','b':'không hay'},locked)),1)
        self.assertEqual(locked,before)

    def test_mask_only_changes_alias_spans_and_preserves_other_unicode(self):
        suffix=unicodedata.normalize('NFD',' không dở, tôi chưa thất vọng')
        raw=unicodedata.normalize('NFD','Mưa Đỏ')+suffix
        aliases=[dict(text='Mưa Đỏ',token='TEN_PHIM')]
        self.assertEqual(mask_text(raw,aliases,'mua_do',normalize_unicode=False),'TEN_PHIM'+suffix)
        unrelated=unicodedata.normalize('NFD','phim rất tốt, diễn xuất ổn')
        recipe=dict(feature='char',light=False,segment=False,teencode=False)
        views,stats,_=prepare_views([dict(id='a',movie_id='mua_do',text_raw=unrelated)],recipe,
                                  VietnamesePreprocessor(self.config()),aliases)
        self.assertEqual(views['a'],unrelated)
        self.assertEqual(stats['changed_comments']['entity_mask'],0)


class PreprocessingExperimentTests(unittest.TestCase):
    def setUp(self):
        helper=review_fixture.DevelopmentReviewTests();helper.setUp();self.addCleanup(helper.doCleanups)
        self.root=helper.root
        self.reviewed=self.root/'reviewed'
        import_review(helper.source,helper.csv(helper.decisions()),self.reviewed,'fixture_a')
        rows=read_csv(self.reviewed/'annotations.csv');eligible=sorted(r['id'] for r in rows if r['status']=='LABELED')
        by_id={r['id']:r for r in rows};_,_,groups=grouped_records(rows)
        folds=[]
        for index in range(3):
            valid=[rid for rid in eligible if int(by_id[rid]['post_id'][4:])%3==index]
            train=[rid for rid in eligible if rid not in valid]
            folds.append(dict(fold=index,train_ids=train,validation_ids=valid,
                              train_counts=dict(Counter(by_id[r]['label'] for r in train)),
                              validation_counts=dict(Counter(by_id[r]['label'] for r in valid))))
        self.locked=dict(seed=42,candidates=len(eligible),folds=folds,group_by_id=groups,
                         omitted_duplicate_ids=[],dataset_manifest_sha256=sha(self.reviewed/'manifest.json'),
                         provisional=False,independent_test=False,ready_to_run=True)
        self.plan_path=self.root/'plan.json';save(self.plan_path,self.locked)
        reference,_,_=execute(rows,dict(variants=['original'],models=['nb','lr','svm'],ngram_max=2,
                                      class_weight='balanced',seed=42,top_features=3),self.locked,[])
        save(self.root/'reference.json',dict(results=reference))
        save(self.root/'aliases.json',dict(aliases=[dict(text='thread0',token='TEN_PHIM')]))
        self.cfg=load('configs/preprocessing_experiments.json')
        self.cfg.update(dataset=str(self.reviewed),dataset_manifest_sha256=sha(self.reviewed/'manifest.json'),
                        locked_plan=str(self.plan_path),locked_plan_sha256=sha(self.plan_path),
                        reference_metrics=str(self.root/'reference.json'),reference_metrics_sha256=sha(self.root/'reference.json'),
                        mask_lexicon=str(self.root/'aliases.json'),mask_lexicon_sha256=sha(self.root/'aliases.json'),
                        expected_candidates=len(eligible))
        self.cfg_path=self.root/'config.json';save(self.cfg_path,self.cfg)

    def test_full_fixture_uses_same_folds_and_reproduces_reference(self):
        output=self.root/'experiment'
        with patch('builtins.print'):
            result=run(self.cfg_path,output,segmenter=lambda value:value,fixture=True)
        self.assertEqual(result['fits'],78)
        self.assertFalse(result['independent_test']);self.assertTrue(result['fixture_only'])
        self.assertEqual(sha(output/'locked_plan.json'),self.cfg['locked_plan_sha256'])
        metrics=load(output/'metrics.json');self.assertEqual(len(metrics['results']),26)
        self.assertEqual(metrics['results'][-1]['parent_run_id'],metrics['selected_parent_run_id'])
        pred=read_csv(output/'predictions.csv');seen=Counter((r['run_id'],r['id']) for r in pred)
        self.assertTrue(all(v==1 for v in seen.values()))
        original={rid:f['fold'] for f in self.locked['folds'] for rid in f['validation_ids']}
        self.assertTrue(all(int(r['fold'])==original[r['id']] for r in pred))
        self.assertEqual(sha(self.reviewed/'manifest.json'),self.cfg['dataset_manifest_sha256'])
        with self.assertRaises(FileExistsError):run(self.cfg_path,output,fixture=True)

    def test_checksum_and_fold_leakage_rejected_before_training(self):
        with self.plan_path.open('a') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'checksum'):read_locked(self.cfg)
        save(self.plan_path,self.locked)
        changed=deepcopy(self.locked)
        changed['folds'][0]['train_ids'].append(changed['folds'][0]['validation_ids'][0])
        save(self.plan_path,changed);cfg=deepcopy(self.cfg);cfg['locked_plan_sha256']=sha(self.plan_path)
        with self.assertRaisesRegex(ValueError,'partition'):read_locked(cfg)

    def test_reference_mismatch_rolls_back_all_outputs(self):
        reference=load(self.root/'reference.json');reference['results'][0]['oof']['macro_f1']=-1
        save(self.root/'reference.json',reference)
        cfg=deepcopy(self.cfg);cfg['reference_metrics_sha256']=sha(self.root/'reference.json');save(self.cfg_path,cfg)
        with patch('builtins.print'),self.assertRaisesRegex(ValueError,'B0 failed'):
            run(self.cfg_path,self.root/'failed',segmenter=lambda value:value,fixture=True)
        self.assertFalse((self.root/'failed').exists())
        self.assertFalse(list(self.root.glob('.phase-e-*')))

    def test_concurrent_config_change_cannot_be_recorded_as_the_original_run(self):
        changed=[]
        def segment(value):
            if not changed:
                with self.cfg_path.open('a') as f:f.write('\n')
                changed.append(True)
            return value
        with patch('builtins.print'),self.assertRaisesRegex(ValueError,'config changed'):
            run(self.cfg_path,self.root/'changed',segmenter=segment,fixture=True)
        self.assertFalse((self.root/'changed').exists())

    def test_word_char_and_union_vocabulary_is_train_only(self):
        train=['phim rất hay trainonlymarker','kịch bản tệ trainonlymarker','thời lượng bao nhiêu trainonlymarker']
        for feature in ('word','char','union'):
            with self.subTest(feature=feature):
                recipe=dict(feature=feature)
                pipeline=estimator(recipe,'lr','balanced',self.cfg)
                pipeline.fit(train,['POS','NEG','NEU'])
                pipeline.predict(['validationzzzzz only'])
                if feature=='word':vecs=[pipeline['vectorizer']]
                elif feature=='char':vecs=[pipeline['features']]
                else:vecs=[v for _,v in pipeline['features'].transformer_list]
                for vec in vecs:
                    self.assertNotIn('validationzzzzz',vec.vocabulary_)
                    self.assertNotIn('zzz',vec.vocabulary_)

    def test_unsupported_feature_changes_are_not_silently_accepted(self):
        cfg=deepcopy(self.cfg);cfg['variants']['B2']['teencode']=True
        with self.assertRaisesRegex(ValueError,'ablation'):validate_config(cfg)


if __name__=='__main__':unittest.main()
