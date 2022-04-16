// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@uniswap/v3-periphery/contracts/libraries/TransferHelper.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Market.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Token.sol";
import "@overlay/v1-core/contracts/libraries/FixedPoint.sol";

// forks of uniswap libraries for solidity^0.8.10
import "./libraries/uniswapv3-core/FullMath.sol";
import "./libraries/uniswapv3-core/TickMath.sol";

contract EthBasisTrade {
    using FixedPoint for uint256;
    
    ISwapRouter public immutable swapRouter;
    IOverlayV1Token public immutable ovl;
    IOverlayV1Market public immutable ovlMarket;
    
    uint public totalPre;

    address[] public depositorAddressPre;
    mapping (address => uint) public depositorInfoPre;

    address[] public depositorAddressPost;
    struct dInfoPostStruct {
        uint256 amount;
        uint256 posId;
    }
    mapping (address => dInfoPostStruct) public depositorInfoPost;

    address public WETH9;
    address public pool;
    uint24 public constant poolFee = 3000;
    ///@dev when currState = 0, contract holds spot WETH only
    ///@dev when currState = 1, contract holds a long on ETH/OVL
    uint256 public currState = 0;
    // TODO: change to enum

    constructor(
        ISwapRouter _swapRouter,
        address _WETH9,
        address _ovl,
        address _pool,
        address _ovlMarket
    ) {
        swapRouter = _swapRouter;
        WETH9 = _WETH9;
        ovl = IOverlayV1Token(_ovl);
        pool = _pool;
        ovlMarket = IOverlayV1Market(_ovlMarket);
    }

    /// TODO: Currently taking WETH deposits. Change to accept ETH deposits.
    function depositWeth(uint256 amountIn) public {
        IERC20(WETH9).transferFrom(msg.sender, address(this), amountIn);
        if (currState == 0) {
            totalPre = totalPre + amountIn;
            depositorAddressPre.push(msg.sender);
            depositorInfoPre[msg.sender] = amountIn;
        } else {
            depositorAddressPost.push(msg.sender);
            depositorInfoPost[msg.sender].amount = amountIn;
            // long weth/ovl by amountIn here
        }
    }

    /// @dev similar to getQuoteAtTick in uniswap v3
    function getQuoteAtTick(
        bool toEth,
        uint128 baseAmount,
        address baseToken,
        address quoteToken
    ) public view returns (uint256 quoteAmount) {
        int24 tick;
        int24 tick_curr;
        (, tick_curr, , , , , ) = IUniswapV3Pool(pool).slot0();
        if (toEth == true) {
            tick = tick_curr + 200;
        } else {
            tick = tick_curr - 200;
        }
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

    function swapExactInputSingle(
        uint256 amountIn,
        bool toEth
    ) public returns (uint256 amountOut) {
        address tokenIn;
        address tokenOut;

        if (toEth == true) {
            tokenIn = address(ovl);
            tokenOut = WETH9;
        } else {
            tokenIn = WETH9;
            tokenOut = address(ovl);
        }
        uint256 amountOutMinimum = getQuoteAtTick(toEth,
                                                  uint128(amountIn),
                                                  tokenIn,
                                                  tokenOut);

        TransferHelper.safeApprove(tokenIn, address(swapRouter), amountIn);

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: poolFee,
            recipient: address(this),
            deadline: block.timestamp + 120,
            amountIn: amountIn,
            amountOutMinimum: amountOutMinimum,
            sqrtPriceLimitX96: 0
        });

        amountOut = swapRouter.exactInputSingle(params);
    }

    function buildOvlPosition(
        uint256 collateral,
        uint256 fee,
        uint256 leverage,
        bool isLong,
        uint256 priceLimit
    ) public returns (uint256 positionId_) {

        TransferHelper.safeApprove(address(ovl), address(ovlMarket), collateral+fee);
        positionId_ = ovlMarket.build(collateral, leverage, isLong, priceLimit);
    }

    function unwindOvlPosition(
        uint256 positionId,
        uint256 fraction,
        uint256 priceLimit
    ) public {
        ovlMarket.unwind(positionId, fraction, priceLimit);
    }

    function getOverlayTradingFee(
        uint totalSize
        ) public view returns (uint256 tradeSize, uint256 fee) {
        fee = totalSize.mulUp(ovlMarket.params(11));
        tradeSize = totalSize - fee;
        }

    function update(bool wethToLong) external {
        if (wethToLong) {
            currState = 1;
            uint ovlTotalPre = swapExactInputSingle(totalPre, false);
            (uint collateral, uint fee) = getOverlayTradingFee(ovlTotalPre);
            buildOvlPosition(collateral, fee, 1e18, true, 10e18); // fix price limit
        }
    }
}