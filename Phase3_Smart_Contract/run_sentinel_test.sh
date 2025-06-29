#!/bin/bash

# ==============================================================================
#                 Sentinel AMM Fork Test Automation Script
#
# Version: 5.2 (Increased Timeout & Typo Fix)
# ==============================================================================

# --- Script Configuration ---
set -e -u -o pipefail

# --- PATH & Directory Setup ---
PROJECT_DIR_DEFAULT="/root/Sentinel-AMM/Phase3_Smart_Contract"
PROJECT_DIR="${FORK_TEST_PROJECT_DIR:-$PROJECT_DIR_DEFAULT}"
LOG_FILE_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_FILE_DIR"
LOG_FILE="$LOG_FILE_DIR/sentinel_test_run_$(date +%Y%m%d_%H%M%S).log"
HARDHAT_NODE_LOG_FILE="$LOG_FILE_DIR/hardhat_node_$(date +%Y%m%d_%H%M%S).log"

# --- Script & File Paths ---
DEPLOY_SCRIPT_SENTINEL="$PROJECT_DIR/scripts/deploySentinel.js"
PYTHON_SCRIPT_SENTINEL="$PROJECT_DIR/test/sentinel_test.py"
FUNDING_SCRIPT="$PROJECT_DIR/test/utils/fund_my_wallet.py"
ENV_FILE="$PROJECT_DIR/.env"
ADDRESS_FILE_SENTINEL="$PROJECT_DIR/sentinel_addresses.json"

# --- Network Configuration ---
LOCAL_RPC_URL="http://127.0.0.1:8545"
HARDHAT_PORT=8545
HARDHAT_HOST="127.0.0.1"

# --- Helper Functions ---
function log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

function kill_hardhat_node() {
    log "Attempting to stop any existing Hardhat node on port $HARDHAT_PORT..."
    PIDS=$(pgrep -f "hardhat node.*--port $HARDHAT_PORT" || true)
    if [ -n "$PIDS" ]; then
        kill $PIDS &>/dev/null || true; sleep 2
        if pgrep -f "hardhat node.*--port $HARDHAT_PORT" &>/dev/null; then
            log "Node still running. Force killing (kill -9)..."
            kill -9 $PIDS &>/dev/null || true
        fi
    fi
    log "Hardhat node stopped or was not running."
}

# --- MAIN SCRIPT EXECUTION ---
exec > >(tee -a "$LOG_FILE") 2>&1

log "=============================================="
log "🚀 Starting Sentinel AMM Test Automation 🚀"
log "=============================================="

log "--- [1/4] Performing Setup ---"
cd "$PROJECT_DIR" || exit 1
log "Changed directory to $(pwd)"

log "Compiling contracts (if needed)..."
npx hardhat compile

if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    log "Activating Python virtual environment..."
    source "$PROJECT_DIR/venv/bin/activate"
fi

log "Loading environment variables from $ENV_FILE..."
set -o allexport; source "$ENV_FILE"; set +o allexport

log "--- [2/4] Starting Hardhat Mainnet Fork ---"
kill_hardhat_node
rm -f "$ADDRESS_FILE_SENTINEL"

log "Starting Hardhat node in the background..."
npx hardhat node --hostname "$HARDHAT_HOST" --port "$HARDHAT_PORT" > "$HARDHAT_NODE_LOG_FILE" 2>&1 &
HARDHAT_PID=$!
# MODIFIED: Increased sleep time to give the fork more time to initialize
log "Hardhat node launched with PID: $HARDHAT_PID. Waiting 25 seconds for initialization..."
sleep 25

# Check if the Hardhat process is still running
if ! ps -p $HARDHAT_PID > /dev/null; then
    log "------------------------------------------------------------------"
    log "❌ CRITICAL: Hardhat node process (PID $HARDHAT_PID) is NOT running."
    log "Displaying the last 20 lines of the node log file for debugging:"
    log "--- LOG START ---"
    # CORRECTED: Fixed the variable name typo
    tail -n 20 "$HARDHAT_NODE_LOG_FILE"
    log "--- LOG END ---"
    log "------------------------------------------------------------------"
    exit 1
else
    log "✅ Hardhat node process is still alive. Checking RPC port..."
fi

# Check if RPC port is now ready
if ! curl -s -X POST --data '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' -H "Content-Type: application/json" "$LOCAL_RPC_URL" --connect-timeout 10 | jq -e '.result' > /dev/null; then
     log "------------------------------------------------------------------"
     log "❌ CRITICAL: Hardhat node process is running, but RPC port is not responding."
     log "Displaying the last 20 lines of the node log file for debugging:"
     log "--- LOG START ---"
     # CORRECTED: Fixed the variable name typo
     tail -n 20 "$HARDHAT_NODE_LOG_FILE"
     log "--- LOG END ---"
     log "------------------------------------------------------------------"
     kill_hardhat_node
     exit 1
fi

log "✅ RPC is ready. Proceeding with tests."
export MAINNET_FORK_RPC_URL="$LOCAL_RPC_URL"

# --- 3. FUND, DEPLOY & TEST ---
log "--- [3/4] Funding, Deploying, and Testing ---"
log "Funding deployer account..."
if ! python3 -u "$FUNDING_SCRIPT"; then
    log "CRITICAL: Wallet funding script failed." && kill_hardhat_node && exit 1
fi

log "Deploying Sentinel AMM system..."
if ! npx hardhat run "$DEPLOY_SCRIPT_SENTINEL" --network localhost; then
    log "CRITICAL: Sentinel deployment script failed." && kill_hardhat_node && exit 1
fi

log "Exporting contract addresses for Python script..."
if [ -f "$ADDRESS_FILE_SENTINEL" ]; then
    export SENTINEL_AMM_ADDRESS=$(jq -r '.sentinelAmmAddress' "$ADDRESS_FILE_SENTINEL")
    export AUTOMATION_TRIGGER_ADDRESS=$(jq -r '.automationTriggerAddress' "$ADDRESS_FILE_SENTINEL")
else
    log "CRITICAL: Address file not found after deployment!"; kill_hardhat_node && exit 1
fi

log "Running the main Python test script..."
test_status=0
if ! python3 -u "$PYTHON_SCRIPT_SENTINEL"; then
    log "❌ ERROR: Python test script failed."
    test_status=1
else
    log "✅ Python test script completed successfully."
fi

# --- 4. TEARDOWN & SUMMARY ---
log "--- [4/4] Performing Teardown & Summary ---"
kill_hardhat_node

if type deactivate &> /dev/null && [[ -n "${VIRTUAL_ENV-}" ]]; then
    log "Deactivating Python virtual environment..."
    deactivate
fi

log "=============================================="
log "✅ Test Automation Script Completed ✅"
log "=============================================="
log "Final Test Result: $( [ $test_status -eq 0 ] && echo "🎉 SUCCESS" || echo "❌ FAILURE" )"
log "Detailed logs available in: $LOG_FILE"
log "=============================================="

exit $test_status