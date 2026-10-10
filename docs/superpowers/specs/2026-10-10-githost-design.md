# githost — Design

A single Python script that uploads and downloads files with GitHub Releases, hiding the 1,000-file limit, login, and other details.

## Commands

```
python githost.py upload   <user/repo> <release> <file or "folder/*"> ...
python githost.py download <user/repo> <release> [folder]
```

Examples:

```
python githost.py upload me/repo v1.0 photo001.jpg photo002.jpg
python githost.py upload me/repo v1.0 "photos/*" "photos2/*"
python githost.py upload me/repo v1.0 "photos/*" photo001.jpg
python githost.py upload me/repo v1.0 "photos/*.jpg"
python githost.py download me/repo v1.0
```

- Folders: use quoted `"photos/*"` (works in Bash, PowerShell, and cmd).
- Bare `photos` stops with: `photos is a folder. Use "photos/*".`

## Requirements

- Python 3 (built-in libraries only, no pip install)
- gh (GitHub CLI) — needed for upload and private downloads, not for public downloads. If missing when needed: `gh not found. Install it from https://cli.github.com`

## Upload

1. **Login:** check gh login; run `gh auth login` only if not logged in.
2. **Collect files:** every file named, plus every file matched by a pattern.
   - Subfolders are skipped (warn, listing them).
   - Files over 2 GB are skipped (warn, listing them).
   - Files with `#` or `[` in the name are skipped (warn, listing them) — gh can't upload them.
   - Two files with the same GitHub name → stop before uploading anything, listing the clashes.
3. **Skip existing:** files already in the release (or its parts) are not sent to gh (warn, listing them). This is needed because gh fails the whole call if even one file is already in the release. Files on disk are never changed.
4. **Split:** fill `v1.0` up to 1,000 files, then `v1.0-part2`, `v1.0-part3`, ... Create missing releases (title = tag, empty notes).
5. **Send:** `gh release upload <tag> --repo <repo> -- <files>`, 100 files per call (Windows command-length limit).
   - On any failure: stop, show gh's error, and say `Run the same command again to finish the rest.` (step 3 skips what's done).

**GitHub names:** GitHub renames some files (`my file.txt` → `my.file.txt`). Steps 2 and 3 compare names using gh's own renaming rule (`sanitizeFileName`, copied from gh).

## Download

1. **Find releases:** `v1.0` plus any `v1.0-part2`, `v1.0-part3`, ...
2. **Try without login first:** public repos download directly from GitHub.
3. **Fall back to gh** for private repos or when the 60-per-hour limit is used up (log in only if needed).
4. **Save:** all parts merge into one folder, `./v1.0/` by default (or the folder given).
5. **Skip existing:** files already on disk are skipped (warn, listing them).
6. **No half files:** every download (direct or via gh) goes to a temporary name and is renamed when complete. A half-finished file is never treated as existing; the next run downloads it in full.
7. **Errors:** release not found → clear message.

## Messages

- Warnings (skipped files, subfolders, oversized or unsupported names) appear only when something was skipped.
- Show progress per release and a final summary (uploaded / downloaded / skipped counts).

## Confirmed facts (tested)

- GitHub refuses file 1,001 in a release (`file_count limited to 1000 assets per release`).
- GitHub's release info lists all files, up to 1,000.
- Real gh uploaded 600 tiny files (~500 per minute) without being blocked.
- gh rejects a whole upload call if any file in it already exists, including under GitHub's renamed name (`my file.txt` vs `my.file.txt`).
- `"photos/*"` patterns expand correctly in Python under Bash, PowerShell, and cmd.

## Testing

- **Dry run:** fake gh, large file counts (e.g. 2,350 files → 1,000 / 1,000 / 350 split), subfolders, clashes, oversized files, `#`/`[` names, bare folder name, renamed names (`my file.txt`).
- **Live run:** tiny limits (e.g. 3 files per release) against hidden draft releases, for upload, re-run after interruption, and gh download.
- **Public download:** drafts aren't public, so test on the existing `v1.0` release.
- **Cleanup:** delete all test releases and temp files afterwards.

## Project changes

- Add `githost.py`.
- Remove `upload.py` (replaced).
- Update README with the two commands.
