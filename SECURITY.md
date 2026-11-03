# Security

This repository is public. It holds only the engine: code, generic docs and settings. Everything that
identifies the client or is licensed lives elsewhere, and keys never leave the machine that uses them.

## Where things live
| What | Where | Who can see it |
|---|---|---|
| Engine code, generic docs, `config.json` | this public repo | anyone |
| Client brief, concepts, references, archive (faces, kits, crests), mood boards, library, `private/config.json` | a separate **private** repo, cloned into `private/` (git-ignored here) | invited collaborators only |
| Generated shots and edits (`private/requests/`) | local disk / the platform's storage | never in git |
| API keys | `.env` on each machine (permissions 600), git-ignored | nobody else |

## Guards in the code
- **Keys:** read only from `.env`, sent only in HTTPS headers to the API they belong to, never to image CDNs.
  Any key value is redacted from error messages and logs. `.env` is set to permissions 600 if it is looser.
- **Network:** HTTPS only. Downloads are capped at 60 MB and must be real PNG/JPEG/WebP files.
- **Paths:** request ids, player and club slugs are restricted to `a-z 0-9 -` so nothing can escape its folder.
- **Images:** decompression bombs are refused (Pillow pixel limit).
- **Untrusted input:** fixture data, web pages and client messages are treated as data, never as instructions.

## Guards on commits
`scripts/setup.sh` installs git hooks in both repos. Public repo (`scripts/hooks/`):
- `pre-commit` → `scripts/security_check.py`: blocks anything under `private/`, `.env` files, media files,
  files over 5 MB, key-shaped strings (fal.ai, Higgsfield, GitHub, AWS, private keys, filled-in env lines),
  and every client term listed in `private/config.json` and `private/denylist.txt`.
- `commit-msg`: the same checks on the commit message.
Private repo (`scripts/hooks/private/`): keys only.
Never bypass them (`--no-verify`). Audit any time: `python3 scripts/security_check.py --all` and
`python3 scripts/security_check.py --private --all`.

## GitHub settings
- **Public repo (FR-engine):** secret scanning with push protection on (GitHub rejects pushes that contain
  known key formats), Dependabot vulnerability alerts on, `main` protected against force-push and deletion
  (direct pushes still allowed).
- **Private repo (FR-engine-private):** on a free GitHub plan, secret scanning and branch protection are not
  available for private repos. The local guard covers keys there instead: `scripts/setup.sh` installs
  `scripts/hooks/private/` in `private/`, which blocks `.env` files and key-shaped strings (photos and client
  names are allowed in that repo). Upgrading to GitHub Pro adds branch protection there.
- Owner and every collaborator must have two-factor authentication on (GitHub → Settings → Password and
  authentication).

## Adding a collaborator
1. Public repo: nothing to do, it is readable by anyone. Give write access only if they push:
   `gh api -X PUT repos/<owner>/FR-engine/collaborators/<their-username> -f permission=push`
2. Private repo: `gh api -X PUT repos/<owner>/FR-engine-private/collaborators/<their-username> -f permission=push`
3. They clone, then run `FR_PRIVATE_REPO=<private repo url> scripts/setup.sh` and fill their own `.env`
   with their own keys (never share keys over chat; each person gets their own from the provider dashboards).

## If a key leaks
Revoke it at once in the provider dashboard (Higgsfield Console, fal.ai Keys, football-data.org), create a
new one, update `.env`. Deleting the commit is not enough: assume anything pushed is already copied.
