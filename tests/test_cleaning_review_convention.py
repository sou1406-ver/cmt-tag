"""Human-confirmed shorthand is explicit and bound to one workbook, not default."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from src.dataset.common import save,sha,verify,csv_rows
from src.dataset.normalization_workbook import import_cleaning


class HumanConventionTests(unittest.TestCase):
    def setup_files(self,p):
        workbook=p/'review.xlsx';workbook.write_bytes(b'fixture workbook')
        coordinator=p/'coordinator.json';save(coordinator,{})
        policy=p/'convention.json';save(policy,dict(status='EXPLICIT_HUMAN_REVIEW_CONVENTION',authorization='Explicit fixture human confirmation',
            workbook_sha256=sha(workbook),coordinator_sha256=sha(coordinator),blank_decision_and_note='ACCEPT',reject_without_note_issue='USER_REPORTED_SEPARATOR'))
        return workbook,coordinator,policy

    def rows(self):return [dict(id='a',text_truoc='raw',text_sau='view',decision='',note=''),dict(id='b',text_truoc='raw',text_sau='view',decision='REJECT',note='')]

    def test_explicit_bound_policy_imports_without_workbook_mutation(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);wb,c,policy=self.setup_files(p);before=sha(wb)
            with patch('src.dataset.normalization_workbook.validate_cleaning',return_value=self.rows()) as validate:
                m=import_cleaning(wb,c,p/'out',policy);validate.assert_called_once_with(wb,c,complete=False)
            self.assertEqual(m['decision_counts'],{'ACCEPT':1,'REJECT':1});self.assertFalse(m['canonical_approved']);self.assertEqual(sha(wb),before)
            verify(p/'out');rows,_=csv_rows((p/'out/human_normalization_decisions.local.csv').read_bytes())
            self.assertEqual(rows[0]['original_decision'],'');self.assertEqual(rows[1]['review_issue'],'USER_REPORTED_SEPARATOR')

    def test_hash_mismatch_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);wb,c,policy=self.setup_files(p);wb.write_bytes(b'edited')
            with self.assertRaisesRegex(ValueError,'checksum-bound'):import_cleaning(wb,c,p/'out',policy)
            self.assertFalse((p/'out').exists())

    def test_note_only_is_not_inferred(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);wb,c,policy=self.setup_files(p);rows=self.rows();rows[0]['note']='needs review'
            with patch('src.dataset.normalization_workbook.validate_cleaning',return_value=rows):
                with self.assertRaisesRegex(ValueError,'Note-only'):import_cleaning(wb,c,p/'out',policy)

    def test_default_remains_complete_and_strict(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);wb,c,_=self.setup_files(p)
            with patch('src.dataset.normalization_workbook.validate_cleaning',side_effect=ValueError('Incomplete')) as validate:
                with self.assertRaises(ValueError):import_cleaning(wb,c,p/'out')
                validate.assert_called_once_with(wb,c,complete=True)
