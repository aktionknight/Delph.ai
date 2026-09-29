"""Require a fresh context/audit record pair in the index or every selected commit.

Uses only Python's standard library and Git. Inspect staged blobs, never working
tree copies. Merge commits need their own pair, absent from all parent histories.
This checks record presence and uniqueness, not the quality of a security review.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DIRECTORIES = ("markdowns/PR_context", "markdowns/audits")
FILENAME = re.compile(r"^\d{8}(?:T\d{6}Z)?-[a-zA-Z0-9][a-zA-Z0-9._-]*\.md$")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], encoding="utf-8", errors="strict").strip()


def resolve(ref: str) -> str:
    return git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")


def names(output: str) -> set[str]:
    return set(filter(None, output.split("\0")))


def new_paths(revision: str | None, parents: list[str]) -> set[str]:
    """Intersect additions against every parent to reject inherited merge records."""
    additions = []
    for parent in parents or [None]:
        if revision is None:
            args = ["diff", "--cached"] + ([parent] if parent else [])
        else:
            args = ["diff-tree", "--root", "-r", "--no-commit-id"]
            args += [parent, revision] if parent else [revision]
        additions.append(names(git(*args, "--find-renames", "--diff-filter=A", "--name-only", "-z", "--", *DIRECTORIES)))
    return set.intersection(*additions)


def previous_paths(parents: list[str]) -> set[str]:
    if not parents:
        return set()
    # --full-history includes deleted records, so deleting and later reusing a
    # filename cannot substitute for a unique record. -m inspects merge changes.
    output = git("log", "--full-history", "-m", "--format=", "--name-only", "-z", *parents, "--", *DIRECTORIES)
    return {path.strip("\n") for path in output.split("\0") if path.strip("\n")}


def validate(revision: str | None, parents: list[str]) -> list[str]:
    added = new_paths(revision, parents)
    seen = previous_paths(parents)
    records: list[set[str]] = []
    for directory in DIRECTORIES:
        records.append({path.removeprefix(directory + "/") for path in added
                        if path.startswith(directory + "/") and FILENAME.fullmatch(path.removeprefix(directory + "/"))})
    paired = records[0] & records[1]
    errors = []
    for filename in sorted(paired):
        paths = [f"{directory}/{filename}" for directory in DIRECTORIES]
        if any(path in seen for path in paths):
            errors.append(f"Record filename was used previously: {filename}")
            continue
        modes = [git("ls-tree", revision, "--", path).split()[0] if revision
                 else git("ls-files", "--stage", "--", path).split()[0] for path in paths]
        if any(mode not in {"100644", "100755"} for mode in modes):
            errors.append(f"Records must be regular Markdown files, not symlinks: {filename}")
            continue
        if any(not git("show", f"{revision or ''}:{path}").strip("\ufeff \t\r\n") for path in paths):
            errors.append(f"Record pair contains an empty file: {filename}")
            continue
        return []
    errors.append("Add and stage matching NEW, nonempty <YYYYMMDD>-<topic>.md files in markdowns/PR_context/ and markdowns/audits/.")
    return errors


def staged_parents() -> list[str]:
    result = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
    parents = [result.stdout.strip()] if result.returncode == 0 else []
    merge_head = Path(git("rev-parse", "--git-path", "MERGE_HEAD"))
    if merge_head.exists():
        parents.extend(merge_head.read_text(encoding="ascii").splitlines())
    return parents


def event_range(path: Path) -> tuple[str | None, str]:
    event = json.loads(path.read_text(encoding="utf-8"))
    if "pull_request" in event:
        request = event["pull_request"]
        return request["base"]["sha"], request["head"]["sha"]
    before, after = event.get("before"), event.get("after")
    if not after or set(after) == {"0"}:
        raise ValueError("Event does not identify a live pushed commit.")
    return (None if not before or set(before) == {"0"} else before), after


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--github-event", type=Path)
    parser.add_argument("--base", help="Exclusive ancestor/range base; omit to check all history")
    parser.add_argument("--head", default="HEAD", help="Inclusive range head")
    args = parser.parse_args()
    try:
        if args.staged:
            checks = [("staged commit", validate(None, staged_parents()))]
        else:
            base, head = event_range(args.github_event) if args.github_event else (args.base, args.head)
            head = resolve(head)
            revisions = [f"{resolve(base)}..{head}"] if base else [head]
            commits = git("rev-list", "--reverse", "--topo-order", *revisions).splitlines()
            checks = []
            for commit in commits:
                parents = git("rev-list", "--parents", "-n", "1", commit).split()[1:]
                checks.append((commit, validate(commit, parents)))
        failed = False
        for label, errors in checks:
            for error in errors:
                print(f"{label}: {error}", file=sys.stderr)
                failed = True
        if failed:
            return 1
        print(f"Commit documentation verified ({len(checks)} commit(s)).")
        return 0
    except (subprocess.CalledProcessError, ValueError, OSError, KeyError) as exc:
        print(f"Unable to check commit documentation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
