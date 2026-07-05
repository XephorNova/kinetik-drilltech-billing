#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "=============================================="
echo " Kinetik Drilltech Billing - Dev Startup"
echo "=============================================="
echo

# --- Resolve npm (works even if PATH hasn't picked up a fresh Node/Volta install yet) ---
if command -v npm &> /dev/null; then
    NPM="npm"
else
    NPM="/c/Program Files/Volta/npm.cmd"
fi

# --- Check MongoDB is reachable on the default port ---
if netstat -an 2>/dev/null | grep ":27017" | grep -q "LISTENING"; then
    echo "[OK] MongoDB detected on port 27017."
else
    echo "[WARN] Nothing is listening on port 27017 - make sure MongoDB is running."
fi

# --- Backend .env ---
if [ ! -f "$BACKEND/.env" ]; then
    cp "$BACKEND/.env.example" "$BACKEND/.env"
    echo "[INFO] Created backend/.env from .env.example - edit JWT_SECRET/ADMIN_PASSWORD before real use."
fi

# --- Backend venv ---
if [ ! -f "$BACKEND/.venv/Scripts/uvicorn.exe" ]; then
    echo "[ERROR] backend/.venv not found or incomplete."
    echo "        Run: cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt"
    exit 1
fi

# --- Frontend .env ---
if [ ! -f "$FRONTEND/.env" ]; then
    cp "$FRONTEND/.env.example" "$FRONTEND/.env"
    echo "[INFO] Created frontend/.env from .env.example"
fi

# --- Frontend deps ---
if [ ! -d "$FRONTEND/node_modules" ]; then
    echo "[INFO] Installing frontend dependencies, this may take a minute..."
    (cd "$FRONTEND" && "$NPM" install)
fi

echo
echo "Starting backend  - http://localhost:8000"
(cd "$BACKEND" && ./.venv/Scripts/uvicorn.exe app.main:app --reload --port 8000) &
BACKEND_PID=$!

echo "Starting frontend - http://localhost:5173"
(cd "$FRONTEND" && "$NPM" run dev) &
FRONTEND_PID=$!

echo
echo "Both services are running in the background (backend pid $BACKEND_PID, frontend pid $FRONTEND_PID)."
echo "Press Ctrl+C to stop both."
echo

trap 'echo; echo "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' EXIT INT TERM

wait
