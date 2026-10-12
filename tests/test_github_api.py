import pytest

from github_repo_manager.github_api import parse_github_url


def test_parse_profile_url():
    assert parse_github_url("https://github.com/microsoft") == "microsoft"


def test_parse_trailing_slash():
    assert parse_github_url("github.com/octocat/") == "octocat"


@pytest.mark.parametrize(
    "value", ["", "https://gitlab.com/example", "https://github.com/a/repo", "https://github.com/settings"]
)
def test_reject_invalid_urls(value):
    with pytest.raises(ValueError):
        parse_github_url(value)
