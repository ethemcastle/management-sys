"""Live GitHub implementation of `GitHubService`.

Reads real branches and pull requests from the GitHub REST API and stores them
in the same pool the mock uses, so the identify-by-ticket-code matching
(`links()`) is shared. Activated automatically when `CADENCE_GITHUB_TOKEN` is
set (a fine-grained PAT or a GitHub App installation token). Without a token,
public repos still work but hit the low unauthenticated rate limit.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import CiStatus, PrState
from app.models.github import RepoBranch, RepoPullRequest
from app.models.issue import Issue
from app.services.github_service import MockGitHubService


class GitHubApiError(RuntimeError):
    """Raised when the GitHub API returns an error (bad repo, auth, rate limit).

    `status` is the HTTP status when one is available (None for transport errors),
    so callers can distinguish e.g. 422 "already exists" from 403/404 "no access".
    """

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


# Auto-refresh window: opening an issue re-pulls from GitHub if the last sync for
# this repo is older than this, so pushed branches/PRs show up without a manual
# reconnect. A short TTL keeps navigation snappy without hammering the API.
_SYNC_TTL_SECONDS = 20
_last_sync: dict[str, datetime] = {}


class LiveGitHubService(MockGitHubService):
    """Live connect + auto-refreshing links; matching is inherited from the mock."""

    def connect(self, db: Session, full_name: str) -> tuple[int, int]:
        repo = self.get_repo(db)
        info = self._api(f"/repos/{full_name}")  # 404/403 -> GitHubApiError
        repo.connected = True
        repo.owner = info["owner"]["login"]
        repo.name = info["name"]
        repo.full_name = info["full_name"]
        repo.default_branch = info.get("default_branch", "main")
        repo.connected_at = datetime.now(timezone.utc)
        return self._sync_pool(db, repo.full_name)

    def links(self, db: Session, key: str):
        """Re-pull from GitHub if the snapshot is stale, then match by key — so a
        branch/PR pushed after connecting appears on its own."""
        repo = self.get_repo(db)
        if repo.connected and repo.full_name:
            last = _last_sync.get(repo.full_name)
            now = datetime.now(timezone.utc)
            if last is None or (now - last).total_seconds() > _SYNC_TTL_SECONDS:
                try:
                    self._sync_pool(db, repo.full_name)
                except GitHubApiError:
                    pass  # keep the last good snapshot on a transient error
        return super().links(db, key)

    def _sync_pool(self, db: Session, full_name: str) -> tuple[int, int]:
        """Replace the branch/PR pool with a fresh pull from GitHub."""
        db.execute(delete(RepoPullRequest))
        db.execute(delete(RepoBranch))

        for b in self._api(f"/repos/{full_name}/branches?per_page=100"):
            sha = (b.get("commit") or {}).get("sha", "")
            db.add(
                RepoBranch(
                    name=b["name"],
                    ahead=0,
                    behind=0,
                    last_commit=f"commit {sha[:7]}" if sha else "",
                )
            )

        for p in self._api(f"/repos/{full_name}/pulls?state=all&per_page=100"):
            # Hide closed (unmerged) PRs — keep open / draft / merged.
            if p.get("state") == "closed" and not p.get("merged_at"):
                continue
            if p.get("merged_at"):
                state = PrState.merged
            elif p.get("draft"):
                state = PrState.draft
            else:
                state = PrState.open
            sha = (p.get("head") or {}).get("sha", "")
            detail = self._pr_checks(full_name, sha) if sha else []
            db.add(
                RepoPullRequest(
                    number=p["number"],
                    title=p["title"],
                    branch=(p.get("head") or {}).get("ref", ""),
                    base=(p.get("base") or {}).get("ref", "main"),
                    state=state,
                    checks=self._overall_checks(detail),
                    checks_detail=detail,
                    additions=0,
                    deletions=0,
                    files_changed=0,
                    author_initials=None,
                    ai_generated=False,
                )
            )

        db.commit()
        _last_sync[full_name] = datetime.now(timezone.utc)
        branches = db.scalar(select(func.count()).select_from(RepoBranch)) or 0
        prs = db.scalar(select(func.count()).select_from(RepoPullRequest)) or 0
        return branches, prs

    # --- real CI checks for a PR's head commit ---
    def _pr_checks(self, full: str, sha: str) -> list[dict]:
        """Real per-check status for a commit: GitHub Actions/app **check-runs** plus
        legacy **commit statuses** (e.g. Vercel deploys), de-duped by name."""
        out: list[dict] = []
        seen: set[str] = set()
        try:
            for c in self._api(f"/repos/{full}/commits/{sha}/check-runs").get("check_runs", []):
                name = c.get("name") or "check"
                if name not in seen:
                    seen.add(name)
                    out.append({"name": name, "status": self._map_check_run(c)})
        except GitHubApiError:
            pass
        try:
            for s in self._api(f"/repos/{full}/commits/{sha}/status").get("statuses", []):
                name = s.get("context") or "status"
                if name not in seen:
                    seen.add(name)
                    out.append({"name": name, "status": self._map_state(s.get("state"))})
        except GitHubApiError:
            pass
        return out

    @staticmethod
    def _map_check_run(c: dict) -> str:
        if c.get("status") != "completed":
            return CiStatus.pending.value  # queued / in_progress
        ok = c.get("conclusion") in ("success", "neutral", "skipped")
        return CiStatus.passing.value if ok else CiStatus.failing.value

    @staticmethod
    def _map_state(state: str | None) -> str:
        return {
            "success": CiStatus.passing.value,
            "pending": CiStatus.pending.value,
            "failure": CiStatus.failing.value,
            "error": CiStatus.failing.value,
        }.get(state or "", CiStatus.pending.value)

    @staticmethod
    def _overall_checks(detail: list[dict]) -> CiStatus:
        statuses = {d["status"] for d in detail}
        if CiStatus.failing.value in statuses:
            return CiStatus.failing
        if CiStatus.pending.value in statuses:
            return CiStatus.pending
        return CiStatus.passing  # all passing, or no checks (neutral)

    @classmethod
    def _api(cls, path: str):
        return cls._request("GET", path)

    @staticmethod
    def _request(method: str, path: str, json_body: dict | None = None):
        url = settings.github_api + path
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "cadence-app",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        try:
            resp = httpx.request(method, url, headers=headers, json=json_body, timeout=20.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            try:
                msg = e.response.json().get("message", "")
            except Exception:
                msg = ""
            raise GitHubApiError(
                f"GitHub API {e.response.status_code}: {msg or path}", status=e.response.status_code
            ) from e
        except httpx.HTTPError as e:
            raise GitHubApiError(f"Could not reach GitHub: {e}") from e

    # --- write: open a real PR (branch off default → commit change(s) → open PR) ---
    def open_pull_request(
        self, db: Session, issue: Issue, commit_files: list[dict] | None = None
    ) -> dict:
        """Create a real branch + commit + PR on the connected repo.

        `commit_files` is a list of {path, content} real edits (from the code-gen
        agent). When omitted, a placeholder note is committed instead so the PR
        still has a diff. Returns {number, url, branch, base, changed, real}. Raises
        GitHubApiError if the token is read-only (403/404) or anything else fails —
        the caller falls back to the mock. Idempotent: an existing branch/PR for the
        ticket is reused rather than duplicated.
        """
        repo = self.get_repo(db)
        full = repo.full_name
        if not (repo.connected and full):
            raise GitHubApiError("No GitHub repo connected")
        base = repo.default_branch or "main"
        owner = repo.owner or full.split("/")[0]
        branch = f"cadence-ai/{issue.key.lower()}-fix"

        # 1. head SHA of the base branch
        base_sha = (self._api(f"/repos/{full}/git/ref/heads/{base}").get("object") or {}).get("sha")
        if not base_sha:
            raise GitHubApiError("Could not read the base branch SHA")

        # 2. create the feature branch (422 == already exists → reuse)
        try:
            self._request("POST", f"/repos/{full}/git/refs",
                          {"ref": f"refs/heads/{branch}", "sha": base_sha})
        except GitHubApiError as e:
            if e.status != 422:
                raise

        # 3. commit the change(s): the AI's real edits, or a placeholder note.
        real = bool(commit_files)
        files = commit_files or [{"path": f"cadence/{issue.key}.md", "content": self._note(issue)}]
        for f in files:
            verb = "apply fix in" if real else "add ticket note"
            self._commit_file(full, branch, f["path"], f["content"],
                              message=f"{issue.key}: {verb} {f['path']}")

        # 4. open the PR (422 == one already exists for this head → reuse it)
        try:
            pr = self._request("POST", f"/repos/{full}/pulls", {
                "title": f"{issue.key}: {issue.title}",
                "head": branch, "base": base, "body": self._pr_body(issue, files if real else None),
            })
        except GitHubApiError as e:
            if e.status != 422:
                raise
            found = self._api(f"/repos/{full}/pulls?head={owner}:{branch}&state=open")
            if not found:
                raise
            pr = found[0]
        return {
            "number": pr["number"], "url": pr.get("html_url", ""),
            "branch": branch, "base": base,
            "changed": [f["path"] for f in files], "real": real,
        }

    def _commit_file(self, full: str, branch: str, path: str, content: str, message: str) -> None:
        """Create or update a single file on the branch (include its sha when it exists)."""
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        try:
            existing = self._api(f"/repos/{full}/contents/{path}?ref={branch}")
            if isinstance(existing, dict) and existing.get("sha"):
                payload["sha"] = existing["sha"]
        except GitHubApiError:
            pass
        self._request("PUT", f"/repos/{full}/contents/{path}", payload)

    @staticmethod
    def _note(issue: Issue) -> str:
        return (
            f"# {issue.key}: {issue.title}\n\n"
            f"- Type: {issue.type.value}\n"
            f"- Priority: {issue.priority}\n"
            f"- Points: {issue.points}\n\n"
            f"{(issue.description or '').strip()}\n\n"
            "_Placeholder commit opened by Cadence AI — replace with the real fix "
            "once AI code-generation is wired in._\n"
        )

    @staticmethod
    def _pr_body(issue: Issue, changed: list[dict] | None = None) -> str:
        head = f"Opened by **Cadence AI** for `{issue.key}` — {issue.title}."
        if changed:
            files = "\n".join(f"- `{f['path']}`" for f in changed)
            return f"{head}\n\nApplied the change described in the ticket:\n{files}"
        return (
            f"{head}\n\nThis PR contains a placeholder note (Cadence AI couldn't derive a "
            "concrete code change from the ticket). Add more detail to the ticket description "
            "and re-run to generate a real edit."
        )
