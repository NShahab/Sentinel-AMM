// scripts/deploySentinel.js
const hre = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("🚀 Starting deployment of Sentinel AMM system...");

    // --- Mainnet Addresses ---
    const UNISWAP_V3_FACTORY_MAINNET = "0x1F98431c8aD98523631AE4a59f267346ea31F984";
    const POSITION_MANAGER_MAINNET = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88";
    const WETH_MAINNET = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2";
    const USDC_MAINNET = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48";

    // NEW: Chainlink ETH/USD Price Feed on Mainnet
    const CHAINLINK_ETH_USD_FEED = "0x5f4eC3Df9cbd43714FE274045F36413C88f58e50";

    const POOL_FEE = 500; // 0.05%
    const INITIAL_RANGE_WIDTH_MULTIPLIER = 100;

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying contracts with the account:", deployer.address);
    console.log("Account balance:", (await deployer.getBalance()).toString());

    // --- 1. Deploy SentinelAMM Contract ---
    console.log("\n1. Deploying SentinelAMM...");
    const SentinelAMM = await hre.ethers.getContractFactory("SentinelAMM");
    const constructorToken0 = WETH_MAINNET < USDC_MAINNET ? WETH_MAINNET : USDC_MAINNET;
    const constructorToken1 = WETH_MAINNET < USDC_MAINNET ? USDC_MAINNET : WETH_MAINNET;

    const sentinelAmm = await SentinelAMM.deploy(
        UNISWAP_V3_FACTORY_MAINNET,
        POSITION_MANAGER_MAINNET,
        constructorToken0,
        constructorToken1,
        POOL_FEE,
        deployer.address,
        INITIAL_RANGE_WIDTH_MULTIPLIER,
        CHAINLINK_ETH_USD_FEED // Pass the new oracle address
    );
    await sentinelAmm.deployed();
    console.log(`✅ SentinelAMM deployed to: ${sentinelAmm.address}`);

    // --- 2. Deploy AutomationTrigger Contract ---
    console.log("\n2. Deploying AutomationTrigger...");
    const AutomationTrigger = await hre.ethers.getContractFactory("AutomationTrigger");
    const automationTrigger = await AutomationTrigger.deploy(
        sentinelAmm.address // Pass the deployed SentinelAMM address to the trigger
    );
    await automationTrigger.deployed();
    console.log(`✅ AutomationTrigger deployed to: ${automationTrigger.address}`);

    // --- 3. Save Deployed Addresses ---
    const addresses = {
        sentinelAmmAddress: sentinelAmm.address,
        automationTriggerAddress: automationTrigger.address
    };
    const outputPath = path.join(__dirname, '..', 'sentinel_addresses.json');
    fs.writeFileSync(outputPath, JSON.stringify(addresses, null, 2));
    console.log(`\n📄 Deployed addresses saved to ${outputPath}`);

    console.log("\n🎉 Deployment complete!");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("Deployment script failed:", error);
        process.exit(1);
    });