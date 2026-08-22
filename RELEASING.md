# Releasing an update

How to push a new version to the clinic computer from anywhere. The app checks
GitHub for a newer release when it opens; if there is one, it updates itself.
Her data (in `Documents\ClinicDB`) is never touched by an update.

## One-time set-up

1. Create a free GitHub account and a repository (for example `clinic-db`).
2. Push this project to it:
   ```bash
   git remote add origin https://github.com/<your-username>/clinic-db.git
   git push -u origin master
   ```
3. In `scripts/updater.py`, set your details near the top:
   ```python
   GITHUB_OWNER = "<your-username>"
   GITHUB_REPO  = "clinic-db"
   ```
4. Build the first `.exe` (below) and give it to the clinic computer once, by
   USB. From then on, updates arrive over the internet.

## Every time you want to release an update

1. **Make and test your changes** on your PC (`python scripts/gui.py`).
2. **Bump the version** in `scripts/updater.py`:
   ```python
   CURRENT_VERSION = "1.1.0"     # was 1.0.0
   ```
   Use higher numbers each time (1.0.0 -> 1.1.0 -> 1.2.0 ...).
3. **Commit and push** the changes to GitHub.
4. **Build the new program:**
   ```bash
   python -m PyInstaller --onefile --windowed --name ClinicSystem --paths scripts --add-data "schema.sql;." --noconfirm scripts/gui.py
   ```
   This makes `dist\ClinicSystem.exe`.
5. **Make its checksum file** (so the app can verify the download is intact):
   ```bash
   python scripts/updater.py dist/ClinicSystem.exe
   ```
   Copy the printed hash into a text file named `ClinicSystem.exe.sha256`.
6. **Create a GitHub release:**
   - On your repo page: *Releases* -> *Draft a new release*.
   - Tag it exactly `v1.1.0` (the `v` plus the same version number).
   - Write a short description (this is shown to her as "what's new").
   - Attach **both** files: `ClinicSystem.exe` and `ClinicSystem.exe.sha256`.
   - Publish.

That's it. Next time she opens the app it will notice `v1.1.0` is newer than
what she has, ask to install it, download it, check it, and restart into the
new version.

## Notes

- The version number in the app and the release tag must match (app `1.1.0`,
  tag `v1.1.0`).
- If GitHub can't be reached, the check is skipped silently -- the app always
  opens normally.
- The previous program is kept as `ClinicSystem-old.exe` until the next start,
  as a fallback; it is then cleaned up automatically.
- Keep the exe named `ClinicSystem.exe` (the `--name ClinicSystem` build flag),
  because the self-update swaps a file by that name.
