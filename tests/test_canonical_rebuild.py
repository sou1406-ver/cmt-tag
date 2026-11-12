"""Raw curation/provenance and fail-closed source switching, using fixtures."""
import json,unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from src.dataset.common import digest,sha,save,seal
from src.dataset.legacy_audit import verified_tail_block,region_audit,template_overlap_audit
from src.dataset.master import canonical_sources,promote_canonical


class CanonicalSourceTests(unittest.TestCase):
    def rule(self):return dict(last_records=2,first_original_id=11,last_original_id=12)
    def rows(self):return [dict(id=str(i),comment='phim bình thường',overall='unverified') for i in (7,11,12)]

    def test_tail_requires_file_position_and_exact_id_sequence(self):
        self.assertEqual(verified_tail_block(self.rows(),self.rule()),{2,3})
        for rows in (list(reversed(self.rows())),[self.rows()[0],self.rows()[2],self.rows()[1]],self.rows()+[dict(id='13',comment='text')]):
            with self.assertRaises(ValueError):verified_tail_block(rows,self.rule())

    def test_missing_duplicate_ids_fail_closed(self):
        for value in ('','11'):
            rows=self.rows();rows[0]['id']=value
            with self.assertRaises(ValueError):verified_tail_block(rows,self.rule())

    def test_region_format_signal_does_not_exclude_or_label(self):
        rows=self.rows();rows[0]['comment']='kịch_bản nhân_vật không dở 😊'
        result=region_audit(rows,2)
        self.assertEqual(result[0]['underscore_rows'],1);self.assertEqual(len(rows),3)
        self.assertNotIn('EXCLUDE',json.dumps(result));self.assertEqual(result[0]['legacy_overall_audit_only'],{'unverified':2})

    def test_contamination_is_review_signal_not_exclusion(self):
        phrase='một câu rất dài có nhiều nội dung giống nhau nhưng không chứng minh nguồn gốc'
        rows=[dict(id=str(i),comment=phrase,overall='ignored') for i in range(4)]
        outside,patterns,summary=template_overlap_audit(rows,{3,4},width=8,min_chars=25,min_records=2)
        self.assertEqual(set(outside),{1,2});self.assertTrue(patterns);self.assertFalse(summary['ai_generated_claim'])
        self.assertEqual(len(rows),4)

    def fixture_source(self,root):
        source=root/'raw.csv';source.write_text('id,comment,overall\n11,phim không dở,neg\n',encoding='utf-8-sig')
        checksum=sha(source)
        obs=dict(source_file='raw.csv',source_row=1,input_sha256=checksum,text_raw='phim không dở')
        item=dict(id='master_identity',source_file='raw.csv',source_row=1,text_raw='phim không dở',source_platform='unknown',group_id='oldgroup',
            movie_id='',post_id='',post_url='',comment_id='',parent_comment_id='',text_variants=['phim không dở'],development_ids=[],review_flags=[],observations=[obs])
        return source,checksum,item,dict(input_sha256={str(source.resolve()):checksum})

    def test_raw_provenance_is_not_joined_by_label_or_text_only(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source,checksum,item,manifest=self.fixture_source(root)
            with patch('src.dataset.master.ROOT',root):
                rows,mapping,index,count=canonical_sources([item],manifest,source,checksum)
            self.assertEqual(rows[0]['original_id'],'11');self.assertEqual(rows[0]['legacy_overall_status'],'UNVERIFIED')
            self.assertNotIn('human_label',rows[0]);self.assertEqual(rows[0]['text_raw'],'phim không dở');self.assertEqual(count,1)
            self.assertEqual(mapping[0]['raw_sha256'],digest('phim không dở'))

    def test_source_checksum_mismatch_blocks_before_curated_output(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source,checksum,item,manifest=self.fixture_source(root);source.write_text('changed',encoding='utf-8')
            with patch('src.dataset.master.ROOT',root),self.assertRaisesRegex(ValueError,'checksum'):
                canonical_sources([item],manifest,source,checksum)

    def test_source_row_or_raw_mismatch_cannot_reuse_master_identity(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source,checksum,item,manifest=self.fixture_source(root)
            altered=deepcopy(item);altered['observations'][0]['text_raw']='different'
            with patch('src.dataset.master.ROOT',root),self.assertRaisesRegex(ValueError,'raw text'):
                canonical_sources([altered],manifest,source,checksum)

    def test_source_namespace_not_numeric_id_decides_legacy(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);legacy,checksum,item,manifest=self.fixture_source(root)
            fb=root/'fb.csv';fb.write_bytes(legacy.read_bytes());fb_item=deepcopy(item)
            fb_item.update(id='facebook_identity',source_file='fb.csv',source_platform='facebook')
            fb_item['observations'][0]['source_file']='fb.csv';manifest['input_sha256'][str(fb.resolve())]=sha(fb)
            with patch('src.dataset.master.ROOT',root):rows,_,_,_=canonical_sources([item,fb_item],manifest,legacy,checksum)
            self.assertEqual([r['source_dataset'] for r in rows],['legacy_29k_unverified','facebook'])
            self.assertNotEqual(rows[0]['record_id'],rows[1]['record_id'])


class CanonicalPromotionTests(unittest.TestCase):
    def test_verified_rebuild_does_not_implicitly_promote(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);version=root/'version';version.mkdir();seal(version,dict(status='REBUILD_VERIFIED',dataset_version='fixture',canonical_content_sha256='content'))
            approval=root/'approval.json';save(approval,dict(source_switch_approved='true'))
            pointer=root/'active.json'
            with self.assertRaisesRegex(ValueError,'Explicit'):promote_canonical(version,approval,pointer)
            self.assertFalse(pointer.exists())

    def test_explicit_source_switch_is_not_quality_approval(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);version=root/'version';version.mkdir();seal(version,dict(status='REBUILD_VERIFIED',dataset_version='fixture',canonical_content_sha256='content'))
            approval=root/'approval.json';save(approval,dict(source_switch_approved=True,reviewer='fixture',approved_at='fixture',manifest_sha256=sha(version/'manifest.json'),canonical_content_sha256='content'))
            pointer=root/'active.json';state=promote_canonical(version,approval,pointer)
            self.assertEqual(state,'QUALITY_REVIEW_PENDING');self.assertFalse(json.loads(pointer.read_text())['canonical_approved'])
            with self.assertRaises(FileExistsError):promote_canonical(version,approval,pointer)


class CanonicalQualityContractTests(unittest.TestCase):
    def validate_fixture(self,content_hash='content',complete=False):
        from src.dataset.quality_review import validate,FIELDS,EVIDENCE
        e=dict(record_id='fixture',text_view='phim hay',text_raw='phim hay',text_previous='phim hay',source_view='raw source checksum fixture',text_sha256=digest('phim hay'))
        contract=dict(kind='canonical',rows=[e],dataset_version='fixture',source_manifest_sha256='source',canonical_content_sha256=content_hash)
        def fake_load(path):
            if path.name=='workbook_input.local.json':return contract
            if path.name=='config.json':return dict(source='master')
            return dict(dataset_version='fixture')
        def fake_sha(path):return 'content' if path.name=='normalized_annotation_view.local.jsonl' else 'source'
        review=dict(id='fixture',text_view='phim hay',human_domain_decision='',human_spam_decision='',human_note='')
        evidence=dict(id='fixture',**{k:e[k] for k in EVIDENCE[1:]})
        with patch('src.dataset.quality_review.verify'),patch('src.dataset.quality_review.load',side_effect=fake_load),patch('src.dataset.quality_review.sha',side_effect=fake_sha),patch('src.dataset.quality_review.read_sheet',side_effect=[(FIELDS,[review],None),(EVIDENCE,[evidence],None)]):
            return validate(Path('fixture.xlsx'),Path('fixture/workbook_input.local.json'),complete)

    def test_canonical_review_requires_new_corpus_checksum(self):
        self.assertEqual(len(self.validate_fixture()[0]),1)
        with self.assertRaisesRegex(ValueError,'Canonical review'):self.validate_fixture('old-corpus')

    def test_blank_canonical_quality_never_becomes_human_approval(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):self.validate_fixture(complete=True)

if __name__=='__main__':unittest.main()
