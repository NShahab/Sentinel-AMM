import os
import json
import logging
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
from pathlib import Path
import time

# --- Logging Setup ---
logger = logging.getLogger('web3_utils')
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Load Environment Variables ---
utils_dir = Path(__file__).resolve().parent
PROJECT_ROOT = utils_dir.parent.parent
env_path = PROJECT_ROOT / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    logger.warning(f".env file not found at expected location: {env_path}")

PRIVATE_KEY = os.getenv('PRIVATE_KEY')
RPC_URL = os.getenv('MAINNET_FORK_RPC_URL', 'http://127.0.0.1:8545')

# --- Web3 Initialization ---
w3 = None

def init_web3(retries=3, delay=2):
    """Initialize Web3 connection and validate environment."""
    global w3
    if w3:
        return True

    if not RPC_URL:
        logger.error("RPC_URL (for fork) not found or set.")
        return False

    for attempt in range(retries):
        try:
            logger.info(f"Attempting to connect to Web3 provider at {RPC_URL} (Attempt {attempt + 1}/{retries})...")
            w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 60}))
            chain_id = w3.eth.chain_id
            logger.info(f"Successfully connected to network via {RPC_URL} - Chain ID: {chain_id}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Web3 provider on attempt {attempt + 1}: {e}")

        if attempt < retries - 1:
            logger.info(f"Retrying connection after {delay} seconds...")
            time.sleep(delay)

    logger.critical("Failed to connect to Web3 provider after multiple retries.")
    w3 = None
    return False

# --- Standard ABIs ---
IERC20_ABI = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function","stateMutability":"view"},{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function","stateMutability":"view"},{"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function","stateMutability":"nonpayable"},{"constant":False,"inputs":[{"name":"spender","type":"address"},{"name":"value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function","stateMutability":"nonpayable"},{"constant":True,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
WETH_ABI = IERC20_ABI + [{"type":"fallback","stateMutability":"payable"},{"type":"receive","stateMutability":"payable"},{"constant":False,"inputs":[],"name":"deposit","outputs":[],"type":"function","stateMutability":"payable"},{"constant":False,"inputs":[{"name":"wad","type":"uint256"}],"name":"withdraw","outputs":[],"type":"function","stateMutability":"nonpayable"}]
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

def load_contract_abi(contract_name):
    """Load a contract ABI from artifacts directory."""
    if contract_name == "IERC20": return IERC20_ABI
    if contract_name == "WETH": return WETH_ABI
    base_path = PROJECT_ROOT
    possible_paths = [
        base_path / f'artifacts/contracts/{contract_name}.sol/{contract_name}.json',
        base_path / f'artifacts/contracts/interfaces/{contract_name}.sol/{contract_name}.json',
        base_path / f'artifacts/@uniswap/v3-core/contracts/interfaces/{contract_name}.sol/{contract_name}.json',
        base_path / f'artifacts/@uniswap/v3-periphery/contracts/interfaces/{contract_name}.sol/{contract_name}.json',
    ]
    for path in possible_paths:
        if path.exists():
            with open(path) as f:
                try:
                    contract_json = json.load(f)
                    if 'abi' not in contract_json: continue
                    return contract_json['abi']
                except json.JSONDecodeError: continue
    raise FileNotFoundError(f"ABI not found for {contract_name} in any expected path relative to {base_path}.")

def get_contract(address, contract_name):
    """Get contract instance with loaded ABI."""
    global w3
    if not w3 and not init_web3():
        raise ConnectionError("Web3 connection failed in get_contract.")
    if not address: raise ValueError(f"Address for {contract_name} not provided")
    try:
        checksum_address = Web3.to_checksum_address(address)
        abi = load_contract_abi(contract_name)
        return w3.eth.contract(address=checksum_address, abi=abi)
    except Exception as e:
        logger.exception(f"Error getting contract {contract_name} at {address}: {e}")
        raise

def send_transaction(tx_params_dict, private_key):
    """Signs, sends a transaction and waits for receipt."""
    global w3
    if not w3 and not init_web3():
        raise ConnectionError("Web3 connection failed in send_transaction.")
    if 'from' not in tx_params_dict: raise ValueError("Transaction 'from' address missing")
    if not private_key:
        logger.error("Private key not provided to send_transaction.")
        return None
    try:
        if 'chainId' not in tx_params_dict: tx_params_dict['chainId'] = w3.eth.chain_id
        if 'nonce' not in tx_params_dict: tx_params_dict['nonce'] = w3.eth.get_transaction_count(tx_params_dict['from'])
        if 'gas' not in tx_params_dict:
            try:
                tx_params_dict['gas'] = int(w3.eth.estimate_gas(tx_params_dict) * 1.25)
            except Exception as gas_err:
                logger.error(f"Gas estimation failed: {gas_err}. Using default 1,000,000.")
                tx_params_dict['gas'] = 1000000
        if 'gasPrice' not in tx_params_dict and 'maxFeePerGas' not in tx_params_dict:
            try:
                fee_history = w3.eth.fee_history(1, 'latest', [10])
                base_fee = fee_history['baseFeePerGas'][-1]
                tip = fee_history['reward'][-1][0] if fee_history['reward'] and fee_history['reward'][-1] else w3.to_wei(1, 'gwei')
                tx_params_dict['maxPriorityFeePerGas'] = tip
                tx_params_dict['maxFeePerGas'] = base_fee * 2 + tip
            except:
                tx_params_dict['gasPrice'] = int(w3.eth.gas_price * 1.1)
        
        signed_tx = w3.eth.account.sign_transaction(tx_params_dict, private_key)
        
        # Corrected attribute for web3.py v6+
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        logger.info(f"Transaction confirmed in block: {receipt.blockNumber}, Status: {receipt.status}")
        return receipt
    except Exception as e:
        logger.exception(f"Transaction processing failed: {e}")
        return None

def wrap_eth_to_weth(amount_wei) -> bool:
    """
    Wrap ETH to WETH by sending ETH to the WETH contract address.
    """
    global w3
    if not w3 and not init_web3():
        raise ConnectionError("Web3 connection failed in wrap_eth_to_weth.")

    if not PRIVATE_KEY:
        logger.error("PRIVATE_KEY not found for wrap_eth_to_weth.")
        return False

    try:
        account = Account.from_key(PRIVATE_KEY)
        checksum_weth_address = Web3.to_checksum_address(WETH_ADDRESS)

        logger.info(f"Attempting to wrap {Web3.from_wei(amount_wei, 'ether')} ETH for {account.address} by sending to {checksum_weth_address}")

        tx_dict = {
            'from': account.address,
            'to': checksum_weth_address,
            'value': amount_wei,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': w3.eth.chain_id,
        }

        try:
            tx_dict['gas'] = int(w3.eth.estimate_gas(tx_dict) * 1.25)
        except Exception as e:
            logger.warning(f"Gas estimation for wrap_eth_to_weth failed: {e}. Using default gas limit 100000.")
            tx_dict['gas'] = 100000

        try:
            fee_history = w3.eth.fee_history(1, 'latest', [10])
            base_fee = fee_history['baseFeePerGas'][-1]
            tip = fee_history['reward'][-1][0] if fee_history['reward'] and fee_history['reward'][-1] else w3.to_wei(1, 'gwei')
            tx_dict['maxPriorityFeePerGas'] = tip
            tx_dict['maxFeePerGas'] = base_fee * 2 + tip
        except:
            tx_dict['gasPrice'] = int(w3.eth.gas_price * 1.1)

        receipt = send_transaction(tx_dict, PRIVATE_KEY)

        if receipt and receipt.status == 1:
            logger.info(f"WETH wrap confirmed successfully.")
            return True
        else:
            logger.error(f"WETH wrap transaction failed or receipt not obtained. Receipt: {receipt}")
            return False
    except Exception as e:
        logger.exception(f"Wrapping ETH to WETH failed: {e}")
        return False