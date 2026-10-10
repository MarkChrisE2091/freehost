# Freehost

Free file hosting via GitHub Releases.

Files are hosted as release assets. Download directly:
```
https://github.com/MarkChrisE2091/freehost/releases/download/{tag}/{filename}
```

Example:
```bash
curl -L https://github.com/MarkChrisE2091/freehost/releases/download/v1.0/SPY.zip -o SPY.zip
```

## Download

### All files in a release

```bash
# curl (no login, public repos only)
curl -s https://api.github.com/repos/MarkChrisE2091/freehost/releases/tags/v1.0 | grep -o '"browser_download_url": *"[^"]*"' | cut -d'"' -f4 | xargs -n1 curl -LO

# gh (requires gh auth login, work for private repo)
gh release download v1.0 --repo MarkChrisE2091/freehost --dir myfolder
```

## Upload

### New release

```bash
# Specific files
gh release create v1.0 --repo MarkChrisE2091/freehost --title "Release v1.0" --notes "description" file1.zip file2.zip

# All files in a folder (no subfolders)
gh release create v1.0 --repo MarkChrisE2091/freehost --title "Release v1.0" --notes "description" "myfolder/*"
```

### Existing release

```bash
# Specific files
gh release upload v1.0 --repo MarkChrisE2091/freehost newfile.zip

# All files in a folder (no subfolders)
gh release upload v1.0 --repo MarkChrisE2091/freehost "myfolder/*"
```

## githost (recommended)

One script for upload and download. Needs Python 3 and [gh](https://cli.github.com) (gh only for upload and private repos download).

```bash
# Upload files and/or whole folders (keep the quotes around folder/*)
python githost.py upload MarkChrisE2091/freehost v1.0 file1.zip "myfolder/*"

# Download every file in a release into ./v1.0/ (or give a folder)
python githost.py download MarkChrisE2091/freehost v1.0
```

- Creates the release if it doesn't exist; logs in with gh only when needed.
- Over 1,000 files: extras go to `v1.0-part2`, `v1.0-part3`, ...; download merges them back into one folder.
- Files already uploaded/downloaded are skipped, so an interrupted run can simply be re-run.
- Skipped (with a warning): subfolders, files of 2 GB or more, names with `#` or `[`.

## Limits

| Limit | Value |
|---|---|
| Max file size | 2 GB |
| Files per release | 1,000 |
| Total storage | Unlimited |
| Bandwidth | Unlimited |
| Link expiration | Never |
