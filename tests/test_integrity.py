import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock_patch

from prguard.__main__ import main
from prguard.core import analyze, register
from prguard.gitops import GuardError, git, resolve
from prguard.llm import explain
from prguard.report import markdown, write_report


class History(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main", ".")
        git(self.repo, "config", "user.name", "Developer B")
        git(self.repo, "config", "user.email", "b@example.test")
        self.original = "".join(f"line {i}\n" for i in range(30))
        self.write("app.txt", self.original)
        self.commit("Initial")
        self.origin = resolve(self.repo, "HEAD")
        git(self.repo, "switch", "-c", "feature/b")
        self.baseline = register(self.repo, "main", "HEAD", "demo/repo", "feature/b",
                                 ["b@example.test"], self.root / "registry")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="")

    def commit(self, msg, author=None):
        git(self.repo, "add", "-A")
        args = ["commit", "-m", msg]
        if author:
            args += ["--author", author]
        git(self.repo, *args)
        return resolve(self.repo, "HEAD")

    def main_change(self, content=None):
        git(self.repo, "switch", "main")
        self.write("app.txt", content or self.original.replace("line 3\n", "A changed 3\n"))
        self.commit("A changed main", "Developer A <a@example.test>")
        git(self.repo, "switch", "feature/b")

    def check(self):
        return analyze(self.repo, "main", "feature/b", self.baseline, "demo/repo", "feature/b")

    def test_old_branch_preserves_other_developer_same_file(self):
        self.main_change()
        self.write("app.txt", self.original.replace("line 25\n", "B changed 25\n"))
        self.commit("B change")
        before = git(self.repo, "status", "--porcelain").stdout
        result, candidate, _ = self.check()
        self.assertEqual(result["status"], "PASS")
        self.assertNotIn(b"-A changed 3", candidate)
        self.assertIn(b"+B changed 25", candidate)
        self.assertEqual(before, git(self.repo, "status", "--porcelain").stdout)
        self.assertEqual(resolve(self.repo, "HEAD"), result["head_sha"])

    def test_direct_conflict_excludes_only_conflicting_hunk(self):
        self.main_change()
        self.write("app.txt", self.original.replace("line 3\n", "B changed 3\n").replace("line 25\n", "B changed 25\n"))
        self.commit("B conflict and independent change")
        result, candidate, _ = self.check()
        self.assertEqual(result["status"], "BLOCK")
        self.assertIn("MERGE_CONFLICT", [f["code"] for f in result["findings"]])
        self.assertTrue(result["candidate_available"])
        self.assertNotIn(b"+B changed 3\n", candidate)
        self.assertIn(b"+B changed 25", candidate)
        self.assertNotIn(b"<<<<<<<", candidate)

    def test_silent_revert_after_sync_is_blocked(self):
        self.main_change()
        git(self.repo, "merge", "main", "--no-edit")
        self.write("app.txt", self.original.replace("line 25\n", "B changed 25\n"))
        self.commit("Accidental restoration of old file")
        result, candidate, excluded = self.check()
        self.assertTrue(result["actual_merge"]["clean"])
        self.assertIn("BASE_CHANGE_LOSS", [f["code"] for f in result["findings"]])
        self.assertIn(b"-A changed 3", excluded)
        self.assertNotIn(b"-A changed 3", candidate)
        self.assertIn(b"+B changed 25", candidate)

    def test_partial_rewrite_after_sync_is_blocked(self):
        self.main_change()
        git(self.repo, "merge", "main", "--no-edit")
        self.write("app.txt", self.original.replace("line 3\n", "B overwrite\n"))
        self.commit("B overwrite A")
        result, _, _ = self.check()
        self.assertEqual(result["status"], "BLOCK")

    def test_foreign_commits_block_candidate(self):
        self.write("foreign.txt", "from qa")
        self.commit("Foreign code", "Developer C <c@example.test>")
        result, candidate, _ = self.check()
        self.assertIn("FOREIGN_COMMITS", [f["code"] for f in result["findings"]])
        self.assertIsNone(candidate)

    def test_dev_reverse_merge_blocked_even_same_author(self):
        git(self.repo, "switch", "-c", "dev", "main")
        self.write("dev-only.txt", "unreleased")
        self.commit("Dev work")
        git(self.repo, "switch", "feature/b")
        self.write("own.txt", "own")
        self.commit("Own")
        git(self.repo, "merge", "dev", "--no-edit")
        result, candidate, _ = self.check()
        self.assertIn("FOREIGN_MERGE", [f["code"] for f in result["findings"]])
        self.assertIsNone(candidate)

    def test_delete_modify_conflict_no_candidate(self):
        self.main_change()
        (self.repo / "app.txt").unlink()
        self.commit("Delete app")
        result, candidate, _ = self.check()
        self.assertIn("STRUCTURAL_CONFLICT", [f["code"] for f in result["findings"]])
        self.assertIsNone(candidate)

    def test_rename_and_independent_modification_preserved(self):
        self.main_change()
        git(self.repo, "mv", "app.txt", "renamed.txt")
        self.commit("Rename")
        result, candidate, _ = self.check()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["candidate_available"])

    def test_binary_conflict_keeps_base(self):
        self.write("img.bin", b"\0base")
        self.commit("Add B binary")
        git(self.repo, "switch", "main")
        self.write("img.bin", b"\0main")
        self.commit("Add A binary", "A <a@example.test>")
        git(self.repo, "switch", "feature/b")
        result, candidate, _ = self.check()
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(candidate, b"")

    def test_missing_baseline_fails_closed(self):
        result, candidate, _ = analyze(self.repo, "main", "HEAD", self.root / "missing", "demo/repo", "feature/b")
        self.assertEqual(result["status"], "BLOCK")
        self.assertIsNone(candidate)

    def test_baseline_cannot_be_overwritten(self):
        with self.assertRaises(FileExistsError):
            register(self.repo, "main", "HEAD", "demo/repo", "feature/b", ["b@example.test"], self.root / "registry")

    def test_baseline_identity_mismatch(self):
        with self.assertRaises(GuardError):
            analyze(self.repo, "main", "HEAD", self.baseline, "different/repo", "feature/b")

    def test_registration_after_development_rejected(self):
        self.write("other", "new")
        self.commit("Work")
        with self.assertRaises(GuardError):
            register(self.repo, "main", "HEAD", "demo/repo", "other", ["b@example.test"], self.root / "registry")

    def test_prepare_applies_verified_candidate(self):
        self.main_change()
        self.write("app.txt", self.original.replace("line 3\n", "B conflict\n").replace("line 25\n", "B independent\n"))
        self.commit("B")
        result, candidate, excluded = self.check()
        out = self.root / "reports"
        write_report(out, result, candidate, excluded)
        code = main(["prepare", "--repo", str(self.repo), "--base", "main", "--head", "feature/b",
                     "--report", str(out), "--dest", str(self.root / "repair")])
        self.assertEqual(code, 0)
        content = (self.root / "repair" / "app.txt").read_text()
        self.assertIn("A changed 3", content)
        self.assertIn("B independent", content)
        self.assertNotIn("B conflict", content)

    def test_stale_base_rejected_on_prepare(self):
        result, candidate, excluded = self.check()
        out = self.root / "reports"
        write_report(out, result, candidate, excluded)
        self.main_change()
        self.assertEqual(main(["prepare", "--repo", str(self.repo), "--base", "main", "--head", "feature/b",
                               "--report", str(out), "--dest", str(self.root / "repair")]), 3)
        self.assertFalse((self.root / "repair").exists())

    def test_stale_head_rejected_on_prepare(self):
        result, candidate, excluded = self.check()
        out = self.root / "reports"
        write_report(out, result, candidate, excluded)
        self.write("new.txt", "changed")
        self.commit("New head")
        self.assertEqual(main(["prepare", "--repo", str(self.repo), "--base", "main", "--head", "feature/b",
                               "--report", str(out), "--dest", str(self.root / "repair")]), 3)
        self.assertFalse((self.root / "repair").exists())

    def test_tampered_candidate_rejected(self):
        result, candidate, excluded = self.check()
        out = self.root / "reports"
        write_report(out, result, candidate, excluded)
        (out / "candidate.patch").write_bytes(b"tampered")
        self.assertEqual(main(["prepare", "--repo", str(self.repo), "--base", "main", "--head", "feature/b",
                               "--report", str(out), "--dest", str(self.root / "repair")]), 3)
        self.assertFalse((self.root / "repair").exists())

    def test_reports_escape_untrusted_text_and_reject_reuse(self):
        result, candidate, excluded = self.check()
        result["branch"] = '<script>alert("x")</script>'
        out = self.root / "reports"
        write_report(out, result, candidate, excluded)
        self.assertNotIn('<script>', (out / "report.html").read_text(encoding="utf-8"))
        self.assertNotIn('<script>', markdown(result))
        with self.assertRaises(FileExistsError):
            write_report(out, result, candidate, excluded)

    def test_llm_endpoint_not_allowlisted(self):
        result, _, _ = self.check()
        with self.assertRaises(GuardError):
            explain(result, {"ollama_url": "https://external.invalid"})

    def test_llm_outage_keeps_git_result(self):
        with mock_patch("prguard.__main__.explain", side_effect=TimeoutError("timeout")):
            out = self.root / "reports"
            code = main(["check", "--repo", str(self.repo), "--base", "main", "--head", "feature/b",
                         "--baseline", str(self.baseline), "--repository", "demo/repo", "--branch", "feature/b",
                         "--out", str(out), "--llm"])
        self.assertEqual(code, 0)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["llm"]["status"], "unavailable")
        self.assertEqual(report["status"], "PASS")

    def test_empty_pr(self):
        result, candidate, _ = self.check()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(candidate, b"")


if __name__ == "__main__":
    unittest.main()
