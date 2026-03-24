#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Alt Data Platform ==="
echo ""

# Copy .env if not present
if [ ! -f "$ROOT/backend/.env" ]; then
  if [ -f "$ROOT/.env.example" ]; then
    cp "$ROOT/.env.example" "$ROOT/backend/.env"
    echo "Copied .env.example to backend/.env"
  fi
fi

# Backend
echo "Starting backend..."
cd "$ROOT/backend"

if ! command -v uvicorn &>/dev/null; then
  echo "Installing Python dependencies..."
  pip install -r requirements.txt
fi

uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Frontend
echo ""
echo "Starting frontend..."
cd "$ROOT/frontend"

if [ ! -d node_modules ]; then
  echo "Installing npm packages..."
  npm install
fi

# Copy env for frontend
if [ ! -f .env.local ]; then
  echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local
fi

npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "==================================="
echo "Backend:  http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop both servers"

# Cleanup on exit
cleanup() {
  echo "Stopping servers..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Stopped."
}
trap cleanup EXIT INT TERM

wait
