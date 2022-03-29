// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@uniswap/v3-periphery/contracts/libraries/TransferHelper.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@uniswap/v3-core/contracts/interfaces/pool/IUniswapV3PoolState.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Market.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Token.sol";
import "@overlay/v1-core/contracts/interfaces/feeds/IOverlayV1Feed.sol";

// forks of uniswap libraries for solidity^0.8.10
import "./libraries/uniswapv3-core/FullMath.sol";
import "./libraries/uniswapv3-core/TickMath.sol";

contract EthBasisTrade {
    ISwapRouter public immutable swapRouter;
    IOverlayV1Token public immutable ovl;
    
    struct dInfo {
        uint256 amount;
        bool deposited;
        bool withdrawn;
    }
    mapping (address => dInfo) public depositorInfo;

    /// TODO: DAI needs to be changed to OVL everywhere
    address public DAI;
    address public WETH9;
    address public pool;
    address public ovlMarket;
    uint24 public constant poolFee = 3000;
    ///@dev when posTracker = 0, contract holds spot WETH only (ideally should be short)
    ///@dev when posTracker = 1, contract holds a long on ETH/OVL
    ///@dev when posTracker = 2, contract holds spot WETH only (ideally lending on money market)
    ///@dev when posTracker = 3, contract holds spot WETH only
    uint256 public posTracker = 3;
    // TODO: change to enum

    constructor(
        ISwapRouter _swapRouter,
        address _DAI,
        address _WETH9,
        address _ovl,
        address _pool,
        address _ovlMarket
    ) {
        swapRouter = _swapRouter;
        DAI = _DAI;
        WETH9 = _WETH9;
        ovl = IOverlayV1Token(_ovl);
        pool = _pool;
        ovlMarket = _ovlMarket;
    }

    /// TODO: Currently taking WETH deposits. Change to accept ETH deposits.
    function depositEth(uint256 amountIn) public {
        TransferHelper.safeTransferFrom(WETH9, msg.sender, address(this), amountIn);
        depositorInfo[msg.sender].amount = amountIn;
        depositorInfo[msg.sender].deposited = true;
        depositorInfo[msg.sender].withdrawn = false;
    }
    
    function getSwapPrice() internal view returns (uint160 swapPrice) {
        (uint160 sqrtPrice, , , , , , ) = IUniswapV3PoolState(pool).slot0();
    }

    function getQuoteAtTick(
        int24 tick,
        uint128 baseAmount,
        address baseToken,
        address quoteToken
    ) internal pure returns (uint256 quoteAmount) {
        uint160 sqrtRatioX96 = TickMath.getSqrtRatioAtTick(tick);

        // Calculate quoteAmount with better precision if 
        // it doesn't overflow when multiplied by itself
        if (sqrtRatioX96 <= type(uint128).max) {
            uint256 ratioX192 = uint256(sqrtRatioX96) * sqrtRatioX96;
            quoteAmount = baseToken < quoteToken
                ? FullMath.mulDiv(ratioX192, baseAmount, 1 << 192)
                : FullMath.mulDiv(1 << 192, baseAmount, ratioX192);
        } else {
            uint256 ratioX128 = FullMath.mulDiv(sqrtRatioX96, sqrtRatioX96, 1 << 64);
            quoteAmount = baseToken < quoteToken
                ? FullMath.mulDiv(ratioX128, baseAmount, 1 << 128)
                : FullMath.mulDiv(1 << 128, baseAmount, ratioX128);
        }
    }

    // function swapExactInputSingle(
    //     uint256 amountIn,
    //     uint256 amountOutMinimum,
    //     bool toEth,
    //     address fromAddr,
    //     address toAddr
    // ) internal returns (uint256 amountOut) {
    //     address tokenIn;
    //     address tokenOut;

    //     if (toEth == true) {
    //         tokenIn = DAI;
    //         tokenOut = WETH9;
    //     } else {
    //         tokenIn = WETH9;
    //         tokenOut = DAI;
    //     }

    //     TransferHelper.safeApprove(tokenIn, address(swapRouter), amountIn);

    //     ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
    //         tokenIn: DAI,
    //         tokenOut: WETH9,
    //         fee: poolFee,
    //         recipient: msg.sender,
    //         deadline: block.timestamp,
    //         amountIn: amountIn,
    //         amountOutMinimum: amountOutMinimum,
    //         sqrtPriceLimitX96: 0
    //     });

    //     amountOut = swapRouter.exactInputSingle(params);
    // }

    // function buildOvlPosition(
    //     uint256 collateral,
    //     uint256 leverage,
    //     bool isLong,
    //     uint256 priceLimit
    // ) internal returns (uint256 positionId_) {
    //     positionId_ = IOverlayV1Market(ovlMarket).build(collateral, leverage, isLong, priceLimit);
    // }

    // function unwindOvlPosition(
    //     uint256 positionId,
    //     uint256 fraction,
    //     uint256 priceLimit
    // ) internal {
    //     IOverlayV1Market(ovlMarket).unwind(positionId, fraction, priceLimit);
    // }

    // function oiShortGTLong() internal returns (uint256 posId) {
    //     swapExactInputSingle(amountIn, amountOutMinimum, toEth, fromAddr, toAddr);
    //     posId = buildOvlPosition(collateral, leverage, ovlLong, priceLimit);
    //     positionTracker = 1;
    // }
    
    // function oiLongGTShort(uint256 posId, uint256 priceLimit) {
    //     unwindOvlPosition(posId, 1e18, priceLimit);
    //     swapExactInputSingle(amountIn, amountOutMinimum, toEth, fromAddr, toAddr);
    //     positionTracker = 0;
    // }

    // function update(uint256 takePosition, uint256 priceLimit) public {
    //     /// when oiLong > oiShort
    //     if (takePosition == 0) {
    //         // require(check if ovl position exists)
    //         oiLongGTShort();
    //     } else if (takePosition == 1) {
    //         // require(check if weth balance greater than 0)
    //         oiShortGTlong();
    //     }
        
    // }
}
