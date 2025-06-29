// scripts/deploySentinel.js - FINAL ALL-IN-ONE VERSION
const hre = require("hardhat");
const fs = require('fs');
const path = require('path');
require('dotenv').config();

async function main() {
    console.log("🚀 Starting deployment of Sentinel AMM system...");

    // --- 1. All Configuration Inside This Script ---
    const networkConfig = {
        // Config for Hardhat local network (chainId 31337)
        31337: {
            name: 'localhost',
            uniswapFactory: "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            positionManager: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
            weth: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            usdc: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            feeTier: 3000,
            rangeWidthMultiplier: 100,
        },
        // Config for Ethereum Mainnet (chainId 1)
        1: {
            name: 'mainnet',
            priceFeed: "0x5F4ec3DF9CbD43714Fe274045F36413C88f58E50",
            // You can add other mainnet addresses here if needed
            uniswapFactory: "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            positionManager: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
            weth: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            usdc: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            feeTier: 3000,
            rangeWidthMultiplier: 100,
        }
    };

    // --- 2. Setup Environment ---
    const chainId = hre.network.config.chainId;
    const isTestEnvironment = chainId === 31337;
    const config = networkConfig[chainId];

    if (!config) {
        throw new Error(`No network configuration found for chainId: ${chainId}. Please add it to the networkConfig object.`);
    }

    if (!process.env.PRIVATE_KEY) {
        throw new Error("PRIVATE_KEY is not set in your .env file!");
    }
    const deployer = new hre.ethers.Wallet(process.env.PRIVATE_KEY, hre.ethers.provider);

    console.log(`🌍 Deploying on network: ${config.name} (ChainId: ${chainId})`);
    console.log("Deploying contracts with the account:", deployer.address);
    console.log("Account balance:", (await deployer.getBalance()).toString());

    let priceFeedAddress;

    // --- 3. Conditionally Deploy Mock or Use Real Address ---
    if (isTestEnvironment) {
        console.log("\n🧪 Test environment detected. Deploying MockAggregatorV3...");
        const MockAggregatorV3 = await hre.ethers.getContractFactory("MockAggregatorV3", deployer); // Connect factory to deployer
        const mockAggregator = await MockAggregatorV3.deploy();
        await mockAggregator.deployed();
        priceFeedAddress = mockAggregator.address;
        console.log(`✅ MockAggregatorV3 deployed to: ${priceFeedAddress}`);
    } else {
        console.log("\n🌐 Live or testnet environment detected. Using real Chainlink address.");
        priceFeedAddress = config.priceFeed;
        console.log(`✅ Using real Price Feed at: ${priceFeedAddress}`);
    }

    // --- 4. Deploy SentinelAMM Contract ---
    console.log("\n1. Deploying SentinelAMM...");
    const SentinelAMM = await hre.ethers.getContractFactory("SentinelAMM", deployer); // Connect factory to deployer
    const sentinelAmm = await SentinelAMM.deploy(
        config.uniswapFactory,
        config.positionManager,
        config.usdc,
        config.weth,
        config.feeTier,
        deployer.address, // Set deployer as owner
        config.rangeWidthMultiplier,
        priceFeedAddress
    );
    await sentinelAmm.deployed();
    console.log(`✅ SentinelAMM deployed to: ${sentinelAmm.address}`);

    // --- 5. Deploy AutomationTrigger Contract ---
    console.log("\n2. Deploying AutomationTrigger...");
    const AutomationTrigger = await hre.ethers.getContractFactory("AutomationTrigger", deployer); // Connect factory to deployer
    const automationTrigger = await AutomationTrigger.deploy(sentinelAmm.address);
    await automationTrigger.deployed();
    console.log(`✅ AutomationTrigger deployed to: ${automationTrigger.address}`);

    // --- 6. Authorize the Trigger ---
    console.log("\n3. Authorizing trigger contract...");
    const tx = await sentinelAmm.setAuthorizedCaller(automationTrigger.address);
    await tx.wait(1);
    console.log("✅ Authorization successful.");

    // --- 7. Save Deployed Addresses ---
    const addresses = {
        sentinelAmmAddress: sentinelAmm.address,
        automationTriggerAddress: automationTrigger.address,
        priceFeedInUse: priceFeedAddress
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