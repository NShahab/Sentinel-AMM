// SPDX-License-Identifier: MIT
pragma solidity ^0.7.6;

import "@openzeppelin/contracts/math/SafeMath.sol"; // Import OZ 3.4 SafeMath

/**
 * @title Safe Square Root Math Library for Solidity 0.7.x
 * @author Adapted from OpenZeppelin Contracts & other sources
 * @notice Provides square root functionality using SafeMath for uint256.
 */
library SqrtMath {
    using SafeMath for uint256;

    // Optional: Include Rounding enum if your main contract needs the rounding variant
    enum Rounding {
        Floor,
        Ceil
    }

    /**
     * @dev Returns the integer square root of a number rounded down (floor).
     * Uses Babylonian method with SafeMath. 6 iterations are sufficient for uint256.
     */
    function sqrt(uint256 a) internal pure returns (uint256) {
        if (a == 0) return 0;

        // Initial estimate - can start with a simple estimate like a/2 or use log2_ based estimate
        // Using roughly x = 2**(log2(a)/2) based estimate (safer)
        uint256 estimate = 1 << (log2_(a) >> 1);
        if (estimate == 0) estimate = 1; // Ensure estimate is not zero if a > 0

        // Babylonian method iterations using SafeMath
        // result = (estimate + a / estimate) / 2;
        uint256 result = estimate.add(a.div(estimate)).div(2);
        result = result.add(a.div(result)).div(2);
        result = result.add(a.div(result)).div(2);
        result = result.add(a.div(result)).div(2);
        result = result.add(a.div(result)).div(2);
        result = result.add(a.div(result)).div(2);

        // Final check for floor rounding (integer truncation might overshoot)
        // Check if result * result > a
        // Avoid direct multiplication if result can be large, use division check: result > a / result
        if (result > a.div(result)) {
            // If result > a/result, it means result*result > a (potential overflow avoided)
            // So, the floor value is result - 1
            return result.sub(1);
        } else {
            // Otherwise, result*result <= a, so result is the floor value
            return result;
        }
    }

    /**
     * @dev Calculates sqrt(a), following the selected rounding direction.
     */
    function sqrt(
        uint256 a,
        Rounding rounding
    ) internal pure returns (uint256) {
        uint256 resultFloor = sqrt(a); // Calculate floor value first
        if (rounding == Rounding.Floor) {
            return resultFloor;
        } else {
            // rounding == Rounding.Ceil
            // Check if ceil is needed (i.e., if a is not a perfect square)
            // If resultFloor * resultFloor < a, then we need to round up
            if (resultFloor.mul(resultFloor) < a) {
                // Use SafeMath for the check
                return resultFloor.add(1);
            } else {
                return resultFloor; // a was a perfect square, floor == ceil
            }
        }
    }

    // --- Internal helper: log2 needed for initial estimate ---
    /**
     * @dev Return the log in base 2 of a positive value rounded towards zero.
     * Returns 0 if given 0. Adapted from OZ 4.x for 0.7.6 compatibility using assembly.
     */
    function log2_(uint256 x) internal pure returns (uint256 r) {
        assembly {
            let v := x
            if iszero(v) {
                r := 0
            }
            if gt(v, 0xffffffffffffffffffffffffffffffff) {
                r := add(r, 128)
                v := shr(128, v)
            }
            if gt(v, 0xffffffffffffffff) {
                r := add(r, 64)
                v := shr(64, v)
            }
            if gt(v, 0xffffffff) {
                r := add(r, 32)
                v := shr(32, v)
            }
            if gt(v, 0xffff) {
                r := add(r, 16)
                v := shr(16, v)
            }
            if gt(v, 0xff) {
                r := add(r, 8)
                v := shr(8, v)
            }
            if gt(v, 0xf) {
                r := add(r, 4)
                v := shr(4, v)
            }
            if gt(v, 0x3) {
                r := add(r, 2)
                v := shr(2, v)
            }
            if gt(v, 0x1) {
                r := add(r, 1)
            }
        }
    }
}
