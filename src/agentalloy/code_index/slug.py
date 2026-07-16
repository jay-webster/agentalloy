"""Canonical repo-slug derivation for the code-index module.

This IS the canonical implementation now: the code-index module stores each
repo's per-slug data directory (``repos/{slug}/``) under the slug derived
here, and every consumer (ingest pipeline, ``/code`` routers, unwire cleanup)
must produce the *identical* string. Adopted from codebase-indexer's
``app/services/slug.py`` (``parse_github_remote`` / ``canonical_slug_for_path``
/ ``derive_slug``) plus ``app/config.py:slugify_repo``; agentalloy no longer
mirrors an external system of record.

The canonical rule is:

  1. Exactly one remote, named ``origin`` (refuse to guess when 0 or >1).
  2. ``origin`` is a github.com URL → ``{org}__{repo}``.
  3. ``origin`` is any other parseable git host (GitLab, Bitbucket,
     self-hosted) → ``{host}__{org}__{repo}``.
  4. Otherwise fall back to the directory basename.

Then ``slugify_repo`` enforces a filesystem-safe charset on the result.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Any single-origin git host: https://<host>/<org>/<repo>(.git)?,
# git@<host>:<org>/<repo>(.git)?, ssh://git@<host>/<org>/<repo>(.git)?.
# <org> may contain slashes (GitLab subgroups); a bare "<host>/<repo>" with no
# org segment is ambiguous and must not match.
_GIT_URL_RE = re.compile(
    r"""^
    (?:
        (?:https?://)(?:[^@/]+@)?(?P<host1>[A-Za-z0-9.-]+)/
        |
        git@(?P<host2>[A-Za-z0-9.-]+):
        |
        ssh://git@(?P<host3>[A-Za-z0-9.-]+)/
    )
    (?P<org>[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*)/
    (?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*?)
    (?:\.git)?/?
    $""",
    re.VERBOSE,
)

_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})

# Hard cap on subprocess wall-clock so a hung filesystem can't stall a query.
_GIT_TIMEOUT_S = 5.0


def slugify_repo(name: str) -> str:
    """Mirror of codebase-indexer ``config.slugify_repo``.

    Replaces anything that's not alphanumeric/dash/underscore/dot with ``_``,
    collapses runs, strips leading/trailing separators. Never empty.
    """
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return s or "repo"


def parse_git_remote(url: str) -> tuple[str, str, str] | None:
    """Parse any single-origin git remote URL into ``(host, org, repo)``.

    None when the URL doesn't parse, or the org segment is missing (a bare
    ``host/repo`` is ambiguous — refuse to guess).

    >>> parse_git_remote("git@github.com:navistone/TheForge.git")
    ('github.com', 'navistone', 'TheForge')
    >>> parse_git_remote("https://gitlab.com/team/backend/repo.git")
    ('gitlab.com', 'team/backend', 'repo')
    >>> parse_git_remote("https://gitlab.com/repo.git") is None
    True
    """
    if not isinstance(url, str):
        return None
    candidate = url.strip()
    if not candidate:
        return None
    match = _GIT_URL_RE.match(candidate)
    if not match:
        return None
    host = match.group("host1") or match.group("host2") or match.group("host3")
    org = match.group("org")
    repo = match.group("repo")
    if not host or not org or not repo:
        return None
    return (host, org, repo)


def parse_github_remote(url: str) -> tuple[str, str] | None:
    """Parse a GitHub remote URL into ``(org, repo)``; None for non-GitHub.

    Mirror of codebase-indexer ``slug.parse_github_remote``.

    >>> parse_github_remote("git@github.com:navistone/TheForge.git")
    ('navistone', 'TheForge')
    >>> parse_github_remote("https://github.com/navistone/TheForge")
    ('navistone', 'TheForge')
    >>> parse_github_remote("https://gitlab.com/foo/bar.git") is None
    True
    """
    parsed = parse_git_remote(url)
    if parsed is None:
        return None
    host, org, repo = parsed
    if host not in _GITHUB_HOSTS or "/" in org:
        return None
    return (org, repo)


def canonical_slug_for_path(local_path: Path) -> str | None:
    """Return the canonical slug for ``local_path``'s single git origin.

    ``{org}__{repo}`` for github.com (unchanged, so existing per-repo indexes
    keep their key); ``{host}__{org}__{repo}`` for any other parseable host
    (GitLab, Bitbucket, self-hosted) — this is what makes two differently
    named checkouts of the same non-GitHub repo (e.g. a worktree) share an
    index instead of each falling back to their own basename. Refuses to
    guess when there are zero or multiple remotes (an ``origin`` fork plus an
    ``upstream`` would otherwise route the slug to the wrong project), or
    when the URL doesn't parse at all — the caller falls back to the
    basename in both cases.
    """
    path = Path(local_path)
    if not path.is_dir():
        return None
    try:
        remotes_proc = subprocess.run(
            ["git", "-C", str(path), "remote"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
        if remotes_proc.returncode != 0:
            return None
        remotes = [r.strip() for r in remotes_proc.stdout.splitlines() if r.strip()]
        if len(remotes) != 1 or remotes[0] != "origin":
            # Zero, multiple, or non-origin remote — ambiguous; use basename.
            return None

        url_proc = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
        if url_proc.returncode != 0:
            return None
        url = (url_proc.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("code_index.slug: git probe failed for %s — %s", path, exc)
        return None

    parsed = parse_git_remote(url)
    if parsed is None:
        return None
    host, org, repo = parsed
    if host in _GITHUB_HOSTS:
        return slugify_repo(f"{org}__{repo}")
    return slugify_repo(f"{host}__{org}__{repo}")


def derive_slug(local_path: Path, fallback_basename: str) -> str:
    """Canonical slug for ``local_path``, else the slugified basename.

    Mirror of codebase-indexer ``slug.derive_slug``.
    """
    canonical = canonical_slug_for_path(Path(local_path))
    if canonical:
        return canonical
    return slugify_repo(fallback_basename or "repo")


def repo_slug(project_root: Path) -> str:
    """The codebase-indexer slug for the repo at ``project_root``.

    Convenience wrapper: ``derive_slug(project_root, project_root.name)``.
    """
    project_root = Path(project_root)
    return derive_slug(project_root, project_root.name)
