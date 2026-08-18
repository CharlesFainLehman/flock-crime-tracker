"""Shared progress-commit helper: push data/ mid-run so git log is a live feed
and interrupted runs lose minimal work. Failures are non-fatal — the workflow's
end-of-run commit step is the backstop."""

import subprocess

from config import REPO_ROOT


def _branch() -> str:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
                         capture_output=True, text=True)
    b = out.stdout.strip()
    return b if b and b != "HEAD" else "main"


def push_progress(message: str) -> None:
    git = ["git", "-C", str(REPO_ROOT),
           "-c", "user.name=flock-tracker-bot",
           "-c", "user.email=actions@users.noreply.github.com"]
    try:
        subprocess.run(git + ["add", "data"], check=True, capture_output=True)
        diff = subprocess.run(git + ["diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            return
        subprocess.run(git + ["commit", "-m", message], check=True, capture_output=True)
        subprocess.run(git + ["pull", "--rebase", "--autostash", "origin", _branch()],
                       check=True, capture_output=True)
        subprocess.run(git + ["push"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"  progress push failed (non-fatal): {e.stderr or e}")
