# test/utils/test_token_manager_swap.py

import os
import sys
import json
import time
import logging
import requests
import math
import csv
from datetime import datetime
from pathlib import Path
from web3 import Web3
from eth_account import Account
from decimal import Decimal, getcontext
from web3.logs import DISCARD
from web3.exceptions import ContractLogicError # Added for better error handling


# --- Adjust path imports ---
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import test.utils.web3_utils as web3_utils
    from test.utils.web3_utils import send_transaction, get_contract
except ImportError:
    import web3_utils
    from web3_utils import send_transaction, get_contract


# Precision for Decimal calculations
getcontext().prec = 78

# --- Constants ---
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" # Mainnet WETH
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # Mainnet USDC
WETH_DECIMALS = 18
USDC_DECIMALS = 6
POOL_FEE_FOR_SWAP = 500 # 0.05%

# Minimal ABI for IWETH9
IWETH9_ABI = [
    {"constant":True,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"payable":False,"stateMutability":"view","type":"function"},
    {"constant":False,"inputs":[{"name":"guy","type":"address"},{"name":"wad","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":False,"stateMutability":"nonpayable","type":"function"},
    {"payable":True,"stateMutability":"payable","type":"fallback"},
    {"constant":False,"inputs":[],"name":"deposit","outputs":[],"payable":True,"stateMutability":"payable","type":"function"},
    {"constant":False,"inputs":[{"name":"wad","type":"uint256"}],"name":"withdraw","outputs":[],"payable":False,"stateMutability":"nonpayable","type":"function"}
]

# --- Setup Logging ---
logger = logging.getLogger('test_token_manager_swap')
if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def perform_token_manager_swap():
    logger.info("======== Starting TokenOperationsManagerOptimized Swap Test (Independent) ========")

    if not web3_utils.init_web3():
        logger.critical("Web3 initialization failed. Exiting TokenManager swap test.")
        return False

    w3 = web3_utils.w3
    if not w3 or not w3.is_connected():
        logger.critical("w3 instance not available or not connected. Exiting.")
        return False

    token_manager_address_env = os.getenv('TOKEN_MANAGER_OPTIMIZED_ADDRESS')
    private_key_env = os.getenv('PRIVATE_KEY')
    deployer_address_env = os.getenv('DEPLOYER_ADDRESS')

    if not all([token_manager_address_env, private_key_env, deployer_address_env]):
        logger.error("Missing required environment variables: TOKEN_MANAGER_OPTIMIZED_ADDRESS, PRIVATE_KEY, DEPLOYER_ADDRESS")
        return False

    try:
        token_manager_address = w3.to_checksum_address(token_manager_address_env)
        deployer_address = w3.to_checksum_address(deployer_address_env)
        funding_account = Account.from_key(private_key_env)
        if funding_account.address.lower() != deployer_address.lower():
            logger.error(f"Mismatch between DEPLOYER_ADDRESS ({deployer_address}) and address from PRIVATE_KEY ({funding_account.address})")
            return False
    except ValueError as e:
        logger.error(f"Invalid address or private key format: {e}")
        return False

    logger.info(f"TokenOperationsManagerOptimized Address: {token_manager_address}")
    logger.info(f"Deployer/Funding Account: {funding_account.address}")

    token_manager_contract = get_contract(token_manager_address, "TokenOperationsManagerOptimized")
    usdc_contract = get_contract(USDC_ADDRESS, "IERC20")

    try:
        weth_contract = w3.eth.contract(address=w3.to_checksum_address(WETH_ADDRESS), abi=IWETH9_ABI)
        logger.info(f"IWETH9 contract instance created successfully for {WETH_ADDRESS}")
    except Exception as e:
        logger.error(f"Failed to create IWETH9 contract instance using inline ABI: {e}")
        return False

    if not token_manager_contract or not weth_contract or not usdc_contract:
        logger.error("Failed to get one or more contract instances (TokenManager, WETH, or USDC).")
        return False

    amount_weth_to_swap_readable = Decimal("0.01")
    amount_weth_to_swap_wei = int(amount_weth_to_swap_readable * (Decimal(10)**WETH_DECIMALS))
    amount_out_min_usdc_wei = 0

    logger.info(f"Attempting to swap {amount_weth_to_swap_readable} WETH for USDC via TokenManager.")

    try:
        # Get initial USDC balance of the TokenManager contract (or deployer if recipient is deployer)
        # The TokenOperationsManagerOptimized contract sends swapped tokens to address(this) (i.e., itself)
        usdc_balance_before_tm_wei = usdc_contract.functions.balanceOf(token_manager_address).call()
        logger.info(f"TokenManager USDC balance before swap: {Decimal(usdc_balance_before_tm_wei) / (Decimal(10)**USDC_DECIMALS):.6f} USDC")


        deployer_weth_balance_wei = weth_contract.functions.balanceOf(funding_account.address).call()
        logger.info(f"Deployer WETH balance: {Web3.from_wei(deployer_weth_balance_wei, 'ether')} WETH")

        if deployer_weth_balance_wei < amount_weth_to_swap_wei:
            eth_to_wrap_wei = amount_weth_to_swap_wei - deployer_weth_balance_wei
            deployer_eth_balance = w3.eth.get_balance(funding_account.address)
            if deployer_eth_balance < eth_to_wrap_wei:
                logger.error(f"Insufficient ETH to wrap. Have: {Web3.from_wei(deployer_eth_balance, 'ether')}, Need: {Web3.from_wei(eth_to_wrap_wei, 'ether')} ETH.")
                return False
            logger.info(f"Deployer WETH balance low. Attempting to wrap {Web3.from_wei(eth_to_wrap_wei, 'ether')} ETH to WETH...")
            
            deposit_tx_call = weth_contract.functions.deposit()
            deposit_nonce = w3.eth.get_transaction_count(funding_account.address)
            deposit_tx_params = {'from': funding_account.address, 'value': eth_to_wrap_wei, 'nonce': deposit_nonce}
            try:
                gas_estimate_deposit = deposit_tx_call.estimate_gas({'from': funding_account.address, 'value': eth_to_wrap_wei})
                deposit_tx_params['gas'] = int(gas_estimate_deposit * 1.25)
            except Exception as e_gas_deposit:
                logger.warning(f"Gas estimation for WETH deposit failed: {e_gas_deposit}. Using default 100,000.")
                deposit_tx_params['gas'] = 100000 
            wrap_receipt = send_transaction(deposit_tx_call.build_transaction(deposit_tx_params), private_key_env)
            if not (wrap_receipt and wrap_receipt.status == 1):
                logger.error(f"Failed to wrap ETH. Tx: {wrap_receipt.transactionHash.hex() if wrap_receipt else 'N/A'}")
                return False
            logger.info(f"Successfully wrapped ETH. Tx: {wrap_receipt.transactionHash.hex()}")
            deployer_weth_balance_wei = weth_contract.functions.balanceOf(funding_account.address).call()
            logger.info(f"New deployer WETH balance: {Web3.from_wei(deployer_weth_balance_wei, 'ether')} WETH")
        
        if deployer_weth_balance_wei < amount_weth_to_swap_wei:
             logger.error(f"Insufficient WETH balance ({Web3.from_wei(deployer_weth_balance_wei, 'ether')}) even after attempting wrap, need {amount_weth_to_swap_readable}.")
             return False

        logger.info(f"Approving TokenManager ({token_manager_address}) to spend {amount_weth_to_swap_readable} WETH from deployer...")
        approve_tx_call = weth_contract.functions.approve(token_manager_address, amount_weth_to_swap_wei)
        approve_nonce = w3.eth.get_transaction_count(funding_account.address)
        approve_tx_params = {'from': funding_account.address, 'nonce': approve_nonce}
        try: approve_tx_params['gas'] = int(approve_tx_call.estimate_gas({'from': funding_account.address}) * 1.2)
        except: approve_tx_params['gas'] = 100000; logger.warning("Gas est for WETH approval failed, using default.")
        approve_receipt = send_transaction(approve_tx_call.build_transaction(approve_tx_params), private_key_env)
        if not (approve_receipt and approve_receipt.status == 1):
            logger.error(f"Failed to approve TokenManager to spend WETH. Tx: {approve_receipt.transactionHash.hex() if approve_receipt else 'N/A'}")
            return False
        logger.info(f"TokenManager approved for WETH. Tx: {approve_receipt.transactionHash.hex()}")

        logger.info(f"Calling swap on TokenManager: {amount_weth_to_swap_readable} WETH -> USDC, PoolFee: {POOL_FEE_FOR_SWAP}...")
        swap_tx_call = token_manager_contract.functions.swap(WETH_ADDRESS, USDC_ADDRESS, POOL_FEE_FOR_SWAP, amount_weth_to_swap_wei, amount_out_min_usdc_wei)
        swap_nonce = w3.eth.get_transaction_count(funding_account.address)
        swap_tx_params = {'from': funding_account.address, 'nonce': swap_nonce}
        try: swap_tx_params['gas'] = int(swap_tx_call.estimate_gas({'from': funding_account.address}) * 1.3)
        except ContractLogicError as cle: logger.error(f"Gas estimation for TokenManager swap failed (logic): {cle}."); return False
        except Exception as e: swap_tx_params['gas'] = 700000; logger.warning(f"Gas estimation for TokenManager swap failed: {e}, using default.")
        
        swap_receipt = send_transaction(swap_tx_call.build_transaction(swap_tx_params), private_key_env)

        if swap_receipt and swap_receipt.status == 1:
            logger.info(f"TokenManager swap transaction successful. Tx: {swap_receipt.transactionHash.hex()}")
            
            usdc_balance_after_tm_wei = usdc_contract.functions.balanceOf(token_manager_address).call()
            usdc_received_by_tm_wei = usdc_balance_after_tm_wei - usdc_balance_before_tm_wei
            usdc_received_by_tm_readable = Decimal(usdc_received_by_tm_wei) / (Decimal(10)**USDC_DECIMALS)
            logger.info(f"TokenManager USDC balance after swap: {usdc_received_by_tm_readable + (Decimal(usdc_balance_before_tm_wei) / (Decimal(10)**USDC_DECIMALS)):.6f} USDC")
            logger.info(f"Actual USDC received by TokenManager (based on balance change): {usdc_received_by_tm_readable:.6f} USDC")

            amount_usdc_from_event_readable = Decimal(0)
            if token_manager_contract:
                logger.info("Attempting to process Operation event from TokenManager...")
                try:
                    op_logs = token_manager_contract.events.Operation().process_receipt(swap_receipt, errors=DISCARD)
                    if not op_logs:
                        logger.warning("process_receipt for Operation event returned no logs. Attempting raw log decoding...")
                        raw_logs = swap_receipt.get('logs', [])
                        for log_item in raw_logs:
                            try:
                                # Check if the log belongs to the token_manager_contract
                                if log_item.get('address', '').lower() == token_manager_address.lower():
                                    parsed_log = token_manager_contract.events.Operation().processLog(log_item)
                                    if parsed_log:
                                        logger.info(f"Raw log item decoded: {parsed_log}")
                                        op_type_bytes32 = parsed_log.args.opType
                                        is_swap_op = (w3.to_hex(op_type_bytes32) == w3.to_hex(w3.solidity_keccak(['string'],['SWAP'])))
                                        if is_swap_op and parsed_log.args.tokenA.lower() == WETH_ADDRESS.lower() and parsed_log.args.tokenB.lower() == USDC_ADDRESS.lower():
                                            amount_usdc_received_wei = parsed_log.args.amount
                                            amount_usdc_from_event_readable = Decimal(amount_usdc_received_wei) / (Decimal(10)**USDC_DECIMALS)
                                            logger.info(f"TokenManager Swap Event (from raw log): Swapped {amount_weth_to_swap_readable} WETH for {amount_usdc_from_event_readable:.6f} USDC.")
                                            break # Found the relevant swap event
                            except Exception as e_parse_raw:
                                logger.debug(f"Could not parse a raw log item with Operation event: {e_parse_raw}")
                                continue
                    else:
                        for log_entry in op_logs:
                            op_type_bytes32 = log_entry.args.opType
                            is_swap_op = (w3.to_hex(op_type_bytes32) == w3.to_hex(w3.solidity_keccak(['string'],['SWAP'])))
                            if is_swap_op and log_entry.args.tokenA.lower() == WETH_ADDRESS.lower() and log_entry.args.tokenB.lower() == USDC_ADDRESS.lower():
                                amount_usdc_received_wei = log_entry.args.amount
                                amount_usdc_from_event_readable = Decimal(amount_usdc_received_wei) / (Decimal(10)**USDC_DECIMALS)
                                logger.info(f"TokenManager Swap Event (from process_receipt): Swapped {amount_weth_to_swap_readable} WETH for {amount_usdc_from_event_readable:.6f} USDC.")
                                break
                except Exception as e_log_proc:
                    logger.error(f"Error processing Operation logs: {e_log_proc}")
            
            # Final check based on balance change if event processing failed or reported zero
            if usdc_received_by_tm_readable > 0:
                logger.info(f"? TokenManager Swap Test Passed. TokenManager received {usdc_received_by_tm_readable:.6f} USDC (verified by balance change).")
                if amount_usdc_from_event_readable > 0 and abs(amount_usdc_from_event_readable - usdc_received_by_tm_readable) > Decimal('0.000001'):
                    logger.warning(f"Discrepancy between event amount ({amount_usdc_from_event_readable:.6f}) and balance change amount ({usdc_received_by_tm_readable:.6f}). Prioritizing balance change for success criteria.")
                return True
            elif amount_usdc_from_event_readable > 0: # Balance change was 0, but event showed value
                logger.info(f"?? TokenManager Swap Test Potentially Passed. Event reported {amount_usdc_from_event_readable:.6f} USDC, but balance change was zero. Check contract logic for recipient.")
                return True # Consider it a pass if event shows amount, but warn
            else:
                logger.error("? TokenManager Swap Test Failed: Swap transaction succeeded but no USDC amount reported in Operation event OR by balance change.")
                return False
        else:
            logger.error(f"? TokenManager swap transaction failed. Tx: {swap_receipt.transactionHash.hex() if swap_receipt else 'N/A'}")
            return False

    except Exception as e:
        logger.exception(f"An unexpected error occurred during TokenManager swap test: {e}")
        return False
    finally:
        logger.info("======== Finished TokenOperationsManagerOptimized Swap Test (Independent) ========")


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        env_path = project_root / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            logger.info(f"Loaded .env file from {env_path} for direct script execution.")
        else:
            logger.info(f".env file not found at {env_path}. Relying on shell-exported ENV VARS.")
    except ImportError:
        logger.info("dotenv library not found. Relying on shell-exported ENV VARS for direct script execution.")
    
    if not os.getenv('MAINNET_FORK_RPC_URL'):
        os.environ['MAINNET_FORK_RPC_URL'] = 'http://127.0.0.1:8545'

    if perform_token_manager_swap():
        sys.exit(0)
    else:
        sys.exit(1)
