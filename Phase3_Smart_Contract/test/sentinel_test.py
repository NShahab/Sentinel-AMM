# sentinel_test.py - FINAL, FULL-FEATURED & CORRECTED VERSION WITH EVENT PARSING
import sys
from pathlib import Path

# Ensures Python can find the 'test.utils' module
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os, json, time, logging, requests, math, csv
from datetime import datetime
from web3 import Web3
from web3.exceptions import ContractLogicError
from eth_account import Account
from decimal import Decimal, getcontext

import test.utils.web3_utils as web3_utils
import test.utils.contract_funder as contract_funder
from test.utils.test_base import LiquidityTestBase

# --- Constants ---
getcontext().prec = 78
ADDRESS_FILE_SENTINEL = project_root / 'sentinel_addresses.json'
RESULTS_FILE = project_root / 'position_results_sentinel.csv'
LSTM_API_URL = os.getenv('LSTM_API_URL', 'http://95.216.156.73:5000/predict_price?symbol=ETHUSDT&interval=4h')
UNISWAP_V3_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
DEFAULT_NUM_SWAPS = int(os.getenv('PREDICTIVE_NUM_SWAPS', 20))

# --- Logging ---
log_file_path = project_root / "sentinel_test.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(log_file_path, mode='a'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger('sentinel_test')


class SentinelTest(LiquidityTestBase):
    """A comprehensive test for the Sentinel AMM system, with improved event parsing."""

    def __init__(self, sentinel_address: str, trigger_address: str):
        self.ACTION_STATES = json.loads('{"INIT": "init", "SETUP_FAILED": "setup_failed", "API_FAILED": "api_failed", "FUNDING_FAILED": "funding_failed", "TX_REVERTED": "tx_reverted", "UNEXPECTED_ERROR": "unexpected_error", "INITIAL_ADJUST_SUCCESS": "initial_adjust_success", "SWAP_SIM_SUCCESS": "swap_sim_success", "SWAP_SIM_FAILED": "swap_sim_failed", "FEES_COLLECT_ONLY_SUCCESS": "fees_collect_only_success", "FEES_COLLECT_ONLY_FAILED": "fees_collect_only_failed", "FINAL_ADJUST_SUCCESS": "final_adjust_success"}')
        super().__init__(sentinel_address, "SentinelAMM")
        self.trigger_address = Web3.to_checksum_address(trigger_address)
        self.trigger_contract = web3_utils.get_contract(self.trigger_address, "AutomationTrigger")
        self.price_feed_contract = None
        self.metrics = self._reset_metrics()

    def _reset_metrics(self):
        base = super()._reset_metrics()
        # Initialize all relevant metrics, especially fees
        extra = {
            'contract_type': 'Sentinel',
            'action_taken': self.ACTION_STATES["INIT"],
            'amount0_provided_to_mint': 0,
            'amount1_provided_to_mint': 0,
            'fees_collected_token0': 0,
            'fees_collected_token1': 0,
        }
        return {**base, **extra}

    def setup(self, desired_range_width_multiplier: int):
        if not super().setup(desired_range_width_multiplier): return False
        try:
            price_feed_address = self.contract.functions.priceFeed().call()
            self.price_feed_contract = web3_utils.get_contract(price_feed_address, "AggregatorV3Interface")
            logger.info(f"Successfully connected to Chainlink Price Feed at {price_feed_address}")
        except Exception as e:
            logger.error(f"Failed to setup connection to Chainlink Price Feed. Error: {e}")
            return False
        return True
    
    def get_chainlink_price(self):
        try:
            price = self.price_feed_contract.functions.latestRoundData().call()[1] / (10**8)
            self.metrics['chainlink_price_onchain'] = price
            return price
        except Exception as e:
            logger.error(f"Could not retrieve price from Chainlink oracle at {self.price_feed_contract.address}. Error: {e}")
            return None

    def get_predicted_price_from_api(self):
        try:
            res = requests.get(LSTM_API_URL, timeout=25); res.raise_for_status()
            price = float(res.json().get('predicted_price'))
            self.metrics['predictedPrice_api'] = price
            return price
        except Exception as e:
            logger.error(f"API Error: {e}"); self.metrics['action_taken'] = self.ACTION_STATES['API_FAILED']; return None

    def calculate_tick_and_price_for_contract(self, price: float):
        try:
            price_decimal = Decimal(str(price))
            sqrt_price_ratio = (price_decimal * (Decimal(10)**(self.token0_decimals - self.token1_decimals))).sqrt()
            tick = math.floor(math.log(sqrt_price_ratio) / math.log(Decimal("1.0001").sqrt()))
            price_for_contract = int(price * (10**8))
            self.metrics.update({'predictedTick_calculated': tick})
            return tick, price_for_contract
        except: return None, None

    def _trigger_adjustment(self, funding_account, private_key, stage_name="adjustment"):
        logger.info(f"\n--- Triggering {stage_name} ---")
        predicted_price = self.get_predicted_price_from_api()
        if not predicted_price:
            return None 

        chainlink_price = self.get_chainlink_price()
        if chainlink_price is None:
            logger.critical("CRITICAL: Aborting adjustment because live on-chain price from Chainlink could not be fetched.")
            self.metrics['action_taken'] = self.ACTION_STATES['UNEXPECTED_ERROR']
            return None
            
        logger.info(f"AI Predicted: ${predicted_price:.2f} | Chainlink Live: ${chainlink_price:.2f}")
        
        predicted_tick, price_for_contract = self.calculate_tick_and_price_for_contract(predicted_price)
        if predicted_tick is None:
            logger.error("Failed to calculate tick from predicted price.")
            return None
        
        tx_call = self.trigger_contract.functions.manualTrigger(predicted_tick, price_for_contract)
        nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
        tx_params = {'from': funding_account.address, 'nonce': nonce, 'gas': 2_000_000}
        
        receipt = web3_utils.send_transaction(tx_call.build_transaction(tx_params), private_key)
        if receipt and receipt.status == 1:
            logger.info(f" {stage_name} Tx Successful: {receipt.transactionHash.hex()}")
            self.metrics.update({'tx_hash': receipt.transactionHash.hex(), 'gas_used': receipt.gasUsed})
            return receipt
        else:
            logger.error(f" {stage_name} Tx Failed.")
            self.metrics['action_taken'] = self.ACTION_STATES['TX_REVERTED']
            return None

    def _perform_swap_for_fees(self, funding_account, private_key):
        logger.info(f"\n--- Simulating {DEFAULT_NUM_SWAPS} Market Swaps To Generate Fees ---")
        # Simplified: always swap 500 USDC for WETH to push price up
        token_in, token_out, amount = self.token0, self.token1, Decimal('500')
        in_dec = self.token0_decimals

        router = web3_utils.get_contract(UNISWAP_V3_ROUTER_ADDRESS, "ISwapRouter")
        token_in_contract = web3_utils.get_contract(token_in, "IERC20")
        amount_wei = int(amount * (10**in_dec))
        
        # Approve once for all swaps
        approve_tx = token_in_contract.functions.approve(UNISWAP_V3_ROUTER_ADDRESS, amount_wei * DEFAULT_NUM_SWAPS)
        nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
        if not web3_utils.send_transaction(approve_tx.build_transaction({'from': funding_account.address, 'gas': 100000, 'nonce': nonce}), private_key):
            return False
        
        successful_swaps = 0
        for i in range(DEFAULT_NUM_SWAPS):
            try:
                params = {
                    'tokenIn': token_in, 'tokenOut': token_out, 'fee': self.contract.functions.fee().call(),
                    'recipient': funding_account.address, 'deadline': int(time.time()) + 600,
                    'amountIn': amount_wei, 'amountOutMinimum': 0, 'sqrtPriceLimitX96': 0
                }
                swap_tx = router.functions.exactInputSingle(params)
                nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
                if web3_utils.send_transaction(swap_tx.build_transaction({'from': funding_account.address, 'gas': 300000, 'nonce': nonce}), private_key):
                    successful_swaps += 1
                    logger.info(f"Swap {i+1}/{DEFAULT_NUM_SWAPS} successful.")
                time.sleep(0.2) # Short delay
            except Exception as e:
                logger.warning(f"Swap {i+1} failed: {e}")
        self.metrics['num_swaps_executed'] = successful_swaps
        return successful_swaps > 0

    def _call_collect_fees_only(self, funding_account, private_key):
        logger.info("\n--- Explicitly Collecting Fees ---")
        tx_call = self.contract.functions.collectCurrentFeesOnly()
        nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
        try:
            receipt = web3_utils.send_transaction(tx_call.build_transaction({'from': funding_account.address, 'nonce': nonce, 'gas': 500000}), private_key)
            if receipt and receipt.status == 1:
                logger.info("Fee collection transaction successful.")
                self.metrics['action_taken'] = self.ACTION_STATES['FEES_COLLECT_ONLY_SUCCESS']
                self._parse_events_from_receipt(receipt) # Use the general parser
                return True
        except Exception as e:
            logger.error(f"Fee collection failed: {e}")
        
        self.metrics['action_taken'] = self.ACTION_STATES['FEES_COLLECT_ONLY_FAILED']
        return False

    def _parse_events_from_receipt(self, receipt):
        """A robust function to parse all relevant events from a receipt."""
        logger.info("--- Parsing events from receipt ---")
        try:
            # Parse LiquidityOperation events (for MINT and REMOVE)
            liq_op_logs = self.contract.events.LiquidityOperation().process_receipt(receipt)
            for log in liq_op_logs:
                op_type = log.args.operationType
                logger.info(f"Found 'LiquidityOperation' event of type: {op_type}")
                if op_type == "MINT":
                    self.metrics['amount0_provided_to_mint'] = log.args.amount0
                    self.metrics['amount1_provided_to_mint'] = log.args.amount1
                elif op_type == "REMOVE":
                    # When removing, the amounts collected include principal AND fees.
                    # We can't easily separate them here, but we can log them.
                    # A more advanced version could calculate the fees based on principal.
                    logger.info(f"REMOVE collected: amount0={log.args.amount0}, amount1={log.args.amount1}")

        except Exception as e:
            logger.warning(f"Could not parse 'LiquidityOperation' events. Error: {e}")

        try:
            # Parse FeesOnlyCollected events
            fee_logs = self.contract.events.FeesOnlyCollected().process_receipt(receipt)
            for log in fee_logs:
                logger.info(f"Found 'FeesOnlyCollected' event: fees0={log.args.amount0Fees}, fees1={log.args.amount1Fees}")
                self.metrics['fees_collected_token0'] += log.args.amount0Fees
                self.metrics['fees_collected_token1'] += log.args.amount1Fees
        except Exception as e:
            logger.warning(f"Could not parse 'FeesOnlyCollected' events. Error: {e}")


    def adjust_position(self, target_weth_balance: float, target_usdc_balance: float):
        private_key = os.getenv('PRIVATE_KEY')
        funding_account = Account.from_key(private_key)
        try:
            # STAGE 1
            logger.info("STAGE 1: Initial Position Mint")
            if not contract_funder.ensure_precise_token_balances(self.contract_address, self.token0, self.token0_decimals, target_usdc_balance, self.token1, self.token1_decimals, target_weth_balance, private_key):
                raise Exception("Initial funding failed")
            receipt1 = self._trigger_adjustment(funding_account, private_key, "Initial Adjustment")
            if not receipt1: raise Exception("Initial adjustment failed")
            self._parse_events_from_receipt(receipt1)
            self.metrics['action_taken'] = self.ACTION_STATES['INITIAL_ADJUST_SUCCESS']
            
            # STAGE 2
            logger.info("\nSTAGE 2: Simulating Swaps to Generate Fees")
            if not self._perform_swap_for_fees(funding_account, private_key):
                # This is not a critical failure, maybe no fees were generated. Log and continue.
                logger.warning("Swap simulation did not execute as expected, fee generation might be low.")
            self.metrics['action_taken'] = self.ACTION_STATES['SWAP_SIM_SUCCESS']

            # STAGE 2.5 (Optional fee collect - good for debugging)
            # self._call_collect_fees_only(funding_account, private_key)
            
            # STAGE 3
            logger.info("\nSTAGE 3: Final Position Adjustment (which also collects fees)")
            # Re-funding is important because the first adjustment might not have used all tokens
            if not contract_funder.ensure_precise_token_balances(self.contract_address, self.token0, self.token0_decimals, target_usdc_balance, self.token1, self.token1_decimals, target_weth_balance, private_key):
                raise Exception("Re-funding failed")
            receipt2 = self._trigger_adjustment(funding_account, private_key, "Final Adjustment")
            if not receipt2: raise Exception("Final adjustment failed")
            self._parse_events_from_receipt(receipt2) # This will parse the REMOVE (with fees) and new MINT
            self.metrics['action_taken'] = self.ACTION_STATES['FINAL_ADJUST_SUCCESS']
            logger.info("\n✅ Full test cycle completed successfully.")
            
        except Exception as e:
            logger.error(f"Error during test cycle: {e}", exc_info=True)
            if self.metrics.get('action_taken') not in self.ACTION_STATES.values():
                self.metrics['action_taken'] = self.ACTION_STATES['UNEXPECTED_ERROR']
            self.metrics['error_message'] = str(e)
        finally:
            pos_info = self.get_position_info()
            if pos_info: self.metrics.update(pos_info)
            self.save_metrics()

    def save_metrics(self):
        self.metrics['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Standardize column names based on the image
        columns = [
            'timestamp', 'contract_type', 'action_taken', 'tx_hash', 'gas_used', 
            'predictedPrice_api', 'chainlink_price_onchain', 'predictedTick_calculated', 
            'liquidity', 'tickLower', 'tickUpper', 
            'amount0_provided_to_mint', 'amount1_provided_to_mint', 
            'fees_collected_token0', 'fees_collected_token1', 
            'error_message', 'num_swaps_executed'
        ]
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_exists = RESULTS_FILE.is_file()
        with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
            # Use extrasaction='ignore' to avoid errors if metrics dict has extra keys
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow(self.metrics)
        logger.info(f"Metrics saved to {RESULTS_FILE}")

def main():
    if not web3_utils.init_web3(): sys.exit(1)
    try:
        with open(ADDRESS_FILE_SENTINEL, 'r') as f: addresses = json.load(f)
        sentinel_address, trigger_address = addresses['sentinelAmmAddress'], addresses['automationTriggerAddress']
    except Exception as e:
        logger.critical(f"Could not read address file: {e}"); sys.exit(1)

    target_weth = float(os.getenv('PREDICTIVE_TARGET_WETH', '10.0'))
    target_usdc = float(os.getenv('PREDICTIVE_TARGET_USDC', '25000.0'))
    rwm = int(os.getenv('PREDICTIVE_RWM', 100))
    test_instance = None
    try:
        test_instance = SentinelTest(sentinel_address, trigger_address)
        if test_instance.setup(desired_range_width_multiplier=rwm):
            test_instance.adjust_position(target_weth_balance=target_weth, target_usdc_balance=target_usdc)
        else:
            logger.error("Setup failed.")
            if test_instance:
                test_instance.metrics['action_taken'] = test_instance.ACTION_STATES['SETUP_FAILED']
                test_instance.metrics['error_message'] = 'Test setup failed.'
                test_instance.save_metrics()
    except Exception as e:
        logger.exception(f"FATAL: An unexpected error occurred: {e}")
        if test_instance:
            test_instance.save_metrics()
        sys.exit(1)
    finally:
        logger.info("\n== Sentinel test run finished. ==")

if __name__ == "__main__":
    main()