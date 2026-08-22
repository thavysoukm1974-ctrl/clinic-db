"""
updater.py -- check GitHub Releases for a newer version and install it.

The idea: this app knows its own version (CURRENT_VERSION). It asks GitHub for
the latest published release; if that release is newer, it downloads the new
program, checks the download is intact (SHA-256), swaps it in, and restarts.
The user's data lives in a separate folder (Documents\\ClinicDB), so replacing
the program never touches it.

Everything here uses only the Python standard library (urllib, json, hashlib),
so the packaged app needs nothing extra installed.

SET-UP (one time): push this project to GitHub and put your details below in
GITHUB_OWNER / GITHUB_REPO. Each release: bump CURRENT_VERSION, build the exe,
and create a GitHub release tagged like "v1.1.0" with two files attached:
    ClinicSystem.exe          (the new program)
    ClinicSystem.exe.sha256   (a text file with the exe's SHA-256 hash)
Run  `python scripts/updater.py dist/ClinicSystem.exe`  to print that hash.
See RELEASING.md for the full step-by-step.
"""

import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# Bump this on every release. It is baked into the built .exe and compared
# against the latest release tag on GitHub.
CURRENT_VERSION = "1.0.3"

# Your GitHub repository, as owner/name.
GITHUB_OWNER = "thavysoukm1974-ctrl"
GITHUB_REPO = "clinic-db"

_API_LATEST = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
_HEADERS = {"User-Agent": "ClinicSystem-Updater"}   # GitHub requires a User-Agent


def _version_tuple(text):
    """Turn '1.2.3' or 'v1.2.3' into (1, 2, 3) so versions compare correctly."""
    parts = text.lstrip("vV").split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def check_for_update(timeout=10):
    """Ask GitHub for the latest release. Return a dict describing it if it is
    NEWER than CURRENT_VERSION, otherwise None.

    Never raises on a network problem -- it returns None -- so a failed or slow
    check can never stop the app from opening.

    The dict is {version, notes, exe_url, sha256_url}.
    """
    try:
        request = urllib.request.Request(_API_LATEST, headers=_HEADERS)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except Exception:
        return None   # offline, rate-limited, repo not found, etc. -- just skip

    latest = data.get("tag_name", "")
    if not _version_tuple(latest) or _version_tuple(latest) <= _version_tuple(CURRENT_VERSION):
        return None   # nothing newer

    exe_url = sha256_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".sha256"):
            sha256_url = asset.get("browser_download_url")
        elif name.endswith(".exe"):
            exe_url = asset.get("browser_download_url")
    if not exe_url:
        return None   # a release with no program attached -- ignore it

    return {"version": latest.lstrip("vV"), "notes": (data.get("body") or "").strip(),
            "exe_url": exe_url, "sha256_url": sha256_url}


def _download(url, dest, timeout=120):
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        dest.write_bytes(response.read())


def _sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(info, dest_dir):
    """Download the new program into dest_dir and verify its checksum (if the
    release provides one). Return the path to the verified new exe, or raise."""
    dest_dir = Path(dest_dir)
    new_exe = dest_dir / "ClinicSystem-new.exe"
    _download(info["exe_url"], new_exe)

    if info.get("sha256_url"):
        hash_file = dest_dir / "ClinicSystem-new.sha256"
        _download(info["sha256_url"], hash_file)
        expected = hash_file.read_text(encoding="utf-8").split()[0].strip().lower()
        hash_file.unlink(missing_ok=True)
        if _sha256_of(new_exe).lower() != expected:
            new_exe.unlink(missing_ok=True)
            raise ValueError("the downloaded update failed its checksum; not installing")
    return new_exe


def apply_update_and_restart(new_exe):
    """Install new_exe in place of the running program and restart it.

    Two Windows facts make this indirect: (1) you cannot overwrite the .exe that
    is currently running, and (2) a PyInstaller one-file exe relaunched directly
    from inside itself trips its own anti-tampering check. So we hand the job to
    a tiny .bat helper that runs as a SEPARATE process: it waits for this program
    to close (which frees the .exe file), swaps in the new one, and starts it.
    The old program is kept as ClinicSystem-old.exe as a fallback.
    """
    current = Path(sys.executable)
    backup = current.with_name("ClinicSystem-old.exe")
    helper = current.with_name("_apply_update.bat")

    lines = [
        "@echo off",
        "ping 127.0.0.1 -n 2 >nul",                       # brief pause
        ":wait",
        # keep waiting while this program is still running (its .exe stays locked)
        f'tasklist /fi "imagename eq {current.name}" | find /i "{current.name}" >nul '
        f'&& ( ping 127.0.0.1 -n 2 >nul & goto wait )',
        f'del "{backup}" >nul 2>&1',
        f'move /y "{current}" "{backup}" >nul',           # keep the old one as fallback
        f'move /y "{new_exe}" "{current}" >nul',          # install the new one
        f'start "" "{current}"',                          # launch the new version
        'del "%~f0" >nul 2>&1',                            # delete this helper script
    ]
    helper.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    # CREATE_NO_WINDOW (0x08000000) so no console window flashes.
    subprocess.Popen(["cmd", "/c", str(helper)], creationflags=0x08000000)


def cleanup_old():
    """Remove the leftover ClinicSystem-old.exe from a previous update, if any."""
    try:
        Path(sys.executable).with_name("ClinicSystem-old.exe").unlink(missing_ok=True)
    except Exception:
        pass


def main():
    # Helper: `python scripts/updater.py <file>` prints the file's SHA-256, which
    # you save as ClinicSystem.exe.sha256 and attach to the GitHub release.
    if len(sys.argv) == 2:
        print(_sha256_of(sys.argv[1]))
    else:
        print("This app's version:", CURRENT_VERSION)
        print("Usage: python scripts/updater.py <file-to-hash>")


if __name__ == "__main__":
    main()
