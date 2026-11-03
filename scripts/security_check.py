#!/usr/bin/env python3
"""Block secrets and private material from reaching the public repository.

  security_check.py              # check the staged files (used by the pre-commit hook)
  security_check.py --all        # check every tracked file (manual audit / CI)
  security_check.py --message F  # check a commit message file (used by the commit-msg hook)

Blocks: anything under private/, .env files, files over 5 MB, images, key-shaped strings, and every term
listed by the private repo (client names, contacts) when private/ is present on this machine.
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
SECRET_PATTERNS = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key"),
    (r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}", "GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{40,}", "GitHub token"),
    (r"\bsk-[A-Za-z0-9_\-]{20,}", "API secret key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32}\b", "fal.ai key"),
    (r"Key\s+[A-Za-z0-9\-]{16,}:[A-Za-z0-9\-]{16,}", "Higgsfield credentials"),
    (r"(?m)^[ \t]*(HF_API_KEY_ID|HF_API_KEY_SECRET|FAL_KEY|FOOTBALL_DATA_TOKEN)[ \t]*=[ \t]*[^\s#]+", "filled-in key in an env file"),
    (r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/+]{20,}['\"]", "hard-coded secret"),
]
BLOCKED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".pdf", ".mp4", ".mov", ".opus", ".zip"}


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=False).stdout


def private_terms():
    """Terms that identify the client, read from the private repo (absent on machines without access)."""
    terms = set()
    priv = ROOT / "private"
    cfg = priv / "config.json"
    if cfg.exists():
        client = json.loads(cfg.read_text()).get("client", {})
        for k in ("name", "contact", "instagram"):
            v = client.get(k)
            if v:
                terms.add(v)
                terms.update(w for w in v.split() if len(w) > 3)
    deny = priv / "denylist.txt"
    if deny.exists():
        terms.update(t.strip() for t in deny.read_text().splitlines() if t.strip() and not t.startswith("#"))
    return sorted(terms, key=len, reverse=True)


def check_text(label, text, terms):
    problems = []
    for pat, what in SECRET_PATTERNS:
        if re.search(pat, text):
            problems.append(f"{label}: looks like a {what}")
    low = text.lower()
    for t in terms:
        if re.search(rf"(?<![a-z0-9]){re.escape(t.lower())}(?![a-z0-9])", low):
            problems.append(f"{label}: contains private term '{t}'")
    return problems


def check_files(paths, staged):
    terms, problems = private_terms(), []
    for p in paths:
        if not p:
            continue
        path = pathlib.PurePosixPath(p)
        if path.parts and path.parts[0] in ("private", "private.local"):
            problems.append(f"{p}: files under private/ never go in the public repo"); continue
        if path.name == ".env" or (path.name.startswith(".env") and path.name != ".env.example"):
            problems.append(f"{p}: env files hold keys"); continue
        if path.suffix.lower() in BLOCKED_EXT:
            problems.append(f"{p}: media files stay out of the public repo"); continue
        data = git("show", f":{p}") if staged else (ROOT / p).read_bytes() if (ROOT / p).exists() else b""
        if len(data) > MAX_BYTES:
            problems.append(f"{p}: larger than 5 MB"); continue
        if p == "scripts/security_check.py":
            continue  # holds the patterns themselves
        problems += check_text(p, data.decode(errors="ignore"), terms)
    return problems


def main():
    args = sys.argv[1:]
    if args[:1] == ["--message"]:
        problems = check_text("commit message", pathlib.Path(args[1]).read_text(), private_terms())
    elif args[:1] == ["--all"]:
        problems = check_files(git("ls-files").decode().splitlines(), staged=False)
    else:
        files = git("diff", "--cached", "--name-only", "--diff-filter=ACMR").decode().splitlines()
        problems = check_files(files, staged=True)
    if problems:
        print("security check FAILED, nothing was committed:", file=sys.stderr)
        for x in problems:
            print("  - " + x, file=sys.stderr)
        print("Fix the content (move client material to private/). Do not bypass this check.", file=sys.stderr)
        sys.exit(1)
    print("security check ok")


if __name__ == "__main__":
    main()
