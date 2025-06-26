// hardhat.config.js
require("@nomicfoundation/hardhat-toolbox");
require("hardhat-deploy");
require("dotenv").config();

// Load environment variables. Rely ONLY on the .env file.
const MAINNET_RPC_URL = process.env.MAINNET_RPC_URL || "";
const PRIVATE_KEY = process.env.PRIVATE_KEY || "";
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "";

module.exports = {
    solidity: {
        compilers: [
            {
                version: "0.7.6",
                settings: {
                    optimizer: {
                        enabled: true,
                        runs: 200
                    }
                }
            }
        ]
    },
    defaultNetwork: "hardhat",
    networks: {
        hardhat: {
            chainId: 31337,
            forking: {
                url: MAINNET_RPC_URL,
                // blockNumber: 19600000, // Pin to specific block for consistency
                enabled: true
            },
            accounts: PRIVATE_KEY ?
                [{
                    privateKey: PRIVATE_KEY,
                    balance: "10000000000000000000000" // 10,000 ETH in wei
                }] :
                [],
            mining: {
                auto: true,
                interval: 5000
            }
        },
        localhost: {
            url: "http://127.0.0.1:8545",
            chainId: 31337,
            accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [], // Simplified account format
            timeout: 120000
        }
    },
    etherscan: {
        apiKey: ETHERSCAN_API_KEY
    },
    namedAccounts: {
        deployer: {
            default: 0, // First account will be deployer
            31337: 0, // Hardhat network
            1: 0 // Mainnet
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
        timeout: 180000 // 3 minutes timeout for tests
    },
    gasReporter: {
        enabled: process.env.REPORT_GAS ? true : false,
        currency: "USD"
    }
};