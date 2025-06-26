
# 🧠 Predictive vs Baseline Liquidity Manager

## 📁 Project Overview: Comparing Baseline and Predictive Liquidity Management Strategies

This project is designed to simulate and compare two liquidity provisioning strategies on Uniswap V3:

- **Baseline Strategy**: A simple approach that adjusts liquidity based on the current spot price from the Uniswap pool.
- **Predictive Strategy**: A smarter method that leverages predicted prices (e.g., from an external LSTM-based API) to proactively reposition liquidity.

---

## 🗂️ Project Structure

```
Phase3_Smart_Contract/
├── contracts/
│   ├── BaselineMinimal.sol                 # Basic spot-price strategy contract
│   └── PredictiveLiquidityManager.sol      # Prediction-based liquidity manager contract
├── scripts/
│   ├── deployMinimal.js                    # Deploys BaselineMinimal
│   └── deployPredictiveManager.js          # Deploys PredictiveLiquidityManager
├── test/
│   ├── baseline/
│   │   └── baseline_test.py                # Tests the Baseline strategy
│   ├── predictive/
│   │   └── predictive_test.py              # Tests the Predictive strategy
│   └── utils/
│       ├── fund_my_wallet.py              # Funds test account with ETH and tokens
│       ├── web3_utils.py                  # Web3 utility functions
│       └── test_base.py                   # Common test functionality
├── deployments/
│   ├── baselineMinimal_address.json        # Address of deployed Baseline contract
│   └── predictiveManager_address.json      # Address of deployed Predictive contract
├── run_fork_test.sh                        # Master shell script to orchestrate testing
├── .env                                    # Environment variables
├── hardhat.config.js                       # Hardhat config file for forking Mainnet
├── requirements.txt                        # Python dependencies
├── package.json                            # Node.js dependencies
```

---

## 🔁 Execution Workflow

### 1. Run `run_fork_test.sh`

- Loads environment variables from `.env`
- Starts a Hardhat local node forked from Ethereum Mainnet using `MAINNET_RPC_URL`
- Executes `fund_my_wallet.py` to fund the deployer account with ETH, WETH, and USDC
- Deploys both contracts (Baseline and Predictive) and stores their addresses in JSON files
- Runs Python test scripts to interact with and evaluate each strategy

### 2. Contract Address Management

Each deployment script saves the contract address to a file like:

```json
{
  "address": "0x123..."
}
```

The test scripts read from these JSON files using `json.load()` and pass the address to Web3 contract instances.

---

## 🧠 Smart Contracts

### ⚙️ BaselineMinimal.sol

- Objective: Manage liquidity based on current pool price using Uniswap V3 NonfungiblePositionManager
- Key Function: `adjustLiquidityWithCurrentPrice()`
  - Reads slot0 from Uniswap pool
  - Calculates lower/upper ticks using `tickSpacing` and `rangeWidthMultiplier`
  - If an active position exists and ticks are unchanged → do nothing
  - Otherwise → remove old position and create a new one
- Emits:
  - `BaselineAdjustmentMetrics`
  - `PositionStateChanged`
  - `PositionMinted`

### ⚙️ PredictiveLiquidityManager.sol

- Objective: Adjust liquidity using a predicted price (fetched from external API)
- Key Function: `updatePredictionAndAdjust(predictedTick)`
  - Converts predicted price to ticks
  - Checks proximity of new tick range to existing one using `_isTickRangeClose`
  - If significantly different → triggers `_adjustLiquidity()`
    - Calls `_removeLiquidity()` then `_mintLiquidity()`
- Emits:
  - `PredictionAdjustmentMetrics`
  - `LiquidityOperation`

- Handles decimals via `token0Decimals`, `token1Decimals` for accurate math
- Includes `uniswapV3MintCallback` as required by Uniswap

---

## 🧪 Python Tests

### 🧷 baseline_test.py

- Loads Baseline contract address from JSON
- Connects to Web3 local node
- Reads current pool price and tick
- Calls `adjustLiquidityWithCurrentPrice()`
- Records gas usage, liquidity changes, ticks, fees collected
- Saves output to `position_results_baseline.csv`

### 🧷 predictive_test.py

- Loads Predictive contract address from JSON
- Calls external API to fetch predicted price
- Converts to predicted tick using Uniswap tick formula
- Calls `updatePredictionAndAdjust(predictedTick)`
- Records liquidity changes and operation metrics
- Saves results to `position_results_predictive.csv`

---

## 🧰 Utilities

### 🔹 fund_my_wallet.py
- Impersonates whale accounts using Hardhat RPC
- Transfers USDC/WETH to deployer
- Uses `hardhat_impersonateAccount`, `setBalance`, and ERC20 transfer calls

### 🔹 web3_utils.py
- Functions to:
  - Load contract ABI from artifacts
  - Instantiate contract instances
  - Send and sign transactions

### 🔹 test_base.py
- Parent class with shared methods:
  - `get_pool_state()`
  - `calculate_tick_from_price()`
  - `get_position_info()`

---

## 📊 Output Files

| File Name | Description |
|-----------|-------------|
| `position_results_baseline.csv` | Results of Baseline strategy execution: ticks, price, gas, liquidity, fees |
| `position_results_predictive.csv` | Same fields as above, using predicted prices |

---

## 🔚 Summary

This system integrates:
- Smart contracts for dynamic liquidity rebalancing
- Python testing framework with Web3.py and API requests
- Automated environment using Hardhat fork + Bash scripting

It enables performance comparison between a reactive (spot price) strategy and a proactive (prediction-based) strategy under real market conditions.

---

## ✅ How to Run

1. Configure `.env`:
   ```env
   MAINNET_RPC_URL=...
   PRIVATE_KEY=...
   DEPLOYER_ADDRESS=...
   LSTM_API_URL=...
   ```

2. Run the test pipeline:
   ```bash
   chmod +x run_fork_test.sh
   ./run_fork_test.sh
   ```

3. Analyze CSV results for strategy comparison

---

For future enhancements:
- Improve prediction source (e.g., on-chain models)
- Incorporate dynamic gas optimization
- Support multi-asset strategies
