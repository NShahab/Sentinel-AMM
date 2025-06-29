// hardhat.config.js - FINAL AND CORRECTED VERSION
require("@nomicfoundation/hardhat-toolbox");
require("hardhat-deploy");
require("dotenv").config();

const MAINNET_RPC_URL = process.env.MAINNET_RPC_URL || "https://rpc.ankr.com/eth"; // Fallback RPC added
const PRIVATE_KEY = process.env.PRIVATE_KEY || "0xkey"; // Default dummy key
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "YourEtherscanApiKey"; // Default dummy key

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
            forking: {
                url: MAINNET_RPC_URL,
                // By OMITTING 'blockNumber', Hardhat will ALWAYS fork from the LATEST block.
                // This is the correct configuration to solve your Chainlink data issue.
            },
            // The accounts part from your config was not standard. 
            // Hardhat provides 20 test accounts with 10000 ETH by default.
            // No need to configure it unless you need a specific private key.
        },
        localhost: {
            url: "http://127.0.0.1:8545",
            chainId: 31337,
            timeout: 120000
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
        deployments: "./deployments"
    },
    mocha: {
        timeout: 200000, // Increased timeout for long-running fork tests
    },
};