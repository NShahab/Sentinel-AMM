// SPDX-License-Identifier: MIT
// MODIFIED: Upgraded pragma to be compatible with the main project
pragma solidity ^0.8.20;

/**
 * @title Square Root Math Library for Solidity >=0.8.0
 * @author Adapted from OpenZeppelin Contracts
 * @notice Provides square root functionality for uint256.
 * It uses standard arithmetic, relying on the compiler's built-in overflow checks.
 */
library SqrtMath {
    // UNCHANGED: The Rounding enum is compatible.
    enum Rounding {
        Floor,
        Ceil
    }

    /**
     * @dev Returns the integer square root of a number rounded down (floor).
     * Uses Babylonian method. 6 iterations are sufficient for uint256.
     */
    function sqrt(uint256 a) internal pure returns (uint256) {
        if (a == 0) return 0;

        uint256 estimate = 1 << (log2_(a) >> 1);
        if (estimate == 0) estimate = 1;

        // MODIFIED: Replaced all .add() and .div() calls with standard operators.
        // The parentheses are important to maintain the order of operations.
        uint256 result = (estimate + a / estimate) / 2;
        result = (result + a / result) / 2;
        result = (result + a / result) / 2;
        result = (result + a / result) / 2;
        result = (result + a / result) / 2;
        result = (result + a / result) / 2;

        // MODIFIED: Replaced .div() and .sub() with standard operators.
        if (result > a / result) {
            return result - 1;
        } else {
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
        uint256 resultFloor = sqrt(a);
        if (rounding == Rounding.Floor) {
            return resultFloor;
        } else {
            // MODIFIED: Replaced .mul() and .add() with standard operators.
            if (resultFloor * resultFloor < a) {
                return resultFloor + 1;
            } else {
                return resultFloor;
            }
        }
    }

    // UNCHANGED: The internal log2_ function using assembly is fully compatible.
    /**
     * @dev Return the log in base 2 of a positive value rounded towards zero.
     * Returns 0 if given 0.
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
