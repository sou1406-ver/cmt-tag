"""Open the same crawler profile normally for user-completed sign-in."""
import os
from pathlib import Path
import subprocess


def open_login(profile,channel='brave',browser_path=None):
    from .__main__ import browser_options
    binary=browser_options(channel,browser_path).get('executable_path')
    if not binary:
        candidates=[Path(os.environ[v])/'Google/Chrome/Application/chrome.exe'
                    for v in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA') if os.environ.get(v)]
        binary=next((str(p) for p in candidates if p.is_file()),None)
    if not binary: raise ValueError('Browser executable not found; use --browser-path')
    profile=Path(profile).resolve(); profile.mkdir(parents=True,exist_ok=True)
    subprocess.Popen([binary,'--user-data-dir='+str(profile),'--disable-background-mode','https://www.facebook.com/'],
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return profile
