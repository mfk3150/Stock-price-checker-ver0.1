import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
import requests
from tabulate import tabulate
from tracker import MarketStatus

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.notifications_cfg = config.get("notifications", {})
        self.console_enabled = self.notifications_cfg.get("console", {}).get("enabled", True)
        self.discord_cfg = self.notifications_cfg.get("discord", {})
        self.discord_enabled = self.discord_cfg.get("enabled", False) or bool(os.environ.get("DISCORD_WEBHOOK_URL"))
        self.email_cfg = self.notifications_cfg.get("email", {})

    def send_alert(self, status: MarketStatus, threshold: float):
        """下落率アラートを各有効なチャネルに送信します"""
        message_title = f"🚨 【下落アラート】{status.name} が最高値から -{threshold}% 下落"
        
        # 1. コンソール出力
        if self.console_enabled:
            print("\n" + "="*60)
            print(f"🚨 {message_title}")
            print(f"・ティッカー: {status.ticker}")
            print(f"・現在価格: ${status.current_price:,.2f} {status.currency}")
            print(f"・史上最高値: ${status.ath:,.2f} {status.currency} ({status.ath_date})")
            print(f"・現在の下落率: -{status.drawdown_pct:.2f}% (下落幅: -${status.drop_amount:,.2f})")
            print(f"・確認時刻: {status.updated_at}")
            print("="*60 + "\n")

        # 2. Discord通知
        if self.discord_enabled:
            self._send_discord_alert(status, threshold)

        # 3. メール通知
        if self.email_cfg.get("enabled", False):
            self._send_email_alert(status, threshold)

    def _get_color_for_threshold(self, threshold: float) -> int:
        """下落率に応じたEmbedカラーコード（10進数RGB）"""
        if threshold < 20:
            return 15844367  # 黄色 (#F1C40F) - 調整局面
        elif threshold < 30:
            return 15105570  # オレンジ (#E67E22) - 本格的な下落
        elif threshold < 45:
            return 15158332  # 赤 (#E74C3C) - 暴落水準 (大チャンス)
        else:
            return 10181046  # 紫 (#9B59B6) - 歴史的暴落水準

    def _send_discord_alert(self, status: MarketStatus, threshold: float):
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or self.discord_cfg.get("webhook_url")
        if not webhook_url or "YOUR_WEBHOOK_URL" in webhook_url:
            logger.warning("[Discord] 有効なWebhook URLが設定されていません。")
            return

        mention = self.discord_cfg.get("mention", "")
        content = f"{mention} 📉 **{status.name} が最高値から -{threshold}% を突破しました！**" if mention else ""

        color = self._get_color_for_threshold(threshold)

        embed = {
            "title": f"🚨 {status.name} ({status.ticker}) 下落アラート",
            "description": f"史上最高値からの下落率が **-{threshold:.1f}%** のラインに到達しました。\nスポット買い増し・押し目買いのルール確認タイミングです。",
            "color": color,
            "fields": [
                {
                    "name": "📊 現在の下落率",
                    "value": f"**`-{status.drawdown_pct:.2f}%`**",
                    "inline": True
                },
                {
                    "name": "💵 現在株価",
                    "value": f"`${status.current_price:,.2f} {status.currency}`",
                    "inline": True
                },
                {
                    "name": "📉 下落幅",
                    "value": f"`-${status.drop_amount:,.2f}`",
                    "inline": True
                },
                {
                    "name": "🏔️ 史上最高値 (ATH)",
                    "value": f"`${status.ath:,.2f}` ({status.ath_date})",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"取得時刻: {status.updated_at} | Drawdown Monitor"
            }
        }

        payload = {
            "content": content,
            "embeds": [embed]
        }

        try:
            res = requests.post(webhook_url, json=payload, timeout=10)
            if res.status_code in [200, 204]:
                logger.info(f"[Discord] アラート送信に成功しました: {status.ticker} (-{threshold}%)")
            else:
                logger.error(f"[Discord] 送信エラー (Status {res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"[Discord] 送信中に例外が発生しました: {e}")

    def _send_email_alert(self, status: MarketStatus, threshold: float):
        smtp_server = self.email_cfg.get("smtp_server")
        smtp_port = self.email_cfg.get("smtp_port", 587)
        sender_email = self.email_cfg.get("sender_email")
        sender_password = self.email_cfg.get("sender_password")
        receiver_email = self.email_cfg.get("receiver_email")

        if not all([smtp_server, sender_email, sender_password, receiver_email]):
            logger.warning("[Email] メール設定が不完全です。送信をスキップします。")
            return

        subject = f"【下落アラート】{status.name} が最高値から -{threshold}% 下落しました"
        body = f"""
ドローダウン監視システムからの通知です。

{status.name} ({status.ticker}) の株価が史上最高値から -{threshold}% の水準に達しました。

■ 詳細データ
・ティッカー: {status.ticker}
・現在価格: ${status.current_price:,.2f} {status.currency}
・史上最高値: ${status.ath:,.2f} ({status.ath_date})
・現在の下落率: -{status.drawdown_pct:.2f}%
・最高値からの下落幅: -${status.drop_amount:,.2f}
・確認時刻: {status.updated_at}

暴落時・押し目買いのルールに従って取引をご検討ください。
--------------------------------------------------
Drawdown Alert System
"""
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
            logger.info(f"[Email] メール送信に成功しました: {receiver_email}")
        except Exception as e:
            logger.error(f"[Email] メール送信中にエラーが発生しました: {e}")

    def send_test_discord(self) -> bool:
        """Discord Webhookの設定確認用テスト送信"""
        webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or self.discord_cfg.get("webhook_url")
        if not webhook_url or "YOUR_WEBHOOK_URL" in webhook_url:
            print("❌ config.yaml または環境変数 DISCORD_WEBHOOK_URL に Discord Webhook URL が入力されていません。")
            return False

        payload = {
            "embeds": [{
                "title": "✅ テスト通知成功！",
                "description": "株価ドローダウン監視ツールのDiscord通知連携が正常に動作しています。\n最高値から設定した割合（15%、30%など）下落すると、ここにアラートが自動で届きます。",
                "color": 3066993,  # 緑
                "fields": [
                    {"name": "ステータス", "value": "稼働準備完了", "inline": True},
                    {"name": "対象指数例", "value": "オルカン, Nasdaq100, FANG+, S&P500", "inline": True}
                ]
            }]
        }
        try:
            res = requests.post(webhook_url, json=payload, timeout=10)
            if res.status_code in [200, 204]:
                print("🎉 Discordへのテスト通知が成功しました！チャンネルをご確認ください。")
                return True
            else:
                print(f"❌ 送信エラー: HTTP {res.status_code} - {res.text}")
                return False
        except Exception as e:
            print(f"❌ 通信エラー: {e}")
            return False

    def display_status_table(self, statuses: List[MarketStatus], targets_config: List[Dict[str, Any]]):
        """全銘柄の現在の状況をきれいな表でターミナルに出力"""
        table_data = []
        for s in statuses:
            cfg = next((t for t in targets_config if t.get("ticker") == s.ticker), {})
            thresholds = cfg.get("thresholds", self.config.get("default_thresholds", []))
            th_str = ", ".join([f"{t}%" for t in sorted(thresholds)])

            table_data.append([
                s.name,
                s.ticker,
                f"${s.current_price:,.2f}",
                f"${s.ath:,.2f}",
                s.ath_date,
                f"-{s.drawdown_pct:.2f}%",
                f"-${s.drop_amount:,.2f}",
                th_str
            ])

        headers = ["銘柄名", "ティッカー", "現在価格", "史上最高値(ATH)", "最高値日", "下落率", "下落幅", "監視しきい値"]
        print("\n" + "="*90)
        print("📈 【現在の最高値とドローダウン（下落率）一覧】")
        print("="*90)
        print(tabulate(table_data, headers=headers, tablefmt="github"))
        print(f"最終取得日時: {statuses[0].updated_at if statuses else '-'}")
        print("="*90 + "\n")
