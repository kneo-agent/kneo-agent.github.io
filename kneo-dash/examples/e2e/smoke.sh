#!/usr/bin/env bash
# E2E fixture boot-smoke (0.6.0 B5, scaffolding-first). Proves the mock-OIDC ↔ Dashboard
# real-OIDC login works end-to-end: the stack boots, a full Authorization-Code + PKCE
# login completes, and /api/me resolves the operator with the role the IdP asserted.
# The Playwright role-matrix / live-SSE / negative-auth suites build on this same stack.
#
#   examples/e2e/smoke.sh
#
# Exits non-zero on any failure. Tears the stack down on exit.
set -euo pipefail
cd "$(dirname "$0")"

DC="docker compose -f docker-compose.yml"
cleanup() { $DC down -v >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "→ booting the E2E stack (mock-OIDC + kneo-serv + dash in OIDC mode)…"
$DC up -d

# Wait for the dash to answer liveness (its lifespan: store migrate + purge loop).
for i in $(seq 1 40); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8090/api/livez || true)" = "200" ] && break
  sleep 2
  [ "$i" = "40" ] && { echo "✗ dash never became live"; exit 1; }
done

# Drive a full Authorization-Code + PKCE login. `--resolve` maps the compose hostname to
# the published port so the browser-side (authorize/callback) reaches the same IdP the dash
# reaches on the network — the standard mock-OIDC dual-network trick.
JAR="$(mktemp)"; trap 'rm -f "$JAR"; cleanup' EXIT
curl -sS -c "$JAR" -b "$JAR" -L --resolve mock-oidc:8080:127.0.0.1 \
  -o /dev/null http://localhost:8090/api/login

ME="$(curl -sS -b "$JAR" http://localhost:8090/api/me)"
echo "  /api/me → $ME"

# The IdP asserts roles:["dash-operator"]; the role_map → the "operator" dashboard role.
echo "$ME" | grep -q '"role":"operator"' || { echo "✗ login did not resolve the operator role"; exit 1; }
echo "$ME" | grep -q '"identity":"e2e-operator@example.test"' || { echo "✗ unexpected identity"; exit 1; }

echo "✓ OIDC login round-trip OK — the mock-OIDC fixture drives the real auth path."
