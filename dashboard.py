import os
import sys
import webbrowser
from datetime import datetime
import yaml

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from tracker import MarketTracker, MarketStatus

def generate_dashboard_html(statuses, config) -> str:
    cards_html = ""
    for s in statuses:
        dd = s.drawdown_pct
        if dd < 10.0:
            badge_color = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
            bar_color = "bg-emerald-500"
            status_text = "健全な推移（小幅な調整）"
        elif dd < 20.0:
            badge_color = "bg-amber-500/20 text-amber-400 border-amber-500/30"
            bar_color = "bg-amber-500"
            status_text = "10%台の調整局面（第1買い増し圏）"
        elif dd < 30.0:
            badge_color = "bg-orange-500/20 text-orange-400 border-orange-500/30"
            bar_color = "bg-orange-500"
            status_text = "20%台の本格下落（第2買い増し水準）"
        else:
            badge_color = "bg-rose-500/20 text-rose-400 border-rose-500/30"
            bar_color = "bg-rose-500"
            status_text = "30%超の歴史的大暴落（全力買い場）"

        levels = [15.0, 30.0, 45.0]
        next_lvl = next((lvl for lvl in levels if lvl > dd), None)
        if next_lvl:
            rem_pct = next_lvl - dd
            target_price = s.ath * (1.0 - next_lvl / 100.0)
            next_hint = f"🎯 次の <strong>-{next_lvl:.0f}%</strong> ラインまで あと <strong>-{rem_pct:.2f}%</strong> (${target_price:,.2f})"
        else:
            next_hint = "🔥 <strong>-45%</strong> 以上の歴史的暴落ライン到達中！"

        meter_width = min(100.0, (dd / 50.0) * 100.0)

        card = f"""
        <div class="bg-slate-900/90 backdrop-blur border border-slate-800 rounded-2xl p-5 shadow-lg">
          <div class="flex items-start justify-between mb-3">
            <div>
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">{s.ticker}</span>
                <span class="text-[11px] px-2 py-0.5 rounded-full border {badge_color} font-medium">{status_text}</span>
              </div>
              <h2 class="text-lg font-bold text-white tracking-tight">{s.name}</h2>
            </div>
            <div class="text-right">
              <div class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight font-mono">
                <span class="{badge_color.split()[1]}">-{s.drawdown_pct:.2f}%</span>
              </div>
              <div class="text-[10px] text-slate-400">最高値からの下落率</div>
            </div>
          </div>

          <!-- プログレスバー -->
          <div class="space-y-1 my-3">
            <div class="flex justify-between text-[11px] font-mono text-slate-400">
              <span>0% (ATH)</span>
              <span class="text-amber-400/80">15%</span>
              <span class="text-orange-400/80">30%</span>
              <span class="text-rose-400/80">45%+</span>
            </div>
            <div class="w-full bg-slate-950 rounded-full h-3 p-0.5 overflow-hidden flex relative border border-slate-800">
              <div class="absolute left-[30%] top-0 bottom-0 w-0.5 bg-slate-700 z-10"></div>
              <div class="absolute left-[60%] top-0 bottom-0 w-0.5 bg-slate-700 z-10"></div>
              <div class="absolute left-[90%] top-0 bottom-0 w-0.5 bg-slate-700 z-10"></div>
              <div class="{bar_color} h-full rounded-full transition-all duration-500" style="width: {meter_width}%"></div>
            </div>
          </div>

          <!-- 詳細データグリッド -->
          <div class="grid grid-cols-3 gap-2 pt-3 border-t border-slate-800/80 text-xs">
            <div class="bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
              <span class="text-slate-400 block text-[10px] mb-0.5">現在株価</span>
              <span class="font-bold text-white text-sm font-mono">${s.current_price:,.2f}</span>
            </div>
            <div class="bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
              <span class="text-slate-400 block text-[10px] mb-0.5">史上最高値 (ATH)</span>
              <span class="font-bold text-slate-200 text-sm font-mono">${s.ath:,.2f}</span>
            </div>
            <div class="bg-slate-950/60 p-2.5 rounded-xl border border-slate-850">
              <span class="text-slate-400 block text-[10px] mb-0.5">下落幅 (ドル)</span>
              <span class="font-bold text-rose-400 text-sm font-mono">-${s.drop_amount:,.2f}</span>
            </div>
          </div>

          <div class="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-300">
            <div>{next_hint}</div>
          </div>
        </div>
        """
        cards_html += card

    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="ja" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="ドローダウン監視">
  <meta name="theme-color" content="#020617">
  <title>株価ドローダウン監視ダッシュボード</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      -webkit-tap-highlight-color: transparent;
    }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-4 px-3 sm:py-8 sm:px-6">
  <div class="max-w-3xl mx-auto space-y-4 sm:space-y-6">

    <!-- ヘッダー -->
    <header class="flex items-center justify-between pb-4 border-b border-slate-800">
      <div>
        <div class="flex items-center gap-1.5">
          <span class="text-xl">📉</span>
          <h1 class="text-xl sm:text-2xl font-black tracking-tight text-white">株価ドローダウン監視</h1>
        </div>
        <p class="text-[11px] sm:text-xs text-slate-400 mt-0.5">最高値からの下落率（ドル建て）</p>
      </div>
      <div class="flex items-center gap-2">
        <div class="text-right text-[10px] sm:text-xs text-slate-400">
          <div>データ取得</div>
          <div class="font-mono text-slate-200 font-semibold">{now_str}</div>
        </div>
        <button onclick="location.reload()" class="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs py-1.5 px-3 rounded-lg shadow active:scale-95 transition flex items-center gap-1">
          <span>🔄</span> 更新
        </button>
      </div>
    </header>

    <!-- クイックサマリーカード -->
    <div class="grid grid-cols-1 gap-3.5 sm:gap-4">
      {cards_html}
    </div>

    <!-- 投資ルールリファレンス -->
    <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 text-xs text-slate-400 space-y-2">
      <div class="font-bold text-slate-300 flex items-center gap-1.5">
        <span>💡</span> 暴落時・押し目買いルールの目安
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 text-[11px]">
        <div class="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800/80">
          <span class="text-amber-400 font-bold block mb-0.5">-15% 下落</span>
          通常の調整局面。1回目のスポット買い増し検討圏。
        </div>
        <div class="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800/80">
          <span class="text-orange-400 font-bold block mb-0.5">-30% 下落</span>
          本格的なベア相場。第2弾の買い増し水準。
        </div>
        <div class="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800/80">
          <span class="text-rose-400 font-bold block mb-0.5">-45%以上</span>
          歴史的暴落水準。全力買い増し好機。
        </div>
      </div>
    </div>

    <footer class="text-center text-[10px] text-slate-500 pt-2 pb-6">
      株価ドローダウン監視システム | データ元: Yahoo Finance
    </footer>

  </div>
</body>
</html>
"""
    return html

def fetch_and_generate(open_browser=True):
    config_path = "config.yaml"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        config = {"targets": []}

    tracker = MarketTracker(history_period=config.get("options", {}).get("history_period", "max"))
    targets = config.get("targets", [])

    print("📊 最新株価および最高値データを取得しています...")
    statuses = []
    for target in targets:
        ticker = target.get("ticker")
        name = target.get("name", ticker)
        s = tracker.fetch_status(ticker, name)
        if s:
            statuses.append(s)

    html_content = generate_dashboard_html(statuses, config)
    
    # dashboard.html と index.html (GitHub Pages用) の両方を出力
    for filename in ["dashboard.html", "index.html"]:
        html_path = os.path.abspath(filename)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    print(f"✅ ダッシュボードを生成しました (dashboard.html / index.html)")
    if open_browser:
        print("🌐 ブラウザで表示します...")
        webbrowser.open(f"file://{os.path.abspath('dashboard.html')}")

if __name__ == "__main__":
    fetch_and_generate(open_browser=True)
