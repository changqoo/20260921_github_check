"""Generate a synthetic two-developer rollback example, without company code."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prguard.core import analyze, register
from prguard.gitops import git
from prguard.report import write_report


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "demo-output").resolve()
    root.mkdir(parents=True, exist_ok=False)
    repo = root / "repository"
    repo.mkdir()
    git(repo, "init", "-b", "main", ".")
    git(repo, "config", "user.name", "Developer B")
    git(repo, "config", "user.email", "b@example.test")
    original = "".join(f"setting_{i} = original\n" for i in range(30))
    file = repo / "settings.txt"

    def save(text, message):
        file.write_text(text, encoding="utf-8", newline="")
        git(repo, "add", "settings.txt")
        git(repo, "commit", "-m", message)

    save(original, "Initial main")
    git(repo, "switch", "-c", "feature/b")
    baseline = register(repo, "main", "HEAD", "demo/repo", "feature/b", ["b@example.test"], root / "registry")
    git(repo, "switch", "main")
    save(original.replace("setting_3 = original", "setting_3 = developer_A"), "A merged into main")
    git(repo, "switch", "feature/b")
    git(repo, "merge", "main", "--no-edit")
    save(original.replace("setting_25 = original", "setting_25 = developer_B"), "B accidentally restores old A section")
    result, candidate, excluded = analyze(repo, "main", "HEAD", baseline, "demo/repo", "feature/b")
    write_report(root / "report", result, candidate, excluded)
    print(f"Expected BLOCK: {root / 'report' / 'report.html'}")


if __name__ == "__main__":
    main()
