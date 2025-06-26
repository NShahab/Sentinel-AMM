// scripts/deployMinimal.js
const hre = require("hardhat");
const { ethers } = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("Starting BaselineMinimal deployment process on the forked network...");

    // --- Mainnet Addresses ---
    const UNISWAP_V3_FACTORY_MAINNET = "0x1F98431c8aD98523631AE4a59f267346ea31F984";
    const POSITION_MANAGER_MAINNET = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88";
    const WETH_MAINNET = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2";
    const USDC_MAINNET = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"; // Mainnet USDC (6 decimals)
    const POOL_FEE = 500; // 0.05% fee tier for WETH/USDC (as per your file)
    const INITIAL_RANGE_WIDTH_MULTIPLIER_BASELINE = 100; // Default or desired value

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying contracts with the account:", deployer.address);
    console.log("Account balance:", (await deployer.getBalance()).toString());

    // --- Verify Pool Existence ---
    console.log(`Checking if the mainnet pool exists (WETH/USDC Fee: ${POOL_FEE})...`);
    const factory = await hre.ethers.getContractAt("IUniswapV3Factory", UNISWAP_V3_FACTORY_MAINNET);
    const token0ForPool = USDC_MAINNET < WETH_MAINNET ? USDC_MAINNET : WETH_MAINNET;
    const token1ForPool = USDC_MAINNET < WETH_MAINNET ? WETH_MAINNET : USDC_MAINNET;
    const poolAddress = await factory.getPool(token0ForPool, token1ForPool, POOL_FEE);

    if (poolAddress === "0x0000000000000000000000000000000000000000") {
        console.error(`ERROR: Pool ${token0ForPool}/${token1ForPool} with fee ${POOL_FEE} does not exist on Mainnet Fork!`);
        process.exit(1);
    } else {
        console.log(`Pool exists on Mainnet Fork at: ${poolAddress}`);
    }

    // --- Deploy BaselineMinimal contract ---
    console.log("\nDeploying BaselineMinimal contract...");
    const BaselineMinimal = await hre.ethers.getContractFactory("BaselineMinimal");
    const constructorToken0 = USDC_MAINNET < WETH_MAINNET ? USDC_MAINNET : WETH_MAINNET;
    const constructorToken1 = USDC_MAINNET < WETH_MAINNET ? WETH_MAINNET : USDC_MAINNET;

    console.log("\nDeploying BaselineMinimal with parameters:");
    console.log("  Factory:", UNISWAP_V3_FACTORY_MAINNET);
    console.log("  Position Manager:", POSITION_MANAGER_MAINNET);
    console.log("  Token0 (constructor):", constructorToken0);
    console.log("  Token1 (constructor):", constructorToken1);
    console.log("  Fee Tier:", POOL_FEE);
    console.log("  Initial Range Width Multiplier:", INITIAL_RANGE_WIDTH_MULTIPLIER_BASELINE);

    const baselineMinimal = await BaselineMinimal.deploy(
        UNISWAP_V3_FACTORY_MAINNET,
        POSITION_MANAGER_MAINNET,
        constructorToken0,
        constructorToken1,
        POOL_FEE,
        INITIAL_RANGE_WIDTH_MULTIPLIER_BASELINE
    );
    await baselineMinimal.deployed();
    const receipt = await baselineMinimal.deployTransaction.wait(1);

    console.log("\nBaselineMinimal Deployed!");
    console.log(`  Address: ${baselineMinimal.address}`);
    console.log(`  Transaction Hash: ${receipt.transactionHash}`);
    console.log(`  Block Number: ${receipt.blockNumber}`);

    // --- Save Deployed Address to Dedicated File ---
    const addresses = { address: baselineMinimal.address }; // Simple structure
    const outputPath = path.join(__dirname, '..', 'baselineMinimal_address.json'); // Dedicated file

    try {
        // Overwrite the file with the new address
        fs.writeFileSync(outputPath, JSON.stringify(addresses, null, 2));
        console.log(`\n✅ BaselineMinimal address saved to ${outputPath}`);
    } catch (err) {
        console.error("FATAL ERROR: Could not save baseline address to JSON file:", err);
        process.exit(1);
    }

    console.log("\nBaseline deployment script finished.");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("Baseline deployment script failed:", error);
        process.exit(1);
    });