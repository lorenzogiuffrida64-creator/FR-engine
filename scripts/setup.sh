#!/bin/sh
# One-time setup on a new machine (run from the repo root): hooks, private repo, .env, dependencies.
set -e
cd "$(dirname "$0")/.."
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/* scripts/*.py scripts/setup.sh
echo "git hooks installed (secret and private-data guard)"

if [ ! -d private/.git ]; then
  if [ -n "$FR_PRIVATE_REPO" ]; then
    git clone "$FR_PRIVATE_REPO" private && echo "private repo cloned into private/"
  else
    echo "private/ is missing: set FR_PRIVATE_REPO=<url of the private repo> and run again (needs access)"
  fi
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env created from .env.example: fill in the keys"
fi
chmod 600 .env

python3 -c "import PIL, numpy" 2>/dev/null && echo "python deps ok" || echo "install deps: python3 -m pip install --user pillow numpy"
python3 scripts/security_check.py --all
