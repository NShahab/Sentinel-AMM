// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6;
pragma abicoder v2;

// Minimized imports
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/SafeMath.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@uniswap/v3-periphery/contracts/interfaces/external/IWETH9.sol";

/**
 * @title TokenOperationsManagerOptimized
 * @notice Optimized for reduced contract size
 */
contract TokenOperationsManagerOptimized is Ownable {
    using SafeERC20 for IERC20;
    using SafeMath for uint256;

    // Core state variables
    ISwapRouter public immutable swapRouter;
    address public immutable WETH9;

    // Single combined event for all operations
    event Operation(
        bytes32 indexed opType,
        address indexed tokenA,
        address indexed tokenB,
        uint256 amount
    );

    constructor(address _swapRouter, address _weth9) {
        swapRouter = ISwapRouter(_swapRouter);
        WETH9 = _weth9;
    }

    // Optimized swap function
    function swap(
        address tokenIn,
        address tokenOut,
        uint24 poolFee,
        uint256 amountIn,
        uint256 amountOutMin
    ) external onlyOwner returns (uint256 amountOut) {
        // Transfer tokens to contract
        IERC20(tokenIn).safeTransferFrom(msg.sender, address(this), amountIn);

        // Approve router
        IERC20(tokenIn).safeApprove(address(swapRouter), amountIn);

        // Execute swap
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
            .ExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                fee: poolFee,
                recipient: address(this),
                deadline: block.timestamp,
                amountIn: amountIn,
                amountOutMinimum: amountOutMin,
                sqrtPriceLimitX96: 0
            });

        amountOut = swapRouter.exactInputSingle(params);

        // Reset approval
        IERC20(tokenIn).safeApprove(address(swapRouter), 0);

        emit Operation(bytes32("SWAP"), tokenIn, tokenOut, amountOut);

        return amountOut;
    }

    // Deposit tokens (including ETH via WETH)
    function deposit(address token, uint256 amount) external payable onlyOwner {
        if (token == WETH9) {
            require(msg.value == amount, "ETH value != amount");
            IWETH9(WETH9).deposit{value: amount}();
        } else {
            require(msg.value == 0, "ETH not needed");
            IERC20(token).safeTransferFrom(msg.sender, address(this), amount);
        }

        emit Operation(bytes32("DEPOSIT"), token, address(0), amount);
    }

    // Withdraw tokens (including ETH via WETH)
    function withdraw(address token, uint256 amount) external onlyOwner {
        if (token == WETH9) {
            uint256 balance = IERC20(WETH9).balanceOf(address(this));
            require(balance >= amount, "Insufficient WETH");
            IWETH9(WETH9).withdraw(amount);
            payable(msg.sender).transfer(amount);
        } else {
            uint256 balance = IERC20(token).balanceOf(address(this));
            require(balance >= amount, "Insufficient balance");
            IERC20(token).safeTransfer(msg.sender, amount);
        }

        emit Operation(bytes32("WITHDRAW"), token, address(0), amount);
    }

    // Combined function for handling ETH
    function handleETH(
        bytes32 action,
        uint256 minAmount,
        address recipient
    ) external onlyOwner {
        address payable to = recipient == address(0)
            ? payable(msg.sender)
            : payable(recipient);

        if (action == bytes32("REFUND_ETH")) {
            uint256 balance = address(this).balance;
            require(balance >= minAmount, "Insufficient ETH");
            to.transfer(balance);
            emit Operation(action, address(0), address(0), balance);
        } else if (action == bytes32("UNWRAP_WETH")) {
            uint256 balance = IERC20(WETH9).balanceOf(address(this));
            require(balance >= minAmount, "Insufficient WETH");
            IWETH9(WETH9).withdraw(balance);
            to.transfer(balance);
            emit Operation(action, WETH9, address(0), balance);
        } else if (
            action == bytes32("SWEEP_TOKEN") && recipient != address(0)
        ) {
            // The recipient must be provided for this operation
            // This operation is handled separately to avoid stack too deep errors
            revert("Use sweepToken function");
        } else {
            revert("Invalid action");
        }
    }

    // Separate function for token sweeping to avoid stack too deep
    function sweepToken(
        address token,
        uint256 minAmount,
        address recipient
    ) external onlyOwner {
        require(recipient != address(0), "Invalid recipient");
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance >= minAmount, "Insufficient balance");
        IERC20(token).safeTransfer(recipient, balance);
        emit Operation(bytes32("SWEEP_TOKEN"), token, address(0), balance);
    }

    // Simplified view functions
    function getBalance(address token) external view returns (uint256) {
        return
            token == address(0)
                ? address(this).balance
                : IERC20(token).balanceOf(address(this));
    }

    // Required to receive ETH
    receive() external payable {}
}
