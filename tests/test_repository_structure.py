"""Active entry points import and show help without reading research data."""
from pathlib import Path
import subprocess
import sys
import unittest
from src.preprocessing import preprocess
from src.dataset.master import minimal_filter_text

class RepositoryStructureTests(unittest.TestCase):
    def test_research_exports_are_ignored_outside_default_directories(self):
        repo=Path(__file__).resolve().parents[1]
        private=['accidental.xlsx','docs/export/comments.csv','pilot.jsonl','reviews.parquet','archive.zip',
                 'docs/annotation_reviews/new/report.json','scratch/cookies.json','scratch/browser_profile_demo/state.json',
                 'outputs/sentiment_pilot_v3_1/pilot_sentiment_annotator_A.xlsx','data/imports/new/comments.csv']
        result=subprocess.run(['git','check-ignore','--no-index','-z','--stdin'],input=('\0'.join(private)+'\0').encode(),
                              capture_output=True,cwd=repo)
        self.assertEqual(set(result.stdout.decode().rstrip('\0').split('\0')),set(private))
        for public in ('tests/fixtures/comments.csv','configs/post_urls.example.csv'):
            result=subprocess.run(['git','check-ignore','--no-index',public],capture_output=True,text=True,cwd=repo)
            self.assertEqual(result.returncode,1,public)

    def test_one_minimal_implementation(self):
        self.assertIs(preprocess, minimal_filter_text)
        self.assertEqual(preprocess('  phim - :)) :):) -_-  '), 'phim - :)) :):) -_-')

    def test_six_workflow_commands(self):
        commands = [['-m','src.crawler','--help'], ['scripts/build_master_dataset.py','--help'],
                    ['-m','src.annotation','export','--help'], ['-m','src.annotation','import-human','--help'],
                    ['-m','src.models','train','--help'], ['-m','src.models','evaluate','--help']]
        for command in commands:
            with self.subTest(command=command):
                result=subprocess.run([sys.executable,*command],capture_output=True,text=True,
                                      cwd=Path(__file__).resolve().parents[1],timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('usage:',result.stdout)

if __name__=='__main__': unittest.main()
