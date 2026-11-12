"""Active entry points import and show help without reading research data."""
from pathlib import Path
import subprocess
import sys
import unittest
from src.preprocessing import preprocess
from src.dataset.master import minimal_filter_text

class RepositoryStructureTests(unittest.TestCase):
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
