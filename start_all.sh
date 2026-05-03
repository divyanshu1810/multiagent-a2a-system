#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start_all.sh  –  Launch the full Multi-Agent A2A Ecosystem
# Usage: bash start_all.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[start_all]${RESET} $*"; }
ok()   { echo -e "${GREEN}✔${RESET} $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
die()  { echo -e "${RED}✘ $*${RESET}"; exit 1; }

# ── Trap: kill all child processes on Ctrl-C ──────────────────────────────────
PIDS=()
cleanup() {
    echo ""
    log "Shutting down all services …"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null && echo "  killed PID $pid"
    done
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Sanity checks ─────────────────────────────────────────────────────────────
[[ -f ".env" ]] || die ".env not found. Copy .env.example → .env and set COHERE_API_KEY."

source .env
[[ -n "$COHERE_API_KEY" ]] || die "COHERE_API_KEY is not set in .env"

# Activate venv if present
if [[ -d ".venv" ]]; then
    source .venv/bin/activate
    ok "Virtual environment activated"
else
    warn "No .venv found – using system Python. Run: uv venv && uv pip install -e ."
fi

# ── Build vector store if not already done ────────────────────────────────────
CHROMA_DIR="${CHROMA_DB_DIR:-./chroma_db}"
if [[ ! -d "$CHROMA_DIR" ]]; then
    log "Vector store not found – building now (this may take a minute) …"
    python -m mcp_server_1.vector_store
    ok "Vector store built at $CHROMA_DIR"
else
    ok "Vector store already exists at $CHROMA_DIR"
fi

# ── Logs directory ────────────────────────────────────────────────────────────
mkdir -p logs

# ── Helper: start a service in background ────────────────────────────────────
start_service() {
    local name="$1"
    local module="$2"
    local port="$3"
    local logfile="logs/${name}.log"

    log "Starting ${BOLD}${name}${RESET} (port ${port}) …"
    python -m "$module" > "$logfile" 2>&1 &
    local pid=$!
    PIDS+=("$pid")

    # Wait up to 8 s for the port to open
    for i in $(seq 1 16); do
        sleep 0.5
        if lsof -i ":${port}" -sTCP:LISTEN -t >/dev/null 2>&1 || \
           ss -tlnp 2>/dev/null | grep -q ":${port} "; then
            ok "${name} is up  →  http://localhost:${port}   (PID ${pid}, log: ${logfile})"
            return 0
        fi
    done

    warn "${name} did not open port ${port} within 8 s – check ${logfile}"
}

# ── Start services in dependency order ───────────────────────────────────────

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}   Multi-Agent A2A Ecosystem – Starting all services          ${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# MCP Servers (no inter-dependencies)
start_service "mcp_server_1" "mcp_server_1.server" "${MCP_SERVER_1_PORT:-8001}"
start_service "mcp_server_2" "mcp_server_2.server" "${MCP_SERVER_2_PORT:-8002}"
start_service "mcp_server_3" "mcp_server_3.server" "${MCP_SERVER_3_PORT:-8003}"

# Remote Agents (depend on MCP servers)
start_service "remote_agent_1" "remote_agent_1.server" "${REMOTE_AGENT_1_PORT:-8010}"
start_service "remote_agent_2" "remote_agent_2.server" "${REMOTE_AGENT_2_PORT:-8011}"

# Host Agent + Gradio UI (depends on remote agents)
start_service "host_agent" "host_agent.app" "7860"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  All services started!${RESET}"
echo ""
echo -e "  MCP Server 1 (RAG Retriever)      →  http://localhost:${MCP_SERVER_1_PORT:-8001}/mcp"
echo -e "  MCP Server 2 (Products & Orders)  →  http://localhost:${MCP_SERVER_2_PORT:-8002}/mcp"
echo -e "  MCP Server 3 (Policy Resources)   →  http://localhost:${MCP_SERVER_3_PORT:-8003}/mcp"
echo -e "  Remote Agent 1 (LangGraph CRAG)   →  http://localhost:${REMOTE_AGENT_1_PORT:-8010}"
echo -e "  Remote Agent 2 (Agno Workflow)    →  http://localhost:${REMOTE_AGENT_2_PORT:-8011}"
echo -e "  ${BOLD}Gradio UI${RESET}                         →  ${GREEN}http://localhost:7860${RESET}"
echo ""
echo -e "  Logs: ./logs/   |   Press ${BOLD}Ctrl-C${RESET} to stop everything."
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# ── Keep script alive (wait for all children) ─────────────────────────────────
wait