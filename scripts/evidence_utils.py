"""Shared helpers for evidence provenance and reproducibility manifests."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_provenance(repo_root: Path) -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            out = subprocess.check_output(args, cwd=str(repo_root), text=True).strip()
        except Exception:
            return ""
        return out

    sha = _run(["git", "rev-parse", "HEAD"])
    dirty = bool(_run(["git", "status", "--porcelain"]))
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return {"git_sha": sha, "git_branch": branch, "git_dirty": dirty}


def runtime_provenance() -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def build_data_manifest(paths: list[Path]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for p in sorted(paths):
        if not p.exists() or not p.is_file():
            continue
        files.append(
            {
                "path": str(p),
                "size_bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
        )
    digest_src = json.dumps(files, sort_keys=True).encode("utf-8")
    manifest_hash = hashlib.sha256(digest_src).hexdigest()
    return {"n_files": len(files), "files": files, "manifest_sha256": manifest_hash}

