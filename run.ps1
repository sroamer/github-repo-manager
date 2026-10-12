$ErrorActionPreference = "Stop"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv was not found. Install it from https://docs.astral.sh/uv/ and rerun." -ForegroundColor Red
    exit 1
}
uv sync
uv run streamlit run src/github_repo_manager/app.py
