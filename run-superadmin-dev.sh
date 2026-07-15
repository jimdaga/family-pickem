#!/usr/bin/env bash
# Run the feature/claude-vibing worktree dev server on :8001 with the scheduler
# enabled, borrowing DB/secret env from the already-running :8000 dev server so
# you don't have to re-enter credentials. Run this in your OWN terminal (not via
# Claude) so it stays up.
set -euo pipefail

MAIN_PID="$(lsof -ti:8000 | head -1 || true)"
if [ -z "${MAIN_PID}" ]; then
  echo "No dev server found on :8000 to borrow env from. Start your usual :8000 server first," >&2
  echo "or export DATABASE_* and SECRET_KEY yourself before running this." >&2
  exit 1
fi

# Pull the env the running server was started with.
eval "$(ps eww -p "${MAIN_PID}" | tr ' ' '\n' \
  | grep -E '^(SECRET_KEY|DATABASE_[A-Z]+|GOOGLE_OAUTH2_[A-Z]+)=' \
  | sed 's/^\([A-Z0-9_]*\)=\(.*\)$/export \1='"'"'\2'"'"'/')"

export DEBUG=True RUN_SCHEDULER=true RUN_WEB_SERVER=true

cd "$(dirname "$0")/pickem"
source /Users/jim/git/family-pickem/venv/bin/activate
exec python manage.py runserver 8001
