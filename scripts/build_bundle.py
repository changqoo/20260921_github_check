"""Create an allowlisted, dependency-free offline source archive."""
import hashlib
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    entries = []
    for directory in ["prguard", "tests", "scripts", "docs", "deploy", ".github"]:
        for path in (root / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                entries.append(path)
    entries += [root / name for name in ["README.md", "config.example.json", ".gitignore"]]
    dest = root / "dist"
    dest.mkdir(exist_ok=True)
    archive = dest / "pr-integrity-agent-source.zip"
    manifest = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(entries):
            relative = file.relative_to(root).as_posix()
            data = file.read_bytes()
            z.writestr("pr-integrity-agent/" + relative, data)
            manifest.append(hashlib.sha256(data).hexdigest() + "  " + relative)
        z.writestr("pr-integrity-agent/MANIFEST.sha256", "\n".join(manifest) + "\n")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n", encoding="ascii")
    print(archive)
    print(digest)


if __name__ == "__main__":
    main()
