import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
import yfinance as yf
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class MarketStatus:
    ticker: str
    name: str
    current_price: float
    ath: float
    ath_date: str
    drawdown_pct: float
    drop_amount: float
    currency: str
    updated_at: str
    is_new_high: bool

class MarketTracker:
    def __init__(self, history_period: str = "max"):
        self.history_period = history_period

    def fetch_status(self, ticker_symbol: str, display_name: Optional[str] = None) -> Optional[MarketStatus]:
        """
        指定したティッカーの史上最高値（ATH）、現在価格、ドローダウン率を取得・計算します。
        """
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period=self.history_period)
            
            if hist.empty:
                logger.error(f"[{ticker_symbol}] データが取得できませんでした。")
                return None

            # 過去全期間の高値（ATH）とその日付
            ath_price = float(hist['High'].max())
            ath_timestamp = hist['High'].idxmax()
            ath_date_str = ath_timestamp.strftime('%Y-%m-%d')

            # 現在価格の取得（リアルタイム fast_info を優先し、なければ最新終値）
            current_price = None
            try:
                fast_price = getattr(ticker.fast_info, 'last_price', None)
                if fast_price is not None and not (isinstance(fast_price, float) and fast_price != fast_price): # check NaN
                    current_price = float(fast_price)
            except Exception:
                current_price = None

            if current_price is None or current_price <= 0:
                current_price = float(hist['Close'].iloc[-1])

            # 新高値判定
            is_new_high = False
            if current_price > ath_price:
                ath_price = current_price
                ath_date_str = datetime.now().strftime('%Y-%m-%d')
                is_new_high = True

            # ドローダウン率（%）と下落額
            drop_amount = ath_price - current_price
            if drop_amount < 0:
                drop_amount = 0.0
            
            drawdown_pct = (drop_amount / ath_price) * 100.0 if ath_price > 0 else 0.0

            currency = "USD"
            try:
                currency = ticker.fast_info.get("currency", "USD") or "USD"
            except Exception:
                pass

            name = display_name if display_name else ticker_symbol

            return MarketStatus(
                ticker=ticker_symbol,
                name=name,
                current_price=round(current_price, 2),
                ath=round(ath_price, 2),
                ath_date=ath_date_str,
                drawdown_pct=round(drawdown_pct, 2),
                drop_amount=round(drop_amount, 2),
                currency=currency,
                updated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                is_new_high=is_new_high
            )

        except Exception as e:
            logger.error(f"[{ticker_symbol}] データ取得中にエラーが発生しました: {e}", exc_info=True)
            return None
