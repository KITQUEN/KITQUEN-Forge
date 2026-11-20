"""Build the Blender extension and a source archive using only the standard library."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "kitquen_forge"
SOURCE_DIRS = {
    ".github",
    "benchmarks",
    "docs",
    "examples",
    "forge_mcp",
    "kitquen_forge",
    "scripts",
    "skills",
    "tests",
}
SOURCE_FILES = {
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
}


def files(folder):
    return [
        path
        for path in folder.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    with ZipFile(args.out / "kitquen_forge-0.1.0.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted(files(ADDON)):
            archive.write(path, path.relative_to(ADDON))
        archive.write(ROOT / "LICENSE", "LICENSE")
    with ZipFile(args.out / "KITQUEN-Forge-0.1.0-alpha-source.zip", "w", ZIP_DEFLATED) as archive:
        sources = [ROOT / name for name in SOURCE_FILES]
        sources.extend(path for name in SOURCE_DIRS for path in files(ROOT / name))
        for path in sorted(sources):
            archive.write(path, Path("KITQUEN-Forge") / path.relative_to(ROOT))


if __name__ == "__main__":
    main()
