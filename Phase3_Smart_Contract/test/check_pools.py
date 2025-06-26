from web3 import Web3

# اتصال به Arbitrum Sepolia
rpc_url = "https://arbitrum-sepolia.infura.io/v3/6cb906401b0b4ab4a53beef2c28ba519"
web3 = Web3(Web3.HTTPProvider(rpc_url))

if not web3.is_connected():
    raise Exception("❌ اتصال به شبکه برقرار نشد")

# آدرس‌ها
factory_address = Web3.to_checksum_address("0x1F98431c8aD98523631AE4a59f267346ea31F984")  # Uniswap V3 Factory
usdc_address = Web3.to_checksum_address("0xAf88d065e77c8cC2239327C5EDb3A432268e5831")   # USDC
weth_address = Web3.to_checksum_address("0x82af49447d8a07e3bd95bd0d56f35241523fbab1")   # WETH
fee = 500  # 0.05%

# ABI فکتوری
factory_abi = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"}
        ],
        "name": "getPool",
        "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ABI استخر
pool_abi = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ایجاد کانترکت فکتوری
factory_contract = web3.eth.contract(address=factory_address, abi=factory_abi)

# گرفتن آدرس استخر
pool_address = factory_contract.functions.getPool(usdc_address, weth_address, fee).call()

if pool_address == "0x0000000000000000000000000000000000000000":
    print("❌ استخر پیدا نشد.")
else:
    print(f"✅ آدرس استخر: {pool_address}")

    # اتصال به کانترکت استخر
    pool_contract = web3.eth.contract(address=pool_address, abi=pool_abi)

    # گرفتن اطلاعات
    slot0 = pool_contract.functions.slot0().call()
    liquidity = pool_contract.functions.liquidity().call()

    print("\n🧪 اطلاعات استخر:")
    print(f"SqrtPriceX96: {slot0[0]}")
    print(f"Tick: {slot0[1]}")
    print(f"Liquidity: {liquidity}")
