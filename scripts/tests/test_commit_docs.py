"""Exercise actual Git indexes/history; no third-party test dependencies."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / "check_commit_docs.py"


class CommitDocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        # A pre-commit test may inherit GIT_INDEX_FILE/GIT_DIR from its caller.
        for key in tuple(self.env):
            if key.startswith("GIT_"):
                self.env.pop(key)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(self.root / "no-hooks"))

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, env=self.env, text=True, stderr=subprocess.PIPE).strip()

    def write(self, name, text="Record evidence and next steps.\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def pair(self, topic):
        filename = f"20260929-{topic}.md"
        for directory in ("PR_context", "audits"):
            self.write(f"markdowns/{directory}/{filename}")
        self.git("add", ".")

    def commit(self, topic):
        self.git("commit", "--allow-empty", "-m", topic)
        return self.git("rev-parse", "HEAD")

    def check(self, *args, success=True):
        result = subprocess.run([sys.executable, str(CHECKER), *args], cwd=self.root, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)

    def test_initial_commit_requires_both_records(self):
        self.write("app.txt", "new app")
        self.git("add", ".")
        self.check("--staged", success=False)
        self.write("markdowns/PR_context/20260929-initial.md")
        self.git("add", ".")
        self.check("--staged", success=False)
        self.pair("initial")
        self.check("--staged")
        self.commit("initial")
        self.check("--head", "HEAD")

    def test_mismatched_names_fail(self):
        self.write("markdowns/PR_context/20260929-context.md")
        self.write("markdowns/audits/20260929-audit.md")
        self.git("add", ".")
        self.check("--staged", success=False)

    def test_empty_record_fails(self):
        self.pair("empty")
        self.write("markdowns/audits/20260929-empty.md", " \n")
        self.git("add", ".")
        self.check("--staged", success=False)

    def test_symlinks_do_not_count_as_records(self):
        self.pair("link")
        path = "markdowns/audits/20260929-link.md"
        blob = self.git("rev-parse", f":{path}")
        self.git("update-index", "--cacheinfo", f"120000,{blob},{path}")
        self.check("--staged", success=False)

    def test_checks_index_not_working_tree(self):
        self.pair("index")
        self.write("markdowns/audits/20260929-index.md", "")
        self.check("--staged")
        self.git("add", ".")
        self.write("markdowns/audits/20260929-index.md")
        self.check("--staged", success=False)

    def test_modified_old_records_do_not_count(self):
        self.pair("old")
        self.commit("initial")
        for folder in ("PR_context", "audits"):
            self.write(f"markdowns/{folder}/20260929-old.md", "Modified old record")
        self.git("add", ".")
        self.check("--staged", success=False)
        self.pair("new")
        self.check("--staged")

    def test_deleted_names_cannot_be_reused(self):
        self.pair("old")
        self.commit("initial")
        self.git("rm", "-r", "markdowns")
        self.pair("deletion")
        self.commit("remove old records")
        self.pair("old")
        self.check("--staged", success=False)

    def test_range_checks_middle_commits(self):
        self.pair("first")
        base = self.commit("first")
        self.commit("missing records")
        self.pair("last")
        self.commit("last")
        self.check("--base", base, "--head", "HEAD", success=False)
        self.check("--base", "HEAD~1", "--head", "HEAD")

    def test_merge_cannot_reuse_branch_pair(self):
        self.pair("initial")
        self.commit("initial")
        self.git("checkout", "-b", "feature")
        self.pair("feature")
        self.commit("feature")
        self.git("checkout", "main")
        self.pair("main")
        self.commit("main")
        self.git("merge", "--no-ff", "--no-commit", "feature")
        self.check("--staged", success=False)
        self.commit("undocumented merge")
        self.check("--base", "HEAD~1", "--head", "HEAD", success=False)

    def test_merge_accepts_own_new_pair(self):
        self.pair("initial")
        self.commit("initial")
        self.git("checkout", "-b", "feature")
        self.pair("feature")
        self.commit("feature")
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "--no-commit", "feature")
        self.pair("merge")
        self.check("--staged")
        self.commit("merge")
        self.check("--head", "HEAD")

    def test_github_push_and_pull_request_ranges(self):
        self.pair("initial")
        base = self.commit("initial")
        self.pair("next")
        head = self.commit("next")
        event = self.root / "event.json"
        for payload in ({"before": base, "after": head},
                        {"before": "0" * 40, "after": head},
                        {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}):
            event.write_text(json.dumps(payload), encoding="utf-8")
            self.check("--github-event", str(event))

    def test_installed_hooks_guard_commit_and_automatic_merge(self):
        for filename in ("pre-commit", "pre-merge-commit"):
            hook = self.root / ".githooks" / filename
            hook.parent.mkdir(exist_ok=True)
            shutil.copyfile(CHECKER.parents[1] / ".githooks" / filename, hook)
            hook.chmod(0o755)
        (self.root / "scripts").mkdir()
        shutil.copyfile(CHECKER, self.root / "scripts" / CHECKER.name)
        self.git("config", "core.hooksPath", ".githooks")
        self.git("add", ".")
        blocked = subprocess.run(["git", "commit", "-m", "missing records"], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(blocked.returncode, 0, blocked.stdout + blocked.stderr)
        self.assertIn("matching NEW", blocked.stderr)
        self.pair("initial")
        self.commit("initial")
        self.git("checkout", "-b", "feature")
        self.pair("feature")
        self.commit("feature")
        self.git("checkout", "main")
        merge = subprocess.run(["git", "merge", "--no-ff", "feature"], cwd=self.root, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(merge.returncode, 0, merge.stdout + merge.stderr)
        self.assertIn("new matching context/audit pair", merge.stderr)
        self.pair("merge")
        self.commit("documented merge")
        self.check("--head", "HEAD")


if __name__ == "__main__":
    unittest.main()
