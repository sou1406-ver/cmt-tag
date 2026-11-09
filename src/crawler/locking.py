"""OS-owned run lock. A process exit releases it even if the file remains."""
import os
from pathlib import Path


class RunBusyError(RuntimeError):
    pass


class LegacyRunLockError(RuntimeError):
    pass


class RunLock:
    def __init__(self,path):
        self.path=Path(path)
        self.file=None

    def __enter__(self):
        try:
            self.file=self.path.open('x+b')
            self.file.write(b' '); self.file.flush()
        except FileExistsError:
            self.file=self.path.open('r+b')
            if self.path.stat().st_size==0:
                self.file.close(); self.file=None
                raise LegacyRunLockError('Legacy empty .browser.lock; verify no old crawler is running before removing only this file.')
        try:
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close(); self.file=None
            raise RunBusyError('This run is being used by another crawler. Close that session before resuming.') from exc
        return self

    def __exit__(self,*exc):
        if self.file is not None:
            try:
                self.file.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.file,fcntl.LOCK_UN)
            finally:
                self.file.close(); self.file=None
        # Never unlink: another process may already hold/open the same inode.


def run_is_busy(path):
    path=Path(path)
    if not path.exists(): return False
    try:
        with RunLock(path): return False
    except (RunBusyError,LegacyRunLockError): return True
