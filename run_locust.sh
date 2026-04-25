#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if ! command -v locust &>/dev/null; then
    echo "locust not found — installing..."
    pip install locust -q
fi

# Open the browser once the server is up
(sleep 2 && xdg-open http://localhost:8089) &

echo "Locust UI  → http://localhost:8089"
echo "Target app → http://localhost:8000"
echo "Press Ctrl+C to stop."
echo ""

locust --host http://localhost:8000
