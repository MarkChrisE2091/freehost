"""githost: upload and download files with GitHub Releases.

Usage:
  python githost.py upload   <user/repo> <release> <file or "folder/*"> ...
  python githost.py download <user/repo> <release> [folder]
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

FILES_PER_RELEASE = 1000   # GitHub's limit per release
FILES_PER_CALL = 100       # keeps each gh command under Windows' length limit
MAX_SIZE = 2 * 1024**3     # GitHub needs each file under 2 GiB
TMP_SUFFIX = ".githost-tmp"
API = "https://api.github.com"
NO_GH = "gh not found. Install it from https://cli.github.com"
CREATE_FLAGS = []          # tests add "--draft"


class Stop(Exception):
    """Stop with a message for the user."""


def github_name(name):
    """The name GitHub gives an uploaded file. Copied from gh's sanitizeFileName."""
    value = unicodedata.normalize("NFD", name)
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = unicodedata.normalize("NFC", value)
    if value.startswith("."):
        value = "default" + value
    value = re.sub(r"[^a-zA-Z0-9\-_+@]+", ".", value)
    value = re.sub(r"\.{2,}", ".", value)
    value = value.strip(".")
    if name != value and "." not in value:
        value = "default." + value
    return value


def warn(what, items):
    """List skipped items, only if there are any."""
    if items:
        print(f"Skipped {len(items)} {what}:")
        for item in items:
            print(f"  {item}")


def collect(items):
    """Turn the user's files and "folder/*" patterns into a list of files to upload."""
    paths = []
    for item in items:
        if os.path.isdir(item):
            raise Stop(f'{item} is a folder. Use "{item}/*" (with quotes).')
        if os.path.exists(item):
            paths.append(item)
        elif any(c in item for c in "*?["):
            matches = sorted(glob.glob(item))
            if not matches:
                raise Stop(f"No files match {item}")
            paths += matches
        else:
            raise Stop(f"Not found: {item}")

    files, subfolders, bad_names, too_big, seen = [], [], [], [], set()
    for path in paths:
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        name = os.path.basename(path)
        if os.path.isdir(path):
            subfolders.append(path)
        elif "#" in name or "[" in name:
            bad_names.append(path)
        elif os.path.getsize(path) >= MAX_SIZE:
            too_big.append(path)
        else:
            files.append(path)
    warn("subfolders", subfolders)
    warn("files with # or [ in the name (gh can't upload them)", bad_names)
    warn("files of 2 GB or more", too_big)

    by_name = {}
    for path in files:
        by_name.setdefault(github_name(os.path.basename(path)), []).append(path)
    clashes = [f"  {name}: {', '.join(p)}" for name, p in by_name.items() if len(p) > 1]
    if clashes:
        raise Stop("These files would get the same name on GitHub:\n" + "\n".join(clashes))
    return files


def part_tag(tag, n):
    """v1.0, v1.0-part2, v1.0-part3, ..."""
    return tag if n == 1 else f"{tag}-part{n}"


def find_parts(releases, tag):
    """Pick the release and its parts out of a list of releases. Returns {part number: release}."""
    parts = {}
    for release in releases:
        if release["tag_name"] == tag:
            parts[1] = release
        else:
            m = re.fullmatch(re.escape(tag) + r"-part(\d+)", release["tag_name"])
            if m and int(m.group(1)) >= 2:
                parts[int(m.group(1))] = release
    return parts


def plan_upload(files, parts):
    """Split files not yet on GitHub across the release and its parts.

    parts: {part number: names already in that part}.
    Returns ([(part number, files)], skipped files).
    """
    existing = {name for names in parts.values() for name in names}
    todo, skipped = [], []
    for path in files:
        (skipped if github_name(os.path.basename(path)) in existing else todo).append(path)
    plan, n = [], 1
    while todo:
        room = FILES_PER_RELEASE - len(parts.get(n, []))
        if room > 0:
            plan.append((n, todo[:room]))
            todo = todo[room:]
        n += 1
    return plan, skipped


def gh(*args):
    """Run gh and return its output. Raises Stop with gh's error message."""
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise Stop(NO_GH)
    if r.returncode != 0:
        raise Stop(r.stderr.strip() or f"gh {args[0]} failed")
    return r.stdout


def ensure_login():
    """Log in with gh, only if not logged in yet."""
    try:
        gh("auth", "status", "--hostname", "github.com")
        return
    except Stop as e:
        if str(e) == NO_GH:
            raise
    print("Not logged in to GitHub. Starting gh auth login ...")
    subprocess.run(["gh", "auth", "login"])
    try:
        gh("auth", "status", "--hostname", "github.com")
    except Stop:
        raise Stop("Still not logged in. Run: gh auth login")


def gh_releases(repo):
    """All releases of a repo (drafts too), each with its file names and sizes."""
    out = gh("api", "--paginate", f"repos/{repo}/releases?per_page=100",
             "--jq", ".[] | {id, tag_name, assets: [.assets[] | {name, size}]}")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def upload(repo, tag, items):
    files = collect(items)
    if not files:
        raise Stop("No files to upload.")
    ensure_login()
    parts = find_parts(gh_releases(repo), tag)
    plan, skipped = plan_upload(files, {n: [a["name"] for a in r["assets"]] for n, r in parts.items()})
    warn(f"files already in {tag}", skipped)
    done = 0
    for n, batch in plan:
        name = part_tag(tag, n)
        if n not in parts:
            gh("release", "create", name, "--repo", repo, "--title", name, "--notes", name, *CREATE_FLAGS)
        for i in range(0, len(batch), FILES_PER_CALL):
            group = batch[i:i + FILES_PER_CALL]
            try:
                gh("release", "upload", name, "--repo", repo, "--", *group)
            except Stop as e:
                raise Stop(f"{e}\nRun the same command again to finish the rest.")
            done += len(group)
            print(f"{name}: {i + len(group)}/{len(batch)} uploaded")
    print(f"Done: {done} uploaded, {len(skipped)} skipped.")


def public_releases(repo, tag):
    """Find the release and its parts without logging in. None if that isn't possible."""
    releases, n = [], 1
    while True:
        url = f"{API}/repos/{repo}/releases/tags/{urllib.parse.quote(part_tag(tag, n))}"
        try:
            with urllib.request.urlopen(url) as r:
                releases.append(json.load(r))
        except urllib.error.HTTPError as e:
            if e.code == 404 and n > 1:
                return releases
            return None  # private, missing, or hourly limit used up
        except urllib.error.URLError as e:
            raise Stop(f"Can't reach GitHub: {e.reason}")
        n += 1


def download(repo, tag, folder=None):
    folder = folder or tag
    releases = public_releases(repo, tag)
    via_gh = releases is None
    if via_gh:
        ensure_login()
        releases = [r for _, r in sorted(find_parts(gh_releases(repo), tag).items())]
    if not releases:
        raise Stop(f"Release {tag} not found in {repo}.")

    os.makedirs(folder, exist_ok=True)
    assets = [(r["tag_name"], a) for r in releases for a in r["assets"]]
    skipped = {a["name"] for _, a in assets if os.path.exists(os.path.join(folder, a["name"]))}
    warn(f"files already in {folder}", sorted(skipped))
    todo = [(t, a) for t, a in assets if a["name"] not in skipped]
    for i, (t, a) in enumerate(todo, 1):
        path = os.path.join(folder, a["name"])
        tmp = path + TMP_SUFFIX
        print(f"[{i}/{len(todo)}] {a['name']}")
        try:
            if via_gh:
                gh("release", "download", t, "--repo", repo, "-p", a["name"], "-O", tmp, "--clobber")
            else:
                with urllib.request.urlopen(a["browser_download_url"]) as r, open(tmp, "wb") as f:
                    shutil.copyfileobj(r, f, 1024 * 1024)
        except (Stop, OSError) as e:
            raise Stop(f"Download failed: {e}\nRun the same command again to finish the rest.")
        os.replace(tmp, path)
    print(f"Done: {len(todo)} downloaded, {len(skipped)} skipped, saved in {folder}")


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # odd file names can't crash printing
    try:
        if len(argv) >= 4 and argv[0] == "upload":
            upload(argv[1], argv[2], argv[3:])
        elif len(argv) in (3, 4) and argv[0] == "download":
            download(*argv[1:])
        else:
            print(__doc__.strip())
            return 1
    except Stop as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Run the same command again to finish the rest.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
