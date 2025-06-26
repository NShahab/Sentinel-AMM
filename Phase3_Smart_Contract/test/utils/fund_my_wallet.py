#!/usr/bin/env python3
"""
Wallet Funding Script for Hardhat Fork Testing
Version: 4.1 (web3.py v5 Compatible)
"""

import os
import sys
import logging
from time import sleep
from web3 import Web3, HTTPProvider
from web3.exceptions import ContractLogicError, BadFunctionCallOutput
from typing import Dict, Any

# --- Constants ---
DEFAULT_RPC_URL = "http://127.0.0.1:8545"
MAX_RETRIES = 3
RETRY_DELAY_S = 5
MIN_ETH_FOR_WHALE_GAS = 0.1
# --- Token & Whale Configuration (web3.py v5 compatible) ---
TOKEN_CONFIG = {
    "WETH": {
        "address": Web3.toChecksumAddress("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
        "whale": Web3.toChecksumAddress("0x2f0b23f53734252bda2277357e97e1517d6b042a"),
        "amount_readable": 300,
        "decimals": 18,
    },
    "USDC": {
        "address": Web3.toChecksumAddress("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"),
        "whale": Web3.toChecksumAddress("0x55fe002aeff02f77364de339a1292923a15844b8"),
        "amount_readable": 3000000,
        "decimals": 6,
    },
}

# --- Minimal ERC20 ABI ---
ERC20_ABI = [
    {"name": "balanceOf", "inputs": [{"name": "_owner", "type": "address"}], "outputs": [{"name": "balance", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"name": "transfer", "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger('wallet_funder')

class WalletFunder:
    def __init__(self):
        self.rpc_url = os.getenv('MAINNET_FORK_RPC_URL', DEFAULT_RPC_URL)
        logger.info(f"Initializing Web3 connection to {self.rpc_url}")
        self.w3 = self._init_web3()
        self.deployer_address = self._get_deployer_address()
        logger.info(f"Target deployer address: {self.deployer_address}")

    def _init_web3(self) -> Web3:
        for attempt in range(MAX_RETRIES):
            try:
                w3 = Web3(HTTPProvider(self.rpc_url, request_kwargs={'timeout': 60}))
                if w3.isConnected(): # CORRECT for web3.py v5
                    logger.info(f"Successfully connected to Ethereum node. Chain ID: {w3.eth.chainId}")
                    return w3
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                sleep(RETRY_DELAY_S)
        logger.critical("Failed to connect to Web3 provider. Is the Hardhat node running?")
        sys.exit(1)

    def _get_deployer_address(self) -> str:
        address = os.getenv('DEPLOYER_ADDRESS')
        if not address:
            logger.critical("FATAL: DEPLOYER_ADDRESS environment variable not set.")
            sys.exit(1)
        return Web3.toChecksumAddress(address) # CORRECT for web3.py v5

    def _make_rpc_request(self, method: str, params: list) -> Any:
        try:
            return self.w3.provider.make_request(method, params)
        except Exception as e:
            logger.error(f"RPC request for method '{method}' failed: {e}", exc_info=True)
            return None

    def set_eth_balance(self, address: str, eth_amount: float) -> bool:
        logger.info(f"Attempting to set ETH balance for {address[:10]}... to {eth_amount} ETH.")
        wei_amount = self.w3.toWei(eth_amount, 'ether') # CORRECT for web3.py v5
        
        result = self._make_rpc_request("hardhat_setBalance", [address, hex(wei_amount)])
        
        if result is None or result.get('error'):
            logger.error(f"RPC call `hardhat_setBalance` failed. Response: {result}")
            return False
            
        sleep(0.5)
        new_balance_wei = self.w3.eth.getBalance(address) # CORRECT for web3.py v5
        if new_balance_wei >= wei_amount:
            logger.info(f"✅ ETH balance successfully set for {address[:10]}.... New balance: {self.w3.fromWei(new_balance_wei, 'ether')} ETH")
            return True
        else:
            logger.error("ETH balance verification failed.")
            return False

    def _ensure_eth_for_gas(self, account: str) -> bool:
        min_wei = self.w3.toWei(MIN_ETH_FOR_WHALE_GAS, 'ether')
        balance_wei = self.w3.eth.getBalance(account)
        if balance_wei < min_wei:
            logger.warning(f"Whale {account[:10]}... has insufficient ETH for gas. Funding with 1 ETH...")
            return self.set_eth_balance(account, 1.0)
        return True

    def transfer_tokens(self, token_symbol: str, config: Dict[str, Any]) -> bool:
        whale_address = config['whale']
        
        logger.info(f"\n--- Processing {token_symbol} transfer from whale {whale_address[:10]}... ---")
        
        if self._make_rpc_request("hardhat_impersonateAccount", [whale_address]) is None: return False
        logger.info(f"Successfully impersonating {whale_address[:10]}...")

        if not self._ensure_eth_for_gas(whale_address):
            self._make_rpc_request("hardhat_stopImpersonatingAccount", [whale_address])
            return False

        success = self._execute_impersonated_transfer(token_symbol, config)

        self._make_rpc_request("hardhat_stopImpersonatingAccount", [whale_address])
        logger.info(f"Stopped impersonating {whale_address[:10]}...")
        
        return success

    def _execute_impersonated_transfer(self, token_symbol: str, config: Dict[str, Any]) -> bool:
        token_address = config['address']
        whale_address = config['whale']
        amount_wei = int(config['amount_readable'] * (10 ** config['decimals']))
        amount_readable = config['amount_readable']

        try:
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            whale_balance_wei = token_contract.functions.balanceOf(whale_address).call()
            
            if whale_balance_wei < amount_wei:
                whale_balance_readable = self.w3.fromWei(whale_balance_wei, 'ether' if config['decimals'] == 18 else 'mwei')
                logger.error(f"Whale has insufficient {token_symbol}. Has: {whale_balance_readable}, Needs: {amount_readable}")
                return False
            
            logger.info(f"Whale has enough {token_symbol}. Transferring {amount_readable} {token_symbol}...")
            
            tx_hash = token_contract.functions.transfer(self.deployer_address, amount_wei).transact({'from': whale_address})
            receipt = self.w3.eth.waitForTransactionReceipt(tx_hash, timeout=180) # CORRECT for web3.py v5

            if receipt.status == 1:
                logger.info(f"✅ {token_symbol} transfer successful. TxHash: {tx_hash.hex()}")
                return True
            else:
                logger.error(f"❌ {token_symbol} transfer transaction reverted.")
                return False
        
        except (ContractLogicError, BadFunctionCallOutput) as e:
            logger.critical(
                f"FATAL: balanceOf call for {token_symbol} failed. Check MAINNET_RPC_URL. Error: {e}",
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected error during {token_symbol} transfer: {e}", exc_info=True)
            return False

def main():
    logger.info("\n" + "="*30 + " Starting Wallet Funding Script " + "="*30)
    funder = WalletFunder()
    all_operations_succeeded = True

    logger.info("\n--- Step 1 of 2: Funding deployer account with ETH ---")
    if not funder.set_eth_balance(funder.deployer_address, 100.0):
        all_operations_succeeded = False

    if all_operations_succeeded:
        logger.info("\n--- Step 2 of 2: Transferring ERC20 tokens ---")
        for token, config in TOKEN_CONFIG.items():
            if not funder.transfer_tokens(token, config):
                all_operations_succeeded = False
                break

    logger.info("\n" + "="*30 + " Wallet Funding Script Finished " + "="*30)
    if all_operations_succeeded:
        logger.info("✅✅✅ All funding operations completed successfully! ✅✅✅")
        sys.exit(0)
    else:
        logger.error("‼️‼️‼️ Some funding operations failed. ‼️‼️‼️")
        sys.exit(1)

if __name__ == "__main__":
    main()
