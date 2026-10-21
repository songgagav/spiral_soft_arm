"""为阶段 A 生成器记录可复现的本地源文件指纹。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

import bpy


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
UPSTREAM_COMMIT = "f563e69f292a6b8cac1946dc45ad9e60d8795391"
PACKAGE_GENERATOR_VERSION = "0.1.0"
SOURCE_PATHS = [
    pathlib.Path("design-tool/DesignTool.py"),
    pathlib.Path("design-tool/blender/geometry.py"),
    pathlib.Path("design-tool/blender/blender_geometry.py"),
    pathlib.Path("design-tool/blender/generate_candidates.py"),
    pathlib.Path("design-tool/blender/build_preprint_assembly.py"),
    pathlib.Path("design-tool/blender/tests/test_preprint_package.py"),
    pathlib.Path("design-tool/blender/validate_candidates.py"),
    pathlib.Path("design-tool/blender/record_provenance.py"),
    *[pathlib.Path(f"design-tool/blender/candidates/{name}.json") for name in ("A36", "A37", "B32", "B33")],
]


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    tracked = []
    for relative in SOURCE_PATHS:
        path = REPO / relative
        if path.is_file():
            tracked.append({"path": relative.as_posix(), "sha256": sha256_file(path)})
    try:
        local_commit = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        local_commit = None
    payload = {
        "lock_schema_version": "1.0.0",
        "generator_version": "0.4.0",
        "preprint_package_generator_version": PACKAGE_GENERATOR_VERSION,
        "blender_version": bpy.app.version_string,
        "local_git_commit": local_commit,
        "upstream_repository": "https://github.com/ZhanchiWang/Open-Spiral-Robots",
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_commit_url": f"https://github.com/ZhanchiWang/Open-Spiral-Robots/commit/{UPSTREAM_COMMIT}",
        "source_files": tracked,
        "model_units": {"length": "mm", "angle": "deg", "mass": "kg", "axis": "+Z"},
    }
    output = HERE / "source_lock.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"已写入 {output}；已计算 {len(tracked)} 个源文件的哈希；local_git_commit={local_commit}")


if __name__ == "__main__":
    main()
