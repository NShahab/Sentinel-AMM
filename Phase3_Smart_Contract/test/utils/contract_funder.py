import logging
import time
from web3 import Web3
from eth_account import Account
from . import web3_utils

logger = logging.getLogger(__name__)

MIN_GAS_FOR_TRANSFER = 50000

def ensure_precise_token_balances(
    contract_address: str,
    token0_address: str,
    token0_decimals: int,
    target_token0_amount_readable: float,
    token1_address: str,
    token1_decimals: int,
    target_token1_amount_readable: float,
    funding_account_private_key: str
) -> bool:
    """
    Ensures the target contract has precise amounts of token0 and token1.
    Funds from the funding_account.
    """
    if not web3_utils.w3:
        if not web3_utils.init_web3():
            logger.error("Web3 connection failed in ensure_precise_token_balances.")
            return False
    
    w3 = web3_utils.w3
    if not w3:
        logger.error("Web3 instance is not available after initialization attempt.")
        return False

    try:
        funding_account = Account.from_key(funding_account_private_key)
        contract_checksum_addr = Web3.to_checksum_address(contract_address)
        funder_checksum_addr = Web3.to_checksum_address(funding_account.address)

        tokens_to_fund = [
            {"name": "Token0", "address": token0_address, "decimals": token0_decimals, "target_readable": target_token0_amount_readable},
            {"name": "Token1", "address": token1_address, "decimals": token1_decimals, "target_readable": target_token1_amount_readable},
        ]

        current_nonce = w3.eth.get_transaction_count(funder_checksum_addr)

        for token_info in tokens_to_fund:
            token_contract = web3_utils.get_contract(token_info["address"], "IERC20")
            if not token_contract:
                logger.error(f"Failed to get contract instance for {token_info['name']} ({token_info['address']})")
                return False
            
            target_wei = int(token_info["target_readable"] * (10**token_info["decimals"]))
            current_bal_wei = token_contract.functions.balanceOf(contract_checksum_addr).call()
            
            needed_wei = target_wei - current_bal_wei

            if needed_wei == 0:
                logger.info(f"Contract {contract_checksum_addr} already has target balance of {token_info['name']} ({token_info['target_readable']}).")
                continue
            elif needed_wei < 0:
                actual_balance_readable = current_bal_wei / (10**token_info['decimals'])
                logger.warning(f"Contract {contract_checksum_addr} has MORE {token_info['name']} ({actual_balance_readable}) than target ({token_info['target_readable']}). Skipping transfer for this token.")
                continue

            funder_bal_wei = token_contract.functions.balanceOf(funder_checksum_addr).call()
            funder_bal_readable = funder_bal_wei / (10**token_info['decimals'])
            needed_readable = needed_wei / (10**token_info['decimals'])

            if funder_bal_wei < needed_wei:
                logger.error(f"Funding account {funder_checksum_addr} has insufficient {token_info['name']} to fund contract. Has: {funder_bal_readable}, Needs: {needed_readable}")
                return False

            logger.info(f"Funding contract {contract_checksum_addr} with {needed_readable:.6f} of {token_info['name']} from {funder_checksum_addr}.")
            
            tx_params_dict = {
                'from': funder_checksum_addr,
                'nonce': current_nonce,
                'chainId': w3.eth.chain_id 
            }
            
            transfer_tx_build = token_contract.functions.transfer(contract_checksum_addr, needed_wei)
            
            try:
                # ==============================================================================
                # <<< FIX START >>>
                # The 'to' field should not be in the estimate_gas dictionary for contract calls
                # in modern web3.py versions, as it's implicit in the contract object.
                # OLD: .estimate_gas({'from': funder_checksum_addr, 'to': token_info["address"]})
                # NEW: .estimate_gas({'from': funder_checksum_addr})
                gas_estimate = transfer_tx_build.estimate_gas({'from': funder_checksum_addr})
                # <<< FIX END >>>
                # ==============================================================================
                tx_params_dict['gas'] = int(gas_estimate * 1.2)
            except Exception as e:
                logger.warning(f"Gas estimation failed for {token_info['name']} transfer: {e}. Using default gas: {MIN_GAS_FOR_TRANSFER * 2}")
                tx_params_dict['gas'] = MIN_GAS_FOR_TRANSFER * 2

            final_transfer_tx = transfer_tx_build.build_transaction(tx_params_dict)

            receipt = web3_utils.send_transaction(final_transfer_tx, funding_account_private_key)
            if not receipt or receipt.status == 0:
                tx_hash_str = receipt.transactionHash.hex() if receipt else 'N/A'
                logger.error(f"Failed to transfer {token_info['name']} to contract {contract_checksum_addr}. TxHash: {tx_hash_str}")
                return False
            
            logger.info(f"{token_info['name']} transfer successful to {contract_checksum_addr}. TxHash: {receipt.transactionHash.hex()}")
            current_nonce += 1
            time.sleep(0.5)

        return True
    except Exception as e:
        logger.exception(f"Error in ensure_precise_token_balances for {contract_address}: {e}")
        return False