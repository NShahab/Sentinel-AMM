// scripts/deployTokenManagerOptimized.js
const hre = require("hardhat");
const fs = require('fs');
const path = require('path');

async function main() {
    console.log("Starting TokenOperationsManagerOptimized deployment process on the forked mainnet network...");

    // --- Mainnet Addresses ---
    // آدرس روتر Uniswap V3 در شبکه اصلی اتریوم
    const SWAP_ROUTER_MAINNET = "0xE592427A0AEce92De3Edee1F18E0157C05861564"; // Correct Mainnet SwapRouter V1
    // آدرس WETH در شبکه اصلی اتریوم
    const WETH_MAINNET = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2";

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deploying contract with the account:", deployer.address);
    console.log("Account balance:", (await deployer.getBalance()).toString());

    console.log("\nDeploying TokenOperationsManagerOptimized with parameters:");
    console.log("  Swap Router (Mainnet):", SWAP_ROUTER_MAINNET);
    console.log("  WETH (Mainnet):", WETH_MAINNET);

    const TokenOperationsManagerOptimized = await hre.ethers.getContractFactory("TokenOperationsManagerOptimized");
    const tokenManager = await TokenOperationsManagerOptimized.deploy(
        SWAP_ROUTER_MAINNET,
        WETH_MAINNET
        // اگر از گزینه های خاص دیپلوی مانند gasLimit استفاده می کنید، اینجا اضافه کنید
        // اما معمولا Hardhat در شبکه local fork این موارد را به خوبی مدیریت می کند
    );
    await tokenManager.deployed();
    const receipt = await tokenManager.deployTransaction.wait(1); // Wait for 1 confirmation

    console.log("\nTokenOperationsManagerOptimized Deployed!");
    console.log(`  Address: ${tokenManager.address}`);
    console.log(`  Transaction Hash: ${receipt.transactionHash}`);
    console.log(`  Block Number: ${receipt.blockNumber}`);

    // --- Save Deployed Address to Dedicated File ---
    const addresses = { address: tokenManager.address };
    // مسیر فایل خروجی برای آدرس قرارداد، در ریشه پروژه
    const outputPath = path.join(__dirname, '..', 'tokenManagerOptimized_address.json');

    try {
        // ایجاد یا بازنویسی فایل با آدرس جدید
        fs.writeFileSync(outputPath, JSON.stringify(addresses, null, 2));
        console.log(`\n✅ TokenOperationsManagerOptimized address saved to ${outputPath}`);
    } catch (err) {
        console.error("FATAL ERROR: Could not save TokenOperationsManagerOptimized address to JSON file:", err);
        process.exit(1); // خروج با خطا در صورت عدم موفقیت در ذخیره فایل
    }

    console.log("\nTokenOperationsManagerOptimized deployment script finished.");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("TokenOperationsManagerOptimized deployment script failed:", error);
        process.exit(1);
    });