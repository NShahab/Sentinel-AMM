// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6; // Keeping the original pragma
pragma abicoder v2; // Keep abicoder v2

// --- Imports ---
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Factory.sol";
import "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";

// Interface for WETH
interface IWETH {
    function deposit() external payable;
    function withdraw(uint256) external;
}

contract BaselineMinimal is Ownable {
    using SafeERC20 for IERC20;

    // --- Main State Variables ---
    IUniswapV3Factory public immutable factory;
    INonfungiblePositionManager public immutable positionManager; // Made immutable
    address public immutable token0;
    address public immutable token1;
    uint24 public immutable fee;
    int24 public immutable tickSpacing; // Made immutable
    uint24 public rangeWidthMultiplier;

    // --- Variables for position tracking ---
    uint256 public currentTokenId;
    uint128 public currentLiquidity;
    bool public hasPosition;
    int24 public lowerTick; // State variable for current lower tick
    int24 public upperTick; // State variable for current upper tick

    // --- Event declarations ---
    event StrategyParamUpdated(string indexed paramName, uint256 newValue);
    event PositionStateChanged(
        uint256 indexed tokenId,
        bool hasPosition,
        int24 lowerTick,
        int24 upperTick,
        uint128 liquidity
    );
    event BaselineAdjustmentMetrics(
        uint256 timestamp,
        uint160 sqrtPriceX96,
        int24 currentTick,
        int24 targetTickLower,
        int24 targetTickUpper,
        bool adjusted
    );
    event PositionMinted(
        uint256 indexed tokenId,
        uint128 liquidity,
        int24 tickLower,
        int24 tickUpper,
        uint256 amount0Actual,
        uint256 amount1Actual
    );

    // New event for fees collected by collectCurrentFeesOnly
    event FeesOnlyCollected(
        uint256 indexed tokenId,
        uint256 amount0Collected,
        uint256 amount1Collected,
        bool success
    );

    constructor(
        address _factory,
        address _positionManager,
        address _token0,
        address _token1,
        uint24 _fee,
        uint24 _initialRangeWidthMultiplier
    ) {
        require(_factory != address(0), "BM: Invalid factory address");
        require(_positionManager != address(0), "BM: Invalid position manager");
        require(_token0 != address(0), "BM: Invalid token0");
        require(_token1 != address(0), "BM: Invalid token1");
        require(_token0 != _token1, "BM: Tokens must be different");
        require(_fee > 0, "BM: Invalid fee");

        factory = IUniswapV3Factory(_factory);
        positionManager = INonfungiblePositionManager(_positionManager);
        token0 = _token0;
        token1 = _token1;
        fee = _fee;

        require(
            _initialRangeWidthMultiplier > 0,
            "BM: Initial RWM must be > 0"
        );
        rangeWidthMultiplier = _initialRangeWidthMultiplier;

        address poolAddress = IUniswapV3Factory(_factory).getPool( // Use constructor argument _factory
                _token0,
                _token1,
                _fee
            );
        require(
            poolAddress != address(0),
            "BM: Pool does not exist for specified tokens/fee"
        );

        // CORRECTED: Read into local var, validate, then assign to immutable
        int24 localTickSpacingValue = IUniswapV3Pool(poolAddress).tickSpacing();
        require(
            localTickSpacingValue > 0,
            "BM: Invalid tick spacing from pool"
        );
        tickSpacing = localTickSpacingValue;

        // Use constructor argument _positionManager for approve to avoid reading immutable during creation
        IERC20(_token0).approve(_positionManager, type(uint256).max);
        IERC20(_token1).approve(_positionManager, type(uint256).max);
    }

    function setRangeWidthMultiplier(uint24 _newMultiplier) external onlyOwner {
        require(_newMultiplier > 0, "BM: RWM must be > 0");
        rangeWidthMultiplier = _newMultiplier;
        emit StrategyParamUpdated(
            "rangeWidthMultiplier",
            uint256(_newMultiplier)
        );
    }

    function adjustLiquidityWithCurrentPrice() public {
        address pool = factory.getPool(token0, token1, fee); // Correctly uses immutable factory
        uint160 sqrtPriceX96;
        int24 currentTick;
        // slot0 returns (sqrtPriceX96, tick, observationIndex, observationCardinality, observationCardinalityNext, feeProtocol, unlocked)
        (sqrtPriceX96, currentTick, , , , , ) = IUniswapV3Pool(pool).slot0();

        // Logic for calculating targetLowerTick and targetUpperTick remains UNCHANGED
        int24 _currentTickSpacing = tickSpacing; // Use stored immutable value, renamed for clarity in this scope
        // int24 halfWidth = (_currentTickSpacing * int24(rangeWidthMultiplier)) / 200; // Example if RWM is in basis points for 100% = 100
        // Your original logic for halfWidth was:
        int24 halfWidth = (_currentTickSpacing * int24(rangeWidthMultiplier)) /
            2; // Based on your example "10 * param / 2" (if RWM is the param and _tickSpacing is 10)
        // If rangeWidthMultiplier is intended to be a direct multiplier of tickSpacing for the *half* width already, then /2 is not needed.
        // Assuming your example "10 که * ضربدر پارامتری می شه" refers to `_currentTickSpacing * rangeWidthMultiplier` being the *total desired width in ticks around the current tick*
        // and then it's halved. This seems like the most direct interpretation of your prior example.
        // If rangeWidthMultiplier = 100 means 100 * tickSpacing half-width, then the division by 2 is not needed.
        // I will keep your original logic: `(_tickSpacing * int24(rangeWidthMultiplier)) / 2`
        if (halfWidth < _currentTickSpacing) {
            // Ensure min width is at least one tickSpacing
            halfWidth = _currentTickSpacing;
        }
        // Ensure ticks are centered and multiples of tickSpacing
        int24 targetLowerTick = ((currentTick - halfWidth) /
            _currentTickSpacing) * _currentTickSpacing;
        int24 targetUpperTick = ((currentTick + halfWidth) /
            _currentTickSpacing) * _currentTickSpacing;

        // If currentTick is already perfectly on a tick, the above might shift it slightly if halfWidth is not a multiple of tickSpacing.
        // A common alternative for centering:
        // int24 centralTick = (currentTick / _currentTickSpacing) * _currentTickSpacing;
        // targetLowerTick = centralTick - halfWidth; // Then ensure halfWidth itself is a multiple of _tickSpacing
        // targetUpperTick = centralTick + halfWidth;
        // targetLowerTick = (targetLowerTick / _currentTickSpacing) * _currentTickSpacing; // Re-align
        // targetUpperTick = (targetUpperTick / _currentTickSpacing) * _currentTickSpacing; // Re-align
        // For now, sticking to your derived logic:

        if (targetLowerTick >= targetUpperTick) {
            // Should ideally be an issue with halfWidth calculation if this happens before boundary checks
            // This typically means halfWidth became zero or negative, or currentTick is too close to boundaries
            // Ensure at least one tickSpacing wide
            targetUpperTick = targetLowerTick + _currentTickSpacing;
        }

        // Boundary checks using TickMath constants are good practice
        int24 minSupportedTick = -887272; // Approx TickMath.MIN_TICK for Uniswap V3
        int24 maxSupportedTick = 887272; // Approx TickMath.MAX_TICK for Uniswap V3

        if (targetLowerTick < minSupportedTick)
            targetLowerTick = minSupportedTick;
        if (targetUpperTick > maxSupportedTick)
            targetUpperTick = maxSupportedTick;

        // Ensure ticks are aligned with spacing AFTER boundary checks
        targetLowerTick =
            (targetLowerTick / _currentTickSpacing) *
            _currentTickSpacing;
        targetUpperTick =
            (targetUpperTick / _currentTickSpacing) *
            _currentTickSpacing;

        // Final validation for tick order and minimum gap
        if (targetLowerTick >= targetUpperTick) {
            if (targetUpperTick == maxSupportedTick) {
                // If upper is already max, lower it, ensuring it's aligned
                targetLowerTick =
                    ((targetUpperTick - _currentTickSpacing) /
                        _currentTickSpacing) *
                    _currentTickSpacing;
            } else {
                // Otherwise, ensure upper is at least one spacing above lower, aligned
                targetUpperTick =
                    ((targetLowerTick + _currentTickSpacing) /
                        _currentTickSpacing) *
                    _currentTickSpacing;
                // Re-check if pushing upper overshot MAX_TICK
                if (targetUpperTick > maxSupportedTick) {
                    targetUpperTick =
                        (maxSupportedTick / _currentTickSpacing) *
                        _currentTickSpacing; // Align max tick
                    targetLowerTick =
                        ((targetUpperTick - _currentTickSpacing) /
                            _currentTickSpacing) *
                        _currentTickSpacing; // Adjust lower accordingly
                }
            }
        }
        // Ensure lower is strictly less than upper after all adjustments
        require(
            targetLowerTick < targetUpperTick,
            "BM: Final tick calc L>=U or not spaced"
        );
        // Also ensure they are at least one tickSpacing apart if not already covered
        require(
            targetUpperTick - targetLowerTick >= _currentTickSpacing,
            "BM: Ticks too close"
        );

        if (
            hasPosition &&
            targetLowerTick == lowerTick && // Uses state variable lowerTick
            targetUpperTick == upperTick // Uses state variable upperTick
        ) {
            emit BaselineAdjustmentMetrics(
                block.timestamp,
                sqrtPriceX96,
                currentTick,
                targetLowerTick,
                targetUpperTick,
                false // Not adjusted
            );
            return;
        }

        if (hasPosition) {
            _removePosition();
        }

        _createPosition(targetLowerTick, targetUpperTick);

        emit BaselineAdjustmentMetrics(
            block.timestamp,
            sqrtPriceX96,
            currentTick,
            targetLowerTick,
            targetUpperTick,
            true // Adjusted
        );
    }

    // NEW public function to only collect fees
    function collectCurrentFeesOnly()
        external
        onlyOwner
        returns (uint256 amount0, uint256 amount1)
    {
        require(hasPosition && currentTokenId != 0, "BM: No active position");

        uint256 _tokenIdToCollect = currentTokenId; // Use a local variable for clarity
        bool collectCallSuccess = false;

        try
            positionManager.collect(
                INonfungiblePositionManager.CollectParams({
                    tokenId: _tokenIdToCollect,
                    recipient: address(this),
                    amount0Max: type(uint128).max,
                    amount1Max: type(uint128).max
                })
            )
        returns (uint256 collected0, uint256 collected1) {
            amount0 = collected0;
            amount1 = collected1;
            collectCallSuccess = true;
        } catch Error(string memory reason) {
            emit FeesOnlyCollected(_tokenIdToCollect, 0, 0, false); // Emit with tokenId
            revert(
                string(
                    abi.encodePacked(
                        "BM: CollectOnly direct call failed - ",
                        reason
                    )
                )
            );
        } catch {
            // Catches other errors like out-of-gas not fitting Error(string)
            emit FeesOnlyCollected(_tokenIdToCollect, 0, 0, false); // Emit with tokenId
            revert("BM: CollectOnly direct call failed with unknown error");
        }

        emit FeesOnlyCollected(
            _tokenIdToCollect,
            amount0,
            amount1,
            collectCallSuccess
        );
        return (amount0, amount1);
    }

    function _removePosition() internal {
        require(hasPosition, "BM: No position to remove");

        uint256 _tokenIdToRemove = currentTokenId;
        uint128 _liquidityToRemove = currentLiquidity;

        // Update state first to prevent re-entrancy issues if any external calls were here
        // though current external calls are well-contained.
        hasPosition = false;
        currentTokenId = 0;
        currentLiquidity = 0;
        lowerTick = 0;
        upperTick = 0;

        emit PositionStateChanged(_tokenIdToRemove, false, 0, 0, 0);

        // If there was liquidity, decrease it.
        if (_liquidityToRemove > 0) {
            try
                positionManager.decreaseLiquidity(
                    INonfungiblePositionManager.DecreaseLiquidityParams({
                        tokenId: _tokenIdToRemove,
                        liquidity: _liquidityToRemove,
                        amount0Min: 0,
                        amount1Min: 0,
                        deadline: block.timestamp
                    })
                )
            // returns (uint256 amount0Decreased, uint256 amount1Decreased)
            {
                // These returned amounts from decreaseLiquidity are principal, not fees.
                // BaselineMinimal doesn't explicitly use them in events here.
            } catch Error(string memory reason) {
                revert(
                    string(
                        abi.encodePacked(
                            "BM: DecreaseLiquidity failed - ",
                            reason
                        )
                    )
                );
            } catch {
                revert("BM: DecreaseLiquidity failed with unknown error");
            }
        }

        // Always attempt to collect any accrued fees for the token ID.
        // This will also collect the principal if decreaseLiquidity was successful.
        try
            positionManager.collect(
                INonfungiblePositionManager.CollectParams({
                    tokenId: _tokenIdToRemove,
                    recipient: address(this), // Tokens sent to this contract
                    amount0Max: type(uint128).max,
                    amount1Max: type(uint128).max
                })
            )
        // returns (uint256 amount0CollectedTotal, uint256 amount1CollectedTotal)
        {
            // These are total tokens withdrawn (principal + fees).
            // No specific event for these amounts in BaselineMinimal _removePosition.
            // The main fee tracking would be via external calls or specific fee collection functions.
        } catch Error(string memory reason) {
            revert(
                string(
                    abi.encodePacked(
                        "BM: Collect during remove failed - ",
                        reason
                    )
                )
            );
        } catch {
            revert("BM: Collect during remove failed with unknown error");
        }

        // Finally, burn the NFT.
        // This should only happen after tokens are successfully withdrawn.
        // The try/catch for burn is to make it best-effort if other operations succeeded.
        try positionManager.burn(_tokenIdToRemove) {} catch Error(
            string memory reason
        ) {
            // Optional: Log or emit warning that burn failed but funds were handled.
            // For now, consistent with original: ignore burn failure reason string.
        } catch {
            // Optional: Log or emit warning.
        }
    }

    function _createPosition(
        int24 _newLowerTick,
        int24 _newUpperTick
    ) internal {
        require(
            _newLowerTick < _newUpperTick,
            "BM: Invalid tick range for create"
        );

        uint256 amount0Desired = IERC20(token0).balanceOf(address(this));
        uint256 amount1Desired = IERC20(token1).balanceOf(address(this));

        if (amount0Desired == 0 && amount1Desired == 0) {
            if (hasPosition) {
                // Should not happen if _removePosition was called before
                hasPosition = false;
                currentTokenId = 0;
                currentLiquidity = 0;
                lowerTick = 0;
                upperTick = 0;
                emit PositionStateChanged(0, false, 0, 0, 0);
            }
            return; // No tokens to provide liquidity with
        }

        uint256 _mintedTokenId;
        uint128 _mintedLiquidity;
        uint256 _amount0Actual;
        uint256 _amount1Actual;

        try
            positionManager.mint(
                INonfungiblePositionManager.MintParams({
                    token0: token0,
                    token1: token1,
                    fee: fee,
                    tickLower: _newLowerTick,
                    tickUpper: _newUpperTick,
                    amount0Desired: amount0Desired,
                    amount1Desired: amount1Desired,
                    amount0Min: 0, // Simplistic: allow any amount of token0 to be used
                    amount1Min: 0, // Simplistic: allow any amount of token1 to be used
                    recipient: address(this),
                    deadline: block.timestamp
                })
            )
        returns (
            uint256 mintedTokenIdFromCall,
            uint128 mintedLiquidityFromCall,
            uint256 amount0FromCall,
            uint256 amount1FromCall
        ) {
            _mintedTokenId = mintedTokenIdFromCall;
            _mintedLiquidity = mintedLiquidityFromCall;
            _amount0Actual = amount0FromCall;
            _amount1Actual = amount1FromCall;
        } catch Error(string memory reason) {
            revert(string(abi.encodePacked("BM: Mint failed - ", reason)));
        } catch {
            revert("BM: Mint failed with unknown error");
        }

        if (_mintedLiquidity > 0) {
            currentTokenId = _mintedTokenId;
            currentLiquidity = _mintedLiquidity;
            hasPosition = true;
            lowerTick = _newLowerTick; // Update state variable lowerTick
            upperTick = _newUpperTick; // Update state variable upperTick

            emit PositionStateChanged(
                _mintedTokenId,
                true,
                _newLowerTick,
                _newUpperTick,
                _mintedLiquidity
            );
            emit PositionMinted(
                _mintedTokenId,
                _mintedLiquidity,
                _newLowerTick,
                _newUpperTick,
                _amount0Actual,
                _amount1Actual
            );
        } else {
            // If mint call succeeded but returned 0 liquidity (should ideally revert in PositionManager or be caught by amount0Min/amount1Min if set > 0)
            // or if tokenId was somehow generated without liquidity.
            if (_mintedTokenId > 0) {
                try positionManager.burn(_mintedTokenId) {} catch {
                    // Best effort to clean up if a token was minted with no liquidity.
                }
            }
            // Ensure state reflects no active position if no liquidity was actually added.
            hasPosition = false;
            currentTokenId = 0;
            currentLiquidity = 0;
            lowerTick = 0;
            upperTick = 0;
            // Potentially emit PositionStateChanged here too if it was previously true
        }
    }

    function rescueTokens(
        address _tokenAddress,
        address _to
    ) external onlyOwner {
        require(_tokenAddress != address(0), "BM: Invalid token address");
        require(_to != address(0), "BM: Invalid recipient address");
        uint256 amount = IERC20(_tokenAddress).balanceOf(address(this));
        if (amount > 0) {
            IERC20(_tokenAddress).safeTransfer(_to, amount);
        }
    }

    function rescueETH() external onlyOwner {
        uint256 balance = address(this).balance;
        if (balance > 0) {
            (bool success, ) = owner().call{value: balance}("");
            require(success, "BM: ETH rescue failed");
        }
    }

    function rescueWETH(uint256 amount) external onlyOwner {
        require(amount > 0, "BM: Amount must be positive");
        // خط require نادرست که باعث خطا شده بود حذف گردید.
        // require(token1 == address(IWETH(token1).deposit), "BM: token1 is not WETH for rescueWETH"); // << این خط حذف شود

        IWETH(token1).withdraw(amount); // این خط به درستی فرض می‌کند token1 آدرس WETH است
        (bool success, ) = owner().call{value: amount}("");
        require(success, "BM: WETH rescue failed - ETH transfer failed");
    }

    function getCurrentPosition()
        external
        view
        returns (
            uint256 tokenId,
            bool active,
            int24 _outLowerTick, // Renamed for clarity to avoid shadowing state vars
            int24 _outUpperTick, // Renamed for clarity
            uint128 liquidity
        )
    {
        return (
            currentTokenId,
            hasPosition,
            lowerTick, // Returns state variable lowerTick
            upperTick, // Returns state variable upperTick
            currentLiquidity
        );
    }
}
