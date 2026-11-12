"""Offline contracts for evidence-based normalization; no browser/API/model."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from src.preprocessing import preprocess
from src.preprocessing.evidence_cleaning import normalize,select_dom,token_evidence,aliases_resource
from src.preprocessing.final_normalization import normalize as v31
from src.dataset.master import cleaning_protection,cleaning_sample
from src.dataset.common import sha


class CleaningTests(unittest.TestCase):
    def row(self,**kw):
        return dict(record_id='r',source_dataset='facebook',comment_id='42',post_id='123',post_url='https://www.facebook.com/groups/5/posts/123',text_raw='Tên A phim không dở',**kw)
    def candidate(self,**kw):
        r=self.row();r.update(text_extraction_version='dom_text_v2',text_without_mentions='phim không dở',checksum_verified=True,mention_count=1,
            source_file='journal.jsonl',source_sha256='x',source_row=1,removed_mention_spans=[dict(start=0,end=5,text='Tên A',href='https://www.facebook.com/profile.php?id=99')]);r.update(kw);return r
    def test_dom_full_identity_and_span_evidence(self):
        text,flags,audit=select_dom(self.row(),[self.candidate()]);self.assertEqual(text,'phim không dở');self.assertEqual(flags,[]);self.assertEqual(audit[0]['status'],'VALID')
    def test_dom_source_checksum_rejected(self):
        self.assertIn('DOM_SOURCE_MISMATCH',select_dom(self.row(),[self.candidate(checksum_verified=False)])[1])
    def test_dom_wrong_post_rejected(self):
        self.assertIn('DOM_SOURCE_MISMATCH',select_dom(self.row(),[self.candidate(post_id='555')])[1])
    def test_dom_content_mismatch(self):
        self.assertIn('DOM_CONTENT_MISMATCH',select_dom(self.row(),[self.candidate(text_raw='khác hẳn')])[1])
    def test_dom_non_account_links_never_authorize_deletion(self):
        for href in ['https://www.facebook.com/photos','https://www.facebook.com/profile.php','https://www.facebook.com/help','https://example.com/name']:
            c=self.candidate();c['removed_mention_spans'][0]['href']=href
            self.assertIn('DOM_CONTENT_MISMATCH',select_dom(self.row(),[c])[1])
    def test_malformed_span_is_a_review_flag(self):
        self.assertIn('DOM_CONTENT_MISMATCH',select_dom(self.row(),[self.candidate(removed_mention_spans=[dict(start='bad')])])[1])
    def test_no_spans_is_not_evidence_of_only_mention_deletion(self):
        self.assertIn('DOM_EVIDENCE_MISSING',select_dom(self.row(),[self.candidate(removed_mention_spans=[])])[1])
    def test_conflicting_valid_dom_views(self):
        r=self.row();r['text_raw']='A B phim'
        a=self.candidate(text_raw='A B phim',text_without_mentions='B phim',removed_mention_spans=[dict(start=0,end=1,text='A',href='https://www.facebook.com/a')])
        b=self.candidate(text_raw='A B phim',text_without_mentions='A phim',removed_mention_spans=[dict(start=2,end=3,text='B',href='https://www.facebook.com/b')])
        text,flags,_=select_dom(r,[a,b]);self.assertEqual(text,r['text_raw']);self.assertIn('DOM_CONFLICT',flags)
    def test_valid_unchanged_dom(self):
        text,flags,_=select_dom(self.row(),[self.candidate(text_without_mentions=self.row()['text_raw'],mention_count=0,removed_mention_spans=[])])
        self.assertEqual(text,self.row()['text_raw']);self.assertEqual(flags,[])
    def test_no_plain_name_guess(self):
        for text in ['Nguyễn Văn A phim rất hay','Mưa Đỏ có Trấn Thành đóng à','Mong đạo diễn làm tốt hơn']:
            r=self.row();r['text_raw']=text
            self.assertEqual(select_dom(r,[])[0],text);self.assertEqual(normalize(text,source='facebook')['text_normalized'],text)
    def test_pinned_alias(self):
        self.assertEqual(normalize(':smiling_face_with_hearts:')['text_normalized'],'🥰')
        self.assertEqual(normalize('phim hay smiling_face_with_hearts',source='legacy_29k_unverified')['text_normalized'],'phim hay 🥰')
    def test_spaced_delimiters_and_repeated_aliases(self):
        self.assertEqual(normalize(': red_heart:: red_heart:')['text_normalized'],'❤️❤️')
    def test_invalid_alias_stays(self):
        self.assertEqual(normalize(':not_a_valid_emoji:')['text_normalized'],':not_a_valid_emoji:')
    def test_alias_identifier_ambiguous(self):
        for text in ['smiling_face_with_hearts','x_smiling_face_with_hearts_y','const x = smiling_face_with_hearts']:
            self.assertEqual(normalize(text)['text_normalized'],text)
    def test_protected_structures_exact(self):
        text='https://example.com/smiling_face_with_hearts #kịch_bản a_b@mail.com `kịch_bản` ```x = kịch_bản```'
        self.assertEqual(normalize(text,source='legacy_29k_unverified',evidence_tokens={'kịch','bản'})['text_normalized'],text)
    def test_emoticons_exact(self):
        for text in ['-_-','^_^','T_T','._.','>_<']:
            r=normalize(text);self.assertEqual(r['text_normalized'],text);self.assertIn('NON_TEXT_REVIEW',r['normalization_flags'])
    def test_underscore_insufficient_evidence(self):
        self.assertEqual(normalize('mô_típ',source='legacy_29k_unverified',evidence_tokens={'mô'})['text_normalized'],'mô_típ')
    def test_underscore_valid_evidence(self):
        r=normalize('mô_típ không hay',source='legacy_29k_unverified',evidence_tokens={'mô','típ'})
        self.assertEqual(r['text_normalized'],'mô típ không hay');self.assertTrue(any(e['rule']=='FB_DISTINCT_TOKEN_EVIDENCE' for e in r['transform_events']))
    def test_frozen_lexical_recovery_not_replaced_by_new_evidence_rule(self):
        r=normalize('kịch_bản không hay',source='legacy_29k_unverified',evidence_tokens=())
        self.assertEqual(r['text_normalized'],v31('kịch_bản không hay',source='legacy_29k_unverified')['text_normalized'])
        self.assertFalse(any(e['rule']=='FB_DISTINCT_TOKEN_EVIDENCE' for e in r['transform_events']))
    def test_technical_and_name_compounds_preserved(self):
        for text in ['user_name','a_123','Trấn_Thành','hà_lan']:
            self.assertEqual(normalize(text,source='legacy_29k_unverified',evidence_tokens={'user','name','Trấn','Thành','hà','lan'})['text_normalized'],text)
    def test_new_rule_not_applied_to_facebook(self):
        r=normalize('mô_típ',source='facebook',evidence_tokens={'mô','típ'})
        self.assertFalse(any(e['rule']=='FB_DISTINCT_TOKEN_EVIDENCE' for e in r['transform_events']))
    def test_distinct_comments_not_occurrences(self):
        rows=[]
        for i in range(6):
            r=self.row();r.update(record_id=str(i),comment_id=str(i+1),text_raw='kịch kịch kịch kịch kịch')
            rows.append(r)
        self.assertNotIn('kịch',token_evidence(rows,set())['vocabulary'])
    def test_protected_evidence_not_counted(self):
        rows=[]
        for i in range(5):
            r=self.row();r.update(record_id=str(i),comment_id=str(i+1),text_raw='kịch '+str(i));rows.append(r)
        self.assertIn('kịch',token_evidence(rows,set())['vocabulary']);self.assertNotIn('kịch',token_evidence(rows,{'0'})['vocabulary'])
    def test_evidence_excludes_urls_code_and_legacy(self):
        r=self.row();r['text_raw']='`kịch` #bản @tên https://x.com/hay';r['source_dataset']='legacy_29k_unverified'
        self.assertEqual(token_evidence([r],set(),1)['vocabulary'],{})
        r['source_dataset']='facebook';self.assertEqual(token_evidence([r],set(),1)['vocabulary'],{})
    def test_mention_email_and_negation(self):
        text='@abc phim không dở a@b.com'
        self.assertEqual(normalize(text,source='facebook')['text_normalized'],'phim không dở a@b.com')
    def test_emoji_and_score_not_excluded(self):
        for text in ['😭','!!!','8/10','4/5','9 đ']:
            r=normalize(text);self.assertEqual(r['text_normalized'],text);self.assertNotIn('EXCLUDE',r['normalization_flags'])
        self.assertNotIn('NON_TEXT_REVIEW',normalize('8/10')['normalization_flags'])
    def test_frozen_v31_bytes_and_behavior(self):
        p=Path('src/preprocessing/final_normalization.py');before=sha(p)
        old=v31('kịch_bản không hay');normalize('kịch_bản không hay',source='legacy_29k_unverified')
        self.assertEqual(old,v31('kịch_bản không hay'));self.assertEqual(before,sha(p))
    def test_facade_and_idempotence(self):
        for text in [': red_heart:', '@abc phim hay','kịch_bản không hay','ko dở 😭','-_-']:
            opts=dict(source='legacy_29k_unverified',evidence_tokens={'kịch','bản'})
            a=preprocess(text,version='plain_text_v3_2',**opts)
            self.assertEqual(a,preprocess(text,version='plain_text_v3_2',**opts))
            self.assertEqual(a['text_normalized'],normalize(a['text_normalized'],**opts)['text_normalized'])
    def test_new_exact_alias_after_dom_protects(self):
        rows=[dict(record_id='a',source_dataset='facebook',text_raw='A phim hay',text_normalized='phim hay'),dict(record_id='b',source_dataset='facebook',text_raw='B phim hay',text_normalized='phim hay')]
        blocked,_=cleaning_protection(rows,{'a'});self.assertEqual(blocked,{'a','b'})
    def test_direct_near_and_raw_alias_leakage(self):
        rows=[dict(record_id='a',source_dataset='facebook',text_raw='một',text_normalized='hai'),dict(record_id='b',source_dataset='facebook',text_raw='ba',text_normalized='bốn'),dict(record_id='c',source_dataset='facebook',text_raw='ba',text_normalized='năm')]
        blocked,_=cleaning_protection(rows,{'a'},[dict(left='a',right='b')]);self.assertEqual(blocked,{'a','b','c'})
    def test_review_excludes_protected_and_no_human_prefill(self):
        rows=[dict(record_id=str(i),text_normalized='mới '+str(i),text_normalized_v3_1='cũ '+str(i),text_preprocessing_source='RAW',transform_events=[],normalization_flags=[]) for i in range(10)]
        selected,m=cleaning_sample(rows,{'0'},{str(i):str(i) for i in range(10)},__import__('collections').defaultdict(set),set())
        self.assertNotIn('0',m['ids']);self.assertLessEqual(len(selected),100);self.assertEqual((selected,m),cleaning_sample(rows,{'0'},{str(i):str(i) for i in range(10)},__import__('collections').defaultdict(set),set()))

    def test_new_review_blank_never_means_accept(self):
        from src.dataset.normalization_workbook import validate_cleaning
        from src.dataset.common import save,seal
        with TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'candidate_corpus.local.jsonl').write_text('fixture',encoding='utf-8')
            save(p/'workbook_input.local.json',dict(kind='cleaning_v3_2',candidate_content_sha256=sha(p/'candidate_corpus.local.jsonl'),rows=[dict(id='r',text_truoc='cũ',text_sau='mới')]))
            seal(p,dict(preprocessing_version='plain_text_v3_2'))
            row=dict(id='r',text_truoc='cũ',text_sau='mới',decision='',note='')
            with patch('src.dataset.normalization_workbook.read_sheet',return_value=(list(row),[row],{})):
                self.assertEqual(validate_cleaning(p/'fake.xlsx',p/'workbook_input.local.json')[0]['decision'],'')
                with self.assertRaisesRegex(ValueError,'blank is pending'):validate_cleaning(p/'fake.xlsx',p/'workbook_input.local.json',True)

    def test_new_review_source_checksum_is_enforced(self):
        from src.dataset.normalization_workbook import validate_cleaning
        from src.dataset.common import save,seal
        with TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'candidate_corpus.local.jsonl').write_text('fixture',encoding='utf-8')
            save(p/'workbook_input.local.json',dict(kind='cleaning_v3_2',candidate_content_sha256='wrong',rows=[]));seal(p,dict(preprocessing_version='plain_text_v3_2'))
            with self.assertRaisesRegex(ValueError,'checksum'):validate_cleaning(p/'fake.xlsx',p/'workbook_input.local.json')

    def test_candidate_cannot_be_promoted_or_self_approved(self):
        from src.dataset.master import promote_canonical
        from src.dataset.common import save,seal
        with TemporaryDirectory() as tmp:
            p=Path(tmp);candidate=p/'candidate';candidate.mkdir()
            seal(candidate,dict(status='CANDIDATE_REBUILT_QUALITY_REVIEW_PENDING',preprocessing_version='plain_text_v3_2',canonical_approved=False))
            save(p/'approval.json',dict(source_switch_approved=True,reviewer='fixture',approved_at='fixture'))
            with self.assertRaises(ValueError):promote_canonical(candidate,p/'approval.json',p/'active.json')
            self.assertFalse((p/'active.json').exists())

    def test_raw_and_human_metadata_not_mutated(self):
        r=self.row();r.update(human_label='POS',human_decisions=[dict(label='POS',version='old')]);before=deepcopy(r)
        select_dom(r,[self.candidate()]);normalize(r['text_raw'],source='facebook')
        self.assertEqual(r,before)


if __name__=='__main__':unittest.main()
