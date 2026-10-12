from pathlib import Path

import pytest

from github_repo_manager.git_ops import default_workspace, safe_component


def test_safe_component():
    assert safe_component("hello-world_1.2") == "hello-world_1.2"
    assert safe_component("a/b") == "a_b"


@pytest.mark.parametrize("value", ["", ".", "..", "   "])
def test_safe_component_rejects_empty(value):
    with pytest.raises(ValueError):
        safe_component(value)


def test_default_workspace(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO_MANAGER_ROOT", str(Path("tmp") / "repos"))
    assert default_workspace("octocat") == Path("tmp") / "repos" / "octocat"
