import argparse
import logging
import os
import sys
import time
from typing import Dict, Any, List
import yaml

# WindowsコンソールでのUnicodeEncodeError（絵文字など）対策
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from tracker import MarketTracker, MarketStatus
from state_manager import StateManager
from notifier import Notifier

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("Main")

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(config_path):
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        sys.exit(1)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗しました: {e}")
        sys.exit(1)

def run_check(config: Dict[str, Any], tracker: MarketTracker, state_mgr: StateManager, notifier: Notifier) -> List[MarketStatus]:
    """全監視対象の株価をチェックし、閾値に達していればアラートを発行します"""
    targets = config.get("targets", [])
    default_thresholds = config.get("default_thresholds", [15, 30, 45])
    statuses = []

    logger.info(f"銘柄チェックを開始します (対象: {len(targets)} 銘柄)...")

    for target in targets:
        ticker = target.get("ticker")
        name = target.get("name", ticker)
        thresholds = target.get("thresholds", default_thresholds)

        status = tracker.fetch_status(ticker, name)
        if not status:
            continue

        statuses.append(status)

        # アラート評価
        new_alerts = state_mgr.evaluate_alerts(
            ticker=ticker,
            current_drawdown_pct=status.drawdown_pct,
            thresholds=thresholds,
            is_new_high=status.is_new_high
        )

        # 発火したアラートごとに通知
        for t in new_alerts:
            logger.warning(f"🚨 【しきい値到達】{name} ({ticker}) が最高値から -{t}% 下落しました！ (現在: -{status.drawdown_pct:.2f}%)")
            notifier.send_alert(status, t)
            state_mgr.record_notification(ticker, status.updated_at)

    logger.info("全銘柄のチェックが完了しました。")
    return statuses

def main():
    parser = argparse.ArgumentParser(description="米国指数・株価ドローダウン（最高値からの下落率）監視アラート")
    parser.add_argument("--config", default="config.yaml", help="設定ファイルのパス (default: config.yaml)")
    parser.add_argument("--status", action="store_true", help="現在の全銘柄の株価・最高値・下落率を一覧表示します")
    parser.add_argument("--check", action="store_true", help="1回チェックを実行し、条件合致時にアラートを送信します (デフォルト動作)")
    parser.add_argument("--daemon", action="store_true", help="指定間隔で定期的にチェックを続ける常駐モードで起動します")
    parser.add_argument("--interval", type=int, default=None, help="デーモンモード時のチェック間隔（秒）。省略時はconfig.yamlの値を使用")
    parser.add_argument("--test-discord", action="store_true", help="Discord Webhookへのテスト通知を送信します")
    parser.add_argument("--reset", action="store_true", help="通知履歴（state.json）をリセットします")

    args = parser.parse_args()

    # 設定ファイルの読み込み
    config = load_config(args.config)
    options = config.get("options", {})
    history_period = options.get("history_period", "max")
    hysteresis_buffer = options.get("hysteresis_buffer", 2.0)
    default_interval = options.get("check_interval_seconds", 3600)

    # 各モジュールの初期化
    tracker = MarketTracker(history_period=history_period)
    state_mgr = StateManager(state_file_path="state.json", hysteresis_buffer=hysteresis_buffer)
    notifier = Notifier(config)

    # 1. 状態リセット
    if args.reset:
        state_mgr.reset_all()
        print("✅ 過去の通知履歴（state.json）を正常にリセットしました。")
        return

    # 2. Discordテスト送信
    if args.test_discord:
        notifier.send_test_discord()
        return

    # 3. 現在状況の一覧表示のみ
    if args.status:
        statuses = []
        for target in config.get("targets", []):
            ticker = target.get("ticker")
            name = target.get("name", ticker)
            s = tracker.fetch_status(ticker, name)
            if s:
                statuses.append(s)
        notifier.display_status_table(statuses, config.get("targets", []))
        return

    # 4. デーモン（常駐監視）モード
    if args.daemon:
        interval = args.interval or default_interval
        logger.info(f"常駐監視モードを開始しました。監視間隔: {interval} 秒 ({interval / 60:.1f} 分)")
        try:
            while True:
                run_check(config, tracker, state_mgr, notifier)
                logger.info(f"次回チェックまで {interval} 秒待機します...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("ユーザーによって監視が停止されました。")
        return

    # 5. デフォルト: 1回チェック実行
    statuses = run_check(config, tracker, state_mgr, notifier)
    # コンソールが有効ならテーブルも表示
    if config.get("notifications", {}).get("console", {}).get("enabled", True):
        notifier.display_status_table(statuses, config.get("targets", []))

if __name__ == "__main__":
    main()
