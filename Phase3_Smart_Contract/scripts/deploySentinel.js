// scripts/deploySentinel.js - FINAL AND ROBUST VERSION
const hre = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("🚀 Starting deployment of Sentinel AMM system...");

    // --- Mainnet Addresses (Ensuring Valid Checksums using getAddress) ---
    const getAddress = hre.ethers.utils.getAddress;

    const UNISWAP_V3_FACTORY_MAINNET = getAddress("0x1f98431c8ad98523631ae4a59f267346ea31f984");
    const POSITION_MANAGER_MAINNET = getAddress("0xc36442b4a4522e871399cd717abdd847ab11fe88");
    const WETH_MAINNET = getAddress("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2");
    const USDC_MAINNET = getAddress("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48");
    const CHAINLINK_ETH_USD_FEED = getAddress("0x5f4ec3df9cbd43714fe274045f36413c88f58e50");

    const POOL_FEE = 500;
    const INITIAL_RANGE_WIDTH_MULTIPLIER = 100;

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying contracts with the account:", deployer.address);
    console.log("Account balance:", (await deployer.getBalance()).toString());

    // --- 1. Deploy SentinelAMM Contract ---
    console.log("\n1. Deploying SentinelAMM...");
    const SentinelAMM = await hre.ethers.getContractFactory("SentinelAMM");

    // Ensure correct token order for the pool
    const token0 = WETH_MAINNET.toLowerCase() < USDC_MAINNET.toLowerCase() ? WETH_MAINNET : USDC_MAINNET;
    const token1 = WETH_MAINNET.toLowerCase() < USDC_MAINNET.toLowerCase() ? USDC_MAINNET : WETH_MAINNET;

    const sentinelAmm = await SentinelAMM.deploy(
        UNISWAP_V3_FACTORY_MAINNET,
        POSITION_MANAGER_MAINNET,
        token0,
        token1,
        POOL_FEE,
        deployer.address,
        INITIAL_RANGE_WIDTH_MULTIPLIER,
        CHAINLINK_ETH_USD_FEED
    );
    await sentinelAmm.deployed();
    console.log(`✅ SentinelAMM deployed to: ${sentinelAmm.address}`);

    // --- 2. Deploy AutomationTrigger Contract ---
    console.log("\n2. Deploying AutomationTrigger...");
    const AutomationTrigger = await hre.ethers.getContractFactory("AutomationTrigger");
    const automationTrigger = await AutomationTrigger.deploy(sentinelAmm.address);
    await automationTrigger.deployed();
    console.log(`✅ AutomationTrigger deployed to: ${automationTrigger.address}`);

    // NEW: Set the AutomationTrigger as an authorized caller on the SentinelAMM contract
    console.log("\n3. Authorizing trigger contract...");
    const tx = await sentinelAmm.setAuthorizedCaller(automationTrigger.address);
    await tx.wait(1);
    console.log("✅ Authorization successful.");

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
