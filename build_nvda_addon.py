from __future__ import annotations

import pathlib
import re
import zipfile


ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"


def manifest_value(field: str) -> str:
    manifest = (ROOT / "manifest.ini").read_text(encoding="utf-8")
    match = re.search(rf"(?m)^{re.escape(field)}\s*=\s*[\"']?([^\"'\r\n]+)", manifest)
    if not match:
        raise RuntimeError(f"Campo {field!r} não encontrado no manifest.ini")
    return match.group(1).strip()


OUTPUT = DIST / f"voz_nativa_do_dosvox-{manifest_value('version')}.nvda-addon"


def iter_files():
    yield ROOT / "manifest.ini", "manifest.ini"
    roots = [
        (ROOT / "doc", "doc"),
        (ROOT / "locale", "locale"),
        (ROOT / "globalPlugins", "globalPlugins"),
        (ROOT / "synthDrivers", "synthDrivers"),
        (ROOT / "brailleDisplayDrivers", "brailleDisplayDrivers"),
        (ROOT / "addon" / "doc", "doc"),
        (ROOT / "addon" / "locale", "locale"),
        (ROOT / "addon" / "globalPlugins", "globalPlugins"),
        (ROOT / "addon" / "synthDrivers", "synthDrivers"),
        (ROOT / "addon" / "brailleDisplayDrivers", "brailleDisplayDrivers"),
    ]
    seen = set()
    for base_path, archive_base in roots:
        if not base_path.exists():
            continue
        for path in base_path.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            archive_name = pathlib.PurePosixPath(archive_base) / path.relative_to(base_path).as_posix()
            if str(archive_name) in seen:
                continue
            seen.add(str(archive_name))
            yield path, str(archive_name)


def main():
    DIST.mkdir(exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, archive_name in iter_files():
            archive.write(path, archive_name)
    print(OUTPUT)


if __name__ == "__main__":
    main()