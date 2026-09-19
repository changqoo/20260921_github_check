"""Run from a trusted installation on an internal, dedicated self-hosted runner.

No PR checkout. No PR Python, workflows, hooks, filters, builds or tests executed.
GITHUB_TOKEN is used only against the configured GitHub host.
"""
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from .core import analyze, baseline_key
from .gitops import GuardError, ObjectRepo, git, resolve
from .llm import NoRedirect, explain
from .report import write_report


class GitHub:
    def __init__(self, config):
        self.server = os.environ["GITHUB_SERVER_URL"].rstrip("/")
        self.api_url = os.environ["GITHUB_API_URL"].rstrip("/")
        if self.server != config["github_server_url"] or self.api_url != config["github_api_url"]:
            raise GuardError("GitHub server/API does not match trusted config")
        if urllib.parse.urlsplit(self.server).scheme != "https" or urllib.parse.urlsplit(self.api_url).scheme != "https":
            raise GuardError("Use HTTPS and install your internal CA certificate")
        self.repository = os.environ["GITHUB_REPOSITORY"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise GuardError("Invalid repository name")
        if self.repository not in config["allowed_repositories"]:
            raise GuardError("Repository not allowed on this runner")
        self.token = os.environ["GITHUB_TOKEN"]
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def api(self, path, body=None):
        req = urllib.request.Request(self.api_url + "/repos/" + self.repository + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json", "User-Agent": "pr-integrity-agent"})
        with self.opener.open(req, timeout=30) as response:
            return json.load(response)

    def status(self, sha, state, description):
        self.api("/statuses/" + sha, {"state": state, "context": "pr-integrity",
            "description": description[:140],
            "target_url": self.server + "/" + self.repository + "/actions/runs/" + os.environ["GITHUB_RUN_ID"]})

    def fetch(self, repo, pr):
        auth = base64.b64encode(("x-access-token:" + self.token).encode()).decode()
        extra = {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "http.extraHeader",
                 "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic " + auth,
                 "GIT_CONFIG_KEY_1": "http.followRedirects", "GIT_CONFIG_VALUE_1": "false"}
        git(repo, "fetch", "--no-tags", self.server + "/" + self.repository + ".git",
            f"+refs/heads/{pr['base']['ref']}:refs/heads/target",
            f"+refs/pull/{pr['number']}/head:refs/heads/proposal", env_extra=extra)
        if resolve(repo, "target") != pr["base"]["sha"] or resolve(repo, "proposal") != pr["head"]["sha"]:
            raise GuardError("PR/base changed during fetch; rerun this check")


def run_one(api, config, number):
    pr = api.api(f"/pulls/{int(number)}")
    if pr["state"] != "open" or pr["base"]["ref"] not in config["targets"]:
        return False
    # Commit statuses are SHA-scoped, not PR/base-scoped: only MAIN receives a gate.
    gate = pr["base"]["ref"] == "main"
    sha = pr["head"]["sha"]
    if gate:
        api.status(sha, "pending", "Inspecting current main + PR snapshot")
    try:
        if pr["head"]["repo"] is None or pr["head"]["repo"]["full_name"] != api.repository:
            raise GuardError("Fork PRs are not supported by the internal baseline registry")
        with ObjectRepo() as repo:
            api.fetch(repo, pr)
            baseline = Path(config["registry_dir"]) / baseline_key(api.repository, pr["head"]["ref"])
            result, candidate, excluded = analyze(repo, "target", "proposal", baseline,
                api.repository, pr["head"]["ref"], pr["base"]["ref"])
            if config.get("llm_enabled", True):
                try:
                    result["llm"] = explain(result, config)
                except Exception as exc:
                    result["llm"] = {"status": "unavailable", "error": str(exc)[:400]}
            latest = api.api(f"/pulls/{int(number)}")
            if latest["head"]["sha"] != sha or latest["base"]["sha"] != result["base_sha"] or latest["base"]["ref"] != pr["base"]["ref"]:
                raise GuardError("Snapshot changed during analysis; rerun required")
            directory = Path(config["reports_dir"]) / os.environ["GITHUB_RUN_ID"] / os.environ.get("GITHUB_RUN_ATTEMPT", "1") / str(number)
            md = write_report(directory, result, candidate, excluded)
            summary = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary, "a", encoding="utf-8") as f:
                    f.write(md[:150000] + "\n")
            print(f"PR #{number}: {result['status']}; report directory: {directory}")
            if gate:
                api.status(sha, "success" if result["status"] == "PASS" else "failure",
                           result["status"] + " base=" + result["base_sha"][:12])
            return gate and result["status"] != "PASS"
    except Exception as exc:
        if gate:
            api.status(sha, "error", "Inspection error: see workflow logs; merge must remain blocked")
        raise exc


def main():
    config = json.loads(Path(os.environ["PRGUARD_CONFIG"]).read_text(encoding="utf-8"))
    api = GitHub(config)
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    if "pull_request" in event:
        numbers = [event["pull_request"]["number"]]
    else:
        numbers = []
        page = 1
        while True:
            prs = api.api(f"/pulls?state=open&per_page=100&page={page}")
            numbers.extend(p["number"] for p in prs if p["base"]["ref"] in config["targets"])
            if len(prs) < 100:
                break
            page += 1
    blocked = False
    for number in numbers:
        try:
            blocked = run_one(api, config, number) or blocked
        except Exception as exc:
            print(f"PR #{number}: ERROR {exc}", file=sys.stderr)
            blocked = True
    return 2 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
