import unittest
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from src.preprocessing.final_normalization import normalize,ABBREVIATIONS
from src.dataset.normalization_workbook import validate,import_review

class FinalNormalizationTests(unittest.TestCase):
    def test_standard_nested_and_split_entities(self):
        for before,after in [('&quot;','"'),('&amp;quot;','"'),('& quot ;','"'),('& amp ; quot ;','"'),('&quot','"'),('& # 39 ;',"'"),('&lt;','<'),('&gt;','>'),('&apos;',"'")]:
            self.assertEqual(normalize(before)['text_normalized'],after)

    def test_depth_limit_unknown_entities_and_ordinary_ampersand(self):
        for raw in ('&amp;amp;amp;amp;amp;quot;','A & B','&notanentity;'):
            result=normalize(raw)['text_normalized'];self.assertEqual(result,raw)
            self.assertEqual(normalize(result)['text_normalized'],result)

    def test_protected_url_code_identity_names_numbers(self):
        raw='https://x/&quot;/ko `ko &quot;` #con_gái @user_name ko.py user_name123 Ngạn_Hà 3 . 14 12 / 11 / 2026'
        self.assertEqual(normalize(raw,source='legacy_29k_unverified')['text_normalized'],raw)

    def test_user_confirmed_compound_and_contextual_function_word(self):
        raw='kịch_bản nhân_vật không_hề hay, con_gái này.'
        result=normalize(raw,source='legacy_29k_unverified')['text_normalized']
        self.assertIn('không hề',result);self.assertIn('con gái',result)
        self.assertEqual(normalize(result,source='legacy_29k_unverified')['text_normalized'],result)

    def test_whole_token_abbreviations_and_source_gate(self):
        raw='phim này ko hay, khum thích, hok xem, đc rồi, cx vậy'
        result=normalize(raw,source='facebook')['text_normalized']
        self.assertEqual(result,'phim này không hay, không thích, không xem, được rồi, cũng vậy')
        self.assertEqual(normalize('phim ko',source='unknown')['text_normalized'],'phim ko')
        self.assertIn('kokomo',normalize('phim kokomo',source='facebook')['text_normalized'])

    def test_quotes_ambiguous_and_expressive_slang_preserved(self):
        raw='phim "ko hay cx bt" k bt dc mn j z t m vl vcl vch'
        self.assertEqual(normalize(raw,source='facebook')['text_normalized'],raw)
        self.assertEqual(normalize('phim &quot;ko hay , cx vậy',source='facebook')['text_normalized'],'phim "ko hay , cx vậy')

    def test_config_disables_auto_group(self):
        cfg=deepcopy(ABBREVIATIONS);cfg['enabled']['auto']=False
        self.assertEqual(normalize('phim ko hay',source='facebook',abbreviations=cfg)['text_normalized'],'phim ko hay')

    def test_punctuation_emoticons_repetition_and_emoji(self):
        raw='hay , nhưng phim . sao ? thật ! :))) =))) :v ... ?! !!! 😭😭'
        expected='hay, nhưng phim. sao? thật! :))) =))) :v ... ?! !!! 😭😭'
        self.assertEqual(normalize(raw,source='facebook')['text_normalized'],expected)

    def test_long_text_deterministic_and_idempotent(self):
        raw=('phim ko hay , nhưng cx đc :))) '*1000).strip()
        result=normalize(raw,source='facebook')['text_normalized']
        self.assertGreater(len(result),30000)
        self.assertEqual(result,normalize(raw,source='facebook')['text_normalized'])
        self.assertEqual(result,normalize(result,source='facebook')['text_normalized'])

    def test_no_approval_or_annotation_pointer_created(self):
        result=normalize('phim ko hay',source='facebook')
        self.assertNotIn('text_annotation',result)
        self.assertEqual(result['normalization_approval'],'PENDING_HUMAN_NORMALIZATION_APPROVAL')

    def test_punctuation_created_alias_reaches_fixed_point(self):
        raw='word :crying_face :'
        result=normalize(raw)['text_normalized']
        self.assertEqual(normalize(result)['text_normalized'],result)

class NormalizationWorkbookTests(unittest.TestCase):
    def fixture(self):
        expected=[dict(record_id=str(i),text_normalized='phim hay',text_raw='phim hay',text_clean_i3='phim hay',
                       changed_vs_i3=False,change_categories=[],normalization_events=[],normalization_flags=[]) for i in range(150)]
        rows=[dict(id=r['record_id'],text_normalized='phim hay',change_categories='UNCHANGED_CONTROL',human_decision='',human_note='') for r in expected]
        evidence=[dict(id=r['record_id'],text_raw='phim hay',text_clean_i3='phim hay',text_normalized='phim hay',
                       transform_events_1=json.dumps(dict(events=[],flags=[]))) for r in expected]
        return expected,rows,evidence

    def run_validation(self,expected,rows,evidence,complete=False):
        reads=[(list(rows[0]),rows,None),(list(evidence[0]),evidence,None)]
        with patch('src.dataset.normalization_workbook.verify'),patch('src.dataset.normalization_workbook.load',return_value=expected),patch('src.dataset.normalization_workbook.read_sheet',side_effect=reads):
            return validate(Path('fixture.xlsx'),Path('fixture/coordinator.json'),complete)

    def test_exact_150_blank_rows_valid_but_not_complete(self):
        expected,rows,evidence=self.fixture()
        self.assertEqual(len(self.run_validation(expected,rows,evidence)),150)
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            self.run_validation(expected,rows,evidence,True)

    def test_tampered_text_evidence_and_duplicate_ids_rejected(self):
        expected,rows,evidence=self.fixture()
        for kind in ('text','evidence','id'):
            r,e=deepcopy(rows),deepcopy(evidence)
            if kind=='text':r[0]['text_normalized']='phim dở'
            elif kind=='evidence':e[0]['text_raw']='changed'
            else:r[0]['id']=r[1]['id']
            with self.assertRaises(ValueError):self.run_validation(expected,r,e)

    def test_sentiment_is_not_a_normalization_decision(self):
        expected,rows,evidence=self.fixture();rows[0]['human_decision']='POS'
        with self.assertRaisesRegex(ValueError,'Invalid human'):
            self.run_validation(expected,rows,evidence)

    def test_import_is_immutable_ledger_without_approval(self):
        _,rows,_=self.fixture()
        for row in rows:row['human_decision']='ACCEPT'
        with TemporaryDirectory() as tmp:
            output=Path(tmp)/'import'
            with patch('src.dataset.normalization_workbook.validate',return_value=rows),patch('src.dataset.normalization_workbook.sha',return_value='fixture'):
                result=import_review(Path('fixture.xlsx'),Path('coordinator.json'),output)
                self.assertFalse(result['annotation_pointer_updated'])
                self.assertEqual(result['status'],'HUMAN_NORMALIZATION_REVIEW_IMPORTED_NOT_CORPUS_APPROVAL')
                with self.assertRaises(FileExistsError):import_review(Path('fixture.xlsx'),Path('coordinator.json'),output)

if __name__=='__main__':unittest.main()
