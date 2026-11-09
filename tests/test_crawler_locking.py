from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.crawler.locking import RunLock, RunBusyError, LegacyRunLockError, run_is_busy


class RunLockTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'.browser.lock'

    def test_live_owner_blocks_second_session_and_export(self):
        with RunLock(self.path):
            self.assertTrue(run_is_busy(self.path))
            with self.assertRaises(RunBusyError):
                with RunLock(self.path): pass
        self.assertFalse(run_is_busy(self.path))

    def test_reopen_after_exception_without_deleting_file(self):
        with self.assertRaises(ValueError):
            with RunLock(self.path): raise ValueError('fixture')
        self.assertTrue(self.path.exists())
        with RunLock(self.path): pass

    def test_abrupt_process_exit_releases_lock(self):
        code='from src.crawler.locking import RunLock; import os,sys; lock=RunLock(sys.argv[1]); lock.__enter__(); os._exit(0)'
        subprocess.run([sys.executable,'-c',code,str(self.path)],check=True,timeout=10)
        with RunLock(self.path): pass

    def test_legacy_empty_file_not_silently_removed(self):
        self.path.touch()
        with self.assertRaises(LegacyRunLockError):
            with RunLock(self.path): pass
        self.assertTrue(run_is_busy(self.path))
        self.assertEqual(self.path.read_bytes(),b'')

    def test_export_checks_live_lock_not_file_existence(self):
        from src.crawler.store import Store, export_run
        from tests.test_crawler import CONFIG, POST, observation
        store=Store(Path(self.temp.name)/'runs',CONFIG)
        store.add(observation(),POST,'fixture')
        lock=store.path/'.browser.lock'
        output=Path(self.temp.name)/'export'
        with RunLock(lock):
            with self.assertRaises(ValueError): export_run(store.path,output)
        self.assertTrue(lock.exists())
        export_run(store.path,output)
        self.assertTrue((output/'comments.csv').is_file())


if __name__=='__main__': unittest.main()
