// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
pragma abicoder v2;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@uniswap/v3-periphery/contracts/libraries/TransferHelper.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@uniswap/v3-core/contracts/interfaces/pool/IUniswapV3PoolImmutables.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Market.sol";
import "@overlay/v1-core/contracts/interfaces/IOverlayV1Token.sol";
import "@overlay/v1-core/contracts/libraries/FixedPoint.sol";
import "@overlay/v1-periphery/contracts/interfaces/IOverlayV1State.sol";

// forks of uniswap libraries for solidity^0.8.10
import "@overlay/v1-core/contracts/libraries/uniswap/v3-core/FullMath.sol";
import "@overlay/v1-core/contracts/libraries/uniswap/v3-core/TickMath.sol";

contract EthBasisTrade {
    using FixedPoint for uint256;
    uint256 public immutable ONE = 1e18;

    ISwapRouter public immutable swapRouter;
    IOverlayV1Token public immutable ovl;
    IOverlayV1Market public immutable ovlMarket;
    IOverlayV1State public immutable ovlState;
    address public immutable WETH9;
    address public immutable pool;
    address public immutable owner;

    uint256 public posId;

    /// @dev when currState = 0, contract holds spot WETH only
    /// @dev when currState = 1, contract holds a long on ETH/OVL
    uint256 public currState = 0; // TODO: change to enum

    event Update(uint256 toState, uint256 amount);

    constructor(
        ISwapRouter _swapRouter,
        address _ovlState,
        address _WETH9,
        address _ovl,
        address _pool,
        address _ovlMarket
    ) {
        owner = msg.sender;
        swapRouter = _swapRouter;
        ovlState = IOverlayV1State(_ovlState);
        WETH9 = _WETH9;
        ovl = IOverlayV1Token(_ovl);
        pool = _pool;
        ovlMarket = IOverlayV1Market(_ovlMarket);
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "!owner");
        _;
    }

    /// TODO: Currently taking WETH deposits. Change to accept ETH deposits.
    function depositWeth(uint256 amountIn) external onlyOwner {
        IERC20(WETH9).transferFrom(msg.sender, address(this), amountIn);
    }

    /// @dev similar to getQuoteAtTick in uniswap v3
    function getQuoteAtTick(
        bool toEth,
        uint128 baseAmount,
        address baseToken,
        address quoteToken
    ) public view returns (uint256 quoteAmount) {
        int24 tick;
        int24 tickCurr;
        (, tickCurr, , , , , ) = IUniswapV3Pool(pool).slot0();
        if (toEth == true) {
            tick = tickCurr + 200;
        } else {
            tick = tickCurr - 200;
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

    function swapExactInputSingle(uint256 amountIn, bool toEth)
        internal
        returns (uint256 amountOut)
    {
        address tokenIn;
        address tokenOut;

        if (toEth == true) {
            tokenIn = address(ovl);
            tokenOut = WETH9;
        } else {
            tokenIn = WETH9;
            tokenOut = address(ovl);
        }
        uint256 amountOutFactor = getQuoteAtTick(toEth, 1e18, tokenIn, tokenOut);
        uint256 amountOutMinimum = FullMath.mulDiv(amountOutFactor, amountIn, 1e18);

        TransferHelper.safeApprove(tokenIn, address(swapRouter), amountIn);

        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: tokenIn,
            tokenOut: tokenOut,
            fee: IUniswapV3PoolImmutables(pool).fee(),
            recipient: address(this),
            deadline: block.timestamp + 120,
            amountIn: amountIn,
            amountOutMinimum: amountOutMinimum,
            sqrtPriceLimitX96: 0
        });

        amountOut = swapRouter.exactInputSingle(params);
    }

    function buildOvlPosition(uint256 size, uint256 priceLimit)
        internal
        returns (uint256 positionId_)
    {
        (uint256 collateral, uint256 fee) = getOverlayTradingFee(size);
        TransferHelper.safeApprove(address(ovl), address(ovlMarket), collateral + fee);
        positionId_ = ovlMarket.build(collateral, 1e18, true, priceLimit);
    }

    function unwindOvlPosition(
        uint256 positionId,
        uint256 fraction,
        uint256 priceLimit
    ) internal {
        ovlMarket.unwind(positionId, fraction, priceLimit);
    }

    /// @notice collateral is equal to notional size since leverage is always 1 for basis trade
    function getOverlayTradingFee(uint256 totalSize)
        public
        view
        returns (uint256 collateral, uint256 fee)
    {
        collateral = totalSize.divDown(1e18 + ovlMarket.params(11));
        fee = collateral.mulUp(ovlMarket.params(11));
    }

    function update() external {
        uint256 ovlAmount;
        int256 fundingRate = ovlState.fundingRate(ovlMarket.feed());
        if (fundingRate < 0) {
            require(currState == 0, "Already long");
            currState = 1;
            uint256 ethAmount = IERC20(WETH9).balanceOf(address(this));
            ovlAmount = swapExactInputSingle(ethAmount, false);
            posId = buildOvlPosition(ovlAmount, 10e18);
        } else {
            require(currState == 1, "Already idle");
            currState = 0;
            unwindOvlPosition(posId, 1e18, 0);
            ovlAmount = ovl.balanceOf(address(this));
            swapExactInputSingle(ovlAmount, true);
        }
    }

    function withdraw() external onlyOwner {
        uint256 ethAmount;
        if (currState == 0) {
            ethAmount = IERC20(WETH9).balanceOf(address(this));
            _withdraw(ethAmount);
        } else {
            unwindOvlPosition(posId, 1e18, 0);
            uint256 ovlAmount = ovl.balanceOf(address(this));
            ethAmount = swapExactInputSingle(ovlAmount, true);
            _withdraw(ethAmount);
        }
    }

    function _withdraw(uint256 ethAmount) internal {
        TransferHelper.safeApprove(WETH9, msg.sender, ethAmount);
        IERC20(WETH9).transferFrom(address(this), msg.sender, ethAmount);
    }
}
