# GitHub Repository Manager

A Windows-friendly Streamlit application that lists repositories owned by a GitHub user or organization, lets you select repositories, clones them in bulk, checks for remote updates, and applies safe fast-forward-only updates.

## Features

- Accepts profile URLs such as `https://github.com/microsoft`.
- Automatically distinguishes users from organizations.
- Handles GitHub API pagination.
- Optional GitHub token for increased API limits and accessible private repositories.
- Select All, Clear All, Clone All, Refresh, and Update All controls.
- Default checkout path: `C:\workspace\code\git\{profile-or-org-name}`.
- Per-repository status, warning, error, and command output.
- Repositories that are updatable, warned, errored, or not cloned are sorted to the top.
- Progress bars name the repository in progress and show each clone/update completion.
- Controls are disabled while a clone, refresh, or update is running.
- Console logging with timestamp and app version for debugging (see [CHANGELOG.md](CHANGELOG.md)).
- Refresh performs `git fetch --prune` and compares `HEAD` with its upstream.
- Update uses `git pull --ff-only`; dirty worktrees, detached HEADs, and branches without upstreams are not changed automatically.

## Requirements

- Windows 10/11
- Git available on `PATH`
- `uv` installed
- Network access to GitHub

## Run with uv

```powershell
cd github-repo-manager
uv sync
uv run streamlit run src/github_repo_manager/app.py
```

Or double-click `run.bat`, or run:

```powershell
.\run.ps1
```

`uv sync` creates `.venv` automatically and installs the locked project dependencies. If a lock file is not included, uv creates it during the first sync.

## Traditional venv fallback

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
streamlit run src/github_repo_manager/app.py
```

## GitHub token

A token is optional for public repositories. Add one in the sidebar for higher rate limits and for private repositories the token is allowed to read. The app keeps it in Streamlit session state only and never writes it to disk.

For cloning private HTTPS repositories, configure Git Credential Manager or authenticate Git on the machine. The token entered in the app is intentionally not embedded in clone URLs or command logs.

## Update behavior

1. **Refresh** fetches remote references and determines whether the checked-out upstream is ahead/behind.
2. **Update All** processes only repositories reported as behind.
3. Updates are skipped if local changes exist.
4. Only fast-forward pulls are allowed, preventing automatic merge commits.
5. Errors and warnings are shown under the relevant repository.

## Tests

```powershell
uv sync --extra dev
uv run pytest
uv run ruff check .
```

## Optional checkout-root override

Set `GITHUB_REPO_MANAGER_ROOT` before launching:

```powershell
$env:GITHUB_REPO_MANAGER_ROOT = "D:\Source"
.\run.ps1
```
