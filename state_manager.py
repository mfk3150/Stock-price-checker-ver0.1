import json
import os
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class StateManager:
    """
    銘柄ごとのアラート通知状態（すでに通知した下落率しきい値やATH記録）を永続化・管理します。
    """
    def __init__(self, state_file_path: str = "state.json", hysteresis_buffer: float = 2.0):
        self.state_file_path = state_file_path
        self.hysteresis_buffer = hysteresis_buffer
        self.state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"状態ファイル({self.state_file_path})の読み込みに失敗しました。新規作成します: {e}")
        return {}

    def save(self):
        try:
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"状態ファイルの保存に失敗しました: {e}")

    def get_ticker_state(self, ticker: str) -> Dict[str, Any]:
        if ticker not in self.state:
            self.state[ticker] = {
                "triggered_thresholds": [],
                "last_notified_at": None,
                "recorded_ath": None,
                "last_drawdown_pct": None,
            }
        return self.state[ticker]

    def evaluate_alerts(self, ticker: str, current_drawdown_pct: float, thresholds: List[float], is_new_high: bool = False) -> List[float]:
        """
        現在の下落率と通知済みリストを比較し、新たに発火すべきしきい値のリストを返します。
        また、株価回復（ヒステリシス考慮）や新高値更新に伴うリセットも処理します。
        """
        ticker_state = self.get_ticker_state(ticker)
        triggered: List[float] = ticker_state.get("triggered_thresholds", [])
        new_alerts: List[float] = []

        # 昇順ソート
        sorted_thresholds = sorted(thresholds)

        # 新高値更新時はすべてのトリガーをリセット
        if is_new_high:
            if triggered:
                logger.info(f"[{ticker}] 史上最高値を更新したため、通知済みトリガーをリセットします。")
                ticker_state["triggered_thresholds"] = []
                self.save()
            return []

        # 1. 回復判定（ヒステリシス付きリセット）
        # 例: 閾値が15%で、hysteresis_bufferが2.0の場合、下落率が 13.0% 未満に回復したら15%のトリガーを解除
        still_triggered = []
        for t in triggered:
            recovery_level = t - self.hysteresis_buffer
            if current_drawdown_pct < recovery_level:
                logger.info(f"[{ticker}] 株価が回復したため、下落率 {t}% のアラートトリガーを解除しました。(現在下落率: {current_drawdown_pct:.2f}%)")
            else:
                still_triggered.append(t)
        ticker_state["triggered_thresholds"] = still_triggered

        # 2. 新規アラート判定
        # 到達している閾値のうち、未通知のものを抽出
        for t in sorted_thresholds:
            if current_drawdown_pct >= t:
                if t not in ticker_state["triggered_thresholds"]:
                    new_alerts.append(t)
                    ticker_state["triggered_thresholds"].append(t)

        ticker_state["last_drawdown_pct"] = current_drawdown_pct
        self.save()

        return new_alerts

    def record_notification(self, ticker: str, timestamp_str: str):
        ticker_state = self.get_ticker_state(ticker)
        ticker_state["last_notified_at"] = timestamp_str
        self.save()

    def reset_all(self):
        """全銘柄の状態を初期化"""
        self.state = {}
        self.save()
        logger.info("状態ファイルを初期化しました。")
