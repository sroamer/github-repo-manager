from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OperationResult:
    status: str
    message: str
    details: str = ""


def safe_component(value: str) -> str:
    if not value.strip():
        raise ValueError("Invalid profile, organization, or repository name.")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip(". ")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Invalid profile, organization, or repository name.")
    return cleaned


def default_workspace(target_name: str) -> Path:
    root = Path(os.environ.get("GITHUB_REPO_MANAGER_ROOT", r"C:\workspace\code\git"))
    return root / safe_component(target_name)


def run_git(args: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Git is not installed or is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Git command timed out after {timeout} seconds.") from exc


def output_of(proc: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part.strip())


def clone_repository(clone_url: str, destination: Path) -> OperationResult:
    if destination.exists():
        if (destination / ".git").exists():
            return OperationResult("warning", "Already cloned; skipped.")
        return OperationResult("error", "Destination exists but is not a Git repository.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = run_git(["clone", "--progress", clone_url, str(destination)])
    except RuntimeError as exc:
        return OperationResult("error", str(exc))
    details = output_of(proc)
    if proc.returncode:
        return OperationResult("error", "Clone failed.", details)
    return OperationResult("success", "Cloned successfully.", details)


def repository_status(path: Path) -> OperationResult:
    if not path.exists():
        return OperationResult("not_cloned", "Not cloned.")
    if not (path / ".git").exists():
        return OperationResult("error", "Folder exists but is not a Git repository.")

    try:
        fetch = run_git(["fetch", "--prune"], cwd=path)
    except RuntimeError as exc:
        return OperationResult("error", str(exc))
    if fetch.returncode:
        return OperationResult("error", "Fetch/check failed.", output_of(fetch))

    branch = run_git(["symbolic-ref", "--short", "HEAD"], cwd=path)
    if branch.returncode:
        return OperationResult("warning", "Detached HEAD; automatic update is disabled.", output_of(branch))

    upstream = run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=path)
    if upstream.returncode:
        return OperationResult("warning", "Current branch has no upstream tracking branch.", output_of(upstream))

    counts = run_git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], cwd=path)
    if counts.returncode:
        return OperationResult("error", "Could not compare local and remote commits.", output_of(counts))
    ahead, behind = (int(value) for value in counts.stdout.split())

    dirty = run_git(["status", "--porcelain"], cwd=path)
    suffix = " Local changes are present." if dirty.stdout.strip() else ""
    if behind:
        return OperationResult("update", f"Update available: {behind} behind, {ahead} ahead.{suffix}")
    if ahead:
        return OperationResult("warning", f"Local branch is {ahead} commit(s) ahead.{suffix}")
    return OperationResult("current", f"Up to date.{suffix}")


def update_repository(path: Path) -> OperationResult:
    status = repository_status(path)
    if status.status != "update":
        return status
    dirty = run_git(["status", "--porcelain"], cwd=path)
    if dirty.stdout.strip():
        return OperationResult("warning", "Skipped because the working tree has local changes.")
    proc = run_git(["pull", "--ff-only"], cwd=path)
    details = output_of(proc)
    if proc.returncode:
        return OperationResult("error", "Update failed. Only fast-forward updates are allowed.", details)
    return OperationResult("success", "Updated successfully.", details)
