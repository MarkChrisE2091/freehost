# freehost

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

## Limits

| Limit | Value |
|---|---|
| Max file size | 2 GB |
| Files per release | 1,000 |
| Total storage | Unlimited |
| Bandwidth | Unlimited |
| Link expiration | Never |
