# baseline_test.py (FINAL-FIXED for web3 v5.x and Indentation)
import os
import sys
import json
import time
import logging
import csv
import math
from datetime import datetime
from pathlib import Path
from web3 import Web3
from eth_account import Account
from decimal import Decimal, getcontext
from web3.logs import DISCARD
from web3.exceptions import ContractLogicError

# --- Adjust path imports ---
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import test.utils.web3_utils as web3_utils
import test.utils.contract_funder as contract_funder

getcontext().prec = 78

try:
    from test.utils.test_base import LiquidityTestBase
    from test.utils.web3_utils import send_transaction, get_contract
except ImportError as e:
    print(f"ERROR importing from test.utils in baseline_test.py: {e}. Check sys.path and __init__.py files.", file=sys.stderr)
    sys.exit(1)

# --- Constants ---
TWO_POW_96 = Decimal(2**96)
MIN_TICK_CONST = -887272
MAX_TICK_CONST = 887272
Q96 = Decimal(2**96)
TOKEN0_DECIMALS = 6
TOKEN1_DECIMALS = 18
UNISWAP_V3_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564" # Mainnet Router

TOKEN_MANAGER_OPTIMIZED_ADDRESS_ENV = os.getenv('TOKEN_MANAGER_OPTIMIZED_ADDRESS')

# --- Setup Logging ---
if not logging.getLogger('baseline_test').hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("baseline_test.log", mode='a'), 
            logging.StreamHandler(sys.stdout)
        ]
    )
logger = logging.getLogger('baseline_test')

# --- Define path for addresses and results ---
ADDRESS_FILE_BASELINE = project_root / 'baselineMinimal_address.json'
RESULTS_FILE = project_root / 'position_results_baseline.csv'

logger.info(f"Project Root for Baseline Test (from baseline_test.py): {project_root}")
logger.info(f"Baseline Address File: {ADDRESS_FILE_BASELINE}")
logger.info(f"Baseline Results File: {RESULTS_FILE}")


class BaselineTest(LiquidityTestBase):
    """Test implementation for BaselineMinimal with token funding."""

    def __init__(self, contract_address: str):
        super().__init__(contract_address, "BaselineMinimal")
        self.ACTION_STATES = { 
            "INIT": "init", "SETUP_FAILED": "setup_failed",
            "POOL_READ_FAILED": "pool_read_failed", "CALCULATION_FAILED": "calculation_failed",
            "SKIPPED_PROXIMITY": "skipped_proximity", "FUNDING_FAILED": "funding_failed",
            "TX_SENT": "tx_sent", "TX_SUCCESS_ADJUSTED": "tx_success_adjusted", 
            "TX_SUCCESS_SKIPPED_ONCHAIN": "tx_success_skipped_onchain", 
            "TX_REVERTED": "tx_reverted", "TX_WAIT_FAILED": "tx_wait_failed",
            "METRICS_UPDATE_FAILED": "metrics_update_failed", "UNEXPECTED_ERROR": "unexpected_error",
            "TX_SUCCESS_ADJUSTED_INITIAL": "tx_success_adjusted_initial",
            "TX_SUCCESS_SWAP_FEES": "tx_success_swap_fees", 
            "TX_SUCCESS_ADJUSTED_FINAL": "tx_success_adjusted_final", 
            "SWAP_FOR_FEES_FAILED": "swap_for_fees_failed",
            "FEES_COLLECT_ONLY_SUCCESS": "fees_collect_only_success", 
            "FEES_COLLECT_ONLY_FAILED": "fees_collect_only_failed"
        }
        self.metrics = self._reset_metrics() 
        self.factory_contract = None
        self.tick_spacing = None
        self.pool_address = None
        self.pool_contract = None
        self.token0_contract_instance = None
        self.token1_contract_instance = None
        
        self.nft_position_manager_address = None
        self.nft_manager_contract_for_events = None 

        self.token_manager_optimized_address = TOKEN_MANAGER_OPTIMIZED_ADDRESS_ENV

    def _reset_metrics(self):
        base_metrics = super()._reset_metrics()
        baseline_specific_metrics = {
            'contract_type': 'Baseline',
            'action_taken': self.ACTION_STATES["INIT"] if hasattr(self, 'ACTION_STATES') else "init",
            'targetTickLower_offchain': None, 
            'targetTickUpper_offchain': None, 
            'currentTickLower_contract': None,
            'currentTickUpper_contract': None,
            'currentLiquidity_contract': None,
            'finalTickLower_contract': None, 
            'finalTickUpper_contract': None,
            'finalLiquidity_contract': None, 
            'fees_collected_token0_via_collect_only': None,
            'fees_collected_token1_via_collect_only': None
        }
        final_metrics = {**base_metrics, **baseline_specific_metrics}
        original_keys_defaults = { 
            'timestamp': None, 'tx_hash': None, 'range_width_multiplier_setting': None,
            'external_api_eth_price': None, 'actualPrice_pool': None, 
            'sqrtPriceX96_pool': None, 'currentTick_pool': None,
            'initial_contract_balance_token0': None, 'initial_contract_balance_token1': None,
            'amount0_provided_to_mint': None, 'amount1_provided_to_mint': None,
            'fees_collected_token0': None, 'fees_collected_token1': None, 
            'gas_used': None, 'gas_cost_eth': None, 'error_message': ""
        }
        for key, default_value in original_keys_defaults.items():
            if key not in final_metrics:
                final_metrics[key] = default_value
        return final_metrics

    def setup(self, desired_range_width_multiplier: int) -> bool: 
        if not super().setup(desired_range_width_multiplier):
            self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
            self.metrics['error_message'] = "Base setup failed"
            return False
        try:
            if not web3_utils.w3:
                logger.error("web3_utils.w3 not available in BaselineTest setup after base.setup()"); self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = "web3_utils.w3 unavailable post base setup"; return False

            try:
                self.nft_position_manager_address = Web3.to_checksum_address(
                    self.contract.functions.positionManager().call() 
                )
                logger.info(f"BaselineTest.setup: Uniswap INonfungiblePositionManager address from OUR contract: {self.nft_position_manager_address}")
            except Exception as e_fetch_nfpm:
                logger.error(f"BaselineTest.setup: Failed to fetch INonfungiblePositionManager address from our contract: {e_fetch_nfpm}")
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                self.metrics['error_message'] = f"Failed to get NFPM address: {str(e_fetch_nfpm)}"
                return False

            if self.nft_position_manager_address and self.nft_position_manager_address != ('0x' + '0'*40):
                nft_manager_abi_collect_event = [{"anonymous": False, "inputs": [{"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"},{"indexed": False, "internalType": "address", "name": "recipient", "type": "address"},{"indexed": False, "internalType": "uint256", "name": "amount0", "type": "uint256"},{"indexed": False, "internalType": "uint256", "name": "amount1", "type": "uint256"}],"name": "Collect","type": "event"}]
                try:
                    self.nft_manager_contract_for_events = web3_utils.w3.eth.contract(
                        address=self.nft_position_manager_address,
                        abi=nft_manager_abi_collect_event
                    )
                    logger.info(f"BaselineTest.setup: Initialized contract instance for INonfungiblePositionManager Collect events at {self.nft_position_manager_address}.")
                except Exception as e_init_nft_events:
                    logger.error(f"BaselineTest.setup: Failed to create contract instance for NFPM Collect events using address '{self.nft_position_manager_address}': {e_init_nft_events}")
                    self.nft_manager_contract_for_events = None
            else:
                logger.warning(f"BaselineTest.setup: self.nft_position_manager_address is not validly set (value: {self.nft_position_manager_address}). Cannot initialize for NFPM Collect events.")
                self.nft_manager_contract_for_events = None

            factory_address = self.contract.functions.factory().call()
            self.factory_contract = get_contract(factory_address, "IUniswapV3Factory")
            if not self.factory_contract: self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = "Factory contract not found"; return False

            fee = self.contract.functions.fee().call()
            self.pool_address = self.factory_contract.functions.getPool(self.token0, self.token1, fee).call()
            
            if not self.pool_address or self.pool_address == '0x' + '0' * 40:
                logger.error(f"Baseline pool address not found for {self.token0}/{self.token1} fee {fee}") 
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = f"Pool not found {self.token0}/{self.token1} fee {fee}"; return False
            
            self.pool_contract = get_contract(self.pool_address, "IUniswapV3Pool")
            if not self.pool_contract: self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = "Pool contract object could not be created"; return False
            logger.info(f"Baseline Pool contract initialized at {self.pool_address}")
            
            self.tick_spacing = self.pool_contract.functions.tickSpacing().call() 
            if not self.tick_spacing or self.tick_spacing <= 0: 
                logger.error(f"Invalid tickSpacing read from pool: {self.tick_spacing}")
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = f"Invalid tickSpacing: {self.tick_spacing}"; return False
            logger.info(f"Baseline Tick spacing from pool: {self.tick_spacing}")
            
            logger.info(f"Setting rangeWidthMultiplier to {desired_range_width_multiplier} for Baseline contract...")
            self.metrics['range_width_multiplier_setting'] = desired_range_width_multiplier 
            
            private_key = os.getenv('PRIVATE_KEY')
            if not private_key:
                logger.error("PRIVATE_KEY not set for setting rangeWidthMultiplier (Baseline).")
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = "PRIVATE_KEY missing for RWM setup (Baseline)"; return False
            
            tx_account = Account.from_key(private_key)
            tx_params_rwm = { 
                'from': tx_account.address,
                'nonce': web3_utils.w3.eth.get_transaction_count(tx_account.address),
                'chainId': web3_utils.w3.eth.chain_id
            }
            try:
                gas_estimate_rwm = self.contract.functions.setRangeWidthMultiplier(desired_range_width_multiplier).estimate_gas({'from': tx_account.address})
                tx_params_rwm['gas'] = int(gas_estimate_rwm * 1.2)
            except Exception as e:
                logger.warning(f"Gas estimation failed for setRangeWidthMultiplier (Baseline): {e}. Using default 200000.")
                tx_params_rwm['gas'] = 200000

            tx_set_rwm_build = self.contract.functions.setRangeWidthMultiplier(desired_range_width_multiplier)
            receipt_rwm = web3_utils.send_transaction(tx_set_rwm_build.build_transaction(tx_params_rwm), private_key)
            
            if not receipt_rwm or receipt_rwm.status == 0:
                tx_hash_rwm_str = receipt_rwm.transactionHash.hex() if receipt_rwm else 'N/A'
                logger.error(f"Failed to set rangeWidthMultiplier for Baseline contract. TxHash: {tx_hash_rwm_str}")
                self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";Failed to set RWM for Baseline (tx: {tx_hash_rwm_str})").strip(";")
                return False
            logger.info(f"rangeWidthMultiplier set successfully for Baseline contract. TxHash: {receipt_rwm.transactionHash.hex()}")
            return True
        except Exception as e:
            logger.exception(f"Baseline setup failed: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]; self.metrics['error_message'] = f"Setup error: {str(e)}"; return False

    def get_position_info(self) -> dict | None:
        """Get current position info from the contract for BaselineMinimal."""
        if not self.contract:
            logger.error(f"({self.contract_name}) Contract not initialized. Run setup first (Baseline Override).")
            return None
        if not web3_utils.w3:
            logger.error(f"({self.contract_name}) Web3 not connected in get_position_info (Baseline Override).")
            return None
        
        try:
            pos_data = None
            if hasattr(self.contract.functions, 'currentPosition'):
                pos_data = self.contract.functions.currentPosition().call()
            elif hasattr(self.contract.functions, 'getCurrentPosition'):
                pos_data = self.contract.functions.getCurrentPosition().call()
            else:
                logger.error(f"({self.contract_name}) No known position info method (currentPosition, getCurrentPosition) found on contract (Baseline Override).")
                return None

            if pos_data:
                if len(pos_data) == 5:
                    position = {
                        'tokenId': pos_data[0],
                        'active': pos_data[1],
                        'tickLower': pos_data[2],
                        'tickUpper': pos_data[3],
                        'liquidity': pos_data[4]
                    }
                    logger.debug(f"({self.contract_name}) Fetched Position Info (Baseline Override): {position}")
                    return position
                else:
                    logger.error(f"({self.contract_name}) Position data format unexpected for BaselineMinimal (expected 5 elements). Data: {pos_data} (Baseline Override)")
                    return None
            else:
                logger.error(f"({self.contract_name}) Position data not found or empty for BaselineMinimal (Baseline Override).")
                return None

        except Exception as e:
            logger.exception(f"({self.contract_name}) Failed to get position info from contract (Baseline Override): {e}")
            return None

    def sqrt_price_x96_to_price_token0_in_token1(self, sqrt_price_x96_str: str) -> Decimal:
        sqrt_price_x96 = Decimal(sqrt_price_x96_str)
        price_t1_in_t0 = (sqrt_price_x96 / Q96) ** 2 
        if price_t1_in_t0 == Decimal(0): return Decimal("inf") if sqrt_price_x96 != Decimal(0) else Decimal(0)
        price_t0_in_t1 = Decimal(1) / price_t1_in_t0
        decimals_adjustment = Decimal(10) ** (TOKEN0_DECIMALS - TOKEN1_DECIMALS)
        if decimals_adjustment == Decimal(0): return Decimal("-1") 
        return price_t0_in_t1 / decimals_adjustment

    def _estimate_liquidity(self, tick_lower: int, tick_upper: int) -> int:
        try:
            if not self.token0_contract_instance and self.token0: self.token0_contract_instance = get_contract(self.token0, "IERC20")
            if not self.token1_contract_instance and self.token1: self.token1_contract_instance = get_contract(self.token1, "IERC20")
            if not self.token0_contract_instance or not self.token1_contract_instance or not self.pool_contract: logger.warning("Cannot estimate liquidity: token contracts or pool contract not initialized."); return 0
            token0_bal = self.token0_contract_instance.functions.balanceOf(self.contract_address).call(); token1_bal = self.token1_contract_instance.functions.balanceOf(self.contract_address).call()
            slot0 = self.pool_contract.functions.slot0().call(); current_tick = slot0[1]
            if current_tick < tick_lower: return int(token0_bal) 
            elif current_tick >= tick_upper: return int(token1_bal) 
            else: return int((token0_bal + token1_bal) / 2) 
        except Exception as e: logger.error(f"Error estimating liquidity: {e}"); return 0

    def get_pool_state(self) -> tuple[int | None, int | None]:
        if not self.pool_contract: logger.error("Pool contract not initialized for get_pool_state (Baseline)."); self.metrics['action_taken'] = self.ACTION_STATES["POOL_READ_FAILED"]; self.metrics['error_message'] = "Pool contract missing for get_pool_state"; return None, None
        if not web3_utils.w3: logger.error("Web3 not connected in get_pool_state (Baseline)."); self.metrics['action_taken'] = self.ACTION_STATES["POOL_READ_FAILED"]; self.metrics['error_message'] = "W3 not connected for get_pool_state" ; return None, None
        try:
            slot0 = self.pool_contract.functions.slot0().call(); sqrt_price_x96, tick = slot0[0], slot0[1]
            self.metrics['sqrtPriceX96_pool'] = sqrt_price_x96; self.metrics['currentTick_pool'] = tick
            self.metrics['actualPrice_pool'] = self.sqrt_price_x96_to_price_token0_in_token1(str(sqrt_price_x96))
            logger.info(f"Pool state read: Tick={tick}, SqrtPriceX96={sqrt_price_x96}, ActualPrice={self.metrics['actualPrice_pool']}") 
            return sqrt_price_x96, tick
        except Exception as e: logger.exception(f"Failed to get pool state (Baseline): {e}"); self.metrics['action_taken'] = self.ACTION_STATES["POOL_READ_FAILED"]; self.metrics['error_message'] = f"Pool state read error: {str(e)}"; return None, None
    
    def calculate_target_ticks_offchain(self, current_tick: int) -> tuple[int | None, int | None]:
        if self.tick_spacing is None or current_tick is None: logger.error("Tick spacing or current_tick not available for target tick calculation (Baseline)."); self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]; self.metrics['error_message'] = "Missing data for target tick calc (Baseline)"; return None, None
        try:
            width_multiplier = self.metrics.get('range_width_multiplier_setting')
            if width_multiplier is None or width_multiplier <= 0: width_multiplier = self.contract.functions.rangeWidthMultiplier().call()
            if width_multiplier is None or width_multiplier <= 0: logger.error(f"Invalid rangeWidthMultiplier ({width_multiplier}) for tick calculation."); self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]; self.metrics['error_message'] = f"Invalid RWM ({width_multiplier}) for tick calc"; return None, None
            
            half_total_tick_width = (self.tick_spacing * width_multiplier) // 2
            
            if half_total_tick_width < self.tick_spacing:
                logger.warning(f"Calculated half width {half_total_tick_width} is less than tick spacing {self.tick_spacing}. Using minimum width.")
                half_total_tick_width = self.tick_spacing

            target_lower_tick = ((current_tick - half_total_tick_width) // self.tick_spacing) * self.tick_spacing
            target_upper_tick = ((current_tick + half_total_tick_width) // self.tick_spacing) * self.tick_spacing

            target_lower_tick = max(MIN_TICK_CONST, target_lower_tick)
            target_upper_tick = min(MAX_TICK_CONST, target_upper_tick)
            
            if target_lower_tick >= target_upper_tick:
                logger.error(f"Invalid tick range calculated: [{target_lower_tick}, {target_upper_tick}]"); self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]; self.metrics['error_message'] = "Generated invalid tick range L >= U"; return None, None
            
            logger.info("Target ticks calculation details:"); logger.info(f"  Current tick: {current_tick}"); logger.info(f"  Range width multiplier: {width_multiplier}"); logger.info(f"  Tick spacing: {self.tick_spacing}");
            logger.info(f"  Half width in ticks: {half_total_tick_width}"); logger.info(f"  Target range: [{target_lower_tick}, {target_upper_tick}]")
            self.metrics['targetTickLower_offchain'] = target_lower_tick; self.metrics['targetTickUpper_offchain'] = target_upper_tick
            return target_lower_tick, target_upper_tick
        except Exception as e: logger.exception(f"Error calculating target ticks off-chain (Baseline): {e}"); self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]; self.metrics['error_message'] = f"Target tick calc error (Baseline): {str(e)}"; return None, None

    def _get_contract_token_balances_individually(self):
        balance0_wei, balance1_wei = 0, 0
        try:
            if self.token0:
                token0_contract_instance = web3_utils.get_contract(self.token0, "IERC20")
                if token0_contract_instance: balance0_wei = token0_contract_instance.functions.balanceOf(self.contract_address).call()
            if self.token1:
                token1_contract_instance = web3_utils.get_contract(self.token1, "IERC20")
                if token1_contract_instance: balance1_wei = token1_contract_instance.functions.balanceOf(self.contract_address).call()
        except Exception as e: logger.warning(f"Could not read contract token balances individually (Baseline): {e}")
        return balance0_wei, balance1_wei

    def _perform_swap_for_fees(self, funding_account, private_key_env, swap_token_in_addr: str, swap_token_out_addr: str, swap_amount_readable: Decimal, token_in_decimals: int, token_out_decimals: int):
        """
        Performs a swap directly via the Uniswap V3 Router to generate fees.
        """
        logger.info(f"Attempting swap directly via Uniswap Router: {swap_amount_readable} of {swap_token_in_addr} for {swap_token_out_addr}.")
        try:
            router_contract = web3_utils.get_contract(UNISWAP_V3_ROUTER_ADDRESS, "ISwapRouter")
            token_in_contract = web3_utils.get_contract(swap_token_in_addr, "IERC20")
            if not router_contract or not token_in_contract:
                logger.error("Failed to get Router or Token contract instance for swap.")
                return False

            amount_to_swap_wei = int(swap_amount_readable * (Decimal(10) ** token_in_decimals))
            pool_fee_for_swap = self.contract.functions.fee().call()
            
            logger.info(f"Approving Uniswap Router ({UNISWAP_V3_ROUTER_ADDRESS}) to spend {swap_amount_readable} of token {swap_token_in_addr}...")
            current_nonce_approve = web3_utils.w3.eth.get_transaction_count(funding_account.address)
            approve_tx_params = {'from': funding_account.address, 'nonce': current_nonce_approve, 'gas': 100000}
            
            built_approve_tx = token_in_contract.functions.approve(UNISWAP_V3_ROUTER_ADDRESS, amount_to_swap_wei).build_transaction(approve_tx_params)
            receipt_approve = web3_utils.send_transaction(built_approve_tx, private_key_env)
            if not receipt_approve or receipt_approve.status == 0:
                logger.error(f"Failed to approve Uniswap Router (Baseline). Receipt: {receipt_approve}")
                return False
            logger.info(f"Uniswap Router approved for Baseline. Tx: {receipt_approve.transactionHash.hex()}")
            
            current_nonce_swap = web3_utils.w3.eth.get_transaction_count(funding_account.address)
            logger.info(f"Calling swap on Uniswap Router for Baseline...")
            
            checksum_token_in = Web3.to_checksum_address(swap_token_in_addr)
            checksum_token_out = Web3.to_checksum_address(swap_token_out_addr)
            
            swap_params = {
                'tokenIn': checksum_token_in,
                'tokenOut': checksum_token_out,
                'fee': pool_fee_for_swap,
                'recipient': funding_account.address,
                'deadline': int(time.time()) + 600,
                'amountIn': amount_to_swap_wei,
                'amountOutMinimum': 0,
                'sqrtPriceLimitX96': 0
            }
            swap_tx_params = {'from': funding_account.address, 'nonce': current_nonce_swap, 'gas': 500000 }
            
            built_swap_tx = router_contract.functions.exactInputSingle(swap_params).build_transaction(swap_tx_params)
            receipt_swap = web3_utils.send_transaction(built_swap_tx, private_key_env)

            if receipt_swap and receipt_swap.status == 1:
                logger.info(f"Swap via Uniswap Router for Baseline successful. Tx: {receipt_swap.transactionHash.hex()}")
                return True
            else:
                logger.error(f"Swap via Uniswap Router for Baseline failed. Receipt: {receipt_swap}")
                return False
        except Exception as e:
            logger.exception(f"Error during _perform_swap_for_fees for Baseline: {e}")
            return False

    def _call_collect_fees_only(self, funding_account, private_key_env) -> bool:
        logger.info("Attempting to call collectCurrentFeesOnly() on BaselineMinimal contract...")
        if not self.contract:
            logger.error("BaselineMinimal contract instance not available for collectCurrentFeesOnly."); return False
        
        if self.metrics.get('fees_collected_token0') is None: self.metrics['fees_collected_token0'] = 0
        if self.metrics.get('fees_collected_token1') is None: self.metrics['fees_collected_token1'] = 0
        if 'fees_collected_token0_via_collect_only' in self.metrics and self.metrics.get('fees_collected_token0_via_collect_only') is None:
            self.metrics['fees_collected_token0_via_collect_only'] = 0
        if 'fees_collected_token1_via_collect_only' in self.metrics and self.metrics.get('fees_collected_token1_via_collect_only') is None:
            self.metrics['fees_collected_token1_via_collect_only'] = 0

        tx_call = self.contract.functions.collectCurrentFeesOnly()
        current_nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
        tx_params = {'from': funding_account.address, 'nonce': current_nonce, 'chainId': web3_utils.w3.eth.chain_id}
        try:
            tx_params['gas'] = int(tx_call.estimate_gas({'from': funding_account.address}) * 1.25)
        except ContractLogicError as cle:
            logger.error(f"Gas estimation for collectCurrentFeesOnly (Baseline) failed (Logic Error): {cle}. This might indicate an issue like no active position or other require failure.")
            self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";CollectFeesGasEstLogicError(Baseline): {str(cle)[:100]}").strip(';'); return False
        except Exception as e:
            tx_params['gas'] = 300000 
            logger.warning(f"Gas estimation for collectCurrentFeesOnly (Baseline) failed: {e}. Using default {tx_params['gas']}.")

        try:
            built_tx = tx_call.build_transaction(tx_params)
            receipt = web3_utils.send_transaction(built_tx, private_key_env)

            if receipt and receipt.status == 1:
                logger.info(f"Baseline collectCurrentFeesOnly() transaction successful. Tx: {receipt.transactionHash.hex()}")
                if "FEES_COLLECT_ONLY_SUCCESS" in self.ACTION_STATES: self.metrics['action_taken'] = self.ACTION_STATES["FEES_COLLECT_ONLY_SUCCESS"]
                
                amount0_from_our_event, amount1_from_our_event = 0,0
                
                # CORRECTED FOR WEB3 v5
                our_fee_event_logs = self.contract.events.FeesOnlyCollected().process_receipt(receipt)
                
                if our_fee_event_logs:
                    log_args = our_fee_event_logs[0].args
                    logger.info(f"BaselineContract FeesOnlyCollected Event: TokenId={log_args.tokenId}, Amount0={log_args.amount0Collected}, Amount1={log_args.amount1Collected}, Success={log_args.success}")
                    if log_args.success: amount0_from_our_event = log_args.amount0Collected; amount1_from_our_event = log_args.amount1Collected
                    else: logger.warning("Baseline FeesOnlyCollected event reported success=false from contract.")
                else: logger.warning("No FeesOnlyCollected event found from Baseline contract after collectCurrentFeesOnly call.")

                if 'fees_collected_token0_via_collect_only' in self.metrics: self.metrics['fees_collected_token0_via_collect_only'] = amount0_from_our_event
                if 'fees_collected_token1_via_collect_only' in self.metrics: self.metrics['fees_collected_token1_via_collect_only'] = amount1_from_our_event
                
                if self.metrics.get('fees_collected_token0') is None: self.metrics['fees_collected_token0'] = 0
                if self.metrics.get('fees_collected_token1') is None: self.metrics['fees_collected_token1'] = 0
                self.metrics['fees_collected_token0'] += amount0_from_our_event
                self.metrics['fees_collected_token1'] += amount1_from_our_event
                
                logger.info(f"Baseline Main fee metrics updated: T0={self.metrics['fees_collected_token0']}, T1={self.metrics['fees_collected_token1']}")

                if self.nft_manager_contract_for_events: 
                    logger.info(f"Checking Uniswap NFPM Collect events in Tx: {receipt.transactionHash.hex()} after Baseline collectCurrentFeesOnly call...")
                    
                    # CORRECTED FOR WEB3 v5
                    collect_logs_nfpm = self.nft_manager_contract_for_events.events.Collect().process_receipt(receipt)
                    
                    found_nfpm_collect = False
                    for nfpm_log_entry in collect_logs_nfpm:
                        if nfpm_log_entry.args.recipient.lower() == self.contract_address.lower():
                            found_nfpm_collect = True
                            logger.info(f"Uniswap NFPM Collect Event (Post Baseline collectCurrentFeesOnly, TokenId={nfpm_log_entry.args.tokenId}): Amount0={nfpm_log_entry.args.amount0}, Amount1={nfpm_log_entry.args.amount1}")
                            if not our_fee_event_logs or not our_fee_event_logs[0].args.success :
                                if 'fees_collected_token0_via_collect_only' in self.metrics: self.metrics['fees_collected_token0_via_collect_only'] = nfpm_log_entry.args.amount0
                                if 'fees_collected_token1_via_collect_only' in self.metrics: self.metrics['fees_collected_token1_via_collect_only'] = nfpm_log_entry.args.amount1
                                logger.info("Updated via_collect_only fee metrics from NFPM event due to issue/absence of contract's event.")
                            elif log_args.amount0Collected != nfpm_log_entry.args.amount0 or log_args.amount1Collected != nfpm_log_entry.args.amount1:
                                logger.warning(f"Discrepancy (Baseline): OurEvent(0:{log_args.amount0Collected}, 1:{log_args.amount1Collected}) vs NFPMEvent(0:{nfpm_log_entry.args.amount0}, 1:{nfpm_log_entry.args.amount1}).")
                                break
                    if not found_nfpm_collect: logger.info("No direct Uniswap NFPM Collect event found with Baseline contract as recipient in this transaction.")
                return True
            else:
                tx_hash_str = receipt.transactionHash.hex() if receipt else "N/A"; logger.error(f"Baseline collectCurrentFeesOnly() transaction failed. Tx: {tx_hash_str}")
                if "FEES_COLLECT_ONLY_FAILED" in self.ACTION_STATES: self.metrics['action_taken'] = self.ACTION_STATES["FEES_COLLECT_ONLY_FAILED"]
                self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";BaselineCollectFeesTxFailed: {tx_hash_str}").strip(';'); return False
        except Exception as e:
            logger.exception(f"Exception during Baseline _call_collect_fees_only: {e}")
            if "FEES_COLLECT_ONLY_FAILED" in self.ACTION_STATES: self.metrics['action_taken'] = self.ACTION_STATES["FEES_COLLECT_ONLY_FAILED"]
            self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";BaselineCollectFeesException: {str(e)[:100]}").strip(';'); return False

    def adjust_position(self, target_weth_balance: float, target_usdc_balance: float):
        self.metrics = self._reset_metrics() 
        try:
            self.get_current_eth_price()
            current_rwm = self.contract.functions.rangeWidthMultiplier().call() 
            self.metrics['range_width_multiplier_setting'] = current_rwm
        except Exception: logger.warning("Could not read current rangeWidthMultiplier from baseline contract for metrics.")

        stage_results = {
            'initial_adjustment': False,
            'swap': False,
            'collect_only': False,
            'final_adjustment': False
        }
        
        private_key_env = os.getenv('PRIVATE_KEY')
        if not private_key_env:
            logger.error("PRIVATE_KEY not found for adjust_position (Baseline)."); self.metrics['action_taken'] = self.ACTION_STATES["UNEXPECTED_ERROR"]; self.metrics['error_message'] = "PRIVATE_KEY missing for adjustment tx (Baseline)"; self.save_metrics(); sys.exit(1)
        funding_account = Account.from_key(private_key_env)
        
        try:
            pos_info_before_all = self.get_position_info()
            if pos_info_before_all:
                self.metrics['currentTickLower_contract'] = pos_info_before_all.get('tickLower',0)
                self.metrics['currentTickUpper_contract'] = pos_info_before_all.get('tickUpper',0)
                self.metrics['currentLiquidity_contract'] = pos_info_before_all.get('liquidity', 0)
            else: self.metrics['currentTickLower_contract'] = 0; self.metrics['currentTickUpper_contract'] = 0; self.metrics['currentLiquidity_contract'] = 0

            # --- STAGE 1: Initial Position Adjustment ---
            logger.info("\n--- STAGE 1: Baseline Strategy - Initial position adjustment ---")
            _, current_tick_initial = self.get_pool_state() 
            if current_tick_initial is None: raise Exception("Could not get initial pool state")
            target_lower_tick_initial, target_upper_tick_initial = self.calculate_target_ticks_offchain(current_tick_initial)
            if target_lower_tick_initial is None or target_upper_tick_initial is None: raise Exception("Could not calculate target ticks")
            
            current_pos_info_for_check = self.get_position_info()
            current_pos_active_stage1 = current_pos_info_for_check.get('active', False) if current_pos_info_for_check else False
            current_lower_for_check = current_pos_info_for_check.get('tickLower') if current_pos_info_for_check else None
            current_upper_for_check = current_pos_info_for_check.get('tickUpper') if current_pos_info_for_check else None

            if current_pos_active_stage1 and current_lower_for_check is not None and current_upper_for_check is not None and self.tick_spacing is not None and \
               target_lower_tick_initial == current_lower_for_check and target_upper_tick_initial == current_upper_for_check:
                logger.info(f"Baseline: Target ticks ({target_lower_tick_initial}, {target_upper_tick_initial}) match current on-chain. Skipping initial on-chain adjustment call.") 
                self.metrics['action_taken'] = self.ACTION_STATES["SKIPPED_PROXIMITY"]
                self.metrics['finalTickLower_contract'] = current_lower_for_check
                self.metrics['finalTickUpper_contract'] = current_upper_for_check
                self.metrics['finalLiquidity_contract'] = current_pos_info_for_check.get('liquidity',0) if current_pos_info_for_check else 0
                stage_results['initial_adjustment'] = True
            else:
                logger.info("Ensuring precise token balances for Baseline contract (initial)...")
                if not contract_funder.ensure_precise_token_balances(
                    self.contract_address, self.token0, self.token0_decimals, target_usdc_balance,
                    self.token1, self.token1_decimals, target_weth_balance, private_key_env
                ):
                    raise Exception("Precise funding for Baseline contract failed (initial).")
                
                balance0_val, balance1_val = self._get_contract_token_balances_individually()
                self.metrics['initial_contract_balance_token0'] = balance0_val
                self.metrics['initial_contract_balance_token1'] = balance1_val
                logger.info(f"Initial contract balances for baseline metrics (after funding): Token0={balance0_val}, Token1={balance1_val}")

                logger.info(f"Calling adjustLiquidityWithCurrentPrice for Baseline contract (initial)...")
                tx_function_call_base_initial = self.contract.functions.adjustLiquidityWithCurrentPrice()
                current_nonce_initial_adjust = web3_utils.w3.eth.get_transaction_count(funding_account.address) 
                tx_params_base_initial = {'from': funding_account.address, 'nonce': current_nonce_initial_adjust, 'chainId': web3_utils.w3.eth.chain_id}
                try: 
                    gas_estimate_base_initial = tx_function_call_base_initial.estimate_gas({'from': funding_account.address})
                    tx_params_base_initial['gas'] = int(gas_estimate_base_initial * 1.25)
                except Exception as est_err_base: 
                    logger.warning(f"Gas estimation for 'adjustLiquidityWithCurrentPrice' (initial) failed: {est_err_base}. Using default 1,500,000")
                    tx_params_base_initial['gas'] = 1500000
                
                built_tx_base_initial = tx_function_call_base_initial.build_transaction(tx_params_base_initial)
                receipt_base_initial = web3_utils.send_transaction(built_tx_base_initial, private_key_env)
                self.metrics['tx_hash'] = receipt_base_initial.transactionHash.hex() if receipt_base_initial else None
                
                if receipt_base_initial and receipt_base_initial.status == 1:
                    logger.info(f"Baseline initial adjustment transaction successful. Tx: {self.metrics['tx_hash']}.")
                    self.metrics['gas_used'] = receipt_base_initial.get('gasUsed', 0) 
                    
                    # CORRECTED FOR WEB3 v5
                    eff_gas_price_base_initial = receipt_base_initial.get('effectiveGasPrice', web3_utils.w3.eth.gas_price)
                    self.metrics['gas_cost_eth'] = float(web3_utils.w3.from_wei(self.metrics['gas_used'] * eff_gas_price_base_initial, 'ether'))
                    stage_results['initial_adjustment'] = True
                    
                    # CORRECTED FOR WEB3 v5
                    adj_metrics_logs_initial = self.contract.events.BaselineAdjustmentMetrics().process_receipt(receipt_base_initial)
                    
                    was_adjusted_onchain_initial = False
                    if adj_metrics_logs_initial:
                        was_adjusted_onchain_initial = adj_metrics_logs_initial[0].args.adjusted
                        self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_ADJUSTED_INITIAL"] if was_adjusted_onchain_initial else self.ACTION_STATES["TX_SUCCESS_SKIPPED_ONCHAIN"]
                        self.metrics['targetTickLower_offchain'] = adj_metrics_logs_initial[0].args.targetTickLower 
                        self.metrics['targetTickUpper_offchain'] = adj_metrics_logs_initial[0].args.targetTickUpper
                    else: 
                        self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_ADJUSTED_INITIAL"]
                    
                    if was_adjusted_onchain_initial:
                        # CORRECTED FOR WEB3 v5
                        mint_logs_base_initial = self.contract.events.PositionMinted().process_receipt(receipt_base_initial)
                        
                        if mint_logs_base_initial: 
                            log_entry = mint_logs_base_initial[0]
                            if hasattr(log_entry.args, 'amount0Actual') and hasattr(log_entry.args, 'amount1Actual'): 
                                self.metrics['amount0_provided_to_mint'] = log_entry.args.amount0Actual 
                                self.metrics['amount1_provided_to_mint'] = log_entry.args.amount1Actual
                                self.metrics['finalTickLower_contract'] = log_entry.args.tickLower 
                                self.metrics['finalTickUpper_contract'] = log_entry.args.tickUpper 
                                self.metrics['finalLiquidity_contract'] = log_entry.args.liquidity
                            else: 
                                logger.error(f"Baseline PositionMinted (initial) event missing amount0Actual/amount1Actual attributes.")
                        else: 
                            logger.warning("Baseline initial tx successful & adjusted, but no PositionMinted event found.")
                    else: 
                        logger.info("Baseline initial adjustment call successful but skipped on-chain position change.")
                        # CORRECTED SYNTAX AND INDENTATION
                        pos_info_after_skip = self.get_position_info()
                        if pos_info_after_skip:
                            self.metrics['finalTickLower_contract'] = pos_info_after_skip.get('tickLower',0)
                            self.metrics['finalTickUpper_contract'] = pos_info_after_skip.get('tickUpper',0)
                            self.metrics['finalLiquidity_contract'] = pos_info_after_skip.get('liquidity',0)
                        self.metrics['amount0_provided_to_mint'] = 0
                        self.metrics['amount1_provided_to_mint'] = 0
                else: 
                    self.metrics['action_taken'] = self.ACTION_STATES["TX_REVERTED"] if receipt_base_initial else self.ACTION_STATES["TX_WAIT_FAILED"]
                    self.metrics['error_message'] = "tx_reverted_onchain (Baseline initial)"
                    if receipt_base_initial: self.metrics['gas_used'] = receipt_base_initial.get('gasUsed', 0)
                    raise Exception("Baseline initial adjustment transaction failed")
        
            # --- STAGE 2: Swap Simulation ---
            if stage_results['initial_adjustment']:
                NUM_SWAPS = 5
                SWAP_AMOUNT_WETH = Decimal("2.5")
                logger.info(f"\n--- STAGE 2: Baseline Strategy - Simulating {NUM_SWAPS} swaps to generate fees ---")
                all_swaps_successful = True
                i = 0
                for i in range(NUM_SWAPS):
                    logger.info(f"--- Performing Swap {i + 1}/{NUM_SWAPS} for Baseline ---")
                    if not self._perform_swap_for_fees(funding_account, private_key_env, self.token1, self.token0, SWAP_AMOUNT_WETH, TOKEN1_DECIMALS, TOKEN0_DECIMALS):
                        logger.error(f"Swap {i + 1} failed. Stopping simulation.")
                        all_swaps_successful = False
                        break
                    time.sleep(1) 
                stage_results['swap'] = all_swaps_successful
                if all_swaps_successful:
                    self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_SWAP_FEES"]
                    logger.info(f"All {NUM_SWAPS} swaps for Baseline completed successfully.")
                else:
                    self.metrics['action_taken'] = self.ACTION_STATES["SWAP_FOR_FEES_FAILED"]
                    self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";Swap simulation failed at iteration {i + 1}").strip(';')
                    raise Exception("Swap Simulation failed")
        
            # --- STAGE 2.5: Explicitly Collect Fees ---
            if stage_results['initial_adjustment'] and stage_results['swap']:
                logger.info("\n--- STAGE 2.5: Baseline Strategy - Explicit Fee Collection ---")
                stage_results['collect_only'] = self._call_collect_fees_only(funding_account, private_key_env)
                if not stage_results['collect_only']:
                    raise Exception("Fee Collection failed")
            
            # --- STAGE 3: Second Position Adjustment ---
            if stage_results['initial_adjustment'] and stage_results['swap'] and stage_results['collect_only']:
                logger.info("\n--- STAGE 3: Baseline Strategy - Second position adjustment (fee collection) ---")
                logger.info("Ensuring precise token balances for Baseline contract (final)...")
                if not contract_funder.ensure_precise_token_balances(
                    self.contract_address, self.token0, self.token0_decimals, target_usdc_balance, 
                    self.token1, self.token1_decimals, target_weth_balance, private_key_env
                ): 
                    logger.error("Precise funding for Baseline contract failed (final).")
                    self.metrics['error_message'] = (self.metrics.get('error_message',"") + ";Funding failed (final)").strip(";")
                
                balance0_before_final_adj, balance1_before_final_adj = self._get_contract_token_balances_individually()
                logger.info(f"Balances before final adjustLiquidityWithCurrentPrice (Baseline): Token0={balance0_before_final_adj}, Token1={balance1_before_final_adj}")

                logger.info(f"Calling adjustLiquidityWithCurrentPrice for Baseline contract (final)...")
                tx_function_call_base_final = self.contract.functions.adjustLiquidityWithCurrentPrice()
                current_nonce_final_adjust = web3_utils.w3.eth.get_transaction_count(funding_account.address) 
                tx_params_base_final = {'from': funding_account.address, 'nonce': current_nonce_final_adjust, 'chainId': web3_utils.w3.eth.chain_id}
                try: 
                    gas_estimate_base_final = tx_function_call_base_final.estimate_gas({'from': funding_account.address})
                    tx_params_base_final['gas'] = int(gas_estimate_base_final * 1.25)
                except Exception as est_err_base_final: 
                    logger.warning(f"Gas estimation for 'adjustLiquidityWithCurrentPrice' (final) failed: {est_err_base_final}. Using default 1,500,000")
                    tx_params_base_final['gas'] = 1500000
                
                built_tx_base_final = tx_function_call_base_final.build_transaction(tx_params_base_final)
                receipt_base_final = web3_utils.send_transaction(built_tx_base_final, private_key_env)
                self.metrics['tx_hash'] = receipt_base_final.transactionHash.hex() if receipt_base_final else self.metrics.get('tx_hash')

                if receipt_base_final and receipt_base_final.status == 1:
                    logger.info(f"Baseline final adjustment transaction successful. Tx: {self.metrics['tx_hash']}.")
                    self.metrics['gas_used'] += receipt_base_final.get('gasUsed', 0) 
                    
                    # CORRECTED FOR WEB3 v5
                    eff_gas_price_base_final = receipt_base_final.get('effectiveGasPrice', web3_utils.w3.eth.gas_price)
                    self.metrics['gas_cost_eth'] += float(web3_utils.w3.from_wei(receipt_base_final.get('gasUsed', 0) * eff_gas_price_base_final, 'ether')) 
                    stage_results['final_adjustment'] = True
                    
                    # CORRECTED FOR WEB3 v5
                    adj_metrics_logs_final = self.contract.events.BaselineAdjustmentMetrics().process_receipt(receipt_base_final)
                    
                    was_adjusted_onchain_final = False
                    if adj_metrics_logs_final:
                        was_adjusted_onchain_final = adj_metrics_logs_final[0].args.adjusted
                        self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_ADJUSTED_FINAL"] if was_adjusted_onchain_final else self.ACTION_STATES["TX_SUCCESS_SKIPPED_ONCHAIN"]
                        self.metrics['targetTickLower_offchain'] = adj_metrics_logs_final[0].args.targetTickLower
                        self.metrics['targetTickUpper_offchain'] = adj_metrics_logs_final[0].args.targetTickUpper
                    else: 
                        self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_ADJUSTED_FINAL"]
                    
                    if was_adjusted_onchain_final:
                        # CORRECTED FOR WEB3 v5
                        mint_logs_base_final = self.contract.events.PositionMinted().process_receipt(receipt_base_final)
                        
                        if mint_logs_base_final:
                            log_entry = mint_logs_base_final[0]
                            self.metrics['amount0_provided_to_mint'] = log_entry.args.amount0Actual 
                            self.metrics['amount1_provided_to_mint'] = log_entry.args.amount1Actual 
                            self.metrics['finalTickLower_contract'] = log_entry.args.tickLower
                            self.metrics['finalTickUpper_contract'] = log_entry.args.tickUpper
                            self.metrics['finalLiquidity_contract'] = log_entry.args.liquidity
                        else: 
                            logger.warning("Baseline final tx successful & adjusted, but no PositionMinted event found.")
                    else: 
                        logger.info("Baseline final adjustment call successful but skipped on-chain position change.")
                    
                    if self.nft_manager_contract_for_events and was_adjusted_onchain_final:
                        logger.info(f"Checking Uniswap NFPM Collect events for fees in FINAL Baseline Tx: {receipt_base_final.transactionHash.hex()} ...")
                        
                        # CORRECTED FOR WEB3 v5
                        collect_logs_nfpm_final = self.nft_manager_contract_for_events.events.Collect().process_receipt(receipt_base_final)
                        
                        if not collect_logs_nfpm_final: logger.info(f"No NFPM Collect events found in FINAL Baseline Tx.")
                        for nfpm_log_entry in collect_logs_nfpm_final:
                            if nfpm_log_entry.args.recipient.lower() == self.contract_address.lower():
                                logger.info(f"Uniswap NFPM Collect Event (FINAL Baseline Tx, TokenId={nfpm_log_entry.args.tokenId}): Amount0={nfpm_log_entry.args.amount0}, Amount1={nfpm_log_entry.args.amount1}")
                                if self.metrics.get('fees_collected_token0') is None: self.metrics['fees_collected_token0'] = 0
                                if self.metrics.get('fees_collected_token1') is None: self.metrics['fees_collected_token1'] = 0
                                self.metrics['fees_collected_token0'] += nfpm_log_entry.args.amount0
                                self.metrics['fees_collected_token1'] += nfpm_log_entry.args.amount1
                                logger.info(f"Main fee metrics (Baseline fees_collected_token0/1) updated from FINAL Tx NFPM Collect: ({self.metrics['fees_collected_token0']}, {self.metrics['fees_collected_token1']})")
                                break
                else:
                    raise Exception("Final adjustment transaction failed")

        except Exception as e:
            logger.exception(f"An exception occurred during Baseline adjust_position: {e}")
            if self.metrics.get("action_taken") == "init": # If no action was set yet
                self.metrics["action_taken"] = self.ACTION_STATES["UNEXPECTED_ERROR"]
            if not self.metrics.get("error_message"):
                self.metrics["error_message"] = str(e)
            
        finally:
            logger.info("Updating final position info in 'finally' block for Baseline (absolute final state)...") 
            final_pos_info = self.get_position_info()
            if final_pos_info:  
                self.metrics['finalTickLower_contract'] = final_pos_info.get('tickLower',0) 
                self.metrics['finalTickUpper_contract'] = final_pos_info.get('tickUpper',0) 
                self.metrics['finalLiquidity_contract'] = final_pos_info.get('liquidity',0)
            else: 
                logger.warning("Baseline: Could not get final position info from contract in finally block.") 
            self.save_metrics() 

    def save_metrics(self): 
        self.metrics['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        metric_value = self.metrics.get('actualPrice_pool') 
        if isinstance(metric_value, Decimal): self.metrics['actualPrice_pool'] = f"{metric_value}"
        elif metric_value is None: self.metrics['actualPrice_pool'] = ""
        
        columns = [
            'timestamp', 'contract_type', 'action_taken', 'tx_hash',
            'range_width_multiplier_setting', 'external_api_eth_price',
            'actualPrice_pool', 'sqrtPriceX96_pool', 'currentTick_pool',
            'targetTickLower_offchain', 'targetTickUpper_offchain',
            'initial_contract_balance_token0', 'initial_contract_balance_token1',
            'currentTickLower_contract', 'currentTickUpper_contract', 'currentLiquidity_contract',
            'finalTickLower_contract', 'finalTickUpper_contract', 'finalLiquidity_contract',
            'amount0_provided_to_mint', 'amount1_provided_to_mint',
            'fees_collected_token0', 'fees_collected_token1',
            'gas_used', 'gas_cost_eth', 'error_message'
        ]
        
        row_data = {}
        for col in columns:
            val = self.metrics.get(col)
            if val is None:
                if col in ['sqrtPriceX96_pool', 'currentTick_pool', 'targetTickLower_offchain', 'targetTickUpper_offchain',
                           'initial_contract_balance_token0', 'initial_contract_balance_token1',
                           'currentTickLower_contract', 'currentTickUpper_contract', 'currentLiquidity_contract',
                           'finalTickLower_contract', 'finalTickUpper_contract', 'finalLiquidity_contract',
                           'amount0_provided_to_mint', 'amount1_provided_to_mint',
                           'fees_collected_token0', 'fees_collected_token1',
                           'fees_collected_token0_via_collect_only', 'fees_collected_token1_via_collect_only',
                           'gas_used', 'gas_cost_eth', 'range_width_multiplier_setting']:
                    row_data[col] = 0 if col not in ['external_api_eth_price'] else ""
                elif col not in ['tx_hash', 'error_message', 'action_taken', 'contract_type', 'timestamp', 'actualPrice_pool', 'external_api_eth_price']:
                    row_data[col] = ""
                elif self.metrics.get(col) is None :
                    row_data[col] = ""
            else:
                if col == 'external_api_eth_price' and isinstance(val, float): row_data[col] = f"{val:.2f}"
                elif col == 'gas_cost_eth' and isinstance(val, float): row_data[col] = f"{val:.18f}" 
                else: row_data[col] = val
        
        try:
            RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            file_exists = RESULTS_FILE.is_file() 
            with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f: 
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore') 
                if not file_exists or os.path.getsize(RESULTS_FILE) == 0: writer.writeheader() 
                writer.writerow(row_data)
            logger.info(f"Baseline metrics saved to {RESULTS_FILE}")
        except Exception as e: 
            logger.exception(f"Failed to save baseline metrics: {e}") 

def main():
    logger.info("="*50)
    logger.info("Starting Baseline Minimal Liquidity Manager Test on Fork")
    logger.info("="*50)

    if not web3_utils.init_web3():
        logger.critical("Web3 initialization failed. Exiting baseline test.")
        sys.exit(1)
        
    if not web3_utils.w3:
        logger.critical("web3_utils.w3 instance not available after init. Exiting baseline test.")
        sys.exit(1)

    baseline_address_val = None
    test_baseline = None
    try:
        baseline_address_env = os.getenv('BASELINE_MINIMAL_ADDRESS')
        if not baseline_address_env:
            logger.error(f"BASELINE_MINIMAL_ADDRESS not found in environment variables.")
            temp_test_b_error = BaselineTest("0x" + "0" * 40)
            temp_test_b_error.metrics['action_taken'] = temp_test_b_error.ACTION_STATES["SETUP_FAILED"]
            temp_test_b_error.metrics['error_message'] = "BASELINE_MINIMAL_ADDRESS env var not found"
            temp_test_b_error.save_metrics()
            raise ValueError("BASELINE_MINIMAL_ADDRESS env var not found")
        
        baseline_address_val = Web3.to_checksum_address(baseline_address_env)
        logger.info(f"Loaded Baseline Minimal Address from ENV: {baseline_address_val}")
        
        test_baseline = BaselineTest(baseline_address_val)
        
        desired_rwm_base = int(os.getenv('BASELINE_RWM', '100'))
        target_weth_for_test = float(os.getenv('BASELINE_TARGET_WETH', '5.0'))
        target_usdc_for_test = float(os.getenv('BASELINE_TARGET_USDC', '10000.0'))
        
        # 1. Call setup with its specific parameter
        setup_success = test_baseline.setup(desired_range_width_multiplier=desired_rwm_base)
        
        # 2. If setup is successful, call adjust_position with its parameters
        if setup_success:
            test_baseline.adjust_position(
                target_weth_balance=target_weth_for_test,
                target_usdc_balance=target_usdc_for_test
            )
        else:
            logger.error("Baseline setup failed. Skipping adjust_position.")
            sys.exit(1)

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration Error for Baseline: {e}")
        if test_baseline:
            test_baseline.metrics['action_taken'] = test_baseline.ACTION_STATES["SETUP_FAILED"]
            test_baseline.metrics['error_message'] = str(e)
            test_baseline.save_metrics()
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred during baseline main execution:")
        if test_baseline:
            test_baseline.metrics['action_taken'] = test_baseline.ACTION_STATES["UNEXPECTED_ERROR"]
            test_baseline.metrics['error_message'] = (test_baseline.metrics.get('error_message', "") + f";MainException: {str(e)}").strip(";")
            test_baseline.save_metrics()
        sys.exit(1)
    finally:
        logger.info("=" * 50)
        logger.info("Baseline test run finished.")
        logger.info("=" * 50)

if __name__ == "__main__":
    main()