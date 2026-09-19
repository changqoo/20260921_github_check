import os
import re
import subprocess
import tempfile
from pathlib import Path


class GuardError(RuntimeError):
    pass


def git(repo, *args, allow=(0,), data=None, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")
    env.update(env_extra or {})
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.quotePath=false",
         "-c", "gc.auto=0", "-C", str(repo), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, timeout=120)
    if result.returncode not in allow:
        raise GuardError(f"git {args[0]} failed ({result.returncode}): " +
                         result.stderr.decode("utf-8", "replace")[:1500])
    return result


def resolve(repo, ref):
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").stdout.decode().strip()


def ancestor(repo, older, newer):
    return git(repo, "merge-base", "--is-ancestor", older, newer, allow=(0, 1)).returncode == 0


class ObjectRepo:
    """Fresh bare repository: no PR checkout, hooks, filters or project commands."""
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prguard-")
        self.path = Path(self.temp.name)
        git(self.path, "init", "--bare", "--object-format=sha1", ".")
        return self.path

    def __exit__(self, *args):
        self.temp.cleanup()


def import_objects(destination, source, shas):
    git(destination, "-c", "protocol.file.allow=always", "fetch", "--no-tags",
        "--no-write-fetch-head", str(Path(source).resolve()), *sorted(set(shas)))


def merge(repo, base, head, origin=None, favor_base=False):
    args = ["merge-tree", "--write-tree", "--name-only", "-z", "--no-messages"]
    if origin:
        args.append("--merge-base=" + origin)
    if favor_base:
        args.append("-Xours")
    p = git(repo, *args, base, head, allow=(0, 1))
    fields = p.stdout.split(b"\0")
    tree = fields[0].decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise GuardError("Unsupported Git merge-tree output; install Git 2.50 or later")
    conflicts = []
    for field in fields[1:]:
        if not field:
            break
        conflicts.append(field.decode("utf-8", "replace"))
    return {"tree": tree, "conflicts": conflicts, "clean": p.returncode == 0}


def paths(repo, old, new):
    return [p.decode("utf-8", "replace") for p in
            git(repo, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", old, new).stdout.split(b"\0") if p]


def patch(repo, old, new):
    return git(repo, "diff", "--no-ext-diff", "--no-textconv", "--binary", "--full-index", old, new).stdout
