#!/bin/bash

# ==============================================================================
#                 Sentinel AMM Fork Test Automation Script
#
# Version: 5.0 (Sentinel Architecture)
# Description:
# Automates end-to-end testing of the Sentinel AMM strategy on a local
# Hardhat Mainnet fork. This version deploys both the SentinelAMM and
# AutomationTrigger contracts and runs the full-cycle Python test script.
# ==============================================================================

# --- Script Configuration ---
set -e -u -o pipefail # Exit on error, treat unset variables as an error, and fail on pipe errors

# --- PATH & Directory Setup ---
PROJECT_DIR_DEFAULT="/root/Sentinel-AMM/Phase3_Smart_Contract"
PROJECT_DIR="${FORK_TEST_PROJECT_DIR:-$PROJECT_DIR_DEFAULT}"
LOG_FILE_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_FILE_DIR"
LOG_FILE="$LOG_FILE_DIR/sentinel_test_run_$(date +%Y%m%d_%H%M%S).log"
HARDHAT_NODE_LOG_FILE="$LOG_FILE_DIR/hardhat_node_$(date +%Y%m%d_%H%M%S).log"

# --- MODIFIED: Script & File Paths ---
# Point to the new Sentinel-specific files
DEPLOY_SCRIPT_SENTINEL="$PROJECT_DIR/scripts/deploySentinel.js"
PYTHON_SCRIPT_SENTINEL="$PROJECT_DIR/test/sentinel_test.py"
FUNDING_SCRIPT="$PROJECT_DIR/test/utils/fund_my_wallet.py"
ENV_FILE="$PROJECT_DIR/.env"
ADDRESS_FILE_SENTINEL="$PROJECT_DIR/sentinel_addresses.json" # New JSON file for both addresses

# --- Network & Retry Configuration ---
LOCAL_RPC_URL="http://127.0.0.1:8545"
HARDHAT_PORT=8545
HARDHAT_HOST="127.0.0.1"
MAX_RETRIES=3
RETRY_DELAY=10 # Seconds

# --- Python Environment ---
VENV_ACTIVATE="$PROJECT_DIR/venv/bin/activate"

# --- Helper Functions (Preserved from your robust original script) ---
function log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

function validate_environment() {
    log "Validating environment prerequisites..."
    local all_ok=true
    local required_commands=(node npm python3 curl jq git)
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log "ERROR: Required command '$cmd' not found." && all_ok=false
        fi
    done

    # MODIFIED: Check for the new files
    local required_files=("$ENV_FILE" "$DEPLOY_SCRIPT_SENTINEL" "$PYTHON_SCRIPT_SENTINEL" "$FUNDING_SCRIPT")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log "ERROR: Required file '$file' not found." && all_ok=false
        fi
    done
    
    # Check for essential environment variables inside .env
    if [ -f "$ENV_FILE" ]; then
        local required_env_vars=("MAINNET_RPC_URL" "PRIVATE_KEY" "DEPLOYER_ADDRESS")
        for var_name in "${required_env_vars[@]}"; do
            if ! grep -q "^${var_name}=" "$ENV_FILE"; then
                 log "ERROR: Required environment variable '$var_name' is not set in $ENV_FILE." && all_ok=false
            fi
        done
    fi

    if [ "$all_ok" = false ]; then
        log "CRITICAL: Environment validation failed. Please fix the errors above." && exit 1
    fi
    log "Environment validation successful."
}

function kill_hardhat_node() {
    log "Attempting to stop any existing Hardhat node on port $HARDHAT_PORT..."
    PIDS=$(pgrep -f "hardhat node.*--port $HARDHAT_PORT" || true)
    if [ -n "$PIDS" ]; then
        kill $PIDS &>/dev/null || true
        sleep 2
        if pgrep -f "hardhat node.*--port $HARDHAT_PORT" &>/dev/null; then
            log "Node still running. Force killing (kill -9)..."
            kill -9 $PIDS &>/dev/null || true
        fi
    fi
    log "Hardhat node stopped or was not running."
}

function check_rpc_ready() {
    log "Checking if RPC at $LOCAL_RPC_URL is ready..."
    for attempt in $(seq 1 20); do
        if curl -s -X POST --data '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' -H "Content-Type: application/json" "$LOCAL_RPC_URL" --connect-timeout 5 | jq -e '.result' > /dev/null; then
            log "RPC is ready." && return 0
        fi
        log "RPC not ready yet (attempt $attempt/20). Retrying in 5 seconds..."
        sleep 5
    done
    log "ERROR: RPC did not become ready." && return 1
}

function run_python_test() {
    local script_path="$1"
    local test_name="$2"
    log "Running Python test: $test_name..."
    if python3 -u "$script_path"; then
        log "✅ $test_name test completed successfully." && return 0
    else
        log "❌ ERROR: $test_name test failed. Check $LOG_FILE for traceback." && return 1
    fi
}

# --- MAIN SCRIPT EXECUTION ---
exec > >(tee -a "$LOG_FILE") 2>&1 # Redirect all output to log file and console

log "=============================================="
log "🚀 Starting Sentinel AMM Test Automation 🚀"
log "=============================================="

# --- 1. SETUP ---
log "--- [1/5] Performing Setup ---"
validate_environment
cd "$PROJECT_DIR" || exit 1
log "Changed directory to $(pwd)"

log "Cleaning and compiling contracts..."
# Ensure old artifacts are gone before compiling with multiple compiler versions
npx hardhat clean 
npx hardhat compile

if [ -f "$VENV_ACTIVATE" ]; then
    log "Activating Python virtual environment..."
    source "$VENV_ACTIVATE"
fi

log "Loading environment variables from $ENV_FILE..."
set -o allexport
source "$ENV_FILE"
set +o allexport

# --- 2. START FORK ---
log "--- [2/5] Starting Hardhat Mainnet Fork ---"
kill_hardhat_node
# MODIFIED: Remove the new address file before deployment
rm -f "$ADDRESS_FILE_SENTINEL"

log "Starting Hardhat node with Mainnet fork..."
# The logic to get the latest block is good, but for speed, we can let Hardhat choose.
# You can add back your LATEST_BLOCK logic here if needed.
nohup npx hardhat node --hostname "$HARDHAT_HOST" --port "$HARDHAT_PORT" > "$HARDHAT_NODE_LOG_FILE" 2>&1 &
HARDHAT_PID=$!
log "Hardhat node started with PID: $HARDHAT_PID. Waiting for RPC to become ready..."

if ! check_rpc_ready; then
    log "CRITICAL: Hardhat node failed to start. Check $HARDHAT_NODE_LOG_FILE."
    kill_hardhat_node
    exit 1
fi
# This ensures the Python scripts use the local fork
export MAINNET_FORK_RPC_URL="$LOCAL_RPC_URL"

# --- 3. FUND WALLETS ---
log "--- [3/5] Funding Wallets ---"
if ! python3 -u "$FUNDING_SCRIPT"; then
    log "CRITICAL: Wallet funding script failed. Check logs."
    kill "$HARDHAT_PID"; exit 1
fi
log "Wallet funding complete."

# --- 4. DEPLOY CONTRACTS & RUN TESTS (MODIFIED SECTION) ---
log "--- [4/5] Deploying Contracts & Running Test ---"

# Deploy both contracts using the new deployment script
log "Deploying Sentinel AMM system (SentinelAMM & AutomationTrigger)..."
if ! npx hardhat run "$DEPLOY_SCRIPT_SENTINEL" --network localhost; then
    log "CRITICAL: Sentinel deployment script failed."
    kill "$HARDHAT_PID"; exit 1
fi

# Export BOTH deployed addresses for the Python script
log "Exporting contract addresses for Python test environment..."
if [ -f "$ADDRESS_FILE_SENTINEL" ]; then
    # Use jq to parse the new JSON file and export variables
    export SENTINEL_AMM_ADDRESS=$(jq -r '.sentinelAmmAddress' "$ADDRESS_FILE_SENTINEL")
    export AUTOMATION_TRIGGER_ADDRESS=$(jq -r '.automationTriggerAddress' "$ADDRESS_FILE_SENTINEL")
    log "  -> Exported SENTINEL_AMM_ADDRESS=${SENTINEL_AMM_ADDRESS}"
    log "  -> Exported AUTOMATION_TRIGGER_ADDRESS=${AUTOMATION_TRIGGER_ADDRESS}"
else
    log "CRITICAL: Sentinel address file not found after deployment!"; kill "$HARDHAT_PID"; exit 1
fi

# Run the single, comprehensive Sentinel test
sentinel_test_status=1
run_python_test "$PYTHON_SCRIPT_SENTINEL" "Sentinel Full-Cycle Strategy"
sentinel_test_status=$?

# --- 5. TEARDOWN & SUMMARY ---
log "--- [5/5] Performing Teardown & Summary ---"
log "Stopping Hardhat node (PID: $HARDHAT_PID)..."
kill "$HARDHAT_PID"
sleep 2
kill_hardhat_node # Final cleanup check

if type deactivate &> /dev/null && [[ -n "${VIRTUAL_ENV-}" ]]; then
    log "Deactivating Python virtual environment..."
    deactivate
fi

log "=============================================="
log "✅ Test Automation Script Completed ✅"
log "=============================================="
log "Sentinel Test Result: $( [ $sentinel_test_status -eq 0 ] && echo "🎉 SUCCESS" || echo "❌ FAILURE" )"
log "Detailed logs available in: $LOG_FILE"
log "Hardhat node logs (if any issues): $HARDHAT_NODE_LOG_FILE"

# Exit with the status of the test run
exit $sentinel_test_status