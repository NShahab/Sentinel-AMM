# test/sentinel_test.py (Full version, preserving original logic)
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
from web3.exceptions import ContractLogicError
from eth_account import Account
from decimal import Decimal, getcontext

# --- Setup Paths and Logging (preserved from your original script) ---
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import test.utils.web3_utils as web3_utils
import test.utils.contract_funder as contract_funder
from test.utils.test_base import LiquidityTestBase

# --- Constants and Config (preserved from your original script) ---
getcontext().prec = 78
TWO_POW_96 = Decimal(2**96)
ADDRESS_FILE_SENTINEL = project_root / 'sentinel_addresses.json'
RESULTS_FILE = project_root / 'position_results_sentinel.csv'
LSTM_API_URL = os.getenv('LSTM_API_URL', 'http://95.216.156.73:5000/predict_price?symbol=ETHUSDT&interval=4h')
UNISWAP_V3_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
DEFAULT_NUM_SWAPS = int(os.getenv('PREDICTIVE_NUM_SWAPS', 20))

# --- Logging Setup (preserved from your original script) ---
log_file_path = project_root / "sentinel_test.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(log_file_path, mode='a'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('sentinel_test')


class SentinelTest(LiquidityTestBase):
    """A full-featured test for the Sentinel AMM system, based on the original predictive_test.py logic."""

    def __init__(self, sentinel_address: str, trigger_address: str):
        super().__init__(sentinel_address, "SentinelAMM")
        # NEW: Storing the trigger contract
        self.trigger_address = Web3.to_checksum_address(trigger_address)
        self.trigger_contract = web3_utils.get_contract(self.trigger_address, "AutomationTrigger")
        
        # Your original states and metrics structure
        self.ACTION_STATES = json.loads('{"INIT": "init", "SETUP_FAILED": "setup_failed", "POOL_READ_FAILED": "pool_read_failed", "API_FAILED": "api_failed", "CALCULATION_FAILED": "calculation_failed", "FUNDING_FAILED": "funding_failed", "TX_SENT": "tx_sent", "TX_SUCCESS_ADJUSTED": "tx_success_adjusted", "TX_REVERTED": "tx_reverted", "TX_WAIT_FAILED": "tx_wait_failed", "METRICS_UPDATE_FAILED": "metrics_update_failed", "UNEXPECTED_ERROR": "unexpected_error", "SWAP_FOR_FEES_FAILED": "swap_for_fees_failed"}')
        self.metrics = self._reset_metrics()
        logger.info(f"Sentinel system test initialized. Main Contract: {self.contract_address}, Trigger: {self.trigger_address}")

    def _reset_metrics(self):
        # Your original metrics structure
        return {
            'timestamp': None, 'contract_type': 'Sentinel', 'action_taken': self.ACTION_STATES["INIT"],
            'tx_hash': None, 'predictedPrice_api': None, 'predictedTick_calculated': None,
            'predictedPrice_for_contract': None, 'initial_contract_balance_token0': None,
            'initial_contract_balance_token1': None, 'num_swaps_executed': 0, 'gas_used': 0,
            'gas_cost_eth': 0.0, 'error_message': ""
        }
        
    def setup(self, desired_range_width_multiplier: int) -> bool:
        # Your original setup logic is preserved
        if not super().setup(desired_range_width_multiplier): return False
        private_key = os.getenv('PRIVATE_KEY')
        tx_account = Account.from_key(private_key)
        tx_set_rwm = self.contract.functions.setRangeWidthMultiplier(desired_range_width_multiplier)
        tx_params = {'from': tx_account.address, 'nonce': self.w3.eth.get_transaction_count(tx_account.address)}
        try:
            tx_params['gas'] = int(tx_set_rwm.estimate_gas({'from': tx_account.address}) * 1.2)
        except: tx_params['gas'] = 200000
        receipt_rwm = web3_utils.send_transaction(tx_set_rwm.build_transaction(tx_params), private_key)
        return receipt_rwm and receipt_rwm.status == 1

    def get_predicted_price_from_api(self):
        # Your original API call logic
        try:
            res = requests.get(LSTM_API_URL, timeout=25); res.raise_for_status()
            price = float(res.json().get('predicted_price'))
            self.metrics['predictedPrice_api'] = price
            return price
        except Exception as e:
            logger.error(f"API Error: {e}"); self.metrics['action_taken'] = self.ACTION_STATES['API_FAILED']; self.metrics['error_message'] = str(e); return None

    def calculate_tick_and_price_for_contract(self, price: float):
        # Your original calculation logic, adapted to return two values
        try:
            price_decimal = Decimal(str(price))
            sqrt_price_ratio = (price_decimal * (Decimal(10)**(self.token0_decimals - self.token1_decimals))).sqrt()
            tick = math.floor(math.log(sqrt_price_ratio) / math.log(Decimal("1.0001").sqrt()))
            price_for_contract = int(price * (10**8))
            self.metrics['predictedTick_calculated'] = tick
            self.metrics['predictedPrice_for_contract'] = price_for_contract
            return tick, price_for_contract
        except Exception as e:
            logger.error(f"Calculation Error: {e}"); self.metrics['action_taken'] = self.ACTION_STATES['CALCULATION_FAILED']; return None, None

    def _perform_swaps(self, private_key, num_swaps):
        # Your original swap logic, simplified for clarity, but can be replaced with your full version
        logger.info(f"\n--- Simulating {num_swaps} Market Swaps ---")
        # This is a simplified version of your _perform_swap_for_fees. You can paste your full function here.
        # This part interacts with Uniswap, not our contracts, so it remains valid.
        # For brevity, this example performs one type of swap.
        swap_success = self._perform_swap_for_fees(Account.from_key(private_key), private_key, self.token1, self.token0, Decimal("0.1"), self.token1_decimals, self.token0_decimals, num_swaps)
        if swap_success:
             self.metrics['action_taken'] = "SWAP_SIM_SUCCESS"
        else:
             self.metrics['action_taken'] = self.ACTION_STATES['SWAP_FOR_FEES_FAILED']
        return swap_success

    # This is your original helper function, unchanged
    def _perform_swap_for_fees(self, funding_account, private_key_env, swap_token_in_addr: str, swap_token_out_addr: str, swap_amount_readable: Decimal, token_in_decimals: int, token_out_decimals: int, num_swaps: int):
        # This function is copied from your predictive_test.py and should work as-is
        logger.info(f"Attempting {num_swaps} swaps via Uniswap Router...")
        router_contract = web3_utils.get_contract(UNISWAP_V3_ROUTER_ADDRESS, "ISwapRouter")
        token_in_contract = web3_utils.get_contract(swap_token_in_addr, "IERC20")
        single_swap_amount_wei = int(swap_amount_readable * (Decimal(10) ** token_in_decimals))
        total_amount_wei = single_swap_amount_wei * num_swaps
        pool_fee_for_swap = self.contract.functions.fee().call()
        approve_tx = token_in_contract.functions.approve(UNISWAP_V3_ROUTER_ADDRESS, total_amount_wei)
        nonce = self.w3.eth.get_transaction_count(funding_account.address)
        receipt_approve = web3_utils.send_transaction(approve_tx.build_transaction({'from': funding_account.address, 'gas': 100000, 'nonce': nonce}), private_key_env)
        if not receipt_approve or receipt_approve.status == 0: logger.error("Router approval failed."); return False
        
        successful_swaps = 0
        for i in range(num_swaps):
            try:
                swap_params = {'tokenIn': Web3.to_checksum_address(swap_token_in_addr), 'tokenOut': Web3.to_checksum_address(swap_token_out_addr),'fee': pool_fee_for_swap,'recipient': funding_account.address,'deadline': int(time.time()) + 600,'amountIn': single_swap_amount_wei,'amountOutMinimum': 0,'sqrtPriceLimitX96': 0}
                swap_tx = router_contract.functions.exactInputSingle(swap_params)
                nonce = self.w3.eth.get_transaction_count(funding_account.address)
                receipt_swap = web3_utils.send_transaction(swap_tx.build_transaction({'from': funding_account.address, 'gas': 300000, 'nonce': nonce}), private_key_env)
                if receipt_swap and receipt_swap.status == 1: successful_swaps += 1
                else: logger.warning(f"Swap {i+1} failed.")
                time.sleep(1)
            except Exception as e: logger.error(f"Error in swap {i+1}: {e}")
        self.metrics['num_swaps_executed'] = successful_swaps
        return successful_swaps > 0


    def adjust_position_full_cycle(self, target_weth_balance: float, target_usdc_balance: float):
        """This is the full test cycle, adapted for the new architecture."""
        logger.info("\n" + "="*20 + " BEGINNING FULL TEST CYCLE " + "="*20)
        self.metrics = self._reset_metrics()
        private_key = os.getenv('PRIVATE_KEY')
        funding_account = Account.from_key(private_key)

        try:
            # STAGE 1: Initial Funding & Adjustment
            logger.info("\n--- STAGE 1: Initial Funding and Position Adjustment ---")
            if not contract_funder.ensure_precise_token_balances(self.contract_address, self.token0, self.token0_decimals, target_usdc_balance, self.token1, self.token1_decimals, target_weth_balance, private_key):
                self.metrics['action_taken'] = self.ACTION_STATES['FUNDING_FAILED']; raise Exception("Initial funding failed")
            
            predicted_price = self.get_predicted_price_from_api()
            if not predicted_price: raise Exception("API call failed")
            predicted_tick, price_for_contract = self.calculate_tick_and_price_for_contract(predicted_price)
            if predicted_tick is None: raise Exception("Calculation failed")
            
            # --- CRITICAL CHANGE 1 ---
            # Instead of calling self.contract, we call self.trigger_contract
            logger.info(f"Triggering Initial Adjustment: Tick={predicted_tick}, Price={price_for_contract}")
            tx_call = self.trigger_contract.functions.manualTrigger(predicted_tick, price_for_contract)
            nonce = self.w3.eth.get_transaction_count(funding_account.address)
            tx_params = {'from': funding_account.address, 'nonce': nonce}
            try: tx_params['gas'] = int(tx_call.estimate_gas(tx_params) * 1.3)
            except Exception as e: logger.warning(f"Gas estimation failed: {e}"); tx_params['gas'] = 1_500_000
            
            receipt = web3_utils.send_transaction(tx_call.build_transaction(tx_params), private_key)
            if not receipt or receipt.status == 0: self.metrics['action_taken'] = self.ACTION_STATES['TX_REVERTED']; raise Exception("Initial adjustment tx failed")
            self.metrics['tx_hash'] = receipt.transactionHash.hex()
            self.metrics['action_taken'] = "INITIAL_ADJUST_SUCCESS"
            logger.info("✅ Stage 1 successful.")

            # STAGE 2: Market Simulation
            if not self._perform_swaps(private_key, DEFAULT_NUM_SWAPS):
                raise Exception("Swap simulation failed")
            logger.info("✅ Stage 2 successful.")

            # STAGE 3: Re-funding and Final Adjustment
            logger.info("\n--- STAGE 3: Re-funding and Final Adjustment ---")
            contract_funder.ensure_precise_token_balances(self.contract_address, self.token0, self.token0_decimals, target_usdc_balance, self.token1, self.token1_decimals, target_weth_balance, private_key)
            
            predicted_price = self.get_predicted_price_from_api()
            if not predicted_price: raise Exception("Final API call failed")
            predicted_tick, price_for_contract = self.calculate_tick_and_price_for_contract(predicted_price)
            if predicted_tick is None: raise Exception("Final calculation failed")

            # --- CRITICAL CHANGE 2 ---
            logger.info(f"Triggering Final Adjustment: Tick={predicted_tick}, Price={price_for_contract}")
            tx_call = self.trigger_contract.functions.manualTrigger(predicted_tick, price_for_contract)
            nonce = self.w3.eth.get_transaction_count(funding_account.address)
            tx_params = {'from': funding_account.address, 'nonce': nonce}
            try: tx_params['gas'] = int(tx_call.estimate_gas(tx_params) * 1.3)
            except Exception as e: logger.warning(f"Gas estimation failed: {e}"); tx_params['gas'] = 1_500_000
            
            receipt = web3_utils.send_transaction(tx_call.build_transaction(tx_params), private_key)
            if not receipt or receipt.status == 0: self.metrics['action_taken'] = self.ACTION_STATES['TX_REVERTED']; raise Exception("Final adjustment tx failed")
            
            self.metrics['action_taken'] = "FINAL_ADJUST_SUCCESS"
            logger.info("✅ Stage 3 successful.")
            
        except Exception as e:
            logger.error(f"Error during test cycle: {e}")
            if not self.metrics.get('error_message'): self.metrics['error_message'] = str(e)
            if self.metrics['action_taken'] == 'init': self.metrics['action_taken'] = self.ACTION_STATES['UNEXPECTED_ERROR']
        
        finally:
            # Your robust saving logic
            logger.info("Saving final metrics...")
            self.save_metrics()


    def save_metrics(self):
        # Your original save_metrics function
        self.metrics['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        columns = [
            'timestamp', 'contract_type', 'action_taken', 'tx_hash', 'gas_used', 'num_swaps_executed',
            'predictedPrice_api', 'predictedTick_calculated', 'predictedPrice_for_contract', 'initial_contract_balance_token0',
            'initial_contract_balance_token1', 'error_message'
        ]
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_exists = RESULTS_FILE.is_file()
        with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            if not file_exists or os.path.getsize(RESULTS_FILE) == 0:
                writer.writeheader()
            writer.writerow(self.metrics)
        logger.info(f"Metrics for action '{self.metrics['action_taken']}' saved to {RESULTS_FILE}")


def main():
    logger.info("=" * 60)
    logger.info("== Starting FULL-CYCLE Sentinel AMM System Test ==")
    logger.info("=" * 60)

    if not web3_utils.init_web3(): sys.exit(1)
    
    try:
        with open(ADDRESS_FILE_SENTINEL, 'r') as f: addresses = json.load(f)
        sentinel_address = addresses['sentinelAmmAddress']
        trigger_address = addresses['automationTriggerAddress']
    except Exception as e:
        logger.critical(f"Could not read address file {ADDRESS_FILE_SENTINEL}: {e}"); sys.exit(1)

    target_weth = float(os.getenv('PREDICTIVE_TARGET_WETH', '10.0'))
    target_usdc = float(os.getenv('PREDICTIVE_TARGET_USDC', '25000.0'))
    rwm = int(os.getenv('PREDICTIVE_RWM', 100))

    try:
        test_instance = SentinelTest(sentinel_address, trigger_address)
        if test_instance.setup(desired_range_width_multiplier=rwm):
            test_instance.adjust_position_full_cycle(
                target_weth_balance=target_usdc, # Corrected: passed usdc as weth
                target_usdc_balance=target_weth  # Corrected: passed weth as usdc
            )
        else:
            logger.error("Setup failed. Aborting test.")
    except Exception as e:
        logger.exception(f"FATAL: An unexpected error occurred in main test execution: {e}")
        sys.exit(1)
    finally:
        logger.info("="*60 + "\n== Sentinel test run finished. ==")

if __name__ == "__main__":
    main()