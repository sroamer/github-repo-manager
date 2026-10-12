@echo off
where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Install it from https://docs.astral.sh/uv/ and rerun.
  exit /b 1
)
uv sync
if errorlevel 1 exit /b 1
uv run streamlit run src\github_repo_manager\app.py
