# test_base.py
import os
import logging
from abc import ABC, abstractmethod
from web3 import Web3
from decimal import Decimal
# Import the web3_utils module itself to access its w3 instance and functions
import test.utils.web3_utils as web3_utils

logger = logging.getLogger('test_base')

class LiquidityTestBase(ABC):
    """Base class for liquidity position testing."""

    def __init__(self, contract_address: str, contract_name: str):
        """Initialize test with contract info."""
        if not contract_address:
            raise ValueError("Contract address cannot be empty")
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract_name = contract_name
        self.contract = None
        self.token0 = None
        self.token1 = None
        self.token0_decimals = None
        self.token1_decimals = None
        self.metrics = self._reset_metrics()

    def _reset_metrics(self):
        """Initialize or reset all metrics to their default values. Override in derived classes."""
        return {
            'timestamp': None,
            'contract_type': None,
            'action_taken': None,
            'tx_hash': None,
            'range_width_multiplier_setting': None,
            'external_api_eth_price': None,
            'actualPrice_pool': None,
            'sqrtPriceX96_pool': None,
            'currentTick_pool': None,
            'targetTickLower_offchain': None,
            'targetTickUpper_offchain': None,
            'initial_contract_balance_token0': None,
            'initial_contract_balance_token1': None,
            'currentTickLower_contract': None,
            'currentTickUpper_contract': None,
            'currentLiquidity_contract': None,
            'finalTickLower_contract': None,
            'finalTickUpper_contract': None,
            'finalLiquidity_contract': None,
            'amount0_provided_to_mint': None,
            'amount1_provided_to_mint': None,
            'fees_collected_token0': None,
            'fees_collected_token1': None,
            'gas_used': None,
            'gas_cost_eth': None,
            'error_message': ""
        }

    def setup(self, desired_range_width_multiplier: int) -> bool:
        """Initialize connection and contracts."""
        try:
            # Ensure Web3 is initialized using the function from web3_utils
            if not web3_utils.init_web3():
                logger.error("Web3 initialization failed in LiquidityTestBase setup")
                return False
            
            # Ensure the w3 instance in web3_utils is usable
            if not web3_utils.w3:
                 logger.error("web3_utils.w3 is not available after init_web3 call.")
                 return False


            logger.info(f"Setting up test for {self.contract_name} at {self.contract_address}")
            # Load main contract using get_contract from web3_utils (which uses web3_utils.w3)
            self.contract = web3_utils.get_contract(self.contract_address, self.contract_name)
            if not self.contract:
                logger.error(f"Failed to load contract {self.contract_name}")
                return False            
            self.token0 = Web3.to_checksum_address(self.contract.functions.token0().call())
            self.token1 = Web3.to_checksum_address(self.contract.functions.token1().call())

            # Get decimals and symbol/name for better logging
            token0_contract = web3_utils.get_contract(self.token0, "IERC20")
            self.token0_decimals = token0_contract.functions.decimals().call()
            token0_name = "Unknown"
            try:
                token0_name = token0_contract.functions.symbol().call()
            except:
                pass

            token1_contract = web3_utils.get_contract(self.token1, "IERC20")
            self.token1_decimals = token1_contract.functions.decimals().call()
            token1_name = "Unknown"
            try:
                token1_name = token1_contract.functions.symbol().call()
            except:
                pass

            # Verify token order (USDC should be token0, WETH token1)
            logger.info("Token configuration:")
            logger.info(f"  Token0: {token0_name} at {self.token0} (Decimals: {self.token0_decimals})")
            logger.info(f"  Token1: {token1_name} at {self.token1} (Decimals: {self.token1_decimals})")
            if self.token0_decimals == 6 and self.token1_decimals == 18:
                logger.info("? Token order verified: USDC(6) is token0, WETH(18) is token1")
            else:
                logger.warning(f"?? Unexpected token decimals configuration: token0({self.token0_decimals}), token1({self.token1_decimals})")
            
            logger.info(f"Setup completed for {self.contract_name}")
            return True

        except Exception as e:
            logger.exception(f"Setup failed for {self.contract_name} at {self.contract_address}: {e}")
            return False

    def check_balances(self) -> bool:
        """Step 2: Check contract's token balances."""
        if not self.contract or not self.token0 or not self.token1:
            logger.error("Contract or tokens not initialized. Run setup first.")
            return False
        if not web3_utils.w3:
            logger.error("Web3 not connected in check_balances.")
            return False
        try:
            token0_contract = web3_utils.get_contract(self.token0, "IERC20")
            token1_contract = web3_utils.get_contract(self.token1, "IERC20")

            balance0_wei = token0_contract.functions.balanceOf(self.contract_address).call()
            balance1_wei = token1_contract.functions.balanceOf(self.contract_address).call()

            readable_balance0 = Decimal(balance0_wei) / (10 ** self.token0_decimals)
            readable_balance1 = Decimal(balance1_wei) / (10 ** self.token1_decimals)

            logger.info(f"Contract Token0 ({self.token0[-6:]}) balance: {readable_balance0:.6f}")
            logger.info(f"Contract Token1 ({self.token1[-6:]}) balance: {readable_balance1:.6f}")
            return True
        except Exception as e:
            logger.exception(f"Balance check failed: {e}")
            return False

    @abstractmethod
    def adjust_position(self) -> bool:
        """Abstract method for adjusting the position. Implement in derived class."""
        pass

    @abstractmethod
    def save_metrics(self):
        """Abstract method for saving metrics. Implement in derived class."""
        pass

    def execute_test_steps(self, desired_range_width_multiplier: int = 50, target_weth_balance: float = 1.0, target_usdc_balance: float = 1000.0) -> bool:
        """Execute all test steps sequentially with required arguments."""
        try:
            logger.info("--- Test Step 1: Setup ---")
            if not self.setup(desired_range_width_multiplier):
                logger.error("Setup failed. Aborting test.")
                if hasattr(self, 'metrics') and self.metrics and hasattr(self, 'ACTION_STATES') and "SETUP_FAILED" in self.ACTION_STATES:
                    self.metrics['action_taken'] = self.ACTION_STATES["SETUP_FAILED"]
                    self.metrics['error_message'] = self.metrics.get('error_message', "Base setup failed in execute_test_steps")
                    self.save_metrics()
                return False

            logger.info("--- Test Step 2: Balance Check ---")
            self.check_balances()

            logger.info("--- Test Step 3: Position Adjustment ---")
            if not self.adjust_position(target_weth_balance, target_usdc_balance):
                logger.error("Position adjustment failed.")
                return False

            logger.info("--- All test steps completed successfully ---")
            return True
        except Exception as e:
            logger.exception(f"Test execution failed during steps: {e}")
            try:
                if hasattr(self, 'metrics') and self.metrics:
                    if hasattr(self, 'ACTION_STATES') and "UNEXPECTED_ERROR" in self.ACTION_STATES:
                        self.metrics['action_taken'] = self.ACTION_STATES["UNEXPECTED_ERROR"]
                    self.metrics['error_message'] = self.metrics.get('error_message', f"Test Execution Aborted: {str(e)}")
                    self.save_metrics()
            except Exception as save_err:
                logger.error(f"Also failed to save metrics during exception handling: {save_err}")
            return False

    def get_position_info(self) -> dict | None:
        """Get current position info from the contract."""
        if not self.contract:
            logger.error("Contract not initialized. Run setup first.")
            return None
        if not web3_utils.w3:
            logger.error("Web3 not connected in get_position_info.")
            return None
        try:
            pos_data = None
            if hasattr(self.contract.functions, 'getPositionState'):
                 pass 
            
            if hasattr(self.contract.functions, 'getCurrentPosition'):
                pos_data = self.contract.functions.getCurrentPosition().call()
            elif hasattr(self.contract.functions, 'currentPosition'):
                pos_data = self.contract.functions.currentPosition().call()
            else:
                logger.error(f"No known position info method (getCurrentPosition, currentPosition) found on contract {self.contract_name}")
                return None

            if pos_data and len(pos_data) == 5:
                position = {
                    'tokenId': pos_data[0],
                    'liquidity': pos_data[1],
                    'tickLower': pos_data[2],
                    'tickUpper': pos_data[3],
                    'active': pos_data[4]
                }
                logger.debug(f"Fetched Position Info: {position}")
                return position
            else:
                logger.error(f"Position data format unexpected or not found. Data: {pos_data}")
                return None

        except Exception as e:
            logger.exception(f"Failed to get position info from contract {self.contract_name}: {e}")
            return None     
    def _calculate_actual_price(self, sqrt_price_x96: int) -> Decimal:
        """
        Calculates the human-readable price from sqrtPriceX96. For USDC/WETH pool:
        - token0 is USDC (6 decimals)
        - token1 is WETH (18 decimals)
        - sqrtPriceX96 represents: v(token1/token0) * 2^96
        We need to:
        1. Convert sqrtPriceX96 to actual price ratio
        2. Invert the ratio since we want USDC/WETH not WETH/USDC
        3. Adjust for decimals
         """
        if not sqrt_price_x96 or sqrt_price_x96 == 0:
            return Decimal(0)
        if self.token0_decimals is None or self.token1_decimals is None:
            logger.error("Token decimals not set, cannot calculate actual price.")
            return Decimal(0)
    
        try:
            # Convert inputs to Decimal for precise calculation
            sqrt_price_x96_dec = Decimal(sqrt_price_x96)
            two_pow_96 = Decimal(2 ** 96)
    
            # Get the square root of the price ratio (token1/token0)
            sqrt_price = sqrt_price_x96_dec / two_pow_96
            
            # Square it to get the actual ratio
            price_ratio = sqrt_price * sqrt_price
            
            # Invert to get token0/token1 (USDC/WETH)
            price = Decimal(1) / price_ratio
    
            # Adjust for decimals: Since we inverted the price, we also invert the decimal adjustment
            decimal_adjustment = Decimal(10) ** (self.token0_decimals - self.token1_decimals)
            actual_price = price * decimal_adjustment            
            logger.debug(f"Price calculation for sqrtPriceX96={sqrt_price_x96}:")
            logger.debug(f"  sqrt_price (after 2^96 division): {sqrt_price}")
            logger.debug(f"  price_ratio (WETH/USDC): {price_ratio}")
            logger.debug(f"  inverted_price (USDC/WETH): {price}")
            logger.debug(f"  decimal_adjustment (10^({self.token0_decimals}-{self.token1_decimals})): {decimal_adjustment}")
            logger.debug(f"  final_price (USDC/WETH): {actual_price}")

            # ????????? ????? ?? ???? Decimal ???? ??? ??? ?????
            return actual_price
    
        except Exception as e:
            logger.exception(f"Error calculating price from sqrtPriceX96={sqrt_price_x96}: {e}")
            return Decimal(0)

    def get_current_eth_price(self) -> float | None:
        """
        Fetches current ETH price in USD from CoinGecko API.
        Returns None if request fails.
        """
        try:
            import requests
            from time import sleep

            # CoinGecko API endpoint for ETH/USD price
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "ethereum",
                "vs_currencies": "usd"
            }
            
            # Add rate limiting delay to respect API limits
            sleep(1)
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                price_data = response.json()
                eth_price = price_data.get('ethereum', {}).get('usd')
                if eth_price:
                    logger.info(f"Current ETH price from CoinGecko: ${eth_price:,.2f}")
                    # Update metrics with external price
                    self.metrics['external_api_eth_price'] = float(eth_price)
                    return float(eth_price)
            
            logger.error(f"Failed to get ETH price. Status code: {response.status_code}")
            return None
            
        except Exception as e:
            logger.exception(f"Error fetching ETH price from CoinGecko: {e}")
            return None