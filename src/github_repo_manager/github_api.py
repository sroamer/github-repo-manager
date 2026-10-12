from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests

API_ROOT = "https://api.github.com"


class GitHubError(RuntimeError):
    """A user-facing GitHub API error."""


@dataclass(frozen=True)
class GitHubTarget:
    name: str
    kind: str  # "user" or "org"


def parse_github_url(value: str) -> str:
    """Return the user/org slug from a github.com profile or organization URL."""
    raw = value.strip()
    if not raw:
        raise ValueError("Enter a GitHub user or organization URL.")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("The URL must use github.com.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1 or parts[0] in {"orgs", "users", "settings", "marketplace"}:
        raise ValueError("Use a profile URL such as https://github.com/microsoft.")
    return parts[0]


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "github-repo-manager-streamlit",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token.strip()}"

    def _get(self, url: str, **params: object) -> requests.Response:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise GitHubError(f"Could not contact GitHub: {exc}") from exc
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubError("GitHub API rate limit reached. Add a token and try again.")
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise GitHubError(f"GitHub API returned {response.status_code}: {detail}")
        return response

    def identify(self, name: str) -> GitHubTarget:
        response = self.session.get(f"{API_ROOT}/orgs/{name}", timeout=self.timeout)
        if response.status_code == 200:
            return GitHubTarget(name=name, kind="org")
        if response.status_code not in {404}:
            self._raise_response(response)
        user = self._get(f"{API_ROOT}/users/{name}").json()
        return GitHubTarget(name=user["login"], kind="user")

    @staticmethod
    def _raise_response(response: requests.Response) -> None:
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise GitHubError(f"GitHub API returned {response.status_code}: {detail}")

    def list_repositories(self, target: GitHubTarget) -> list[dict]:
        if target.kind == "org":
            url = f"{API_ROOT}/orgs/{target.name}/repos"
            params: dict[str, object] = {"type": "all", "sort": "full_name", "per_page": 100}
        else:
            url = f"{API_ROOT}/users/{target.name}/repos"
            params = {"type": "owner", "sort": "full_name", "per_page": 100}

        repositories: list[dict] = []
        while url:
            response = self._get(url, **params)
            repositories.extend(response.json())
            url = response.links.get("next", {}).get("url", "")
            params = {}

        # If the token belongs to this user, include private repositories owned by them.
        if target.kind == "user" and "Authorization" in self.session.headers:
            try:
                authenticated = self._get(f"{API_ROOT}/user").json()
                if authenticated.get("login", "").casefold() == target.name.casefold():
                    private_and_public = self._list_authenticated_owned(target.name)
                    by_id = {repo["id"]: repo for repo in repositories}
                    by_id.update({repo["id"]: repo for repo in private_and_public})
                    repositories = list(by_id.values())
            except GitHubError:
                pass

        return sorted(repositories, key=lambda repo: repo["name"].casefold())

    def _list_authenticated_owned(self, owner: str) -> list[dict]:
        url = f"{API_ROOT}/user/repos"
        params: dict[str, object] = {
            "visibility": "all",
            "affiliation": "owner",
            "sort": "full_name",
            "per_page": 100,
        }
        result: list[dict] = []
        while url:
            response = self._get(url, **params)
            result.extend(
                repo
                for repo in response.json()
                if repo.get("owner", {}).get("login", "").casefold() == owner.casefold()
            )
            url = response.links.get("next", {}).get("url", "")
            params = {}
        return result
