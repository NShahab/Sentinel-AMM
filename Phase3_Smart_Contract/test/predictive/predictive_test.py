# predictive_test.py (FINAL-FIXED for web3 v5.x and All Syntax)
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
    print(f"ERROR importing from test.utils in predictive_test.py: {e}. Check sys.path and __init__.py files.", file=sys.stderr)
    sys.exit(1)

# --- Constants ---
TWO_POW_96 = Decimal(2**96)
MIN_TICK_CONST = -887272
MAX_TICK_CONST = 887272
UNISWAP_V3_ROUTER_ADDRESS = "0xE592427A0AEce92De3Edee1F18E0157C05861564" # Mainnet Router
DEFAULT_NUM_SWAPS = 20  # ????? ??????? ???????

TOKEN_MANAGER_OPTIMIZED_ADDRESS_ENV = os.getenv('TOKEN_MANAGER_OPTIMIZED_ADDRESS')

# --- Setup Logging ---
if not logging.getLogger('predictive_test').hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("predictive_test.log", mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
logger = logging.getLogger('predictive_test')

# --- Define path for addresses and results ---
ADDRESS_FILE_PREDICTIVE = project_root / 'predictiveManager_address.json'
RESULTS_FILE = project_root / 'position_results_predictive.csv'
LSTM_API_URL = os.getenv('LSTM_API_URL', 'http://95.216.156.73:5000/predict_price?symbol=ETHUSDT&interval=4h')

logger.info(f"Project Root for Predictive Test (from predictive_test.py): {project_root}")
logger.info(f"Predictive Address File: {ADDRESS_FILE_PREDICTIVE}")
logger.info(f"Predictive Results File: {RESULTS_FILE}")
logger.info(f"LSTM API URL: {LSTM_API_URL}")

class PredictiveTest(LiquidityTestBase):
    """Test implementation for PredictiveLiquidityManager contract testing on a fork."""

    def __init__(self, contract_address: str):
        self.ACTION_STATES = {
            "INIT": "init", "SETUP_FAILED": "setup_failed",
            "POOL_READ_FAILED": "pool_read_failed", "API_FAILED": "api_failed",
            "CALCULATION_FAILED": "calculation_failed", "FUNDING_FAILED": "funding_failed",
            "TX_SENT": "tx_sent",
            "TX_SUCCESS_ADJUSTED": "tx_success_adjusted",
            "TX_REVERTED": "tx_reverted", "TX_WAIT_FAILED": "tx_wait_failed",
            "METRICS_UPDATE_FAILED": "metrics_update_failed",
            "UNEXPECTED_ERROR": "unexpected_error",
            "TX_SUCCESS_ADJUSTED_INITIAL": "tx_success_adjusted_initial",
            "TX_SUCCESS_SWAP_FEES": "tx_success_swap_fees",
            "TX_SUCCESS_ADJUSTED_FINAL": "tx_success_adjusted_final",
            "SWAP_FOR_FEES_FAILED": "swap_for_fees_failed",
            "FEES_COLLECT_ONLY_SUCCESS": "fees_collect_only_success",
            "FEES_COLLECT_ONLY_FAILED": "fees_collect_only_failed"
        }
        super().__init__(contract_address, "PredictiveLiquidityManager")
        self.metrics = self._reset_metrics()
        self.pool_address = None
        self.pool_contract = None
        self.nft_position_manager_address = None
        self.nft_manager_contract_for_events = None
        self.token_manager_optimized_address = TOKEN_MANAGER_OPTIMIZED_ADDRESS_ENV # Store for reference if needed

    def _reset_metrics(self):
        base_metrics = super()._reset_metrics()
        predictive_metrics = {
            'contract_type': 'Predictive',
            'action_taken': self.ACTION_STATES["INIT"],
            'predictedPrice_api': None,
            'predictedTick_calculated': None,
            'actualPrice_pool': None,
            'fees_collected_token0_via_collect_only': None,
            'fees_collected_token1_via_collect_only': None,
            'num_swaps_executed': 0  # ????? ???? ????? ???? ???? ????? ???????? ???? ???
        }
        final_metrics = {**base_metrics, **predictive_metrics}
        original_keys_defaults = {
            'timestamp': None, 'tx_hash': None, 'range_width_multiplier_setting': None,
            'external_api_eth_price': None, 'sqrtPriceX96_pool': 0, 'currentTick_pool': 0,
            'targetTickLower_calculated': 0, 'targetTickUpper_calculated': 0,
            'initial_contract_balance_token0': None, 'initial_contract_balance_token1': None,
            'finalTickLower_contract': 0, 'finalTickUpper_contract': 0, 'liquidity_contract': 0,
            'amount0_provided_to_mint': None, 'amount1_provided_to_mint': None,
            'fees_collected_token0': None, 'fees_collected_token1': None,
            'gas_used': 0, 'gas_cost_eth': 0.0, 'error_message': ""
        }
        for key, default_value in original_keys_defaults.items():
            if key not in final_metrics:
                final_metrics[key] = default_value
        return final_metrics

    def setup(self, desired_range_width_multiplier: int) -> bool:
        if not super().setup(desired_range_width_multiplier):
            self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
            self.metrics['error_message'] = self.metrics.get('error_message', "Base setup failed")
            if not self.metrics.get('error_message'): self.metrics['error_message'] = "Base setup failed"
            return False
        try:
            if not web3_utils.w3:
                logger.error("web3_utils.w3 not available in PredictiveTest setup after base.setup()")
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                self.metrics['error_message'] = "web3_utils.w3 unavailable post base setup"
                return False

            try:
                self.nft_position_manager_address = Web3.to_checksum_address(
                    self.contract.functions.positionManager().call()
                )
                logger.info(f"PredictiveTest.setup: Fetched Uniswap INonfungiblePositionManager address from OUR contract: {self.nft_position_manager_address}")
            except Exception as e_fetch_nfpm:
                logger.error(f"PredictiveTest.setup: Failed to fetch INonfungiblePositionManager address from our contract: {e_fetch_nfpm}")
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
                    logger.info(f"PredictiveTest.setup: Initialized contract instance for INonfungiblePositionManager Collect events at {self.nft_position_manager_address}.")
                except Exception as e_init_nft_events:
                    logger.error(f"PredictiveTest.setup: Failed to create contract instance for NFPM Collect events using address '{self.nft_position_manager_address}': {e_init_nft_events}")
                    self.nft_manager_contract_for_events = None
            else:
                logger.warning(f"PredictiveTest.setup: self.nft_position_manager_address is not validly set (value: {self.nft_position_manager_address}). Cannot initialize for NFPM Collect events.")
                self.nft_manager_contract_for_events = None

            factory_address = self.contract.functions.factory().call()
            factory_contract = get_contract(factory_address, "IUniswapV3Factory")
            if not factory_contract:
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                self.metrics['error_message'] = "Factory contract not found"
                return False

            fee = self.contract.functions.fee().call()
            self.pool_address = factory_contract.functions.getPool(self.token0, self.token1, fee).call()
            
            if not self.pool_address or self.pool_address == '0x' + '0' * 40:
                logger.error(f"Predictive pool address not found for {self.token0}/{self.token1} fee {fee}")
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                self.metrics['error_message'] = f"Pool not found {self.token0}/{self.token1} fee {fee}"
                return False
                
            self.pool_contract = get_contract(self.pool_address, "IUniswapV3Pool")
            if not self.pool_contract:
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                self.metrics['error_message'] = "Pool contract object could not be created"
                return False

            logger.info(f"Predictive Pool contract initialized at {self.pool_address}")
            
            logger.info(f"Setting rangeWidthMultiplier to {desired_range_width_multiplier} for Predictive contract...")
            self.metrics['range_width_multiplier_setting'] = desired_range_width_multiplier
            
            private_key = os.getenv('PRIVATE_KEY')
            if not private_key:
                logger.error("PRIVATE_KEY not set for setting rangeWidthMultiplier.")
                self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                self.metrics['error_message'] = "PRIVATE_KEY missing for RWM setup"
                return False
            
            tx_account = Account.from_key(private_key)
            tx_params = {
                'from': tx_account.address,
                'nonce': web3_utils.w3.eth.get_transaction_count(tx_account.address),
                'chainId': web3_utils.w3.eth.chain_id
            }
            try:
                # web3.py v5 uses estimate_gas
                gas_estimate = self.contract.functions.setRangeWidthMultiplier(desired_range_width_multiplier).estimate_gas({'from': tx_account.address})
                tx_params['gas'] = int(gas_estimate * 1.2)
            except Exception as e:
                logger.warning(f"Gas estimation failed for setRangeWidthMultiplier: {e}. Using default 200000.")
                tx_params['gas'] = 200000

            tx_set_rwm_build = self.contract.functions.setRangeWidthMultiplier(desired_range_width_multiplier)
            # web3.py v5 uses build_transaction
            receipt_rwm = web3_utils.send_transaction(tx_set_rwm_build.build_transaction(tx_params), private_key)
            
            if not receipt_rwm or receipt_rwm.status == 0:
                tx_hash_rwm = receipt_rwm.transactionHash.hex() if receipt_rwm else 'N/A'
                logger.error(f"Failed to set rangeWidthMultiplier for Predictive contract. TxHash: {tx_hash_rwm}")
                self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";Failed to set RWM (tx: {tx_hash_rwm})").strip(';')
                return False
            logger.info(f"rangeWidthMultiplier set successfully for Predictive contract. TxHash: {receipt_rwm.transactionHash.hex()}")
            return True
        except Exception as e:
            logger.exception(f"Predictive setup failed: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
            self.metrics['error_message'] = f"Setup error: {str(e)}"
            return False

    def get_pool_state(self) -> tuple[int | None, int | None]:
        if not self.pool_contract:
            logger.error("Pool contract not initialized for get_pool_state (Predictive).")
            self.metrics['action_taken'] = self.ACTION_STATES["POOL_READ_FAILED"]
            self.metrics['error_message'] = "Pool contract missing for get_pool_state"
            return None, None

        if not web3_utils.w3:
            logger.error("Web3 not connected in get_pool_state (Predictive).")
            self.metrics['action_taken'] = self.ACTION_STATES["POOL_READ_FAILED"]
            self.metrics['error_message'] = "W3 not connected for get_pool_state"
            return None, None

        try:
            slot0 = self.pool_contract.functions.slot0().call()
            sqrt_price_x96, tick = slot0[0], slot0[1]
            self.metrics['sqrtPriceX96_pool'] = sqrt_price_x96
            self.metrics['currentTick_pool'] = tick
            self.metrics['actualPrice_pool'] = self.sqrt_price_x96_to_price_token0_in_token1(str(sqrt_price_x96))
            return sqrt_price_x96, tick
        except Exception as e:
            logger.exception(f"Failed to get pool state (Predictive): {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["POOL_READ_FAILED"]
            self.metrics['error_message'] = f"Pool state read error: {str(e)}"
            return None, None

    def get_predicted_price_from_api(self) -> float | None:
        try:
            logger.info(f"Querying LSTM API at {LSTM_API_URL}...")
            response = requests.get(LSTM_API_URL, timeout=25)
            response.raise_for_status()
            data = response.json()
            
            predicted_price_str = data.get('predicted_price') or data.get('price') or data.get('prediction')
            if predicted_price_str is None:
                logger.error(f"Predicted price key not found in API response. Data: {data}")
                raise ValueError("Predicted price not in API response")

            if isinstance(predicted_price_str, str):
                predicted_price_str = predicted_price_str.replace("USD", "").strip()

            predicted_price = float(predicted_price_str)
            logger.info(f"Received predicted ETH price from API: {predicted_price:.4f} USD")
            self.metrics['predictedPrice_api'] = predicted_price
            return predicted_price
        except requests.exceptions.Timeout:
            logger.error(f"Timeout when querying LSTM API at {LSTM_API_URL}")
            self.metrics['action_taken'] = self.ACTION_STATES["API_FAILED"]
            self.metrics['error_message'] = f"API Timeout: {LSTM_API_URL}"
            return None
        except requests.exceptions.RequestException as e:
            logger.exception(f"Error getting prediction from API {LSTM_API_URL}: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["API_FAILED"]
            self.metrics['error_message'] = f"API Request Error: {str(e)}"
            return None
        except (ValueError, KeyError) as e:
            data_for_log = 'N/A'
            if 'data' in locals(): data_for_log = data
            logger.exception(f"Error processing API response from {LSTM_API_URL}. Data: {data_for_log}. Error: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["API_FAILED"]
            self.metrics['error_message'] = f"API Response Processing Error: {str(e)}"
            return None

    def calculate_tick_from_price(self, price: float) -> int | None:
        """Calculate Uniswap V3 tick from a given price."""
        if self.token0_decimals is None or self.token1_decimals is None:
            logger.error("Token decimals not available for tick calculation. Ensure LiquidityTestBase.setup() was successful.")
            self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]
            self.metrics['error_message'] = "Token decimals missing for tick calc"
            return None
            
        try:
            price_decimal = Decimal(str(price))
            effective_sqrt_price_arg = (Decimal(1) / price_decimal) * (Decimal(10)**(self.token1_decimals - self.token0_decimals))
            
            if effective_sqrt_price_arg <= 0:
                logger.error(f"Argument for sqrt in tick calculation is non-positive: {effective_sqrt_price_arg} (price: {price}, dec0: {self.token0_decimals}, dec1: {self.token1_decimals})")
                self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]
                self.metrics['error_message'] = "Invalid arg for sqrt in tick calc"
                return None
            
            effective_sqrt_price = effective_sqrt_price_arg.sqrt()
            
            if effective_sqrt_price <= 0:
                logger.error(f"Effective sqrt price for tick calculation is non-positive: {effective_sqrt_price}")
                self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]
                self.metrics['error_message'] = "Invalid effective_sqrt_price for tick calc"
                return None

            tick = math.floor(math.log(float(effective_sqrt_price)) / math.log(math.sqrt(1.0001)))
            tick = max(MIN_TICK_CONST, min(MAX_TICK_CONST, tick))
            
            logger.info(f"Tick calculation details (Original Predictive Logic):")
            logger.info(f"  Input price (assumed T1/T0, e.g. WETH/USDC): {price}")
            logger.info(f"  Effective_sqrt_price_arg ((1/price) * 10^(dec1-dec0)): {effective_sqrt_price_arg}")
            logger.info(f"  Effective_sqrt_price: {effective_sqrt_price}")
            logger.info(f"  Final tick: {tick}")
            
            self.metrics['predictedTick_calculated'] = tick
            return tick
            
        except Exception as e:
            logger.exception(f"Failed to calculate predicted tick from price {price}: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["CALCULATION_FAILED"]
            self.metrics['error_message'] = f"Tick Calculation Error: {str(e)}"
            return None

    def update_pool_and_position_metrics(self, final_update=False):
        try:
            if self.pool_contract:
                slot0 = self.pool_contract.functions.slot0().call()
                sqrt_price_x96_pool, current_tick_pool = slot0[0], slot0[1]
                self.metrics['sqrtPriceX96_pool'] = sqrt_price_x96_pool
                self.metrics['currentTick_pool'] = current_tick_pool
                self.metrics['actualPrice_pool'] = self.sqrt_price_x96_to_price_token0_in_token1(str(sqrt_price_x96_pool))
            else:
                logger.warning("Pool contract not available for metrics update (pool_and_position).")

            position_info = self.get_position_info()
            if position_info:
                is_active = position_info.get('active', False)
                if 'active' not in position_info and len(position_info) == 5 :
                    is_active = position_info[4]

                if 'currentTickLower_contract' in self.metrics:
                    self.metrics['currentTickLower_contract'] = position_info.get('tickLower', self.metrics.get('currentTickLower_contract',0))
                if 'currentTickUpper_contract' in self.metrics:
                    self.metrics['currentTickUpper_contract'] = position_info.get('tickUpper', self.metrics.get('currentTickUpper_contract',0))
                if 'currentLiquidity_contract' in self.metrics:
                    self.metrics['currentLiquidity_contract'] = position_info.get('liquidity', self.metrics.get('currentLiquidity_contract',0))

                if final_update or (is_active and position_info.get('liquidity', 0) > 0):
                    self.metrics['finalTickLower_contract'] = position_info.get('tickLower', 0)
                    self.metrics['finalTickUpper_contract'] = position_info.get('tickUpper', 0)
                    if self.metrics.get('liquidity_contract', 0) == 0 or final_update:
                        self.metrics['liquidity_contract'] = position_info.get('liquidity', 0)
            else:
                logger.warning("Could not get position info from contract for metrics update.")

        except Exception as e:
            logger.exception(f"Error updating pool/position metrics: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["METRICS_UPDATE_FAILED"]
            if not self.metrics.get('error_message'): self.metrics['error_message'] = f"Metrics Update Error: {str(e)}"

    def sqrt_price_x96_to_price_token0_in_token1(self, sqrt_price_x96_str: str) -> Decimal:
        """Convert sqrtPriceX96 to price of token0 in terms of token1 (USDC/WETH) - YOUR ORIGINAL FUNCTION"""
        sqrt_price_x96 = Decimal(sqrt_price_x96_str)
        if sqrt_price_x96 == Decimal(0): return Decimal(0)
        
        if self.token0_decimals is None or self.token1_decimals is None:
            logger.error("Token decimals not available for sqrt_price_x96_to_price_token0_in_token1 (Predictive)")
            return Decimal("-1")

        price_t1_in_t0 = (sqrt_price_x96 / TWO_POW_96)**2
        if price_t1_in_t0 == Decimal(0):
            return Decimal("inf") if sqrt_price_x96 != Decimal(0) else Decimal(0)
        
        price_t0_in_t1 = Decimal(1) / price_t1_in_t0
        decimals_adjustment = Decimal(10)**(self.token0_decimals - self.token1_decimals)
        if decimals_adjustment == Decimal(0):
            return Decimal("-1")

        return price_t0_in_t1 / decimals_adjustment

    def _get_contract_token_balances_individually(self):
        """Helper to get token balances individually for the contract."""
        balance0_wei, balance1_wei = 0, 0
        try:
            if self.token0:
                token0_contract_instance = web3_utils.get_contract(self.token0, "IERC20")
                if token0_contract_instance:
                    balance0_wei = token0_contract_instance.functions.balanceOf(self.contract_address).call()
            if self.token1:
                token1_contract_instance = web3_utils.get_contract(self.token1, "IERC20")
                if token1_contract_instance:
                    balance1_wei = token1_contract_instance.functions.balanceOf(self.contract_address).call()
        except Exception as e:
            logger.warning(f"Could not read contract token balances individually: {e}")
        return balance0_wei, balance1_wei

    def _perform_swap_for_fees(self, funding_account, private_key_env, swap_token_in_addr: str, swap_token_out_addr: str, swap_amount_readable: Decimal, token_in_decimals: int, token_out_decimals: int, num_swaps: int = DEFAULT_NUM_SWAPS):
        """
        Performs multiple swaps directly via the Uniswap V3 Router with a single approve to generate fees.
        """
        logger.info(f"Attempting {num_swaps} swaps via Uniswap Router: {swap_amount_readable} of {swap_token_in_addr} for {swap_token_out_addr} each.")

        try:
            # Get contracts
            router_contract = web3_utils.get_contract(UNISWAP_V3_ROUTER_ADDRESS, "ISwapRouter")
            token_in_contract = web3_utils.get_contract(swap_token_in_addr, "IERC20")
            if not router_contract or not token_in_contract:
                logger.error("Failed to get Router or Token contract instance for swap.")
                return False

            # Calculate total amount needed for all swaps
            single_swap_amount_wei = int(swap_amount_readable * (Decimal(10) ** token_in_decimals))
            total_amount_wei = single_swap_amount_wei * num_swaps
            pool_fee_for_swap = self.contract.functions.fee().call()

            # 1. Single approve for all swaps
            logger.info(f"Approving Uniswap Router ({UNISWAP_V3_ROUTER_ADDRESS}) to spend {total_amount_wei} wei of token {swap_token_in_addr}...")
            
            current_nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
            approve_tx_params = {
                'from': funding_account.address, 
                'nonce': current_nonce, 
                'gas': 100000  # Fixed gas for approve
            }
            
            built_approve_tx = token_in_contract.functions.approve(
                UNISWAP_V3_ROUTER_ADDRESS, 
                total_amount_wei
            ).build_transaction(approve_tx_params)
            
            receipt_approve = web3_utils.send_transaction(built_approve_tx, private_key_env)

            if not receipt_approve or receipt_approve.status == 0:
                logger.error(f"Failed to approve Uniswap Router. Receipt: {receipt_approve}")
                return False
            
            logger.info(f"Uniswap Router approved for total amount. Tx: {receipt_approve.transactionHash.hex()}")

            # 2. Perform multiple swaps
            successful_swaps = 0
            
            for i in range(num_swaps):
                logger.info(f"--- Performing Swap {i + 1}/{num_swaps} ---")
                
                current_nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
                swap_params = {
                    'tokenIn': Web3.to_checksum_address(swap_token_in_addr),
                    'tokenOut': Web3.to_checksum_address(swap_token_out_addr),
                    'fee': pool_fee_for_swap,
                    'recipient': funding_account.address,
                    'deadline': int(time.time()) + 600,
                    'amountIn': single_swap_amount_wei,
                    'amountOutMinimum': 0,
                    'sqrtPriceLimitX96': 0
                }

                swap_tx_params = {
                    'from': funding_account.address,
                    'nonce': current_nonce,
                    'gas': 200000  # Reduced gas for subsequent swaps
                }
                
                try:
                    built_swap_tx = router_contract.functions.exactInputSingle(swap_params).build_transaction(swap_tx_params)
                    receipt_swap = web3_utils.send_transaction(built_swap_tx, private_key_env)

                    if receipt_swap and receipt_swap.status == 1:
                        successful_swaps += 1
                        logger.info(f"Swap {i + 1} successful. Tx: {receipt_swap.transactionHash.hex()}")
                    else:
                        logger.warning(f"Swap {i + 1} failed. Continuing with next swaps...")
                        
                except Exception as e:
                    logger.warning(f"Error in swap {i + 1}: {str(e)}. Continuing...")
                
                # Small delay between swaps
                time.sleep(1)

            logger.info(f"Completed {successful_swaps}/{num_swaps} swaps successfully.")
            self.metrics['num_swaps_executed'] = successful_swaps
            return successful_swaps > 0

        except Exception as e:
            logger.exception(f"Error during _perform_swap_for_fees (Direct Router Swap): {e}")
            return False

    def _call_collect_fees_only(self, funding_account, private_key_env) -> bool:
        logger.info("Attempting to call collectCurrentFeesOnly() on PredictiveLiquidityManager...")
        if not self.contract:
            logger.error("PredictiveLiquidityManager contract instance not available for collectCurrentFeesOnly.")
            return False
        
        if self.metrics.get('fees_collected_token0') is None: self.metrics['fees_collected_token0'] = 0
        if self.metrics.get('fees_collected_token1') is None: self.metrics['fees_collected_token1'] = 0
        if self.metrics.get('fees_collected_token0_via_collect_only') is None: self.metrics['fees_collected_token0_via_collect_only'] = 0
        if self.metrics.get('fees_collected_token1_via_collect_only') is None: self.metrics['fees_collected_token1_via_collect_only'] = 0

        tx_call = self.contract.functions.collectCurrentFeesOnly()
        current_nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
        tx_params = {'from': funding_account.address, 'nonce': current_nonce, 'chainId': web3_utils.w3.eth.chain_id}
        try:
            tx_params['gas'] = int(tx_call.estimate_gas({'from': funding_account.address}) * 1.25)
        except ContractLogicError as cle:
            logger.error(f"Gas estimation for collectCurrentFeesOnly failed (Logic Error): {cle}. This might indicate an issue like no active position or other require failure.")
            self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";CollectFeesGasEstLogicError: {str(cle)[:100]}").strip(';')
            return False
        except Exception as e:
            tx_params['gas'] = 300000
            logger.warning(f"Gas estimation for collectCurrentFeesOnly failed: {e}. Using default {tx_params['gas']}.")

        try:
            built_tx = tx_call.build_transaction(tx_params)
            receipt = web3_utils.send_transaction(built_tx, private_key_env)

            if receipt and receipt.status == 1:
                logger.info(f"collectCurrentFeesOnly() transaction successful. Tx: {receipt.transactionHash.hex()}")
                self.metrics['action_taken'] = self.ACTION_STATES["FEES_COLLECT_ONLY_SUCCESS"]
                
                amount0_from_our_event, amount1_from_our_event = 0, 0
                
                # CORRECTED FOR WEB3 v5
                our_fee_event_logs = self.contract.events.FeesOnlyCollected().process_receipt(receipt)
                
                if our_fee_event_logs:
                    log_args = our_fee_event_logs[0].args
                    logger.info(f"PredictiveContract FeesOnlyCollected Event: TokenId={log_args.tokenId}, Amount0={log_args.amount0Fees}, Amount1={log_args.amount1Fees}, Success={log_args.success}")
                    if log_args.success:
                        amount0_from_our_event = log_args.amount0Fees
                        amount1_from_our_event = log_args.amount1Fees
                    else:
                        logger.warning("FeesOnlyCollected event reported success=false from contract.")
                else:
                    logger.warning("No FeesOnlyCollected event found from our contract after collectCurrentFeesOnly call.")

                self.metrics['fees_collected_token0_via_collect_only'] = amount0_from_our_event
                self.metrics['fees_collected_token1_via_collect_only'] = amount1_from_our_event
                
                # Accumulate fees
                if self.metrics.get('fees_collected_token0') is None: self.metrics['fees_collected_token0'] = 0
                if self.metrics.get('fees_collected_token1') is None: self.metrics['fees_collected_token1'] = 0
                self.metrics['fees_collected_token0'] += amount0_from_our_event
                self.metrics['fees_collected_token1'] += amount1_from_our_event

                logger.info(f"Main fee metrics updated: T0={self.metrics['fees_collected_token0']}, T1={self.metrics['fees_collected_token1']}")

                if self.nft_manager_contract_for_events:
                    logger.info(f"Checking Uniswap NFPM Collect events in Tx: {receipt.transactionHash.hex()} after collectCurrentFeesOnly call...")
                    
                    # CORRECTED FOR WEB3 v5
                    collect_logs_nfpm = self.nft_manager_contract_for_events.events.Collect().process_receipt(receipt)
                    
                    found_nfpm_collect = False
                    for nfpm_log_entry in collect_logs_nfpm:
                        if nfpm_log_entry.args.recipient.lower() == self.contract_address.lower():
                            found_nfpm_collect = True
                            logger.info(f"Uniswap NFPM Collect Event (Post collectCurrentFeesOnly, TokenId={nfpm_log_entry.args.tokenId}): Amount0={nfpm_log_entry.args.amount0}, Amount1={nfpm_log_entry.args.amount1}")
                            if not our_fee_event_logs or not our_fee_event_logs[0].args.success :
                                self.metrics['fees_collected_token0_via_collect_only'] = nfpm_log_entry.args.amount0
                                self.metrics['fees_collected_token1_via_collect_only'] = nfpm_log_entry.args.amount1
                                logger.info("Updated via_collect_only fee metrics from NFPM event due to issue/absence of contract's event.")
                            elif log_args.amount0Fees != nfpm_log_entry.args.amount0 or log_args.amount1Fees != nfpm_log_entry.args.amount1:
                                logger.warning(f"Discrepancy: OurEvent(0:{log_args.amount0Fees}, 1:{log_args.amount1Fees}) vs NFPMEvent(0:{nfpm_log_entry.args.amount0}, 1:{nfpm_log_entry.args.amount1}). Prioritizing our contract's event if successful.")
                            break
                    if not found_nfpm_collect:
                        logger.info("No direct Uniswap NFPM Collect event found with our contract as recipient in this transaction.")
                return True
            else:
                tx_hash_str = receipt.transactionHash.hex() if receipt else "N/A"
                logger.error(f"collectCurrentFeesOnly() transaction failed. Tx: {tx_hash_str}")
                self.metrics['action_taken'] = self.ACTION_STATES["FEES_COLLECT_ONLY_FAILED"]
                self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";CollectFeesTxFailed: {tx_hash_str}").strip(';')
                return False
        except Exception as e:
            logger.exception(f"Exception during _call_collect_fees_only: {e}")
            self.metrics['action_taken'] = self.ACTION_STATES["FEES_COLLECT_ONLY_FAILED"]
            self.metrics['error_message'] = (self.metrics.get('error_message', "") + f";CollectFeesException: {str(e)[:100]}").strip(';')
            return False

    def adjust_position(self, target_weth_balance: float, target_usdc_balance: float):
        # This function now returns nothing and handles its own exceptions/exit logic.
        self.metrics = self._reset_metrics()
        try:
            self.get_current_eth_price()
            current_rwm = self.contract.functions.rangeWidthMultiplier().call()
            self.metrics['range_width_multiplier_setting'] = current_rwm
        except Exception:
            logger.warning("Could not read current rangeWidthMultiplier from predictive contract for metrics.")

        private_key_env = os.getenv('PRIVATE_KEY')
        if not private_key_env:
            logger.error("PRIVATE_KEY not found for adjust_position.")
            self.metrics['action_taken'] = self.ACTION_STATES["UNEXPECTED_ERROR"]
            self.metrics['error_message'] = "PRIVATE_KEY missing for adjustment tx"
            self.save_metrics()
            sys.exit(1) # Exit on critical config error
        
        funding_account = Account.from_key(private_key_env)
        stage_results = {'initial_adjustment': False, 'swap': False, 'collect_only': False, 'final_adjustment': False}
        
        try:
            pos_info_before_all = self.get_position_info()
            if pos_info_before_all:
                if 'currentTickLower_contract' in self.metrics: self.metrics['currentTickLower_contract'] = pos_info_before_all.get('tickLower')
                if 'currentTickUpper_contract' in self.metrics: self.metrics['currentTickUpper_contract'] = pos_info_before_all.get('tickUpper')
                if 'currentLiquidity_contract' in self.metrics: self.metrics['currentLiquidity_contract'] = pos_info_before_all.get('liquidity', 0)

            # --- STAGE 1: Initial Position Adjustment by Strategy Contract ---
            logger.info("\n--- STAGE 1: Predictive Strategy - Initial position adjustment ---")
            predicted_price = self.get_predicted_price_from_api()
            if predicted_price is None:
                self.save_metrics()
                sys.exit(1) # Exit if API fails
            predicted_tick = self.calculate_tick_from_price(predicted_price)
            if predicted_tick is None:
                self.save_metrics()
                sys.exit(1) # Exit if calculation fails
            self.update_pool_and_position_metrics(final_update=False)
            
            logger.info("Ensuring precise token balances for Predictive contract (initial)...")
            if not contract_funder.ensure_precise_token_balances(
                self.contract_address, self.token0, self.token0_decimals, target_usdc_balance,
                self.token1, self.token1_decimals, target_weth_balance, private_key_env
            ):
                logger.error("Precise funding for Predictive contract failed (initial).")
                self.metrics['action_taken'] = self.ACTION_STATES["FUNDING_FAILED"]
                self.metrics['error_message'] = "Precise contract funding failed (initial)"
                self.save_metrics()
                sys.exit(1)
            
            balance0_val, balance1_val = self._get_contract_token_balances_individually()
            self.metrics['initial_contract_balance_token0'] = balance0_val
            self.metrics['initial_contract_balance_token1'] = balance1_val
            logger.info(f"Initial contract balances for metrics (after funding): Token0={balance0_val}, Token1={balance1_val}")

            logger.info(f"Calling updatePredictionAndAdjust (initial) with predictedTick: {predicted_tick}")
            tx_function_call_initial = self.contract.functions.updatePredictionAndAdjust(predicted_tick)
            current_nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
            tx_params_initial = {'from': funding_account.address, 'nonce': current_nonce, 'chainId': web3_utils.w3.eth.chain_id}
            try:
                tx_params_initial['gas'] = int(tx_function_call_initial.estimate_gas({'from': funding_account.address}) * 1.25)
            except Exception as est_err:
                logger.warning(f"Gas estimation for 'updatePredictionAndAdjust' (initial) failed: {est_err}. Using default 1,500,000")
                tx_params_initial['gas'] = 1500000
            
            built_tx_initial = tx_function_call_initial.build_transaction(tx_params_initial)
            receipt_initial = web3_utils.send_transaction(built_tx_initial, private_key_env)
            self.metrics['tx_hash'] = receipt_initial.transactionHash.hex() if receipt_initial else None
            
            if receipt_initial and receipt_initial.status == 1:
                logger.info(f"Initial adjustment transaction successful. Tx: {self.metrics['tx_hash']}")
                self.metrics['gas_used'] = receipt_initial.get('gasUsed', 0)
                
                # CORRECTED FOR WEB3 v5
                effective_gas_price_initial = receipt_initial.get('effectiveGasPrice', web3_utils.w3.eth.gas_price)
                self.metrics['gas_cost_eth'] = float(web3_utils.w3.from_wei(self.metrics['gas_used'] * effective_gas_price_initial, 'ether'))
                
                self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_ADJUSTED_INITIAL"]
                
                logger.info("Processing LiquidityOperation event to capture mint amounts...")
                try:
                    # CORRECTED FOR WEB3 v5
                    mint_logs = self.contract.events.LiquidityOperation().process_receipt(receipt_initial)
                    for log in mint_logs:
                        if log.args.operationType == "MINT":
                            self.metrics['amount0_provided_to_mint'] = log.args.amount0
                            self.metrics['amount1_provided_to_mint'] = log.args.amount1
                            logger.info(f"Captured Mint Amounts: Token0={log.args.amount0}, Token1={log.args.amount1}")
                            break 
                except Exception as e:
                    logger.warning(f"Could not process LiquidityOperation event after initial adjustment: {e}")

                stage_results['initial_adjustment'] = True
            else:
                logger.error(f"Initial adjustment transaction reverted or failed. Tx: {self.metrics.get('tx_hash', 'N/A')}")
                self.metrics['action_taken'] = self.ACTION_STATES["TX_REVERTED"] if receipt_initial else self.ACTION_STATES["TX_WAIT_FAILED"]
                raise Exception("Initial adjustment transaction failed") # Raise exception to enter finally block
        
            # --- STAGE 2: Market Simulation based on selected scenario ---
            if stage_results['initial_adjustment']:
                logger.info(f"\n--- STAGE 2: Simulating market activity ---")

                num_swaps = int(os.getenv('PREDICTIVE_NUM_SWAPS', DEFAULT_NUM_SWAPS))
                swap_scenario = int(os.getenv('SWAP_SCENARIO', '0')) 

                logger.info(f"\n--- STAGE 2: Simulating {num_swaps} swaps (Scenario: {swap_scenario}) ---")

                predicted_tick_for_trend = self.metrics.get('predictedTick_calculated')
                _, current_tick_for_trend = self.get_pool_state()
                
                swap_direction_determined = False
                
                if swap_scenario == 1:
                    logger.info("--> Manual Override: Forcing BEARISH trend (selling WETH for USDC).")
                    token_to_swap_in = self.token1
                    token_to_swap_out = self.token0
                    amount_to_swap_readable = Decimal(os.getenv('PREDICTIVE_SWAP_AMOUNT_ETH', '2.5'))
                    token_in_decimals = self.token1_decimals
                    token_out_decimals = self.token0_decimals
                    swap_direction_determined = True
                elif swap_scenario == 2:
                    logger.info("--> Manual Override: Forcing BULLISH trend (buying WETH with USDC).")
                    token_to_swap_in = self.token0
                    token_to_swap_out = self.token1
                    amount_to_swap_readable = Decimal(os.getenv('PREDICTIVE_SWAP_AMOUNT_USDC', '50000'))
                    token_in_decimals = self.token0_decimals
                    token_out_decimals = self.token1_decimals
                    swap_direction_determined = True
                elif swap_scenario == 0:
                    logger.info("--> Automatic Mode: Simulating trend towards predicted price.")
                    if predicted_tick_for_trend is not None and current_tick_for_trend is not None:
                        if predicted_tick_for_trend > current_tick_for_trend:
                            logger.info(f"Simulating BULLISH trend: Moving price UP from {current_tick_for_trend} towards {predicted_tick_for_trend}")
                            token_to_swap_in, token_to_swap_out = self.token0, self.token1
                            amount_to_swap_readable = Decimal(os.getenv('PREDICTIVE_SWAP_AMOUNT_USDC', '50000'))
                            token_in_decimals, token_out_decimals = self.token0_decimals, self.token1_decimals
                            swap_direction_determined = True
                        else:
                            logger.info(f"Simulating BEARISH trend: Moving price DOWN from {current_tick_for_trend} towards {predicted_tick_for_trend}")
                            token_to_swap_in, token_to_swap_out = self.token1, self.token0
                            amount_to_swap_readable = Decimal(os.getenv('PREDICTIVE_SWAP_AMOUNT_ETH', '2.5'))
                            token_in_decimals, token_out_decimals = self.token1_decimals, self.token0_decimals
                            swap_direction_determined = True
                    else:
                        logger.error("Auto scenario failed: Cannot determine trend without predicted/current ticks.")
                else:
                    logger.error(f"Invalid SWAP_SCENARIO: {swap_scenario}. Skipping swaps.")

                if swap_direction_determined:
                    # ????? ??? ??????? ?? ?? approve
                    swap_success = self._perform_swap_for_fees(
                        funding_account, private_key_env,
                        token_to_swap_in, token_to_swap_out,
                        amount_to_swap_readable,
                        token_in_decimals, token_out_decimals,
                        num_swaps=num_swaps
                    )
                    stage_results['swap'] = swap_success
                else:
                    stage_results['swap'] = False

                if stage_results['swap']:
                    self.metrics['action_taken'] = self.ACTION_STATES["TX_SUCCESS_SWAP_FEES"]
                    logger.info(f"All {num_swaps} swaps completed successfully.")
                else:
                    self.metrics['action_taken'] = self.ACTION_STATES["SWAP_FOR_FEES_FAILED"]
                    self.metrics['error_message'] = (self.metrics.get('error_message', "") + ";Swap simulation failed or was skipped.").strip(';')
                    raise Exception("Swap simulation failed")

            # --- STAGE 2.5: Explicitly Collect Fees ---
            if stage_results['initial_adjustment'] and stage_results['swap']:
                logger.info("\n--- STAGE 2.5: Predictive Strategy - Explicit Fee Collection ---")
                stage_results['collect_only'] = self._call_collect_fees_only(funding_account, private_key_env)
                if not stage_results['collect_only']:
                    raise Exception("Fee collection failed")
            
            # --- STAGE 3: Second Position Adjustment by Strategy Contract ---
            if stage_results['initial_adjustment'] and stage_results['swap'] and stage_results['collect_only']:
                logger.info("\n--- STAGE 3: Predictive Strategy - Second position adjustment ---")
                predicted_price_final = self.get_predicted_price_from_api()
                predicted_tick_final = None
                if predicted_price_final is None:
                    logger.warning("Could not get new prediction for final adjustment. Using last known pool tick.")
                    if self.pool_contract: slot0_final = self.pool_contract.functions.slot0().call(); predicted_tick_final = slot0_final[1]
                    else: logger.error("Pool contract not available for fallback tick during final adjustment.")
                else:
                    predicted_tick_final = self.calculate_tick_from_price(predicted_price_final)
                
                if predicted_tick_final is not None:
                    logger.info("Ensuring precise token balances for Predictive contract (final)...")
                    if not contract_funder.ensure_precise_token_balances(
                        self.contract_address, self.token0, self.token0_decimals, target_usdc_balance,
                        self.token1, self.token1_decimals, target_weth_balance, private_key_env
                    ):
                        logger.error("Precise funding for Predictive contract failed (final).")
                        self.metrics['error_message'] = (self.metrics.get('error_message', "") + ";Funding failed (final)").strip(';')
                    
                    balance0_before_final_adj, balance1_before_final_adj = self._get_contract_token_balances_individually()
                    logger.info(f"Balances before final updatePredictionAndAdjust: Token0={balance0_before_final_adj}, Token1={balance1_before_final_adj}")

                    logger.info(f"Calling updatePredictionAndAdjust (final) with predictedTick: {predicted_tick_final}")
                    tx_function_call_final = self.contract.functions.updatePredictionAndAdjust(predicted_tick_final)
                    current_nonce = web3_utils.w3.eth.get_transaction_count(funding_account.address)
                    tx_params_final = {'from': funding_account.address, 'nonce': current_nonce, 'chainId': web3_utils.w3.eth.chain_id}
                    try: tx_params_final['gas'] = int(tx_function_call_final.estimate_gas({'from': funding_account.address}) * 1.25)
                    except Exception as est_err_final: logger.warning(f"Gas estimation failed for 'updatePredictionAndAdjust' (final): {est_err_final}. Using default 1,500,000"); tx_params_final['gas'] = 1500000
                    
                    built_tx_final = tx_function_call_final.build_transaction(tx_params_final)
                    receipt_final = web3_utils.send_transaction(built_tx_final, private_key_env)
                    self.metrics['tx_hash'] = receipt_final.transactionHash.hex() if receipt_final else self.metrics.get('tx_hash')

                    if receipt_final and receipt_final.status == 1:
                        logger.info(f"Final adjustment transaction successful. Tx: {receipt_final.transactionHash.hex()}")
                        
                        logger.info("Processing LiquidityOperation event to capture amounts from final adjustment...")
                        try:
                            # CORRECTED FOR WEB3 v5
                            final_mint_logs = self.contract.events.LiquidityOperation().process_receipt(receipt_final)
                            
                            fees_token0 = 0
                            fees_token1 = 0
                            for log in final_mint_logs:
                                if log.args.operationType == "MINT":
                                    self.metrics['amount0_provided_to_mint'] = log.args.amount0
                                    self.metrics['amount1_provided_to_mint'] = log.args.amount1
                                    logger.info(f"Captured Final Mint Amounts: Token0={log.args.amount0}, Token1={log.args.amount1}")
                                elif log.args.operationType == "REMOVE":
                                    fees_token0 += log.args.amount0 
                                    fees_token1 += log.args.amount1 
                                    logger.info(f"Captured Collected Amounts from REMOVE event: Token0={log.args.amount0}, Token1={log.args.amount1}")

                            if self.metrics.get('fees_collected_token0') is None: self.metrics['fees_collected_token0'] = 0
                            if self.metrics.get('fees_collected_token1') is None: self.metrics['fees_collected_token1'] = 0
                            self.metrics['fees_collected_token0'] += fees_token0
                            self.metrics['fees_collected_token1'] += fees_token1

                        except Exception as e:
                            logger.warning(f"Could not process LiquidityOperation event after final adjustment: {e}")

                        stage_results['final_adjustment'] = True
                    else:
                        raise Exception("Final adjustment transaction failed")
                else:
                    raise Exception("Could not determine a target tick for final adjustment")
        
        except Exception as e:
            logger.exception(f"A failure occurred in adjust_position main try-block: {e}")
            # The finally block will handle saving metrics. The function will implicitly return None (failure).

        finally:
            logger.info("Updating final pool and position metrics in 'finally' block for Predictive...")
            self.update_pool_and_position_metrics(final_update=True)
            self.save_metrics()


    def save_metrics(self):
        self.metrics['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        metric_value = self.metrics.get('actualPrice_pool')
        if isinstance(metric_value, Decimal): self.metrics['actualPrice_pool'] = f"{metric_value}"
        elif metric_value is None: self.metrics['actualPrice_pool'] = ""
        
        columns = [
            'timestamp', 'contract_type', 'action_taken', 'tx_hash',
            'range_width_multiplier_setting',
            'predictedPrice_api', 'predictedTick_calculated',
            'external_api_eth_price',
            'actualPrice_pool', 'sqrtPriceX96_pool', 'currentTick_pool',
            'targetTickLower_calculated', 'targetTickUpper_calculated',
            'initial_contract_balance_token0',
            'initial_contract_balance_token1',
            'finalTickLower_contract', 'finalTickUpper_contract', 'liquidity_contract',
            'amount0_provided_to_mint',
            'amount1_provided_to_mint',
            'fees_collected_token0',
            'fees_collected_token1',
            'num_swaps_executed',  # ????? ???? ???? ????
            'gas_used', 'gas_cost_eth', 'error_message'
        ]
        
        row_data = {}
        for col in columns:
            val = self.metrics.get(col)
            if val is None:
                if col in ['sqrtPriceX96_pool', 'currentTick_pool', 'targetTickLower_calculated',
                            'targetTickUpper_calculated',
                            'initial_contract_balance_token0',
                            'initial_contract_balance_token1', 'finalTickLower_contract',
                            'finalTickUpper_contract', 'liquidity_contract',
                            'amount0_provided_to_mint', 'amount1_provided_to_mint',
                            'fees_collected_token0', 'fees_collected_token1',
                            'fees_collected_token0_via_collect_only',
                            'fees_collected_token1_via_collect_only',
                            'gas_used', 'gas_cost_eth', 'range_width_multiplier_setting',
                            'predictedTick_calculated', 'num_swaps_executed']:
                    row_data[col] = 0 if col not in ['predictedPrice_api', 'external_api_eth_price'] else ""
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
                if not file_exists or os.path.getsize(RESULTS_FILE) == 0:
                    writer.writeheader()
                writer.writerow(row_data)
            logger.info(f"Predictive metrics saved to {RESULTS_FILE}")
        except Exception as e:
            logger.exception(f"Failed to save predictive metrics: {e}")

# --- Main Function ---
def main():
    logger.info("=" * 50)
    logger.info("Starting Predictive Liquidity Manager Test on Fork")
    logger.info("=" * 50)

    if not web3_utils.init_web3():
        logger.critical("Web3 initialization failed. Exiting predictive test.")
        sys.exit(1)
    
    if not web3_utils.w3:
        logger.critical("web3_utils.w3 instance not available after init. Exiting predictive test.")
        sys.exit(1)

    predictive_address = None
    test_instance = None
    try:
        predictive_address_env = os.getenv('PREDICTIVE_MANAGER_ADDRESS')
        if not predictive_address_env :
            logger.error(f"PREDICTIVE_MANAGER_ADDRESS environment variable not found.")
            temp_test_for_error_log = PredictiveTest(contract_address="0x"+"0"*40)
            temp_test_for_error_log.metrics['action_taken'] = temp_test_for_error_log.ACTION_STATES["SETUP_FAILED"]
            temp_test_for_error_log.metrics['error_message'] = "PREDICTIVE_MANAGER_ADDRESS env var not found"
            temp_test_for_error_log.save_metrics()
            raise ValueError("PREDICTIVE_MANAGER_ADDRESS env var not found")
        
        predictive_address = Web3.to_checksum_address(predictive_address_env)
        logger.info(f"Loaded Predictive Manager Address from ENV: {predictive_address}")

        test_instance = PredictiveTest(predictive_address)
        
        desired_rwm = int(os.getenv('PREDICTIVE_RWM', '100'))
        target_weth = float(os.getenv('PREDICTIVE_TARGET_WETH', '5.0'))
        target_usdc = float(os.getenv('PREDICTIVE_TARGET_USDC', '10000.0'))

        setup_success = test_instance.setup(desired_range_width_multiplier=desired_rwm)
        
        if setup_success:
            test_instance.adjust_position(
                target_weth_balance=target_weth,
                target_usdc_balance=target_usdc
            )
        else:
            logger.error("Predictive setup failed. Skipping adjust_position.")
            sys.exit(1)

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration Error for Predictive: {e}")
        if test_instance:
            test_instance.metrics['action_taken'] = test_instance.ACTION_STATES["SETUP_FAILED"]
            test_instance.metrics['error_message'] = str(e)
            test_instance.save_metrics()
        sys.exit(1)
        
    except Exception as e:
        logger.exception(f"An unexpected error occurred during predictive main execution:")
        if test_instance:
            test_instance.metrics['action_taken'] = test_instance.ACTION_STATES["UNEXPECTED_ERROR"]
            test_instance.metrics['error_message'] = (test_instance.metrics.get('error_message',"") + f"; MainException: {str(e)}").strip(";")
            test_instance.save_metrics()
        sys.exit(1)
        
    finally:
        logger.info("=" * 50)
        logger.info("Predictive test run finished.")
        logger.info("=" * 50)

if __name__ == "__main__":
    main()