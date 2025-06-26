#!/bin/bash

# ==============================================================================
#                 Optimized DEX Fork Test Automation Script
#
# Version: 4.1 (Combined & Hardened)
# Description:
# Automates end-to-end testing of DEX strategies on a local Hardhat Mainnet fork.
# This version merges the clean, unified workflow of v4.0 with the robust
# validation and error-checking capabilities of v2.4.
# ==============================================================================

# --- Script Configuration ---
set -e -u -o pipefail

# --- PATH & Directory Setup ---
PROJECT_DIR_DEFAULT="/root/Uni-Dex-Marketplace_test/Phase3_Smart_Contract"
PROJECT_DIR="${FORK_TEST_PROJECT_DIR:-$PROJECT_DIR_DEFAULT}"
LOG_FILE_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_FILE_DIR"
LOG_FILE="$LOG_FILE_DIR/fork_test_run_$(date +%Y%m%d_%H%M%S).log"
HARDHAT_NODE_LOG_FILE="$LOG_FILE_DIR/hardhat_node_$(date +%Y%m%d_%H%M%S).log"

# --- Script & File Paths ---
DEPLOY_SCRIPT_PREDICTIVE="$PROJECT_DIR/scripts/deployPredictiveManager.js"
DEPLOY_SCRIPT_BASELINE="$PROJECT_DIR/scripts/deployMinimal.js"
DEPLOY_SCRIPT_TOKEN_MANAGER="$PROJECT_DIR/scripts/deployTokenManagerOptimized.js"
PYTHON_SCRIPT_PREDICTIVE="$PROJECT_DIR/test/predictive/predictive_test.py"
PYTHON_SCRIPT_BASELINE="$PROJECT_DIR/test/baseline/baseline_test.py"
FUNDING_SCRIPT="$PROJECT_DIR/test/utils/fund_my_wallet.py"
ENV_FILE="$PROJECT_DIR/.env"

# --- Address Files (Generated during deployment) ---
ADDRESS_FILE_PREDICTIVE="$PROJECT_DIR/predictiveManager_address.json"
ADDRESS_FILE_BASELINE="$PROJECT_DIR/baselineMinimal_address.json"
ADDRESS_FILE_TOKEN_MANAGER="$PROJECT_DIR/tokenManagerOptimized_address.json"

# --- Network & Retry Configuration ---
LOCAL_RPC_URL="http://127.0.0.1:8545"
HARDHAT_PORT=8545
HARDHAT_HOST="127.0.0.1" # Use 0.0.0.0 to allow external connections (e.g., from Docker)
MAX_RETRIES=3
RETRY_DELAY=10 # Seconds

# --- Python Environment ---
VENV_ACTIVATE="$PROJECT_DIR/venv/bin/activate"

# --- Helper Functions ---

# Logs a message to both the console and the main log file.
function log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# (ENHANCED from v2.4) Validates that all required commands, files, and ENV variables are present.
function validate_environment() {
    log "Validating environment prerequisites..."
    local all_ok=true
    local required_commands=(node npm python3 curl jq git)
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log "ERROR: Required command '$cmd' not found."
            all_ok=false
        fi
    done

    local required_files=("$ENV_FILE" "$DEPLOY_SCRIPT_PREDICTIVE" "$DEPLOY_SCRIPT_BASELINE" \
                          "$PYTHON_SCRIPT_PREDICTIVE" "$PYTHON_SCRIPT_BASELINE" "$FUNDING_SCRIPT")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log "ERROR: Required file '$file' not found."
            all_ok=false
        fi
    done
    
    # (ADDED from v2.4) Check for essential environment variables inside .env
    if [ -f "$ENV_FILE" ]; then
        local temp_env_vars
        temp_env_vars=$(grep -v '^#' "$ENV_FILE" | grep -v '^$') # Read non-comment, non-empty lines
        local required_env_vars=("MAINNET_RPC_URL" "PRIVATE_KEY" "DEPLOYER_ADDRESS")
        for var_name in "${required_env_vars[@]}"; do
            if ! echo "$temp_env_vars" | grep -q "^${var_name}="; then
                 log "ERROR: Required environment variable '$var_name' is not set in $ENV_FILE."
                 all_ok=false
            fi
        done
    fi

    if [ "$all_ok" = false ]; then
        log "CRITICAL: Environment validation failed. Please fix the errors above."
        exit 1
    fi
    log "Environment validation successful."
}

# Stops any running Hardhat node on the configured port.
function kill_hardhat_node() {
    log "Attempting to stop any existing Hardhat node on port $HARDHAT_PORT..."
    # Use pgrep to find process IDs by name and arguments
    PIDS=$(pgrep -f "hardhat node.*--port $HARDHAT_PORT" || true)
    if [ -n "$PIDS" ]; then
        # First, try to kill gracefully
        kill $PIDS &>/dev/null || true
        sleep 2
        # Check if it's still running and force kill if necessary
        if pgrep -f "hardhat node.*--port $HARDHAT_PORT" &>/dev/null; then
            log "Node still running. Force killing (kill -9)..."
            kill -9 $PIDS &>/dev/null || true
        fi
    fi
    log "Hardhat node stopped or was not running."
}


# Checks if the Hardhat RPC is ready to accept connections.
function check_rpc_ready() {
    log "Checking if RPC at $LOCAL_RPC_URL is ready..."
    for attempt in $(seq 1 20); do
        if curl -s -X POST --data '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}' \
           -H "Content-Type: application/json" "$LOCAL_RPC_URL" --connect-timeout 5 --max-time 10 2>/dev/null | jq -e '.result' > /dev/null; then
            log "RPC is ready."
            return 0 # Success
        fi
        log "RPC not ready yet (attempt $attempt/20). Retrying in 5 seconds..."
        sleep 5
    done
    log "ERROR: RPC did not become ready."
    return 1 # Failure
}

# A robust function to deploy a single contract with retries.
function deploy_contract() {
    local script_path="$1"
    local address_file="$2"
    local contract_name="$3"

    log "Deploying $contract_name..."
    rm -f "$address_file"

    for attempt in $(seq 1 $MAX_RETRIES); do
        log "Attempt $attempt of $MAX_RETRIES to deploy $contract_name..."
        if npx hardhat run "$script_path" --network localhost >> "$LOG_FILE" 2>&1; then
            # (ENHANCED from v2.4) More robust check for valid address file and content
            if [ -f "$address_file" ] && [[ "$(jq -r '.address' "$address_file" 2>/dev/null)" =~ ^0x[a-fA-F0-9]{40}$ ]]; then
                log "? $contract_name deployed successfully!"
                return 0 # Success
            else
                log "ERROR: Deployment script ran, but address file '$address_file' is missing or its content is invalid."
            fi
        else
            log "ERROR: Hardhat deployment script failed for $contract_name on attempt $attempt."
        fi

        if [ "$attempt" -lt "$MAX_RETRIES" ]; then
            log "Retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        fi
    done

    log "FATAL: Failed to deploy $contract_name after $MAX_RETRIES attempts."
    return 1 # Failure
}

# A wrapper function to run a Python test.
function run_python_test() {
    local script_path="$1"
    local test_name="$2"
    log "Running Python test: $test_name..."
    if python3 -u "$script_path" >> "$LOG_FILE" 2>&1; then
        log "? $test_name test completed successfully."
        return 0
    else
        log "? ERROR: $test_name test failed. Check $LOG_FILE for traceback."
        return 1
    fi
}

# --- MAIN SCRIPT EXECUTION ---
# Redirect all script output to log file and console using a process substitution
exec > >(tee -a "$LOG_FILE") 2>&1

log "=============================================="
log "?? Starting DEX Fork Test Automation Script ??"
log "=============================================="

# --- 1. SETUP ---
log "--- [1/5] Performing Setup ---"
validate_environment
cd "$PROJECT_DIR" || exit 1
log "Changed directory to $(pwd)"

log "Cleaning and compiling contracts..."
npx hardhat clean
npx hardhat compile

# Activate Python environment
if [ -f "$VENV_ACTIVATE" ]; then
    log "Activating Python virtual environment..."
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
    log "Python virtual environment activated: $(command -v python3)"
else
    log "WARNING: Python venv not found. Using system Python."
fi

# Load environment variables from .env
log "Loading environment variables from $ENV_FILE..."
set -o allexport
# shellcheck source=/dev/null
source "$ENV_FILE"
set +o allexport
log "Environment variables loaded."

# --- 2. START FORK ---
log "--- [2/5] Starting Hardhat Mainnet Fork ---"
kill_hardhat_node
rm -f "$ADDRESS_FILE_PREDICTIVE" "$ADDRESS_FILE_BASELINE" "$ADDRESS_FILE_TOKEN_MANAGER"

log "Fetching latest block number from Mainnet..."
log "DEBUG: About to call curl. The value of MAINNET_RPC_URL is:"
log "DEBUG: -->${MAINNET_RPC_URL}<--"
LATEST_BLOCK_HEX=$(curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' "$MAINNET_RPC_URL" | jq -r '.result')
if [[ "$LATEST_BLOCK_HEX" =~ ^0x[a-fA-F0-9]+$ ]]; then
    LATEST_BLOCK_DEC=$((LATEST_BLOCK_HEX))
    log "Forking from block number: $LATEST_BLOCK_DEC"
else
    log "CRITICAL: Failed to fetch valid block number. Response: $LATEST_BLOCK_HEX"
    exit 1
fi
log "Setting NODE_OPTIONS to increase memory for Hardhat..."
export NODE_OPTIONS=--max-old-space-size=4096

log "Starting Hardhat node with Mainnet fork pinned to block $LATEST_BLOCK_DEC..."
# (ENHANCED from v2.4) Added --hostname for more flexibility
nohup npx hardhat node --hostname "$HARDHAT_HOST" --port "$HARDHAT_PORT" \
    --fork "$MAINNET_RPC_URL" --fork-block-number "$LATEST_BLOCK_DEC" > "$HARDHAT_NODE_LOG_FILE" 2>&1 &
HARDHAT_PID=$!
log "Hardhat node started with PID: $HARDHAT_PID. Waiting for RPC to become ready..."

if ! check_rpc_ready; then
    log "CRITICAL: Hardhat node failed to start. Check $HARDHAT_NODE_LOG_FILE."
    kill_hardhat_node
    exit 1
fi
export MAINNET_FORK_RPC_URL="$LOCAL_RPC_URL"

# --- 3. FUND WALLETS ---
log "--- [3/5] Funding Wallets ---"
log "Funding deployer account..."
if ! python3 -u "$FUNDING_SCRIPT"; then
    log "CRITICAL: Wallet funding script failed. Check logs."
    kill "$HARDHAT_PID"
    exit 1
fi
log "Wallet funding complete."

# --- 4. DEPLOY CONTRACTS & RUN TESTS ---
log "--- [4/5] Deploying Contracts & Running Tests ---"

# Deploy all contracts first
if ! deploy_contract "$DEPLOY_SCRIPT_PREDICTIVE" "$ADDRESS_FILE_PREDICTIVE" "PredictiveManager"; then exit 1; fi
if ! deploy_contract "$DEPLOY_SCRIPT_BASELINE" "$ADDRESS_FILE_BASELINE" "BaselineMinimal"; then exit 1; fi
if ! deploy_contract "$DEPLOY_SCRIPT_TOKEN_MANAGER" "$ADDRESS_FILE_TOKEN_MANAGER" "TokenManagerOptimized"; then exit 1; fi

# (ADDED from v2.4) Export all addresses for the Python scripts with validation
log "Exporting contract addresses for Python test environment..."
if [ -f "$ADDRESS_FILE_PREDICTIVE" ]; then
    export PREDICTIVE_MANAGER_ADDRESS=$(jq -r '.address' "$ADDRESS_FILE_PREDICTIVE")
    log "Exported PREDICTIVE_MANAGER_ADDRESS=${PREDICTIVE_MANAGER_ADDRESS}"
else log "CRITICAL: Predictive address file not found after deployment!"; exit 1; fi

if [ -f "$ADDRESS_FILE_BASELINE" ]; then
    export BASELINE_MINIMAL_ADDRESS=$(jq -r '.address' "$ADDRESS_FILE_BASELINE")
    log "Exported BASELINE_MINIMAL_ADDRESS=${BASELINE_MINIMAL_ADDRESS}"
else log "CRITICAL: Baseline address file not found after deployment!"; exit 1; fi

if [ -f "$ADDRESS_FILE_TOKEN_MANAGER" ]; then
    export TOKEN_MANAGER_OPTIMIZED_ADDRESS=$(jq -r '.address' "$ADDRESS_FILE_TOKEN_MANAGER")
    log "Exported TOKEN_MANAGER_OPTIMIZED_ADDRESS=${TOKEN_MANAGER_OPTIMIZED_ADDRESS}"
else log "CRITICAL: Token Manager address file not found after deployment!"; exit 1; fi

# Run tests sequentially
predictive_test_status=1
baseline_test_status=1

run_python_test "$PYTHON_SCRIPT_PREDICTIVE" "Predictive Strategy"
predictive_test_status=$?

run_python_test "$PYTHON_SCRIPT_BASELINE" "Baseline Strategy"
baseline_test_status=$?

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
log "?? Test Automation Script Completed ??"
log "=============================================="
log "Predictive Test Result: $( [ $predictive_test_status -eq 0 ] && echo "? SUCCESS" || echo "? FAILURE" )"
log "Baseline Test Result:   $( [ $baseline_test_status -eq 0 ] && echo "? SUCCESS" || echo "? FAILURE" )"
log "Detailed logs available in: $LOG_FILE"
log "Hardhat node logs (if any issues): $HARDHAT_NODE_LOG_FILE"

if [ $predictive_test_status -ne 0 ] || [ $baseline_test_status -ne 0 ]; then
    exit 1
fi
exit 0