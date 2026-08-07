#!/usr/bin/env bash
# Live-weekend simulation harness (DEV ONLY). Brings up throwaway Redis + an
# ASGI server, points the site at the isolated demo season (9999), replays a
# dramatized ~13-game weekend in ~5 min, then restores everything.
#
# Usage: scripts/live-sim.sh <your-username> [duration_seconds]
set -euo pipefail

OWNER="${1:?Usage: scripts/live-sim.sh <your-username> [duration_seconds]}"
DURATION="${2:-300}"
REDIS_NAME="pickem-live-sim-redis"
PORT=8000
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/pickem"

export DEBUG=True
export REDIS_URL="redis://localhost:6379/0"

UVICORN_PID=""
OLD_SEASON=""

cleanup() {
  echo "== teardown =="
  if [[ -n "$OLD_SEASON" ]]; then
    # Restore the captured real season via a tiny shell one-liner.
    uv run python manage.py shell -c \
      "from pickem_api.models import currentSeason as c; r=c.objects.first();\
 r and (setattr(r,'season',$OLD_SEASON) or r.save(update_fields=['season']))" \
      >/dev/null 2>&1 || true
  fi
  uv run python manage.py seed_demo_weekend --wipe >/dev/null 2>&1 || true
  [[ -n "$UVICORN_PID" ]] && kill "$UVICORN_PID" >/dev/null 2>&1 || true
  docker rm -f "$REDIS_NAME" >/dev/null 2>&1 || true
  echo "== done =="
}
trap cleanup EXIT INT TERM

echo "== starting throwaway Redis =="
docker rm -f "$REDIS_NAME" >/dev/null 2>&1 || true
docker run -d --rm -p 6379:6379 --name "$REDIS_NAME" redis:7-alpine >/dev/null

echo "== launching uvicorn on :$PORT =="
uv run uvicorn pickem.asgi:application --host 0.0.0.0 --port "$PORT" \
  --log-level warning &
UVICORN_PID=$!

echo "== waiting for /healthz/ =="
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:$PORT/healthz/" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -sf "http://localhost:$PORT/healthz/" >/dev/null || { echo "server never came up"; exit 1; }

echo "== capturing current season =="
OLD_SEASON="$(uv run python manage.py seed_demo_weekend --print-current-season | tail -n1 | tr -dc '0-9')"
echo "captured season: ${OLD_SEASON:-<none>}"

echo "== seeding demo weekend + pointing season at 9999 =="
uv run python manage.py seed_demo_weekend --owner "$OWNER"
uv run python manage.py seed_demo_weekend --make-current

cat <<EOF

  ┌───────────────────────────────────────────────────────────┐
  │ Open http://localhost:$PORT and sign in as $OWNER
  │ Watch:  /scores  (select Week 1)
  │         the lobby Week Points panel  (demo family/pool)
  │         /standings
  │ Simulation runs for ${DURATION}s. Ctrl-C to stop early (auto-cleans up).
  └───────────────────────────────────────────────────────────┘

EOF

echo "== running simulation (${DURATION}s) =="
uv run python manage.py simulate_weekend --duration "$DURATION"

echo "Simulation finished; cleaning up."
