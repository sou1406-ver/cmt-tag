"""Compatibility of structural adapters, without data preparation or model fitting."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.preprocessing import preprocess
from src.dataset.common import read_sheet,validate_review_ids,literal_text
from src.dataset import quality_review,quality_workbook


class RepositoryStructureTests(unittest.TestCase):
    def test_version_dispatch_preserves_engine_results(self):
        from src.preprocessing.normalization import normalize
        from src.preprocessing.plain_text import preprocess as v1
        from src.preprocessing.plain_text_v3 import preprocess as v3
        from src.preprocessing.final_normalization import normalize as v31
        raw='phim ko hay , kịch_bản 😊 #movie_review'
        for version,engine in [('plain_text_v1',v1),('plain_text_v3',v3),('plain_text_v3_1',v31)]:
            result=preprocess(raw,version=version)
            self.assertEqual(result['details'],engine(raw))
            self.assertEqual(result['text_normalized'],engine(raw)['text_normalized' if version.endswith('3_1') else 'text_clean'])
        self.assertEqual(preprocess(raw,version='basic_v1')['text_normalized'],normalize(raw))
        with self.assertRaises(ValueError):preprocess(raw,version='unregistered')

    def test_current_dispatch_forwards_resources_and_never_approves(self):
        from src.preprocessing.final_normalization import normalize
        options=dict(source='facebook',accepted_tokens={'kịch_bản'})
        result=preprocess('phim ko hay kịch_bản',**options)
        self.assertEqual(result['details'],normalize('phim ko hay kịch_bản',**options))
        self.assertNotIn('text_annotation',result['details'])
        self.assertEqual(result['details']['normalization_approval'],'PENDING_HUMAN_NORMALIZATION_APPROVAL')

    def test_old_excel_reader_reexport_and_literal_contract(self):
        self.assertIs(quality_workbook.read_sheet,read_sheet)
        self.assertEqual(literal_text("'=literal"),'=literal')
        self.assertEqual(literal_text("'unchanged"),"'unchanged")

    def test_shared_id_validation_keeps_schema_errors(self):
        validate_review_ids([dict(id='a')],{'a'},1,'fixture')
        for rows in ([],[dict(id='a'),dict(id='a')],[dict(id='b')]):
            with self.assertRaisesRegex(ValueError,'fixture'):validate_review_ids(rows,{'a'},1,'fixture')

    def test_prepare_route_uses_original_defaults(self):
        fixture=dict(status='pending',rows=3,eligible_proposed=0,eligible_approved=0)
        with patch('src.dataset.quality_readiness.build',return_value=fixture) as build,contextlib.redirect_stdout(io.StringIO()):quality_review.main(['prepare'])
        build.assert_called_once_with(Path('configs/phase_j_v1.json'),Path('outputs/phase_j/v2'))

    def test_evaluation_old_script_exports_same_implementation(self):
        from scripts.evaluate_quality_review import evaluate
        self.assertIs(evaluate,quality_review.evaluate)

    def test_help_smoke_canonical_and_compatibility_routes(self):
        commands=[['-m','src.dataset.quality_review','--help'],['-m','src.dataset.quality_review','import','--help'],
            ['scripts/prepare_quality_readiness.py','--help'],['scripts/import_domain_spam_review.py','--help'],
            ['scripts/evaluate_quality_review.py','--help'],['scripts/freeze_annotation_dataset.py','--help']]
        for args in commands:
            result=subprocess.run([sys.executable,*args],capture_output=True,text=True,cwd=Path(__file__).resolve().parents[1],timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('usage:',result.stdout)

if __name__=='__main__':unittest.main()
