import contextlib, io, json, os, pathlib, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import githost


class GithubNameTest(unittest.TestCase):
    def test_matches_real_github_renames(self):
        # Pairs observed on real uploads to GitHub
        cases = {
            "SPY.zip": "SPY.zip",
            "my file.txt": "my.file.txt",
            "c20  z.txt": "c20.z.txt",
            "a(1).txt": "a.1.txt",
            "d1..b.txt": "d1.b.txt",
            ".hidden": "default.hidden",
            "d3end.": "default.d3end",
            "!e2lead": "default.e2lead",
            "e3trail!": "default.e3trail",
            "über.txt": "uber.txt",
            "日本.zip": "default.zip",
            "-dash.txt": "-dash.txt",
            "a+b@c-d_e.txt": "a+b@c-d_e.txt",
        }
        for name, expected in cases.items():
            self.assertEqual(githost.github_name(name), expected, name)


def make(path, data=b"x"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def quiet(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = fn(*args)
    return result, out.getvalue()


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_bare_folder_stops(self):
        os.mkdir("photos")
        with self.assertRaisesRegex(githost.Stop, r'photos is a folder\. Use "photos/\*"'):
            githost.collect(["photos"])

    def test_pattern_and_file_mixed(self):
        make("photos/a.jpg"); make("photos/b.png"); make("c.jpg")
        files, _ = quiet(githost.collect, ["photos/*", "c.jpg"])
        self.assertEqual([os.path.basename(f) for f in files], ["a.jpg", "b.png", "c.jpg"])

    def test_skips_subfolders_bad_names_and_big_files_with_warnings(self):
        make("p/ok.txt"); make("p/sub/inner.txt"); make("p/a#b.txt"); make("p/a[1].txt"); make("p/big.bin", b"x" * 10)
        old = githost.MAX_SIZE
        githost.MAX_SIZE = 5
        try:
            files, out = quiet(githost.collect, ["p/*"])
        finally:
            githost.MAX_SIZE = old
        self.assertEqual([os.path.basename(f) for f in files], ["ok.txt"])
        self.assertIn("Skipped 1 subfolders", out)
        self.assertIn("a#b.txt", out)
        self.assertIn("a[1].txt", out)
        self.assertIn("big.bin", out)

    def test_no_warning_when_nothing_skipped(self):
        make("p/ok.txt")
        _, out = quiet(githost.collect, ["p/*"])
        self.assertEqual(out, "")

    def test_same_file_twice_counts_once(self):
        make("p/a.txt")
        files, _ = quiet(githost.collect, ["p/*", "p/a.txt"])
        self.assertEqual(len(files), 1)

    def test_same_github_name_stops(self):
        make("x/my file.txt"); make("y/my(file.txt")
        with self.assertRaisesRegex(githost.Stop, "same name on GitHub"):
            quiet(githost.collect, ["x/*", "y/*"])

    def test_missing_file_and_empty_pattern_stop(self):
        with self.assertRaisesRegex(githost.Stop, "Not found: nope.txt"):
            githost.collect(["nope.txt"])
        with self.assertRaisesRegex(githost.Stop, "No files match"):
            githost.collect(["nothing/*"])


class PartsTest(unittest.TestCase):
    def test_find_parts(self):
        tags = ["v1.0", "v1.0-part2", "v1.0-part3", "v1.01", "v1.0-partX", "v1.0-part1", "other"]
        parts = githost.find_parts([{"tag_name": t} for t in tags], "v1.0")
        self.assertEqual({n: r["tag_name"] for n, r in parts.items()},
                         {1: "v1.0", 2: "v1.0-part2", 3: "v1.0-part3"})

    def test_part_tag(self):
        self.assertEqual(githost.part_tag("v1.0", 1), "v1.0")
        self.assertEqual(githost.part_tag("v1.0", 2), "v1.0-part2")


class PlanTest(unittest.TestCase):
    def sizes(self, plan):
        return [(n, len(files)) for n, files in plan]

    def test_split_2350_new_files(self):
        plan, skipped = githost.plan_upload([f"f{i}" for i in range(2350)], {})
        self.assertEqual(self.sizes(plan), [(1, 1000), (2, 1000), (3, 350)])
        self.assertEqual(skipped, [])

    def test_fills_existing_release_first(self):
        parts = {1: [f"old{i}" for i in range(990)]}
        plan, _ = githost.plan_upload([f"new{i}" for i in range(25)], parts)
        self.assertEqual(self.sizes(plan), [(1, 10), (2, 15)])

    def test_full_first_part_goes_to_next(self):
        parts = {1: [f"a{i}" for i in range(1000)], 2: ["b0", "b1"]}
        plan, _ = githost.plan_upload(["n1", "n2", "n3"], parts)
        self.assertEqual(self.sizes(plan), [(2, 3)])

    def test_skips_files_already_uploaded_under_github_name(self):
        plan, skipped = githost.plan_upload([os.path.join("x", "my file.txt"), os.path.join("x", "b.txt")],
                                            {1: ["my.file.txt"]})
        self.assertEqual(skipped, [os.path.join("x", "my file.txt")])
        self.assertEqual(plan, [(1, [os.path.join("x", "b.txt")])])


class FakeGh:
    """Records gh calls; answers 'api' with the given releases."""
    def __init__(self, releases=(), fail_on_upload=None):
        self.releases, self.calls, self.uploads, self.fail_on_upload = list(releases), [], 0, fail_on_upload

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == "api":
            return "\n".join(json.dumps(r) for r in self.releases)
        if args[:2] == ("release", "upload"):
            self.uploads += 1
            if self.uploads == self.fail_on_upload:
                raise githost.Stop("HTTP 403: secondary rate limit")
        return ""


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        for i in range(250):
            make(f"photos/p{i:03d}.jpg")
        self.saved = githost.gh, githost.ensure_login
        githost.ensure_login = lambda: None

    def tearDown(self):
        githost.gh, githost.ensure_login = self.saved
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_upload(self, fake):
        githost.gh = fake
        return quiet(githost.upload, "me/repo", "v1.0", ["photos/*"])[1]

    def test_new_release_groups_of_100(self):
        fake = FakeGh()
        out = self.run_upload(fake)
        creates = [c for c in fake.calls if c[:2] == ("release", "create")]
        uploads = [c for c in fake.calls if c[:2] == ("release", "upload")]
        self.assertEqual([c[2] for c in creates], ["v1.0"])
        self.assertEqual(creates[0][creates[0].index("--notes") + 1], "v1.0")
        self.assertEqual([len(c) - c.index("--") - 1 for c in uploads], [100, 100, 50])
        self.assertTrue(all(c[2] == "v1.0" for c in uploads))
        self.assertIn("Done: 250 uploaded, 0 skipped", out)

    def test_existing_full_release_creates_part2_only(self):
        full = {"id": 1, "tag_name": "v1.0", "assets": [{"name": f"o{i}", "size": 1} for i in range(1000)]}
        fake = FakeGh([full])
        self.run_upload(fake)
        creates = [c for c in fake.calls if c[:2] == ("release", "create")]
        self.assertEqual([c[2] for c in creates], ["v1.0-part2"])
        self.assertEqual(creates[0][creates[0].index("--notes") + 1], "v1.0-part2")

    def test_skips_already_uploaded_and_warns(self):
        rel = {"id": 1, "tag_name": "v1.0", "assets": [{"name": f"p{i:03d}.jpg", "size": 1} for i in range(150)]}
        fake = FakeGh([rel])
        out = self.run_upload(fake)
        uploads = [c for c in fake.calls if c[:2] == ("release", "upload")]
        self.assertEqual([len(c) - c.index("--") - 1 for c in uploads], [100])
        self.assertIn("Skipped 150 files already in v1.0", out)
        self.assertNotIn(("release", "create"), [c[:2] for c in fake.calls])

    def test_failure_stops_with_rerun_hint(self):
        fake = FakeGh(fail_on_upload=2)
        with self.assertRaisesRegex(githost.Stop, "(?s)rate limit.*Run the same command again"):
            self.run_upload(fake)
        self.assertEqual(fake.uploads, 2)


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        make("src/a.txt", b"A"); make("src/b.txt", b"B"); make("src/c.txt", b"C")
        self.saved = githost.gh, githost.ensure_login, githost.public_releases
        githost.ensure_login = lambda: None

    def tearDown(self):
        githost.gh, githost.ensure_login, githost.public_releases = self.saved
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def asset(self, name):
        return {"name": name, "size": 1, "browser_download_url": pathlib.Path(os.path.abspath(f"src/{name}")).as_uri()}

    def test_public_merges_parts_into_one_folder(self):
        githost.public_releases = lambda repo, tag: [
            {"tag_name": "v1.0", "assets": [self.asset("a.txt"), self.asset("b.txt")]},
            {"tag_name": "v1.0-part2", "assets": [self.asset("c.txt")]},
        ]
        _, out = quiet(githost.download, "me/repo", "v1.0")
        self.assertEqual(sorted(os.listdir("v1.0")), ["a.txt", "b.txt", "c.txt"])
        self.assertIn("Done: 3 downloaded, 0 skipped", out)

    def test_skips_existing_but_not_half_files(self):
        githost.public_releases = lambda repo, tag: [
            {"tag_name": "v1.0", "assets": [self.asset("a.txt"), self.asset("b.txt")]}]
        make("v1.0/a.txt", b"old")
        make("v1.0/b.txt" + githost.TMP_SUFFIX, b"half")
        _, out = quiet(githost.download, "me/repo", "v1.0")
        with open("v1.0/a.txt", "rb") as f:
            self.assertEqual(f.read(), b"old")
        with open("v1.0/b.txt", "rb") as f:
            self.assertEqual(f.read(), b"B")
        self.assertEqual(sorted(os.listdir("v1.0")), ["a.txt", "b.txt"])
        self.assertIn("Skipped 1 files already in v1.0", out)

    def test_falls_back_to_gh(self):
        githost.public_releases = lambda repo, tag: None
        rels = [{"id": 1, "tag_name": "v1.0", "assets": [{"name": "a.txt", "size": 1}]},
                {"id": 2, "tag_name": "v1.0-part2", "assets": [{"name": "c.txt", "size": 1}]}]
        calls = []

        def fake(*args):
            calls.append(args)
            if args[0] == "api":
                return "\n".join(json.dumps(r) for r in rels)
            make(args[args.index("-O") + 1], args[args.index("-p") + 1].encode())
            return ""
        githost.gh = fake
        quiet(githost.download, "me/repo", "v1.0", "dest")
        self.assertEqual(sorted(os.listdir("dest")), ["a.txt", "c.txt"])
        self.assertEqual([c[2] for c in calls if c[:2] == ("release", "download")], ["v1.0", "v1.0-part2"])

    def test_not_found(self):
        githost.public_releases = lambda repo, tag: None
        githost.gh = lambda *a: ""
        with self.assertRaisesRegex(githost.Stop, "Release v9 not found in me/repo"):
            githost.download("me/repo", "v9")


class MainTest(unittest.TestCase):
    def test_usage_on_bad_args(self):
        code, out = quiet(githost.main, [])
        self.assertEqual(code, 1)
        self.assertIn("Usage", out)

    def test_stop_prints_message(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = githost.main(["upload", "me/repo", "v1.0", "nope.txt"])
        self.assertEqual(code, 1)
        self.assertIn("Not found: nope.txt", err.getvalue())


if __name__ == "__main__":
    unittest.main()
