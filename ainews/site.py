"""The `digests` branch, checked out as a git worktree at build/site.

Runs read state from it and publish to it. `main` is never written by a Run.
Commits use the Run's own git identity (the owner's): routines refuse to push to a
branch that carries commits by anyone else.
"""

import subprocess
import time

from ainews import config


def git(*args, cwd=config.ROOT, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def branch():
    return config.settings()["digests_branch"]


def checkout():
    """Bring build/site up to date with the remote `digests` branch, creating it if needed."""
    git("worktree", "prune")
    remote_exists = git("ls-remote", "--exit-code", "--heads", "origin", branch(),
                        check=False).returncode == 0
    if remote_exists:
        git("fetch", "origin", f"{branch()}:refs/remotes/origin/{branch()}")
        start = f"origin/{branch()}"
    else:
        # First ever Run: start the branch from an empty commit, unrelated to `main`.
        empty_tree = git("hash-object", "-t", "tree", "/dev/null").stdout.strip()
        start = git("commit-tree", empty_tree, "-m", "Start digests branch").stdout.strip()

    if (config.SITE / ".git").exists():
        git("checkout", "-B", branch(), start, cwd=config.SITE)
        git("reset", "--hard", start, cwd=config.SITE)
        git("clean", "-fd", cwd=config.SITE)
    else:
        config.BUILD.mkdir(exist_ok=True)
        git("worktree", "add", "-f", "-B", branch(), str(config.SITE), start)


def publish(date):
    """Commit everything in build/site and push it. Retries the push."""
    git("add", "-A", cwd=config.SITE)
    if git("diff", "--cached", "--quiet", cwd=config.SITE, check=False).returncode != 0:
        git("commit", "-m", f"Digest {date}", cwd=config.SITE)
    attempts = config.settings()["fetch_attempts"]
    for attempt in range(attempts):
        result = git("push", "origin", f"{branch()}:{branch()}", cwd=config.SITE, check=False)
        if result.returncode == 0:
            return
        if attempt == attempts - 1:
            raise RuntimeError(f"git push failed: {result.stderr.strip()[:500]}")
        time.sleep(2**attempt)
