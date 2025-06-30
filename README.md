Sentinel AMM: AI-Predictive Liquidity Automated & Secured by Chainlink
An intelligent, automated liquidity management strategy for Uniswap V3 that leverages AI for price prediction, Chainlink Automation for decentralized execution, and Chainlink Price Feeds for on-chain security.

Submitted to the Chainlink Chronos Hackathon 2025

The Story: From a Predictive Model to a Fortified Protocol
Our journey began with a sophisticated research project. We developed a powerful system featuring an LSTM AI model to proactively forecast market prices and a smart contract (PredictiveLiquidityManager) that adjusted Uniswap V3 liquidity based on these AI predictions.

While innovative, this initial architecture had two critical vulnerabilities:

A Centralized Point of Failure: The entire system relied on a centralized server to trigger adjustments. If our server went down, the strategy would halt.

A Blind Trust Security Risk: The smart contract blindly trusted the price from our off-chain API. A faulty prediction could lead to catastrophic losses.

For this hackathon, we transformed this prototype into a production-ready, secure, and resilient protocol: Sentinel AMM.

We solved these core challenges by deeply integrating two of Chainlink's cornerstone services:

🛡️ Chainlink Price Feeds as a "Safety Guardrail": Our smart contract no longer blindly trusts the AI. It first fetches the highly reliable, decentralized market price from Chainlink Price Feeds. If the AI's prediction deviates too far from this on-chain source of truth, the transaction is safely reverted.

⚙️ Chainlink Automation as a "Decentralized Executor": We replaced our fragile, centralized script with Chainlink's battle-tested automation network. This ensures our strategy is executed reliably and consistently, completely removing our server as a single point of failure.

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

Off-Chain & Testing: 🐍 Python, web3.py, PyTorch, hardhat-deploy, ethers.js

Infrastructure: Node.js, Infura/Alchemy (for forking)

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
    // ... proceed with liquidity adjustment ...
}
2. The Decentralized Executor (Chainlink Automation)
Our AutomationTrigger.sol contract is a lightweight, secure entry point for the Chainlink Automation network. It implements the AutomationCompatibleInterface standard.

Code Snippet (AutomationTrigger.sol):

Solidity

import "./interfaces/AutomationCompatibleInterface.sol";

contract AutomationTrigger is AutomationCompatibleInterface {
    ISentinelAMM public immutable sentinel;
    address public immutable owner;

    constructor(address _sentinelAddress) {
        sentinel = ISentinelAMM(_sentinelAddress);
        owner = msg.sender;
    }
    
    function checkUpkeep(...) external view override returns (bool upkeepNeeded, bytes memory performData) {
        upkeepNeeded = true; // For a time-based upkeep, always ready
        performData = "";
    }

    function performUpkeep(bytes calldata performData) external override {
        // In a production system, this is where Chainlink Functions would
        // be called to fetch the AI prediction before triggering the Sentinel.
        // For the demo, we use manualTrigger to simulate this data flow.
    }

    // Demo function to simulate data input from AI -> Chainlink Functions
    function manualTrigger(int24 predictedTick, uint256 predictedPrice_8_decimals) external {
        require(msg.sender == owner, "Only owner can trigger manually");
        sentinel.updatePredictionAndAdjust(predictedTick, predictedPrice_8_decimals);
    }
}
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
├── scripts/
│   └── deploySentinel.js             # (Reference) An alternative ethers.js deploy script.
│
├── test/
│   ├── utils/                        # Python testing utilities.
│   └── sentinel_test.py              # The primary end-to-end test script.
│
├── .env.example                      # Example environment variables.
├── hardhat.config.js                 # Hardhat config with Mainnet forking.
├── helper-hardhat-config.js          # Stores network-specific addresses.
├── requirements.txt                  # Python dependencies.
└── run_sentinel_test.sh              # Master script to run the full test pipeline.
🚀 Getting Started: How to Run the Test Pipeline
Follow these steps to run the complete end-to-end test simulation.

1. Prerequisites
Node.js (v18 or later)

Python (v3.10 or later)

venv for Python virtual environments

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
Now, open the .env file and add your own keys:

Code snippet

# Get a free URL from a provider like Alchemy or Infura
MAINNET_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY"

# Your Ethereum account private key (from MetaMask, etc.)
# IMPORTANT: This account will be used to deploy contracts and run tests.
PRIVATE_KEY="0x..."

# (Optional) Etherscan API key for contract verification
ETHERSCAN_API_KEY="..."

# These are for the Python test script
PREDICTIVE_TARGET_WETH="10.0"
PREDICTIVE_TARGET_USDC="25000.0"
3. Execute the Test Pipeline
Run the master script. This single command will handle everything automatically.

Bash

# Make the script executable (only need to do this once)
chmod +x run_sentinel_test.sh

# Run the full test pipeline
bash run_sentinel_test.sh
What this script does:

Starts a local Hardhat node, forking from your MAINNET_RPC_URL.

Runs the deployment script (deploy/01-deploy-sentinel.js) which intelligently deploys the mock oracle and all necessary contracts.

Executes the end-to-end Python test (test/sentinel_test.py).

The Python script simulates funding the contract, creating a position, generating fees through swaps, and rebalancing the position.

All results are saved to position_results_sentinel.csv.

Finally, it shuts down the Hardhat node.

🔮 Future Work
Integrate Chainlink Functions: Replace the demo manualTrigger with a fully decentralized off-chain computation solution to fetch predictions from our AI model.

Expand to L2s & More Pools: Deploy the system on Layer 2 networks like Arbitrum or Optimism and support a wider variety of trading pairs.

Develop a User Interface: Create a simple and intuitive UI for users to deposit and withdraw their funds.

📄 License
This project is licensed under the MIT License.