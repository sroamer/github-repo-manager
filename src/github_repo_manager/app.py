from __future__ import annotations

import logging
import time
from pathlib import Path

import streamlit as st

from github_repo_manager import __version__
from github_repo_manager.git_ops import (
    OperationResult,
    clone_repository,
    default_workspace,
    repository_status,
    safe_component,
    update_repository,
)
from github_repo_manager.github_api import GitHubClient, GitHubError, parse_github_url

STATUS_ICON = {
    "success": "✅",
    "current": "✅",
    "update": "⬇️",
    "warning": "⚠️",
    "error": "❌",
    "not_cloned": "○",
}


def initialize_state() -> None:
    defaults = {"repos": [], "target": None, "results": {}, "statuses": {}, "source_url": "", "pending_op": None}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def result_block(repo_name: str, result: OperationResult | None) -> None:
    if not result:
        return
    icon = STATUS_ICON.get(result.status, "ℹ️")
    if result.status == "error":
        st.error(f"{icon} {result.message}")
    elif result.status == "warning":
        st.warning(f"{icon} {result.message}")
    elif result.status in {"success", "current"}:
        st.success(f"{icon} {result.message}")
    else:
        st.info(f"{icon} {result.message}")
    if result.details:
        with st.expander(f"Command output for {repo_name}"):
            st.code(result.details, language="text")


def main() -> None:
    st.set_page_config(page_title="GitHub Repository Manager", page_icon="📦", layout="wide")
    initialize_state()

    st.title("📦 GitHub Repository Manager")
    st.caption("Discover, clone, check, and fast-forward repositories from one GitHub profile or organization.")

    with st.sidebar:
        st.header("Settings")
        token = st.text_input(
            "GitHub token (optional)",
            type="password",
            help="Recommended for higher API limits and required for private repositories you can access.",
        )
        st.caption("The token is kept only in this browser session and is not written to disk.")

    busy = st.session_state.pending_op is not None

    source_url = st.text_input(
        "GitHub user or organization URL",
        placeholder="https://github.com/microsoft",
        value=st.session_state.source_url,
        disabled=busy,
    )

    if st.button("View All", type="primary", use_container_width=True, disabled=busy):
        try:
            name = parse_github_url(source_url)
            client = GitHubClient(token or None)
            target = client.identify(name)
            repos = client.list_repositories(target)
            st.session_state.repos = repos
            st.session_state.target = target
            st.session_state.source_url = source_url
            st.session_state.results = {}
            st.session_state.statuses = {}
            for repo in repos:
                st.session_state.setdefault(f"repo_{repo['id']}", False)
            st.success(f"Found {len(repos)} repositories for {target.kind} '{target.name}'.")
        except (ValueError, GitHubError) as exc:
            st.error(str(exc))

    target = st.session_state.target
    repos = st.session_state.repos
    if not target:
        st.info("Enter a GitHub profile or organization URL, then select **View All**.")
        return

    default_path = str(default_workspace(target.name))
    workspace_text = st.text_input("Checkout folder", value=default_path, disabled=busy)
    workspace = Path(workspace_text).expanduser()
    st.caption(f"Repositories will be stored under: `{workspace}`")

    controls = st.columns(4)
    if controls[0].button("Select All", use_container_width=True, disabled=busy):
        for repo in repos:
            st.session_state[f"repo_{repo['id']}"] = True
        st.rerun()
    if controls[1].button("Clear All", use_container_width=True, disabled=busy):
        for repo in repos:
            st.session_state[f"repo_{repo['id']}"] = False
        st.rerun()

    selected = [repo for repo in repos if st.session_state.get(f"repo_{repo['id']}", False)]

    if controls[2].button("Clone All", use_container_width=True, disabled=busy or not selected):
        st.session_state.pending_op = "clone"
        st.rerun()

    if controls[3].button("Refresh", use_container_width=True, disabled=busy):
        st.session_state.pending_op = "refresh"
        st.rerun()

    update_ids = {
        repo_id for repo_id, status in st.session_state.statuses.items() if status.status == "update"
    }
    if st.button(
        "Update All", type="primary", disabled=busy or not update_ids, use_container_width=True
    ):
        st.session_state.pending_op = "update"
        st.rerun()

    # The operation runs on the rerun where every button is already rendered disabled.
    pending = st.session_state.pending_op
    if pending:
        try:
            if pending == "clone":
                run_clone(selected, workspace)
            elif pending == "refresh":
                run_refresh(repos, workspace)
            elif pending == "update":
                run_update([repo for repo in repos if repo["id"] in update_ids], workspace)
        finally:
            st.session_state.pending_op = None
        st.rerun()

    updates = [repo for repo in repos if repo["id"] in update_ids]
    if updates:
        st.warning("Updates available: " + ", ".join(repo["name"] for repo in updates))

    render_repositories(repos, busy)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("github_repo_manager")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [v" + __version__ + "] %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.info("GitHub Repository Manager v%s started", __version__)
    return logger


LOG = setup_logging()
COMPLETED_PAUSE_SECONDS = 0.4


def run_clone(selected: list, workspace: Path) -> None:
    total = len(selected)
    LOG.info("Clone started: %d repositories into %s", total, workspace)
    progress = st.progress(0, text="Cloning selected repositories...")
    for index, repo in enumerate(selected, start=1):
        progress.progress((index - 1) / total, text=f"Cloning {repo['name']} ({index}/{total})...")
        destination = workspace / safe_component(repo["name"])
        result = clone_repository(repo["clone_url"], destination)
        st.session_state.results[repo["id"]] = result
        LOG.info("Clone %s: %s - %s", result.status, repo["name"], result.message)
        icon = STATUS_ICON.get(result.status, "??")
        progress.progress(index / total, text=f"{icon} Clone completed: {repo['name']} ({index}/{total})")
        time.sleep(COMPLETED_PAUSE_SECONDS)
    progress.empty()
    LOG.info("Clone finished")


def run_refresh(repos: list, workspace: Path) -> None:
    total = max(len(repos), 1)
    LOG.info("Refresh started: %d repositories in %s", len(repos), workspace)
    progress = st.progress(0, text="Fetching and checking repositories...")
    statuses = {}
    for index, repo in enumerate(repos, start=1):
        progress.progress((index - 1) / total, text=f"Checking {repo['name']} ({index}/{total})...")
        status = repository_status(workspace / safe_component(repo["name"]))
        statuses[repo["id"]] = status
        LOG.info("Refresh %s: %s", status.status, repo["name"])
        progress.progress(index / total, text=f"Checked {repo['name']} ({index}/{total})")
    st.session_state.statuses = statuses
    progress.empty()
    LOG.info("Refresh finished")


def run_update(update_repos: list, workspace: Path) -> None:
    total = len(update_repos)
    LOG.info("Update started: %d repositories", total)
    progress = st.progress(0, text="Updating repositories with available changes...")
    for index, repo in enumerate(update_repos, start=1):
        progress.progress((index - 1) / total, text=f"Updating {repo['name']} ({index}/{total})...")
        path = workspace / safe_component(repo["name"])
        result = update_repository(path)
        st.session_state.results[repo["id"]] = result
        st.session_state.statuses[repo["id"]] = repository_status(path)
        LOG.info("Update %s: %s - %s", result.status, repo["name"], result.message)
        icon = STATUS_ICON.get(result.status, "??")
        progress.progress(index / total, text=f"{icon} Update completed: {repo['name']} ({index}/{total})")
        time.sleep(COMPLETED_PAUSE_SECONDS)
    progress.empty()
    LOG.info("Update finished")


ATTENTION_ORDER = {"update": 0, "warning": 1, "error": 2, "not_cloned": 3}


def attention_rank(repo: dict) -> int:
    status = st.session_state.statuses.get(repo["id"])
    result = st.session_state.results.get(repo["id"])
    state = status.status if status else (result.status if result else None)
    return ATTENTION_ORDER.get(state, len(ATTENTION_ORDER))

def render_repositories(repos: list, busy: bool) -> None:
    st.subheader(f"Repositories ({len(repos)})")
    for repo in sorted(repos, key=attention_rank):
        status = st.session_state.statuses.get(repo["id"])
        icon = STATUS_ICON.get(status.status, "") if status else ""
        with st.container(border=True):
            left, middle, right = st.columns([0.7, 7, 2])
            left.checkbox("Select", key=f"repo_{repo['id']}", label_visibility="collapsed", disabled=busy)
            middle.markdown(f"### {icon} [{repo['name']}]({repo['html_url']})")
            visibility = "Private" if repo.get("private") else "Public"
            archived = " · Archived" if repo.get("archived") else ""
            right.caption(f"{visibility}{archived} · {repo.get('language') or 'No language'}")
            if repo.get("description"):
                middle.write(repo["description"])
            middle.caption(f"Default branch: {repo.get('default_branch', 'unknown')} · Clone: {repo['clone_url']}")
            result_block(repo["name"], status)
            operation_result = st.session_state.results.get(repo["id"])
            if operation_result and operation_result != status:
                result_block(repo["name"], operation_result)


if __name__ == "__main__":
    main()
