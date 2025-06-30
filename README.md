Sentinel AMM: AI-Predictive Liquidity, Automated & Secured by Chainlink
An intelligent, automated liquidity management strategy for Uniswap V3 that leverages AI for price prediction, Chainlink Automation for decentralized execution, and Chainlink Price Feeds for on-chain security.

Submitted to the Chainlink Chronos Hackathon 2025

The Story: From a Predictive Model to a Fortified Protocol
Our journey began with a sophisticated research project to revolutionize AMM liquidity management. We developed a powerful system featuring an LSTM AI model to proactively forecast market prices and a smart contract that adjusted Uniswap V3 liquidity based on these predictions.

While innovative, this initial architecture had two critical vulnerabilities:

A Centralized Point of Failure: The entire system relied on a centralized server to trigger adjustments. If our server went down, the strategy would halt.

A Blind Trust Security Risk: The smart contract blindly trusted the price from our off-chain API. A faulty prediction could lead to catastrophic losses.

For this hackathon, we transformed this prototype into a production-ready, secure, and resilient protocol: Sentinel AMM.

We solved these core challenges by deeply integrating two of Chainlink's cornerstone services:

🛡️ Chainlink Price Feeds as a "Safety Guardrail": Our smart contract no longer blindly trusts the AI. It first fetches the highly reliable, decentralized market price from Chainlink Price Feeds. If the AI's prediction deviates too far from this on-chain source of truth, the transaction is safely reverted.

⚙️ Chainlink Automation as a "Decentralized Executor": We replaced our fragile, centralized script with Chainlink's battle-tested automation network. This ensures our strategy is executed reliably and consistently, removing our server as a single point of failure.

Sentinel AMM is the evolution: an intelligent strategy guarded by uncompromisable on-chain truth and driven by unstoppable on-chain automation.

🏛️ System Architecture
Our system seamlessly integrates an off-chain AI brain with an on-chain DeFi muscle, bridged and secured by the Chainlink network.

+--------------------------+         +--------------------------+         +---------------------------+
|     OFF-CHAIN (Brain)    |         |    CHAINLINK (Bridge)    |         |      ON-CHAIN (Muscle)    |
+--------------------------+         +--------------------------+         +---------------------------+
|                          |         |                          |         |                           |
|  [AI Price Model (LSTM)] | --► API | [Chainlink Automation]   | --► Call| [AutomationTrigger.sol]   |
|                          |         | (Time-based Trigger)     |         |                           |
|                          |         |                          |         |             |             |
|                          |         |                          |         |             ▼             |
|                          |         |                          |         |    [SentinelAMM.sol]      |
|                          |         |                          |         |      (The Vault)          |
|                          |         | [Chainlink Price Feed]   | --► Read|             |             |
|                          |         | (For On-Chain Security)  |         |             |             |
|                          |         |                          |         |             ▼             |
|                          |         |                          |         |      [Uniswap V3 Pool]    |
|                          |         |                          |         |                           |
+--------------------------+         +--------------------------+         +---------------------------+
🛠️ Technology Stack
Smart Contracts: Solidity, Hardhat, OpenZeppelin

Decentralized Services: 🔗 Chainlink Automation, 🔗 Chainlink Price Feeds

DeFi Protocol: 🦄 Uniswap V3

Off-Chain & Testing: 🐍 Python, web3.py, PyTorch

Development & Deployment: hardhat-deploy, ethers.js, Node.js

Infrastructure: Infura/Alchemy (for Mainnet Forking)

🔬 Technical Deep Dive & Code Highlights
1. The Safety Guardrail (Chainlink Price Feed)
To prevent bad predictions from causing losses, SentinelAMM.sol validates every AI prediction against the on-chain truth from a Chainlink Price Feed before adjusting the position.

Code Snippet (SentinelAMM.sol):

Solidity

function updatePredictionAndAdjust(
    int24 predictedTick,
    uint256 predictedPrice_8_decimals
) external nonReentrant onlyAuth {
    // --- 1. Sentinel Safety Guardrail ---
    (, int256 currentChainlinkPrice_8_decimals, , , ) = priceFeed.latestRoundData();
    require(
        currentChainlinkPrice_8_decimals > 0,
        "Sentinel: Invalid Chainlink price"
    );

    // Calculate deviation between AI prediction and Chainlink price
    uint256 difference = _getDifference(uint256(currentChainlinkPrice_8_decimals), predictedPrice_8_decimals);
    uint256 tenPercentOfCurrent = uint256(currentChainlinkPrice_8_decimals) / 10;

    // Revert if deviation is more than 10%
    require(
        difference <= tenPercentOfCurrent,
        "Sentinel: Prediction deviates too much!"
    );

    // --- 2. Core Logic ---
    // ... if validation passes, proceed with liquidity adjustment ...
}
2. The Decentralized Executor (Chainlink Automation)
Our AutomationTrigger.sol contract is a lightweight, secure entry point for the Chainlink Automation network. It implements the AutomationCompatibleInterface standard, making it fully compatible with the Chainlink Network.

Code Snippet (AutomationTrigger.sol):

Solidity

import "./interfaces/AutomationCompatibleInterface.sol";

contract AutomationTrigger is AutomationCompatibleInterface {
    ISentinelAMM public immutable sentinel;

    // ... constructor ...
    
    function checkUpkeep(...) external view override returns (bool upkeepNeeded, bytes memory performData) {
        upkeepNeeded = true; // For a time-based upkeep, always ready
        performData = "";
    }

    function performUpkeep(bytes calldata performData) external override {
        // In production, this is where Chainlink Functions would be called
        // to fetch the AI prediction before triggering the Sentinel.
    }
}
Note: For this hackathon demo, we use a manualTrigger() function to simulate the data flow from AI -> Chainlink Functions -> Smart Contract. The architecture is designed for a seamless upgrade to Chainlink Functions.

🗂️ Project Structure
/
├── contracts/
│   ├── SentinelAMM.sol               # The main vault, hardened by Chainlink.
│   ├── AutomationTrigger.sol         # The contract for Chainlink Automation.
│   └── mocks/
│       └── MockAggregatorV3.sol      # Mock Price Feed for reliable testing.
│
├── deploy/
│   └── 01-deploy-sentinel.js         # Smart deployment script for all contracts.
│
├── test/
│   ├── utils/                        # Python testing utilities.
│   └── sentinel_test.py              # The primary end-to-end test script.
│
├── .env.example                      # Example environment variables.
├── hardhat.config.js                 # Hardhat config with Mainnet forking enabled.
├── helper-hardhat-config.js          # Stores network-specific addresses for deployment.
├── requirements.txt                  # Python dependencies.
└── run_sentinel_test.sh              # Master script to run the full test pipeline.
🚀 Getting Started: How to Run the Test Pipeline
Follow these steps to run the complete end-to-end test simulation on a local Hardhat node.

1. Prerequisites
Node.js (v18 or later)

Python (v3.10 or later) & venv

2. Installation & Setup
1. Clone the repository:

Bash

git clone [Your-Repo-URL]
cd [Your-Repo-Folder]
2. Install Node.js dependencies:

Bash

npm install
3. Set up Python virtual environment and install dependencies:

Bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
4. Configure your Environment Variables:
Create a .env file in the project root by copying the example file.

Bash

cp .env.example .env
Now, open the .env file and add your own keys. A high-quality MAINNET_RPC_URL from Alchemy or Infura is required for forking.

Code snippet

# Get a free URL from a provider like Alchemy or Infura
MAINNET_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"

# Your Ethereum account private key (from MetaMask, etc.)
# IMPORTANT: This account will be used to deploy contracts and run tests.
PRIVATE_KEY="0x..."

# (Optional) Etherscan API key for contract verification
ETHERSCAN_API_KEY="..."

# Python Test Script Variables
PREDICTIVE_TARGET_WETH="10.0"
PREDICTIVE_TARGET_USDC="25000.0"
3. Execute the Test Pipeline
This single command will handle everything automatically.

Bash

# Make the script executable (only need to do this once)
chmod +x run_sentinel_test.sh

# Run the full test pipeline
bash run_sentinel_test.sh
What this script does:

Starts a local Hardhat node, forking from your MAINNET_RPC_URL to get Uniswap V3's state.

Runs the deployment script (deploy/01-deploy-sentinel.js), which intelligently deploys the mock oracle and all necessary contracts.

Executes the end-to-end Python test (test/sentinel_test.py).

The Python script simulates the full workflow: funding, minting a position, generating fees through swaps, and rebalancing the position.

All results are saved to position_results_sentinel.csv.

Finally, it shuts down the Hardhat node.

🔮 Future Work
Integrate Chainlink Functions: Replace the demo's simulated data flow with a fully decentralized off-chain computation solution to fetch predictions from our AI model.

Expand to L2s & More Pools: Deploy the system on Layer 2 networks like Arbitrum or Optimism and support a wider variety of trading pairs.

Develop a User Interface: Create a simple and intuitive UI for users to easily deposit and withdraw funds.

📄 License
This project is licensed under the MIT License.
