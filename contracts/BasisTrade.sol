// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;
pragma abicoder v2;

import '@uniswap/v3-periphery/contracts/libraries/TransferHelper.sol';
import '@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol';
import '@uniswap/v3-core/contracts/interfaces/pool/IUniswapV3PoolState.sol';
import './interfaces/overlay/v1-core/IOverlayV1Market.sol';

contract BasisTrade {
    ISwapRouter public immutable swapRouter;

    /// TODO: DAI needs to be changed to OVL everywhere
    address public DAI;
    address public WETH9;
    address public pool;
    uint24 public constant poolFee = 3000;

    constructor(ISwapRouter _swapRouter, address _DAI, address _WETH9, address _pool) {
        swapRouter = _swapRouter;
        DAI = _DAI;
        WETH9 = _WETH9;
        pool = _pool;
    }

    function swapExactInputSingle(uint256 amountIn, bool toEth, address fromAddr, address toAddr) internal returns (uint256 amountOut) {
        address tokenIn;
        address tokenOut;

        if (toEth == true) {
            address tokenIn = DAI;
            address tokenOut = WETH9;
        }
        else {
            address tokenIn = WETH9;
            address tokenOut = DAI;
        }

        TransferHelper.safeTransferFrom(tokenIn, msg.sender, address(this), amountIn);

        TransferHelper.safeApprove(tokenIn, address(swapRouter), amountIn);

        ISwapRouter.ExactInputSingleParams memory params =
            ISwapRouter.ExactInputSingleParams({
                tokenIn: DAI,
                tokenOut: WETH9,
                fee: poolFee,
                recipient: msg.sender,
                deadline: block.timestamp,
                amountIn: amountIn,
                amountOutMinimum: 0,
                sqrtPriceLimitX96: 0
            });

        amountOut = swapRouter.exactInputSingle(params);
    }

    function getSwapPrice() internal view returns (uint160 swapPrice) {
        (uint160 sqrtPrice, , , , , , ) = IUniswapV3PoolState(pool).slot0();
    }
}