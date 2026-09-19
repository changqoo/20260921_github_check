import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .gitops import GuardError, ObjectRepo, ancestor, git, import_objects, merge, patch, paths, resolve


def baseline_key(repository, branch):
    return hashlib.sha256((repository + "\n" + branch).encode()).hexdigest() + ".json"


def register(repo, main, head, repository, branch, owners, registry):
    start = resolve(repo, head)
    if start != resolve(repo, main):
        raise GuardError("Register at branch creation: head must equal current main. Existing branches need an audited baseline; see docs/OPERATIONS.md")
    if not owners or not all("@" in e for e in owners):
        raise GuardError("At least one exact Git author email is required")
    record = {"version": 1, "repository": repository, "branch": branch,
              "start_sha": start, "owners": sorted(set(owners)),
              "registered_at": datetime.now(timezone.utc).isoformat()}
    directory = Path(registry)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / baseline_key(repository, branch)
    with target.open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return target


def analyze(repo, base, head, baseline, repository, branch, target="main", max_commits=500):
    base_sha, head_sha = resolve(repo, base), resolve(repo, head)
    result = {"version": 1, "repository": repository, "branch": branch, "target": target,
              "base_sha": base_sha, "head_sha": head_sha, "status": "PASS", "findings": [],
              "created_at": datetime.now(timezone.utc).isoformat(), "candidate_available": False,
              "llm": {"status": "disabled"}}

    def flag(code, message, files=None):
        result["status"] = "BLOCK"
        result["findings"].append({"code": code, "message": message, "files": files or []})

    if not baseline or not Path(baseline).is_file():
        flag("BASELINE_MISSING", "개발 시작 기준점이 등록되지 않아 변경 소유 범위를 확인할 수 없습니다.")
        return result, None, None
    record = json.loads(Path(baseline).read_text(encoding="utf-8"))
    if record.get("version") != 1 or record.get("repository") != repository or record.get("branch") != branch:
        raise GuardError("Baseline identity/version mismatch")
    owners = record.get("owners")
    if not isinstance(owners, list) or not owners or not all(isinstance(e, str) and "@" in e for e in owners):
        raise GuardError("Invalid baseline owners")
    origin = resolve(repo, record["start_sha"])
    result["origin_sha"] = origin
    result["owners"] = owners
    with ObjectRepo() as isolated:
        import_objects(isolated, repo, [base_sha, head_sha, origin])
        if not ancestor(isolated, origin, base_sha) or not ancestor(isolated, origin, head_sha):
            flag("BASELINE_NOT_ANCESTOR", "기준점이 대상/개발 브랜치의 공통 조상이 아닙니다. 재작성 이력을 확인하세요.")
            return result, None, None
        commits = git(isolated, "rev-list", "--reverse", head_sha, "^" + base_sha).stdout.decode().splitlines()
        result["commit_count"] = len(commits)
        if len(commits) > max_commits:
            flag("LIMIT_EXCEEDED", f"검사 한도 {max_commits} commits 초과")
            return result, None, None
        foreign = []
        merges = []
        for sha in commits:
            email = git(isolated, "show", "-s", "--format=%ae", sha).stdout.decode("utf-8", "replace").strip()
            if email.casefold() not in {o.casefold() for o in owners}:
                foreign.append({"sha": sha, "author": email})
            parents = git(isolated, "rev-list", "--parents", "-n", "1", sha).stdout.decode().split()[1:]
            # Permit syncing main into a feature, but not merging dev/qa/another feature.
            if len(parents) > 1 and any(not ancestor(isolated, p, base_sha) for p in parents[1:]):
                merges.append(sha)
        if foreign:
            flag("FOREIGN_COMMITS", "등록한 개발자 외의 커밋이 포함되어 있습니다. dev/qa 역병합 여부를 확인하세요.")
        if merges:
            flag("FOREIGN_MERGE", "대상 브랜치 외의 이력을 합친 merge commit이 있습니다.")
        result["foreign_commits"], result["foreign_merges"] = foreign, merges
        actual = merge(isolated, base_sha, head_sha)
        origin_merge = merge(isolated, base_sha, head_sha, origin=origin)
        protected = merge(isolated, base_sha, head_sha, origin=origin, favor_base=True)
        result["actual_merge"] = actual
        result["origin_conflicts"] = origin_merge["conflicts"]
        result["changed_files"] = paths(isolated, origin, head_sha)
        result["base_changed_files"] = paths(isolated, origin, base_sha)
        result["overlapping_files"] = sorted(set(result["changed_files"]) & set(result["base_changed_files"]))
        if not actual["clean"]:
            flag("MERGE_CONFLICT", "실제 PR 병합에 충돌이 있습니다.", actual["conflicts"])
        if not origin_merge["clean"]:
            flag("OVERLAPPING_EDITS", "개발 시작 후 양쪽에서 변경한 구간이 겹칩니다. 후보에서는 대상 브랜치를 우선합니다.", origin_merge["conflicts"])
        if not protected["clean"]:
            flag("STRUCTURAL_CONFLICT", "삭제/수정·이름변경 등의 충돌을 안전하게 해소할 수 없어 후보를 생성하지 않았습니다.", protected["conflicts"])
        suppressed = None
        if actual["clean"] and protected["clean"] and actual["tree"] != protected["tree"]:
            affected = paths(isolated, protected["tree"], actual["tree"])
            flag("BASE_CHANGE_LOSS", "일반 병합 결과가 기존 변경 보존 후보와 다릅니다. 타인 변경의 원복 또는 의도적인 재수정인지 확인해야 합니다.", affected)
            suppressed = patch(isolated, protected["tree"], actual["tree"])
        candidate = None
        if protected["clean"] and not foreign and not merges:
            candidate = patch(isolated, base_sha, protected["tree"])
            result["candidate_available"] = True
            result["candidate_tree"] = protected["tree"]
            result["candidate_files"] = paths(isolated, base_sha, protected["tree"])
            result["candidate_patch_sha256"] = hashlib.sha256(candidate).hexdigest()
        if not result["findings"]:
            result["findings"].append({"code": "NO_DETECTED_RISK", "message": "검사한 이력에서 충돌·기존 변경 손실 징후가 발견되지 않았습니다. 기능 테스트는 별도입니다.", "files": []})
        return result, candidate, suppressed
