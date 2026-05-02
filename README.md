# freehost

Free file hosting via GitHub Releases.

## Download

```
https://github.com/MarkChrisE2091/freehost/releases/download/{tag}/{filename}
```

Example:
```bash
curl -L https://github.com/MarkChrisE2091/freehost/releases/download/v1.0/SPY.zip -o SPY.zip
```

## Upload

```bash
# One command — creates release + uploads file (no prompts)
gh release create v1.0 --repo MarkChrisE2091/freehost --title "My Release" --notes "description" file1.zip file2.zip

# Add files to an existing release
gh release upload v1.0 --repo MarkChrisE2091/freehost newfile.zip
```

## Limits

| Limit | Value |
|---|---|
| Max file size | 2 GB |
| Files per release | 1,000 |
| Total storage | Unlimited |
| Bandwidth | Unlimited |
| Link expiration | Never |
