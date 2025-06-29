// hardhat.config.js - FINAL, CORRECTED FORKING-ENABLED VERSION
require("@nomicfoundation/hardhat-toolbox");
require("hardhat-deploy");
require("dotenv").config();

const MAINNET_RPC_URL = process.env.MAINNET_RPC_URL || "";
const PRIVATE_KEY = process.env.PRIVATE_KEY || "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "YourEtherscanApiKey";

module.exports = {
    solidity: {
        version: "0.8.20",
        settings: {
            optimizer: {
                enabled: true,
                runs: 200,
            },
        },
    },
    defaultNetwork: "hardhat",
    networks: {
        hardhat: {
            chainId: 31337,
            // Forking IS ENABLED. This is necessary for Uniswap V3 contracts to exist.
            forking: {
                url: MAINNET_RPC_URL,
                // By not specifying a 'blockNumber', it will use the latest block.
                // This requires a high-quality RPC URL from Alchemy or Infura.
            },
        },
        localhost: {
            url: "http://127.0.0.1:8545",
            chainId: 31337,
        }
    },
    etherscan: {
        apiKey: {
            mainnet: ETHERSCAN_API_KEY,
        }
    },
    namedAccounts: {
        deployer: {
            default: 0,
        }
    },
    paths: {
        sources: "./contracts",
        tests: "./test",
        cache: "./cache",
        artifacts: "./artifacts",
        deployments: "deployments"
    },
    mocha: {
        timeout: 300000, // Increased timeout for forking
    },
};