# #!/usr/bin/env bash
# # Start FastAPI (uvicorn) and Streamlit together. Run from repo root: ./start.sh
# set -euo pipefail

# ROOT="$(cd "$(dirname "$0")" && pwd)"
# cd "$ROOT"

# if [[ ! -d .venv ]]; then
#   echo "Missing .venv — run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
#   exit 1
# fi

# # shellcheck source=/dev/null
# source .venv/bin/activate

UVICORN_PORT="${UVICORN_PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

cleanup() {
  if [[ -n "${UV_PID:-}" ]]; then kill "$UV_PID" 2>/dev/null || true; fi
  if [[ -n "${ST_PID:-}" ]]; then kill "$ST_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI on http://0.0.0.0:${UVICORN_PORT} (docs: /docs)"
uvicorn app.main:app --host 0.0.0.0 --port "${UVICORN_PORT}" &
UV_PID=$!

echo "Starting Streamlit on http://0.0.0.0:${STREAMLIT_PORT}"
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port "${STREAMLIT_PORT}" &
ST_PID=$!

wait
