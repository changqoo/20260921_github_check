import argparse
import hashlib
import json
import sys
from pathlib import Path

from .core import analyze, register
from .gitops import GuardError, git, import_objects, resolve
from .llm import explain
from .report import write_report


def run_check(args):
    config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
    result, candidate, excluded = analyze(args.repo, args.base, args.head, args.baseline,
                                           args.repository, args.branch, args.target)
    if args.llm:
        try:
            result["llm"] = explain(result, config)
        except Exception as exc:
            result["llm"] = {"status": "unavailable", "error": str(exc)[:400]}
    write_report(args.out, result, candidate, excluded)
    print(f"{result['status']}: {Path(args.out).resolve() / 'report.html'}")
    return 0 if result["status"] == "PASS" else 2


def prepare(args):
    report = json.loads((Path(args.report) / "report.json").read_text(encoding="utf-8"))
    if not report["candidate_available"]:
        raise GuardError("No candidate is available")
    candidate = (Path(args.report) / "candidate.patch").read_bytes()
    if hashlib.sha256(candidate).hexdigest() != report["candidate_patch_sha256"]:
        raise GuardError("Candidate patch checksum mismatch")
    if resolve(args.repo, args.base) != report["base_sha"]:
        raise GuardError("Base has moved. Re-run check before preparing a candidate")
    if resolve(args.repo, args.head) != report["head_sha"]:
        raise GuardError("Head has moved. Re-run check before preparing a candidate")
    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=False)
    git(dest, "init", ".")
    import_objects(dest, args.repo, [report["base_sha"]])
    git(dest, "switch", "-c", "integrity-candidate", report["base_sha"])
    if candidate:
        git(dest, "apply", "--check", "--index", "-", data=candidate)
        git(dest, "apply", "--index", "-", data=candidate)
    tree = git(dest, "write-tree").stdout.decode().strip()
    if tree != report["candidate_tree"]:
        raise GuardError("Applied tree differs from verified candidate")
    print(f"Candidate applied and staged in {dest}. Review excluded changes and rerun dev/qa tests before committing.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Local Git + Gemma 3 PR integrity guard")
    sub = p.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="Register an immutable branch-start baseline")
    reg.add_argument("--repo", default=".")
    reg.add_argument("--main", default="origin/main")
    reg.add_argument("--head", default="HEAD")
    reg.add_argument("--repository", required=True)
    reg.add_argument("--branch", required=True)
    reg.add_argument("--owner", action="append", required=True)
    reg.add_argument("--registry", required=True)
    check = sub.add_parser("check")
    check.add_argument("--repo", default=".")
    check.add_argument("--base", default="origin/main")
    check.add_argument("--head", default="HEAD")
    check.add_argument("--baseline", required=True)
    check.add_argument("--repository", required=True)
    check.add_argument("--branch", required=True)
    check.add_argument("--target", default="main")
    check.add_argument("--out", required=True)
    check.add_argument("--llm", action="store_true")
    check.add_argument("--config")
    prep = sub.add_parser("prepare", help="Automatically apply candidate to a NEW isolated working directory")
    prep.add_argument("--repo", default=".")
    prep.add_argument("--base", default="origin/main")
    prep.add_argument("--head", default="HEAD")
    prep.add_argument("--report", required=True)
    prep.add_argument("--dest", required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "register":
            print(register(args.repo, args.main, args.head, args.repository, args.branch, args.owner, args.registry))
            return 0
        return run_check(args) if args.command == "check" else prepare(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
