import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prguard.core import register
from prguard.github_runner import run_one
from prguard.gitops import GuardError, git, import_objects, resolve


class FakeGitHub:
    repository = "demo/repo"

    def __init__(self, repo, target="main", changed=False):
        self.repo = repo
        sha = resolve(repo, "HEAD")
        self.pr = {"number": 1, "state": "open", "base": {"ref": target, "sha": sha},
                   "head": {"ref": "feature/b", "sha": sha, "repo": {"full_name": self.repository}}}
        self.statuses = []
        self.calls = 0
        self.changed = changed

    def api(self, path):
        self.calls += 1
        value = copy.deepcopy(self.pr)
        if self.changed and self.calls > 1:
            value["base"]["sha"] = "1" * 40
        return value

    def fetch(self, repo, pr):
        import_objects(repo, self.repo, [pr["head"]["sha"]])
        for ref in ["target", "proposal"]:
            git(repo, "update-ref", "refs/heads/" + ref, pr["head"]["sha"])

    def status(self, sha, state, description):
        self.statuses.append(state)


class GitHubAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main", ".")
        git(self.repo, "config", "user.name", "B")
        git(self.repo, "config", "user.email", "b@example.test")
        git(self.repo, "commit", "--allow-empty", "-m", "Initial")
        register(self.repo, "main", "HEAD", "demo/repo", "feature/b", ["b@example.test"], self.root / "registry")
        self.config = {"targets": ["main", "qa", "dev"], "registry_dir": str(self.root / "registry"),
                       "reports_dir": str(self.root / "reports"), "llm_enabled": False}
        self.env = patch.dict(os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
                                          "GITHUB_STEP_SUMMARY": str(self.root / "summary.md")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_main_status_and_summary(self):
        api = FakeGitHub(self.repo)
        self.assertFalse(run_one(api, self.config, 1))
        self.assertEqual(api.statuses, ["pending", "success"])
        self.assertIn("PASS", (self.root / "summary.md").read_text(encoding="utf-8"))

    def test_qa_does_not_override_main_status(self):
        api = FakeGitHub(self.repo, target="qa")
        self.assertFalse(run_one(api, self.config, 1))
        self.assertEqual(api.statuses, [])
        self.assertTrue((self.root / "summary.md").is_file())

    def test_race_fails_closed(self):
        api = FakeGitHub(self.repo, changed=True)
        with self.assertRaises(GuardError):
            run_one(api, self.config, 1)
        self.assertEqual(api.statuses, ["pending", "error"])

    def test_missing_baseline_posts_failure(self):
        api = FakeGitHub(self.repo)
        api.pr["head"]["ref"] = "unregistered"
        self.assertTrue(run_one(api, self.config, 1))
        self.assertEqual(api.statuses, ["pending", "failure"])

    def test_fork_not_processed(self):
        api = FakeGitHub(self.repo)
        api.pr["head"]["repo"]["full_name"] = "external/repo"
        with self.assertRaises(GuardError):
            run_one(api, self.config, 1)
        self.assertEqual(api.statuses, ["pending", "error"])


if __name__ == "__main__":
    unittest.main()
