# Sentinel AMM: AI-Predictive Liquidity Automated & Secured by Chainlink

A predictive Automated Market Maker (AMM) strategy for Uniswap V3, secured by Chainlink Data Feeds and decentralized by Chainlink Automation.

**Submitted to the Chainlink Chromion Hackathon 2025**

## The Story: From a Predictive Model to a Fortified Protocol

Our journey began with a sophisticated research project aimed at revolutionizing AMM liquidity management. We developed a powerful system featuring:

- **Phase 1 (Data Collection):** A robust pipeline to gather historical market data.
- **Phase 2 (AI Prediction):** A trained LSTM model to proactively forecast market prices.
- **Phase 3 (Initial Implementation):** A smart contract, `PredictiveLiquidityManager`, that adjusted Uniswap V3 liquidity based on these AI predictions.

While innovative, our initial architecture had two critical vulnerabilities inherent in many DeFi projects:

1. **A Centralized Point of Failure:** The entire system relied on a centralized, off-chain script to trigger strategy adjustments. If our server went down, the strategy would halt.
2. **A Blind Trust Security Risk:** The smart contract blindly trusted the price predictions from our off-chain API. A faulty prediction, whether from a model bug or a malicious attack, could lead to catastrophic losses by placing liquidity in a disastrous range.

For the Chainlink Chromion Hackathon, we transformed this academic prototype into a production-ready, secure, and resilient protocol: **Sentinel AMM**.

We solved these core challenges by integrating two of Chainlink's cornerstone services:

- 🛡️ **Chainlink Data Feeds as a "Safety Guardrail":** Our smart contract no longer blindly trusts the AI's prediction. It first fetches the highly reliable, decentralized, and tamper-proof market price from Chainlink Data Feeds. If the AI's prediction deviates too far from this on-chain source of truth, the transaction is safely reverted, preventing flawed strategy execution.
- ⚙️ **Chainlink Automation as a "Decentralized Executor":** We replaced our fragile, centralized script with Chainlink's battle-tested, decentralized automation network. This ensures our strategy is executed reliably and consistently based on our predefined schedule (e.g., every 4 hours), completely removing our server as a single point of failure.

**Sentinel AMM is the evolution:** an intelligent strategy guarded by uncompromisable on-chain truth and driven by unstoppable on-chain automation.

## Core Architecture & Features

*(Note: Include a new diagram here that adds Chainlink Automation and Data Feeds to your previous flowchart.)*

1. **Decentralized Trigger (Chainlink Automation):**
   - A time-based Upkeep is registered with the Chainlink Automation network.
   - The network reliably calls our smart contract at a predefined interval (e.g., every 4 hours), ensuring consistent strategy execution without any centralized servers.

2. **AI Price Prediction (Off-Chain Brain):**
   - Our LSTM model, hosted on an external server, continues to serve as the "brain" of the operation, providing forward-looking market analysis.

3. **On-Chain Validation (Chainlink Data Feeds):**
   - The Sentinel AMM contract receives the prediction from the AI.
   - It immediately calls a Chainlink Data Feed (e.g., ETH/USD) to get the current, trusted market price.
   - It validates that the prediction is within a safe threshold (e.g., +/- 10%) of the real market price. If not, the operation is securely halted.

4. **Automated Liquidity Management (On-Chain Action):**
   - If the prediction is validated, the contract calculates the optimal new liquidity range based on the AI's price target.
   - It then atomically removes the old liquidity position and mints a new one in the new range on Uniswap V3.

## 🗂️ Project Structure

The repository is structured to highlight the core Sentinel AMM strategy. The original Baseline contract remains for historical context but is not the focus of this hackathon submission.
/
├── contracts/
│ ├── SentinelAMM.sol # The upgraded Predictive Manager, hardened by Chainlink.
│ ├── AutomationCompatible.sol # The contract that Chainlink Automation interacts with.
│ └── BaselineMinimal.sol # (For reference) The original spot-price strategy.
│
├── scripts/
│ ├── deploySentinel.js # Deploys SentinelAMM and the Automation contract.
│ └── deployMinimal.js # (For reference)
│
├── test/
│ └── sentinel/
│ └── sentinel_test.py # The primary test script for the Sentinel AMM strategy.
│
├── run_sentinel_test.sh # Master script to run the full test pipeline for Sentinel AMM.
├── .env # Environment variables (including Chainlink Price Feed address).
├── hardhat.config.js # Hardhat config for Mainnet forking.
├── requirements.txt # Python dependencies.
└── package.json # Node.js dependencies.


## ✅ How to Run

1. **Configure .env:** Set `MAINNET_RPC_URL`, `PRIVATE_KEY`, etc.
2. **Install Dependencies:** Run `npm install` and `pip install -r requirements.txt`.
3. **Execute the Test Pipeline:**
   ```bash
   chmod +x run_sentinel_test.sh
   ./run_sentinel_test.sh

This will start a Hardhat fork, deploy the contracts, and run the Python test script to simulate the Sentinel AMM strategy, validating its logic against Chainlink Data Feeds in a forked environment.