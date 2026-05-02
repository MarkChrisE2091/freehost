# freehost

Free file hosting via GitHub Releases.

## Download

Files are hosted as release assets. Download directly:

```
https://github.com/MarkChrisE2091/freehost/releases/download/{tag}/{filename}
```

### Example

```bash
curl -L https://github.com/MarkChrisE2091/freehost/releases/download/v1.0/SPY.zip -o SPY.zip
```

## Upload

```bash
# Create a new release with files
gh release create v1.0 --title "Release v1.0" file1.zip file2.zip

# Add files to an existing release
gh release upload v1.0 newfile.zip
```

## Limits

| Limit | Value |
|---|---|
| Max file size | 2 GB |
| Files per release | 1,000 |
| Total storage | Unlimited |
| Bandwidth | Unlimited |
| Link expiration | Never |
