const hre = require("hardhat");
const { ethers } = require("hardhat");

async function main() {
    console.log("بررسی آدرس‌های قراردادها در سپولیا...");
    console.log("=========================================");

    const addresses = [
        { name: "Factory", address: "0x1F98431c8aD98523631AE4a59f267346ea31F984" },
        { name: "Position Manager", address: "0x1238536071E1c677A632429e3655c799b22cDA52" },
        { name: "Swap Router", address: "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E" },
        { name: "WETH", address: "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9" },
        { name: "USDC", address: "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238" }
    ];

    // مقایسه با آدرس‌های رسمی UniswapV3 در Sepolia
    const officialAddresses = {
        "Factory": "0x0227628f3F023bb0B980b67D528571c95c6DaC1c",
        "Position Manager": "0x1238536071E1c677A632429e3655c799b22cDA52",
        "Swap Router": "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E",
        "WETH": "0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9"
    };

    for (const item of addresses) {
        try {
            const code = await ethers.provider.getCode(item.address);
            const isContract = code !== '0x';
            const isOfficialAddress = officialAddresses[item.name] === item.address;

            console.log(`${item.name} (${item.address}):`);
            console.log(`  - وضعیت کد: ${isContract ? '✅ دارای کد (قرارداد معتبر)' : '❌ بدون کد (احتمالا آدرس نامعتبر)'}`);
            console.log(`  - تطابق با آدرس رسمی: ${isOfficialAddress ? '✅ مطابقت دارد' :
                (officialAddresses[item.name] ? `❌ مطابقت ندارد (آدرس رسمی: ${officialAddresses[item.name]})` : '❓ آدرس رسمی نامشخص')}`);
            console.log("  -----------------------------------------");
        } catch (error) {
            console.log(`${item.name} (${item.address}): ❌ خطا در بررسی: ${error.message}`);
            console.log("  -----------------------------------------");
        }
    }

    console.log("\nتوجه: اگر آدرس‌ها کد ندارند یا با آدرس‌های رسمی مطابقت ندارند،");
    console.log("باید آدرس‌های صحیح برای شبکه سپولیا را از مستندات رسمی Uniswap استخراج کنید.");
    console.log("آدرس‌های رسمی: https://docs.uniswap.org/contracts/v3/reference/deployments");
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
}); 