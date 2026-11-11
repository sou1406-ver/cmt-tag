import json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from copy import deepcopy
from src.dataset.common import load,sha,save,seal,write_jsonl,write_csv
from src.dataset.quality_readiness import layers,quality_metrics,isolation,spam_marker,verified_post
from src.dataset.quality_review import validate,import_review,FIELDS,EVIDENCE
from src.dataset.quality_release import freeze,export,write_blind_files


class QualityLayersTests(unittest.TestCase):
    def row(self,text,**kwargs):
        return dict(text_normalized=text,source_dataset='legacy_29k_unverified',quality_reasons=[],**kwargs)

    def test_domain_never_sentiment_or_metadata_truth(self):
        r=layers(self.row('hôm nay ăn bánh',movie_id='film',post_id='123',post_url='https://www.facebook.com/x/posts/123',comment_id='2'))
        self.assertEqual(r['domain_status'],'UNCERTAIN')
        self.assertNotIn('NEU',r.values())

    def test_offtopic_and_spam_are_separate(self):
        spam=layers(self.row('phim hay mua ngay đặt hàng inbox giảm giá'))
        self.assertEqual(spam['domain_status'],'IN_DOMAIN_CANDIDATE');self.assertEqual(spam['spam_status'],'SPAM_CANDIDATE')
        clean=layers(self.row('hôm nay ăn bánh'))
        self.assertEqual(clean['spam_status'],'NOT_FLAGGED_UNVALIDATED')
        self.assertNotEqual(clean['final_quality_decision'],'EXCLUDE_TECHNICAL')

    def test_long_review_and_emoji_not_automatically_spam(self):
        review='phim '+ ' '.join('từ'+str(i) for i in range(300))
        for text in (review,'phim hay '+ '😂'*100):
            r=layers(self.row(text));self.assertEqual(r['technical_status'],'VALID');self.assertEqual(r['spam_status'],'NOT_FLAGGED_UNVALIDATED')

    def test_structural_repetition_review_not_auto_exclusion(self):
        r=layers(self.row(('phim có diễn xuất và kịch bản tốt nhưng nhịp chưa ổn '*20)))
        self.assertEqual(r['spam_status'],'SPAM_CANDIDATE');self.assertEqual(r['final_quality_decision'],'REVIEW_PROPOSED')

    def test_technical_only_definite_exclusions(self):
        self.assertEqual(layers(self.row(''))['technical_status'],'EXCLUDE_EMPTY')
        self.assertEqual(layers(self.row('Xem thêm'))['technical_status'],'EXCLUDE_EXACT_UI')
        self.assertEqual(layers(self.row('phim \ufffd'))['technical_status'],'REVIEW_ENCODING')

    def test_parent_context_not_automatic_domain_confirmation(self):
        child=self.row('đúng thế',parent_comment_id='123')
        r=layers(child,self.row('phim hay'))
        self.assertEqual(r['domain_status'],'CONTEXT_REQUIRED')

    def test_post_identity_url_must_match(self):
        r=self.row('phim hay',post_id='123',post_url='https://www.facebook.com/a/posts/124',comment_id='7');r['source_dataset']='facebook'
        self.assertEqual(verified_post(r),'');r['post_id']='124';self.assertEqual(verified_post(r),'124')

    def test_spam_marker_is_explicit(self):
        self.assertEqual(spam_marker('[NOT_SPAM] đã xem'),'NOT_SPAM')
        self.assertEqual(spam_marker('ngoài phim'),'')
        self.assertEqual(spam_marker('[SPAM]suffix'),'')

    def test_metrics_need_real_complete_decisions(self):
        with self.assertRaises(ValueError):quality_metrics([])
        with self.assertRaises(ValueError):quality_metrics([dict(human_domain_decision='IN_DOMAIN',human_spam_decision='')])

    def test_false_keep_false_exclude_and_spam_metrics(self):
        base=dict(source_dataset='facebook',text_view='phim hay',repetition_diagnostics=dict(repetition_risk=False))
        rows=[dict(base,domain_status='IN_DOMAIN_CANDIDATE',spam_status='NOT_FLAGGED_UNVALIDATED',final_quality_decision='KEEP_PROPOSED',human_domain_decision='OFF_TOPIC',human_spam_decision='NOT_SPAM'),
              dict(base,domain_status='OFF_TOPIC_CANDIDATE',spam_status='SPAM_CANDIDATE',final_quality_decision='EXCLUDE_TECHNICAL',human_domain_decision='IN_DOMAIN',human_spam_decision='NOT_SPAM')]
        m=quality_metrics(rows)['overall'];self.assertEqual(m['false_keep'],1);self.assertEqual(m['false_exclude'],1);self.assertEqual(m['spam_precision'],0)

    def test_isolation_id_exact_near_post(self):
        rows=[dict(record_id=str(i),source_dataset='facebook',post_id='123',post_url='https://www.facebook.com/a/posts/123',comment_id=str(i)) for i in (1,2)]
        m=isolation(rows,{'1'},{'2'},[dict(left='1',right='2')],{'1':'same','2':'same'})
        self.assertEqual(m['verified_post_overlap'],1);self.assertEqual(m['exact_group_overlap'],1);self.assertEqual(m['direct_near_overlap'],1)


class QualityWorkbookTests(unittest.TestCase):
    def fixture(self):
        from src.dataset.common import digest
        expected=[dict(record_id=str(i),text_view='phim hay',text_raw='phim hay',text_previous='phim hay',source_view='fixture',text_sha256=digest('phim hay')) for i in range(40)]
        rows=[dict(id=r['record_id'],text_view=r['text_view'],human_domain_decision='',human_spam_decision='',human_note='') for r in expected]
        evidence=[dict(id=r['record_id'],**{k:r[k] for k in EVIDENCE[1:]}) for r in expected]
        return expected,rows,evidence

    def validate_fixture(self,expected,rows,evidence,complete=False,reserved=None,source_sha='source'):
        def mocked_load(p):
            if p.name=='holdout_input.local.json':return dict(kind='holdout',rows=expected,source_manifest_sha256=source_sha)
            if p.name=='config.json':return dict(source='fake',holdout_reservation='reservation.json')
            return dict(ids=reserved if reserved is not None else [r['record_id'] for r in expected])
        with patch('src.dataset.quality_review.verify'),patch('src.dataset.quality_review.sha',return_value='source'),patch('src.dataset.quality_review.load',side_effect=mocked_load),patch('src.dataset.quality_review.read_sheet',side_effect=[(FIELDS,rows,None),(EVIDENCE,evidence,None)]):
            return validate(Path('fixture.xlsx'),Path('fixture/holdout_input.local.json'),complete)

    def test_40_blank_validate_but_cannot_import(self):
        e,r,v=self.fixture();self.assertEqual(len(self.validate_fixture(e,r,v)[0]),40)
        with self.assertRaisesRegex(ValueError,'Incomplete'):self.validate_fixture(e,r,v,True)

    def test_holdout_ids_checksum_text_and_sentiment_tampering(self):
        e,r,v=self.fixture()
        with self.assertRaises(ValueError):self.validate_fixture(e,r,v,reserved=['other']*40)
        with self.assertRaises(ValueError):self.validate_fixture(e,r,v,source_sha='wrong')
        for key,value in [('id','1'),('text_view','changed'),('human_domain_decision','POS'),('human_spam_decision','OFF_TOPIC')]:
            altered=deepcopy(r);altered[0][key]=value
            with self.assertRaises(ValueError):self.validate_fixture(e,altered,v)
        altered=deepcopy(v);altered[0]['text_raw']='changed'
        with self.assertRaises(ValueError):self.validate_fixture(e,r,altered)

    def test_holdout_import_never_computes_rule_metrics(self):
        e,r,_=self.fixture()
        for row in r:row.update(human_domain_decision='UNSURE',human_spam_decision='SPAM_UNSURE')
        c=dict(kind='holdout',rows=e,source_manifest_sha256='source',normalization_version='plain_text_v3_1')
        with TemporaryDirectory() as tmp,patch('src.dataset.quality_review.validate',return_value=(r,c)),patch('src.dataset.quality_review.sha',return_value='fixture'),patch('src.dataset.quality_review.quality_metrics',side_effect=AssertionError('Holdout tuning')):
            output=Path(tmp)/'import';m=import_review(Path('f.xlsx'),Path('c.json'),output)
            self.assertFalse(m['annotation_pointer_updated']);self.assertEqual(m['rows'],40)
            self.assertIsNone(load(output/'metrics.json')['metrics'])

    def test_release_requires_actual_freeze_and_explicit_approval(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'approval.json';save(a,dict(approved='true'))
            with patch('src.dataset.quality_release.verify'),patch('src.dataset.quality_release.load',side_effect=[dict(approved='true'),dict()]):
                with self.assertRaisesRegex(ValueError,'Explicit human'):freeze(root,{},a,root/'out')
            with patch('src.dataset.quality_release.verify',return_value=dict(status='DATASET_FREEZE_PENDING')):
                with self.assertRaisesRegex(ValueError,'frozen corpus'):export(root,root,root/'candidate.csv',a,root/'out')

    def test_three_blind_outputs_identical_without_labels(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[dict(record_id='fixture',text_annotation='phim hay',legacy_overall='secret',human_label='POS')]
            hashes=write_blind_files(root,rows);self.assertEqual(len(set(hashes.values())),1)
            content=(root/'codex_input.csv').read_text(encoding='utf-8-sig')
            self.assertEqual(content,'id,text_annotation\nfixture,phim hay\n');self.assertNotIn('secret',content)

    def test_export_after_valid_fixture_freeze_and_checksum_approval(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';frozen=root/'frozen';source.mkdir();frozen.mkdir()
            norm=root/'norm';norm.mkdir();write_csv(norm/'direct_near_normalized.local.csv',[],['left','right','method'])
            old=root/'outputs/phase_i3/v3';old.mkdir(parents=True);write_csv(old/'direct_near_duplicates.local.csv',[],['left','right','method'])
            save(source/'config.json',dict(source='norm'));seal(source,dict(status='DATASET_FREEZE_PENDING'))
            rows=[dict(record_id=str(i),text_annotation='phim fixture '+str(i),annotation_eligibility='ELIGIBLE_APPROVED',human_decisions=[],test_reserved=False,master_group_id=str(i),source_dataset='fixture') for i in range(500)]
            write_jsonl(frozen/'approved_annotation_pool.local.jsonl',rows)
            seal(frozen,dict(status='DATASET_FROZEN_FOR_ANNOTATION',source_manifest_sha256=sha(source/'manifest.json'),guideline_sha256='fixture'))
            candidate=root/'candidate.csv';write_csv(candidate,[dict(id=r['record_id'],text_annotation=r['text_annotation']) for r in rows],['id','text_annotation'])
            approval=root/'approval.json';save(approval,dict(approved=True,reviewer='fixture',approved_at='fixture',candidate_sha256=sha(candidate),frozen_manifest_sha256=sha(frozen/'manifest.json')))
            with patch('src.dataset.quality_release.ROOT',root),patch('src.dataset.quality_release.assert_allowed') as guard:
                result=export(frozen,source,candidate,approval,root/'release')
                guard.assert_called_once();self.assertEqual(result['rows'],500);self.assertEqual(len(set(result['sha256'].values())),1)
            self.assertEqual(load(root/'release/manifest.json')['agreement_interpretation'],'silver, never gold')

if __name__=='__main__':unittest.main()
