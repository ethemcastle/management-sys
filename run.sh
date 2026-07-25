#!/usr/bin/env bash
# Run ALL of Cadence (production build + public HTTPS tunnel) in one command,
# then print the URL to paste into Ybug.
#
#   ./run.sh          build + start everything, print the URLs
#   ./run.sh down     stop everything (your data is kept on the volume)
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose -f docker-compose.prod.yml)

if [ "${1:-}" = "down" ]; then
  "${COMPOSE[@]}" down
  echo "Stopped. (Data kept — use '${COMPOSE[*]} down -v' to also wipe it.)"
  exit 0
fi

echo "▸ Building and starting Cadence…"
"${COMPOSE[@]}" up --build -d

echo "▸ Waiting for the public HTTPS URL (Cloudflare tunnel)…"
CID="$("${COMPOSE[@]}" ps -q tunnel)"
URL=""
for _ in $(seq 1 45); do
  URL="$(docker logs "$CID" 2>&1 | grep -oE 'https://[a-z0-9.-]+\.trycloudflare\.com' | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done

echo
echo "────────────────────────────────────────────────────────────"
echo "  Cadence is running"
echo "    Local:    http://localhost:8080"
if [ -n "$URL" ]; then
  echo "    Public:   $URL"
  echo
  echo "  Paste this into Ybug → Project settings → Integrations → Webhooks:"
  echo "    $URL/api/ybug/webhook"
else
  echo "    Public:   (not ready yet — check: ${COMPOSE[*]} logs tunnel)"
fi
echo "────────────────────────────────────────────────────────────"
