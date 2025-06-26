// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6; // Keeping the original pragma
pragma abicoder v2; // Keep abicoder v2

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Factory.sol";
import "@uniswap/v3-core/contracts/interfaces/callback/IUniswapV3MintCallback.sol";
import "@uniswap/v3-core/contracts/libraries/TickMath.sol";

import "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";

interface IERC20Decimals {
    function decimals() external view returns (uint8);
}

contract PredictiveLiquidityManager is
    Ownable,
    ReentrancyGuard,
    IUniswapV3MintCallback
{
    using SafeERC20 for IERC20;

    IUniswapV3Factory public immutable factory;
    INonfungiblePositionManager public immutable positionManager; // Made immutable as it's set in constructor
    address public immutable token0;
    address public immutable token1;
    uint8 public immutable token0Decimals;
    uint8 public immutable token1Decimals;
    uint24 public immutable fee;
    int24 public immutable tickSpacing;

    struct Position {
        uint256 tokenId;
        uint128 liquidity;
        int24 tickLower;
        int24 tickUpper;
        bool active;
    }
    Position public currentPosition;

    uint24 public rangeWidthMultiplier;

    event LiquidityOperation(
        string operationType, // "MINT", "REMOVE"
        uint256 indexed tokenId,
        int24 tickLower,
        int24 tickUpper,
        uint128 liquidity,
        uint256 amount0, // For MINT: actual amount used; For REMOVE: total collected (principal+fees)
        uint256 amount1, // For MINT: actual amount used; For REMOVE: total collected (principal+fees)
        bool success // Indicates if the core Uniswap operation (mint/decrease/collect) was successful
    );

    event PredictionAdjustmentMetrics(
        int24 predictedTick,
        int24 finalTickLower,
        int24 finalTickUpper,
        uint128 liquidity, // Liquidity of the position AFTER adjustment
        bool adjusted // True if position was actually removed/minted
    );
    event StrategyParamUpdated(string indexed paramName, uint256 newValue);

    // New event specifically for fees collected via collectCurrentFeesOnly
    event FeesOnlyCollected(
        uint256 indexed tokenId,
        uint256 amount0Fees,
        uint256 amount1Fees,
        bool success
    );

    constructor(
        address _factory,
        address _positionManager,
        address _token0,
        address _token1,
        uint24 _fee,
        address _initialOwner,
        uint24 _initialRangeWidthMultiplier
    ) {
        factory = IUniswapV3Factory(_factory);
        positionManager = INonfungiblePositionManager(_positionManager);
        token0 = _token0;
        token1 = _token1;
        fee = _fee;
        require(_initialRangeWidthMultiplier > 0, "Initial RWM must be > 0");
        rangeWidthMultiplier = _initialRangeWidthMultiplier;

        try IERC20Decimals(_token0).decimals() returns (uint8 _decimals) {
            token0Decimals = _decimals;
        } catch {
            revert("Token0 does not support decimals()");
        }
        try IERC20Decimals(_token1).decimals() returns (uint8 _decimals) {
            token1Decimals = _decimals;
        } catch {
            revert("Token1 does not support decimals()");
        }

        address poolAddress = IUniswapV3Factory(_factory).getPool(
            _token0,
            _token1,
            _fee
        );
        require(poolAddress != address(0), "Pool does not exist");
        tickSpacing = IUniswapV3Pool(poolAddress).tickSpacing();

        IERC20(_token0).safeApprove(_positionManager, type(uint256).max);
        IERC20(_token1).safeApprove(_positionManager, type(uint256).max);

        if (_initialOwner != address(0)) {
            transferOwnership(_initialOwner);
        }
    }

    function setRangeWidthMultiplier(uint24 _newMultiplier) external onlyOwner {
        require(_newMultiplier > 0, "RWM must be > 0");
        rangeWidthMultiplier = _newMultiplier;
        emit StrategyParamUpdated(
            "rangeWidthMultiplier",
            uint256(_newMultiplier)
        );
    }

    function updatePredictionAndAdjust(
        int24 predictedTick
    ) external nonReentrant onlyOwner {
        (int24 targetTickLower, int24 targetTickUpper) = _calculateTicks(
            predictedTick
        );
        bool adjusted = false;
        if (
            currentPosition.active &&
            _isTickRangeClose( // Your existing check
                currentPosition.tickLower,
                currentPosition.tickUpper,
                targetTickLower,
                targetTickUpper
            )
        ) {
            _emitPredictionMetrics(
                predictedTick,
                currentPosition.tickLower, // Emit current ticks if no adjustment
                currentPosition.tickUpper,
                false // Not adjusted
            );
            return;
        }

        adjusted = _updatePositionIfNeeded(targetTickLower, targetTickUpper);
        _emitPredictionMetrics(
            predictedTick,
            targetTickLower, // Emit target ticks used for adjustment
            targetTickUpper,
            adjusted
        );
    }

    // NEW public function to only collect fees
    function collectCurrentFeesOnly()
        external
        nonReentrant
        onlyOwner
        returns (uint256 amount0, uint256 amount1)
    {
        require(
            currentPosition.active && currentPosition.tokenId != 0,
            "PLM: No active position to collect fees from"
        );

        uint256 _tokenId = currentPosition.tokenId;
        bool collectCallSuccess = false;

        try
            positionManager.collect(
                INonfungiblePositionManager.CollectParams({
                    tokenId: _tokenId,
                    recipient: address(this), // Fees to this contract
                    amount0Max: type(uint128).max, // Collect all available
                    amount1Max: type(uint128).max // Collect all available
                })
            )
        returns (uint256 collected0, uint256 collected1) {
            amount0 = collected0;
            amount1 = collected1;
            collectCallSuccess = true;
        } catch Error(string memory reason) {
            // Optional: emit an error event or log the reason
            // For now, success will remain false
            emit FeesOnlyCollected(_tokenId, 0, 0, false); // Emit failure
            revert(
                string(abi.encodePacked("PLM: CollectOnly failed - ", reason))
            );
        } catch {
            emit FeesOnlyCollected(_tokenId, 0, 0, false); // Emit failure
            revert("PLM: CollectOnly failed with unknown error");
        }

        emit FeesOnlyCollected(_tokenId, amount0, amount1, collectCallSuccess);
        return (amount0, amount1);
    }

    function _calculateTicks(
        int24 targetCenterTick
    ) internal view returns (int24 tickLower, int24 tickUpper) {
        require(tickSpacing > 0, "Invalid tick spacing");
        int24 halfWidth = (tickSpacing * int24(rangeWidthMultiplier)) / 2;
        if (halfWidth <= 0) halfWidth = tickSpacing;
        halfWidth = (halfWidth / tickSpacing) * tickSpacing;
        if (halfWidth == 0) halfWidth = tickSpacing;

        int24 rawTickLower = targetCenterTick - halfWidth;
        int24 rawTickUpper = targetCenterTick + halfWidth;

        tickLower = floorToTickSpacing(rawTickLower, tickSpacing);
        tickUpper = floorToTickSpacing(rawTickUpper, tickSpacing);
        if ((rawTickUpper % tickSpacing) != 0 && rawTickUpper > 0) {
            // Ensure rounding up for positive side
            tickUpper += tickSpacing;
        } else if (
            (rawTickUpper % tickSpacing) != 0 &&
            rawTickUpper < 0 &&
            tickUpper != rawTickUpper
        ) {
            // For negative ticks, floorToTickSpacing moves away from zero. If rawTickUpper was not a multiple,
            // and floor moved it further from targetCenterTick, consider adding tickSpacing if logic requires tighter upper bound.
            // This part is complex; for now, simple floor for upper is used and then checked.
        }

        if (tickLower >= tickUpper) {
            tickUpper = tickLower + tickSpacing;
        }

        tickLower = tickLower < TickMath.MIN_TICK
            ? floorToTickSpacing(TickMath.MIN_TICK, tickSpacing)
            : tickLower;
        tickUpper = tickUpper > TickMath.MAX_TICK
            ? floorToTickSpacing(TickMath.MAX_TICK, tickSpacing)
            : tickUpper;

        if (tickLower >= tickUpper) {
            // Final check
            if (tickUpper == TickMath.MAX_TICK) {
                tickLower = tickUpper - tickSpacing;
            } else {
                tickUpper = tickLower + tickSpacing;
                if (tickUpper > TickMath.MAX_TICK) {
                    // Re-check if pushing upper overshot MAX_TICK
                    tickUpper = floorToTickSpacing(
                        TickMath.MAX_TICK,
                        tickSpacing
                    );
                    tickLower = tickUpper - tickSpacing; // Adjust lower accordingly
                }
            }
        }
        // Ensure lower is strictly less than upper, and within bounds.
        require(
            tickLower < tickUpper,
            "PLM: TickLower must be less than TickUpper"
        );
        require(
            tickLower >= TickMath.MIN_TICK && tickUpper <= TickMath.MAX_TICK,
            "PLM: Ticks out of bounds"
        );

        return (tickLower, tickUpper);
    }

    function _isTickRangeClose(
        int24 oldLower,
        int24 oldUpper,
        int24 newLower,
        int24 newUpper
    ) internal view returns (bool) {
        // If either old or new range is significantly different, they are not close.
        // Tolerance could be a fraction of rangeWidthMultiplier or a fixed number of tickSpacings.
        // For simplicity, using half of the halfWidth (quarter of total width in ticks) as a threshold.
        int24 tolerance = (tickSpacing * int24(rangeWidthMultiplier)) / 4;
        if (tolerance < tickSpacing) tolerance = tickSpacing; // Minimum tolerance of one tickSpacing

        return (_abs(oldLower - newLower) < tolerance &&
            _abs(oldUpper - newUpper) < tolerance);
    }

    function _abs(int24 x) internal pure returns (int24) {
        return x >= 0 ? x : -x;
    }

    function _updatePositionIfNeeded(
        int24 targetTickLower,
        int24 targetTickUpper
    ) internal returns (bool adjusted) {
        if (
            !currentPosition.active ||
            targetTickLower != currentPosition.tickLower ||
            targetTickUpper != currentPosition.tickUpper
        ) {
            _adjustLiquidity(targetTickLower, targetTickUpper);
            return true;
        }
        return false;
    }

    function _adjustLiquidity(int24 tickLower, int24 tickUpper) internal {
        if (currentPosition.active) {
            _removeLiquidity();
        }
        uint256 balance0 = IERC20(token0).balanceOf(address(this));
        uint256 balance1 = IERC20(token1).balanceOf(address(this));
        if (balance0 > 0 || balance1 > 0) {
            _mintLiquidity(tickLower, tickUpper, balance0, balance1);
        } else {
            currentPosition = Position(0, 0, 0, 0, false);
        }
    }

    function _removeLiquidity() internal {
        require(
            currentPosition.active && currentPosition.tokenId != 0,
            "PLM: No active position to remove"
        );
        uint256 _tokenId = currentPosition.tokenId;
        uint128 _liquidity = currentPosition.liquidity;
        int24 _tickLower = currentPosition.tickLower;
        int24 _tickUpper = currentPosition.tickUpper;

        // Reset position state before external calls for reentrancy safety,
        // though ReentrancyGuard is also used.
        currentPosition = Position(0, 0, 0, 0, false);

        bool decreaseOpSuccess = false;
        uint256 amount0FromDecrease = 0; // Not directly returned by decreaseLiquidity
        uint256 amount1FromDecrease = 0; // Not directly returned by decreaseLiquidity

        bool collectOpSuccess = false;
        uint256 amount0FromCollect = 0;
        uint256 amount1FromCollect = 0;

        if (_liquidity > 0) {
            try
                positionManager.decreaseLiquidity(
                    INonfungiblePositionManager.DecreaseLiquidityParams({
                        tokenId: _tokenId,
                        liquidity: _liquidity,
                        amount0Min: 0,
                        amount1Min: 0,
                        deadline: block.timestamp
                    })
                )
            returns (
                // DecreaseLiquidity does not return amounts, they are claimed by collect
                uint256 decAmount0,
                uint256 decAmount1
            ) {
                amount0FromDecrease = decAmount0; // Store amounts from decrease
                amount1FromDecrease = decAmount1;
                decreaseOpSuccess = true;
            } catch Error(string memory reason) {
                // For LiquidityOperation, report total collected as 0 if decrease fails severely
                emit LiquidityOperation(
                    "REMOVE",
                    _tokenId,
                    _tickLower,
                    _tickUpper,
                    _liquidity,
                    0,
                    0,
                    false
                );
                revert(
                    string(
                        abi.encodePacked(
                            "PLM: DecreaseLiquidity failed - ",
                            reason
                        )
                    )
                );
            } catch {
                emit LiquidityOperation(
                    "REMOVE",
                    _tokenId,
                    _tickLower,
                    _tickUpper,
                    _liquidity,
                    0,
                    0,
                    false
                );
                revert("PLM: DecreaseLiquidity failed with unknown error");
            }
        } else {
            // If liquidity was already zero, consider decrease "successful" for flow
            decreaseOpSuccess = true;
        }

        // Always attempt to collect, even if liquidity was 0 (there might be uncollected fees)
        // The success of the REMOVE operation will largely depend on collect if decrease was "successful" (even for 0 liquidity)
        try
            positionManager.collect(
                INonfungiblePositionManager.CollectParams({
                    tokenId: _tokenId,
                    recipient: address(this),
                    amount0Max: type(uint128).max,
                    amount1Max: type(uint128).max
                })
            )
        returns (uint256 collected0, uint256 collected1) {
            amount0FromCollect = collected0;
            amount1FromCollect = collected1;
            collectOpSuccess = true;
        } catch Error(string memory reason) {
            // If collect fails, the overall REMOVE operation's success might be debatable.
            // We still emit amounts from decrease if that succeeded.
            emit LiquidityOperation(
                "REMOVE",
                _tokenId,
                _tickLower,
                _tickUpper,
                _liquidity,
                amount0FromDecrease,
                amount1FromDecrease,
                false
            );
            revert(string(abi.encodePacked("PLM: Collect failed - ", reason)));
        } catch {
            emit LiquidityOperation(
                "REMOVE",
                _tokenId,
                _tickLower,
                _tickUpper,
                _liquidity,
                amount0FromDecrease,
                amount1FromDecrease,
                false
            );
            revert("PLM: Collect failed with unknown error");
        }

        // Burn the NFT only if collect was (at least attempted and didn't revert here)
        // and decrease was successful.
        if (decreaseOpSuccess) {
            // Might be true even if _liquidity was 0.
            try positionManager.burn(_tokenId) {} catch Error(
                string memory reason
            ) {
                // Log or handle burn failure; it's non-critical for fund recovery but bad for state.
                // For simplicity, we don't revert the whole tx for burn failure.
            } catch {
                /* Similarly, ignore unknown burn error for now */
            }
        }

        // The amounts reported in LiquidityOperation REMOVE are what was collected.
        // The 'success' flag should reflect if both decrease (if applicable) and collect were successful.
        emit LiquidityOperation(
            "REMOVE",
            _tokenId,
            _tickLower,
            _tickUpper,
            _liquidity, // The original liquidity removed
            amount0FromCollect, // Total amount0 moved to this contract by collect
            amount1FromCollect, // Total amount1 moved to this contract by collect
            decreaseOpSuccess && collectOpSuccess // Overall success
        );
    }

    function _mintLiquidity(
        int24 tickLower,
        int24 tickUpper,
        uint256 amount0Desired,
        uint256 amount1Desired
    ) internal {
        require(!currentPosition.active, "PLM: Position already active");
        INonfungiblePositionManager.MintParams
            memory params = INonfungiblePositionManager.MintParams({
                token0: token0,
                token1: token1,
                fee: fee,
                tickLower: tickLower,
                tickUpper: tickUpper,
                amount0Desired: amount0Desired,
                amount1Desired: amount1Desired,
                amount0Min: 0, // Adjust if slippage protection is needed
                amount1Min: 0, // Adjust if slippage protection is needed
                recipient: address(this),
                deadline: block.timestamp
            });
        uint256 tokenIdMinted = 0;
        uint128 liquidityMinted = 0;
        uint256 amount0Actual = 0;
        uint256 amount1Actual = 0;
        bool mintCallSuccess = false;

        try positionManager.mint(params) returns (
            uint256 _tokenId,
            uint128 _liquidity,
            uint256 _amount0,
            uint256 _amount1
        ) {
            tokenIdMinted = _tokenId;
            liquidityMinted = _liquidity;
            amount0Actual = _amount0;
            amount1Actual = _amount1;
            mintCallSuccess = true; // The call itself succeeded
        } catch Error(string memory reason) {
            // mintCallSuccess remains false
            revert(string(abi.encodePacked("PLM: Mint failed - ", reason)));
        } catch {
            // mintCallSuccess remains false
            revert("PLM: Mint failed with unknown error");
        }

        if (mintCallSuccess && liquidityMinted > 0) {
            currentPosition = Position(
                tokenIdMinted,
                liquidityMinted,
                tickLower,
                tickUpper,
                true
            );
        } else {
            // If liquidity is 0 but a tokenId was created (should not happen if mint reverts on 0 liquidity), burn it.
            if (mintCallSuccess && tokenIdMinted != 0) {
                try positionManager.burn(tokenIdMinted) {} catch {}
            }
            currentPosition = Position(0, 0, 0, 0, false);
            mintCallSuccess = false; // Mark as overall not successful if no liquidity
        }

        emit LiquidityOperation(
            "MINT",
            tokenIdMinted,
            tickLower,
            tickUpper,
            liquidityMinted,
            amount0Actual,
            amount1Actual,
            mintCallSuccess && liquidityMinted > 0 // Success only if liquidity > 0
        );

        if (!(mintCallSuccess && liquidityMinted > 0)) {
            // If mint didn't result in liquidity, ensure position is marked inactive
            currentPosition = Position(0, 0, 0, 0, false);
        }
    }

    function floorToTickSpacing(
        int24 tick,
        int24 _tickSpacing
    ) internal pure returns (int24) {
        require(_tickSpacing > 0, "Tick spacing must be positive");
        int24 compressed = tick / _tickSpacing;
        if (tick < 0 && (tick % _tickSpacing != 0)) {
            compressed--;
        }
        return compressed * _tickSpacing;
    }

    function _emitPredictionMetrics(
        int24 predictedTick,
        int24 finalTickLower,
        int24 finalTickUpper,
        bool adjusted
    ) internal {
        uint128 liquidityToReport = currentPosition.active
            ? currentPosition.liquidity
            : 0;
        emit PredictionAdjustmentMetrics(
            predictedTick,
            finalTickLower,
            finalTickUpper,
            liquidityToReport,
            adjusted
        );
    }

    function uniswapV3MintCallback(
        uint256 amount0Owed,
        uint256 amount1Owed,
        bytes calldata data // Removed "memory" as it's calldata
    ) external override {
        // data parameter is unused, marked as warning by compiler, acceptable for override
        require(
            msg.sender == address(positionManager) ||
                msg.sender == factory.getPool(token0, token1, fee), // Callback can be from pool too
            "PLM: Unauthorized callback"
        );
        if (amount0Owed > 0) {
            IERC20(token0).safeTransfer(msg.sender, amount0Owed);
        }
        if (amount1Owed > 0) {
            IERC20(token1).safeTransfer(msg.sender, amount1Owed);
        }
    }
}
