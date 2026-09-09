import datetime as dt
import json
import os
import threading
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk


REFRESH_MS = 5000
SIM_POLL_MS = 60000
TRANSPARENT_COLOR = "#ff00ff"
SIM_STATE_FILE = os.path.join(os.path.dirname(__file__), "stock_simulation_state.json")
SIM_REPORT_FILE = os.path.join(os.path.dirname(__file__), "stock_simulation_report.md")
SIM_REPORT_ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "stock_reports")
SIM_CAPITAL = 100000.0
SIM_DAYS = 30
PUSHPLUS_TOKEN = "e39674189a874c48888292f80e0c3464"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
SIM_PLANS = {
    "sh601138": {"name": "工业富联", "buy_low": 62.8, "buy_high": 64.0, "stop": 61.5, "tp1": 68.0, "tp2": 70.0},
    "sh601899": {"name": "紫金矿业", "buy_low": 32.4, "buy_high": 33.0, "stop": 31.6, "tp1": 35.0, "tp2": 35.8},
    "sh603259": {"name": "药明康德", "buy_low": 150.0, "buy_high": 153.0, "stop": 146.0, "tp1": 161.0, "tp2": 166.0},
}


def normalize_code(code: str) -> str:
    code = code.strip().lower()
    if code.startswith(("sh", "sz")):
        return code
    if code.startswith(("6", "5", "9")):
        return "sh" + code
    return "sz" + code


def fetch_quotes(codes):
    normalized = [normalize_code(code) for code in codes]
    url = "https://hq.sinajs.cn/list=" + ",".join(normalized)
    request = urllib.request.Request(
        url,
        headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        text = response.read().decode("gbk", errors="ignore")

    results = {}
    for line in text.strip().splitlines():
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        code = left.split("_")[-1]
        values = right.strip().strip(';"').split(",")
        if len(values) < 32 or not values[0]:
            continue
        try:
            previous = float(values[2])
            current = float(values[3])
            results[code] = {
                "code": code,
                "current": current,
                "change": current - previous,
                "pct": (current - previous) / previous * 100 if previous else 0,
            }
        except (ValueError, IndexError):
            continue
    return results


def push_wechat(title, content, template="html"):
    # 通过 PushPlus 推送到微信；纯标准库，失败静默（不影响主流程）
    data = urllib.parse.urlencode({
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": template,
    }).encode("utf-8")
    request = urllib.request.Request(
        PUSHPLUS_URL, data=data, method="POST",
        headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class SimulationTracker:
    def __init__(self, root):
        self.root = root
        self.state = self.load_state()
        self.poll()

    def load_state(self):
        if os.path.exists(SIM_STATE_FILE):
            try:
                with open(SIM_STATE_FILE, "r", encoding="utf-8") as file:
                    return json.load(file)
            except (OSError, ValueError):
                pass
        return {
            "start_date": None,
            "end_date": None,
            "cash": SIM_CAPITAL,
            "positions": {},
            "trades": [],
            "daily": [],
            "last_quotes": {},
        }

    def save_state(self):
        with open(SIM_STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(self.state, file, ensure_ascii=False, indent=2)

    def poll(self):
        now = dt.datetime.now()
        market_open = now.weekday() < 5 and dt.time(9, 30) <= now.time() <= dt.time(15, 0)
        if market_open and self.state["start_date"] is None:
            self.state["start_date"] = now.date().isoformat()
            self.state["end_date"] = (now.date() + dt.timedelta(days=SIM_DAYS)).isoformat()
            self.record("模拟周期开始，初始资金 {:.2f} 元".format(SIM_CAPITAL))
            self.save_state()

        active = self.state["start_date"] and now.date().isoformat() <= self.state["end_date"]
        if active and market_open:
            threading.Thread(target=self.load_and_process, daemon=True).start()
        elif self.state["start_date"]:
            self.write_report({})
        self.root.after(SIM_POLL_MS, self.poll)

    def load_and_process(self):
        try:
            quotes = fetch_quotes(list(SIM_PLANS))
        except Exception:
            return
        self.root.after(0, self.process, quotes)

    def process(self, quotes):
        if quotes:
            self.state["last_quotes"] = quotes
        else:
            quotes = self.state.get("last_quotes", {})
        today = dt.date.today().isoformat()
        day_log = next((item for item in self.state["daily"] if item["date"] == today), None)
        if day_log is None:
            day_log = {"date": today, "actions": [], "quotes": {}, "cash": self.state["cash"], "asset": self.state["cash"]}
            self.state["daily"].append(day_log)
        else:
            day_log["actions"] = [action for action in day_log.get("actions", []) if action != "无交易"]
        alerts = []
        for code, plan in SIM_PLANS.items():
            quote = quotes.get(code)
            if not quote:
                continue
            position = self.state["positions"].get(code)
            price = quote["current"]
            if position:
                if price <= plan["stop"]:
                    action = self.sell(code, price, position["shares"], "止损")
                    day_log["actions"].append(action)
                    alerts.append({"code": code, "kind": "stop", "price": price, "text": action})
                elif not position["tp1_done"] and price >= plan["tp1"]:
                    shares = position["shares"] // 2
                    if shares:
                        action = self.sell(code, price, shares, "第一止盈")
                        day_log["actions"].append(action)
                        alerts.append({"code": code, "kind": "tp1", "price": price, "text": action})
                        self.state["positions"][code]["tp1_done"] = True
                elif position["tp1_done"] and price >= plan["tp2"]:
                    action = self.sell(code, price, position["shares"], "第二止盈")
                    day_log["actions"].append(action)
                    alerts.append({"code": code, "kind": "tp2", "price": price, "text": action})
            elif plan["buy_low"] <= price <= plan["buy_high"]:
                budget = SIM_CAPITAL / len(SIM_PLANS)
                shares = int(budget // price // 100) * 100
                if shares:
                    cost = shares * price
                    self.state["cash"] -= cost
                    self.state["positions"][code] = {
                        "shares": shares,
                        "buy_price": price,
                        "buy_date": today,
                        "tp1_done": False,
                    }
                    action = "买入 {} {} 股，成交价 {:.2f} 元".format(plan["name"], shares, price)
                    self.record(action, code=code, action="buy", price=price, shares=shares,
                                value=cost, plan_version=self.state.get("start_date"))
                    day_log["actions"].append(action)
                    alerts.append({"code": code, "kind": "buy", "price": price, "text": action})
        day_log["quotes"] = quotes
        day_log["cash"] = self.state["cash"]
        day_log["asset"] = self.calculate_asset(quotes)
        self.state["last_asset"] = day_log["asset"]
        if not day_log["actions"]:
            day_log["actions"].append("无交易")
        self.save_state()
        self.write_report(quotes)
        if alerts:
            self.show_trade_popup(alerts)
            self.push_trade_alerts(alerts)

    def push_trade_alerts(self, alerts):
        # 微信推送成交提醒（HTML，附推荐计划），放后台线程避免卡界面
        kind_style = {
            "buy": ("模拟买入成交", "#16a34a"),
            "tp1": ("到达止盈1（卖出一半）", "#d97706"),
            "tp2": ("到达止盈2（清仓）", "#0d9488"),
            "stop": ("触发止损（清仓）", "#dc2626"),
        }
        # 标题一眼看出：什么股、什么操作、什么价
        title_action = {"buy": "买入", "tp1": "止盈卖半", "tp2": "止盈清仓", "stop": "止损清仓"}

        def one_line(ev):
            name = SIM_PLANS[ev["code"]]["name"]
            action = title_action.get(ev["kind"], "提醒")
            price = ev.get("price")
            return "{} {} @{:.2f}".format(name, action, price) if price else "{} {}".format(name, action)

        if len(alerts) == 1:
            push_title = "股·" + one_line(alerts[0])
        else:
            push_title = "股·{}条信号：".format(len(alerts)) + "、".join(one_line(e) for e in alerts[:3])
        parts = [
            "<div style='font-family:Microsoft YaHei,Arial;font-size:14px;line-height:1.7'>",
            "<p style='color:#888;margin:0'>{} · A股模拟跟踪</p>".format(
                dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ]
        for ev in alerts:
            plan = SIM_PLANS[ev["code"]]
            title, color = kind_style.get(ev["kind"], ("交易提醒", "#333"))
            parts.append("<hr style='border:none;border-top:1px solid #eee'>")
            parts.append("<h3 style='color:{};margin:8px 0 4px'>{} · {}</h3>".format(
                color, title, plan["name"]))
            parts.append("<p style='margin:2px 0'>{}</p>".format(ev["text"]))
            parts.append(
                "<table style='border-collapse:collapse;margin:6px 0;font-size:13px'>"
                "<tr><td style='padding:3px 14px;color:#888'>买入区间</td>"
                "<td style='padding:3px 14px'><b>{low} - {high}</b></td></tr>"
                "<tr><td style='padding:3px 14px;color:#888'>止损价</td>"
                "<td style='padding:3px 14px;color:#dc2626'><b>{stop}</b></td></tr>"
                "<tr><td style='padding:3px 14px;color:#888'>止盈1（卖一半）</td>"
                "<td style='padding:3px 14px;color:#16a34a'><b>{tp1}</b></td></tr>"
                "<tr><td style='padding:3px 14px;color:#888'>止盈2（清仓）</td>"
                "<td style='padding:3px 14px;color:#16a34a'><b>{tp2}</b></td></tr>"
                "</table>".format(
                    low=plan["buy_low"], high=plan["buy_high"],
                    stop=plan["stop"], tp1=plan["tp1"], tp2=plan["tp2"]))
        parts.append("<hr style='border:none;border-top:1px solid #eee'>")
        parts.append("<p style='margin:4px 0'>当前总资产：<b>{:.2f} 元</b></p>".format(
            self.state.get("last_asset", 0)))
        parts.append("<p style='color:#aaa;font-size:12px;margin:2px 0'>仅为程序模拟，不会真实下单，仅供研究参考</p>")
        parts.append("</div>")
        content = "".join(parts)

        def worker():
            # 微信(PushPlus)推送；失败静默，不影响主流程
            try:
                push_wechat(push_title, content)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def show_trade_popup(self, alerts):
        # 买卖成交时弹出置顶提醒，8 秒后自动关闭
        win = tk.Toplevel(self.root)
        win.title("模拟交易提醒")
        win.geometry("340x{}".format(120 + len(alerts) * 28))
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg="#111827")
        tk.Label(win, text="模拟交易成交提醒", bg="#111827", fg="#fbbf24",
                 font=("Microsoft YaHei", 13, "bold")).pack(pady=(14, 8))
        for ev in alerts:
            tk.Label(win, text=ev["text"], bg="#111827", fg="white",
                     font=("Microsoft YaHei", 11), wraplength=300, justify="left").pack(anchor="w", padx=20)
        tk.Button(win, text="知道了", width=10, command=win.destroy).pack(pady=10)
        win.after(8000, win.destroy)

    def calculate_asset(self, quotes):
        asset = self.state["cash"]
        for code, position in self.state["positions"].items():
            asset += position["shares"] * quotes.get(code, {}).get("current", position["buy_price"])
        return asset

    def sell(self, code, price, shares, reason):
        position = self.state["positions"][code]
        shares = min(shares, position["shares"])
        proceeds = shares * price
        cost = shares * position["buy_price"]
        pnl = proceeds - cost
        self.state["cash"] += proceeds
        position["shares"] -= shares
        action = "卖出 {} {} 股，成交价 {:.2f} 元，原因：{}，本笔盈亏 {:+.2f} 元".format(
            SIM_PLANS[code]["name"], shares, price, reason, pnl)
        self.record(action, code=code, action="sell", price=price, shares=shares,
                    value=proceeds, pnl=pnl, reason=reason,
                    plan_version=self.state.get("start_date"))
        if position["shares"] == 0:
            del self.state["positions"][code]
        return action

    def record(self, text, **fields):
        trade = {"date": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "text": text}
        trade.update(fields)
        self.state["trades"].append(trade)

    def period_summary(self, start, end):
        trades = []
        for trade in self.state.get("trades", []):
            if trade.get("action") != "sell":
                continue
            day = trade.get("date", "")[:10]
            if start <= day <= end:
                trades.append(trade)
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) < 0]
        profit = sum(t.get("pnl", 0) for t in wins)
        loss = sum(t.get("pnl", 0) for t in losses)
        lines = ["## 周期复盘", "", "- 统计区间：{} 至 {}".format(start, end),
                 "- 完成卖出笔数：{}".format(len(trades)),
                 "- 盈利笔数/亏损笔数：{}/{}".format(len(wins), len(losses)),
                 "- 胜率：{}".format("{:.1f}%".format(len(wins) / len(trades) * 100) if trades else "暂无样本"),
                 "- 已实现盈亏：{:+.2f} 元".format(sum(t.get("pnl", 0) for t in trades)),
                 "- 平均盈利/平均亏损：{:+.2f} / {:+.2f} 元".format(
                     profit / len(wins) if wins else 0, loss / len(losses) if losses else 0),
                 "- 盈亏比：{}".format("{:.2f}".format(profit / abs(loss)) if loss else ("暂无亏损样本" if not profit else "无亏损样本")),
                 "", "| 股票 | 代码 | 完成卖出 | 盈利 | 亏损 | 已实现盈亏 |", "|---|---:|---:|---:|---:|---:|"]
        for code, plan in SIM_PLANS.items():
            items = [t for t in trades if t.get("code") == code]
            if items:
                lines.append("| {} | {} | {} | {} | {} | {:+.2f} |".format(
                    plan["name"], code[-6:], len(items),
                    sum(t.get("pnl", 0) > 0 for t in items),
                    sum(t.get("pnl", 0) < 0 for t in items),
                    sum(t.get("pnl", 0) for t in items)))
        return lines

    def write_report(self, quotes):
        # 非交易时间或本次取行情失败时，沿用最后一次有效行情，避免估值被买入价覆盖
        if not quotes:
            quotes = self.state.get("last_quotes", {})
        start = self.state["start_date"] or "等待 9:30 启动"
        end = self.state["end_date"] or "未开始"
        market_value = self.state["cash"]
        cost_total = 0.0
        pnl_total = 0.0
        position_lines = []
        for code, position in self.state["positions"].items():
            current = quotes.get(code, {}).get("current", position["buy_price"])
            value = position["shares"] * current
            cost = position["shares"] * position["buy_price"]
            pnl = value - cost
            pnl_pct = (current - position["buy_price"]) / position["buy_price"] * 100
            cost_total += cost
            pnl_total += pnl
            market_value += value
            # 对照计划给出当前状态，方便看偏差
            plan = SIM_PLANS[code]
            plan_buy = (plan["buy_low"] + plan["buy_high"]) / 2
            if current <= plan["stop"]:
                status = "已到止损位"
            elif position["tp1_done"] and current >= plan["tp2"]:
                status = "已到止盈2"
            elif not position["tp1_done"] and current >= plan["tp1"]:
                status = "已到止盈1"
            elif current < plan["buy_low"]:
                status = "低于买入区间"
            elif current > plan["buy_high"]:
                status = "高于买入区间"
            else:
                status = "买入区间内"
            position_lines.append(
                "| {name} | {code} | {shares} | {plan_buy:.2f} | {actual_buy:.2f} "
                "| {current:.2f} | {value:.2f} | {pnl:+.2f}（{pnl_pct:+.2f}%） | {status} |".format(
                    name=plan["name"], code=code[-6:], shares=position["shares"],
                    plan_buy=plan_buy, actual_buy=position["buy_price"],
                    current=current, value=value, pnl=pnl, pnl_pct=pnl_pct, status=status))
        if position_lines:
            pnl_pct_total = pnl_total / cost_total * 100 if cost_total else 0
            position_lines.append(
                "| **持仓合计** | - | - | - | - | - | {value:.2f} | **{pnl:+.2f}（{pnl_pct:+.2f}%）** | - |".format(
                    value=market_value - self.state["cash"], pnl=pnl_total, pnl_pct=pnl_pct_total))
        profit = market_value - SIM_CAPITAL

        # 推荐计划与预期目标：固定写入，便于日后对照偏差
        plan_lines = []
        budget_each = SIM_CAPITAL / len(SIM_PLANS)
        expected_win = 0.0
        expected_loss = 0.0
        for code, plan in SIM_PLANS.items():
            buy_mid = (plan["buy_low"] + plan["buy_high"]) / 2
            shares = int(budget_each // buy_mid // 100) * 100
            # 止盈2的预期盈利：按"一半止盈1、一半止盈2"估算
            half = shares // 2
            win = half * (plan["tp1"] - buy_mid) + (shares - half) * (plan["tp2"] - buy_mid)
            loss = shares * (buy_mid - plan["stop"])
            expected_win += win
            expected_loss += loss
            plan_lines.append(
                "| {name} | {code} | {lo:.2f}-{hi:.2f} | {buy_mid:.2f} "
                "| {stop:.2f}（{stop_pct:+.1f}%）"
                " | {tp1:.2f}（{tp1_pct:+.1f}%） | {tp2:.2f}（{tp2_pct:+.1f}%）"
                " | {shares} | 盈利约 {win:+.0f} 元 / 亏损约 {loss:.0f} 元 |".format(
                    name=plan["name"], code=code[-6:],
                    lo=plan["buy_low"], hi=plan["buy_high"], buy_mid=buy_mid,
                    stop=plan["stop"], stop_pct=(plan["stop"] - buy_mid) / buy_mid * 100,
                    tp1=plan["tp1"], tp1_pct=(plan["tp1"] - buy_mid) / buy_mid * 100,
                    tp2=plan["tp2"], tp2_pct=(plan["tp2"] - buy_mid) / buy_mid * 100,
                    shares=shares, win=win, loss=-loss))

        lines = [
            "# A 股月内模拟交易报告", "",
            "> 仅为程序模拟，不会真实下单；行情来自公开接口，价格和结果仅供研究。", "",
            "- 模拟周期：{} 至 {}".format(start, end),
            "- 初始资金：{:.2f} 元".format(SIM_CAPITAL),
            "- 当前资产：{:.2f} 元".format(market_value),
            "- 浮动盈亏：{:+.2f} 元（{:+.2f}%）".format(profit, profit / SIM_CAPITAL * 100), "",
            "## 推荐计划与预期目标", "",
            "> 以下为建仓时定好的计划，固定不变；日常对照实际成交价/最新价看是否偏离。",
            "- 策略：每只股票分配约 {:.0f} 元；价格进入买入区间即按拟定买入价挂单，跌到止损位全部止损，涨到止盈1卖一半、止盈2清仓。".format(budget_each),
            "- 整体预期：三只全部到止盈约 **盈利 {:+.0f} 元**；三只全部止损约 **亏损 {:.0f} 元**。".format(
                expected_win, expected_loss), "",
            "| 股票 | 代码 | 买入区间 | 拟定买入价 | 止损价 | 止盈1 | 止盈2 | 约持股数 | 单只预期盈亏 |",
            "|---|---|---|---:|---|---|---|---:|---|",
        ]
        lines.extend(plan_lines)
        lines.extend([
            "",
            "## 当前持仓", "",
            "| 股票 | 代码 | 股数 | 计划买入价 | 实际买入价 | 最新价 | 市值 | 浮动盈亏 | 对照计划状态 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ])
        lines.extend(position_lines or ["| 无 | - | - | - | - | - | - | - | - |"])
        lines.extend(["", "## 每日操作日志", ""])
        for day in self.state["daily"]:
            lines.append("### {}".format(day["date"]))
            lines.append("- 当日现金：{:.2f} 元".format(day.get("cash", 0)))
            lines.append("- 当日总资产：{:.2f} 元".format(day.get("asset", 0)))
            actions = day.get("actions") or ["无交易"]
            for action in actions:
                lines.append("- {}".format(action))
            lines.append("")
        lines.extend(["## 交易明细", ""])
        for trade in self.state["trades"]:
            if "text" in trade:
                lines.append("- {}：{}".format(trade["date"], trade["text"]))
            else:
                lines.append("- {}：卖出 {} 股，价格 {:.2f}，原因：{}".format(trade["date"], trade["code"], trade["price"], trade["reason"]))
        report = "\n".join(lines) + "\n"
        with open(SIM_REPORT_FILE, "w", encoding="utf-8") as file:
            file.write(report)

        now = dt.datetime.now()
        periods = (
            ("daily", now.strftime("%Y-%m-%d.md"), now.date(), now.date()),
            ("weekly", now.strftime("%Y-W%W.md"), now.date() - dt.timedelta(days=now.weekday()),
             now.date() - dt.timedelta(days=now.weekday()) + dt.timedelta(days=6)),
            ("monthly", now.strftime("%Y-%m.md"), now.date().replace(day=1),
             (now.date().replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)),
        )
        for period, filename, start, end in periods:
            directory = os.path.join(SIM_REPORT_ARCHIVE_DIR, period)
            os.makedirs(directory, exist_ok=True)
            archived = list(lines) + [""] + self.period_summary(start.isoformat(), end.isoformat()) + [""]
            archived += ["## 优化纪律", "",
                         "- 先累计样本再调参：单个周期完成卖出少于 20 笔时，只记录不改核心规则。",
                         "- 优化目标同时看胜率、盈亏比、期望值和最大回撤，不能只看一笔输赢。",
                         "- 若连续样本显示买入区间过高或止损过密，下一版计划只微调买入区间、止损距离和止盈分批。"]
            with open(os.path.join(directory, filename), "w", encoding="utf-8") as file:
                file.write("\n".join(archived) + "\n")


class StockFloatWindow:
    def __init__(self, root):
        self.root = root
        self.codes = []
        self.selected_code = None
        self.request_id = 0
        self.drag_offset = (0, 0)
        self.settings_window = None
        self.price_text = None
        self.pct_text = None

        root.geometry("124x58+80+80")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.82)
        root.configure(bg=TRANSPARENT_COLOR)
        try:
            root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(root, width=124, height=58, bg=TRANSPARENT_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.oval = self.canvas.create_oval(3, 3, 121, 55, fill="#111827", outline="#374151", width=1)
        self.price_text = self.canvas.create_text(62, 22, text="--", fill="white", font=("Arial", 19, "bold"))
        self.pct_text = self.canvas.create_text(62, 42, text="--", fill="#d1d5db", font=("Arial", 10, "bold"))

        for widget in (root, self.canvas):
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag_window)
            widget.bind("<Button-3>", self.show_menu)
            widget.bind("<Double-Button-1>", self.open_settings)

        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label="设置股票", command=self.open_settings)
        self.menu.add_command(label="立即刷新", command=self.refresh)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=root.destroy)
        self.refresh()

    def start_drag(self, event):
        self.drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag_window(self, event):
        self.root.geometry(f"+{event.x_root - self.drag_offset[0]}+{event.y_root - self.drag_offset[1]}")

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def open_settings(self, event=None):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title("设置股票")
        win.geometry("300x310")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        tk.Label(win, text="股票代码", anchor="w").pack(fill="x", padx=14, pady=(14, 4))
        row = tk.Frame(win)
        row.pack(fill="x", padx=14)
        code_var = tk.StringVar()
        entry = tk.Entry(row, textvariable=code_var, font=("Arial", 11), relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True, ipady=4)

        stock_list = tk.Listbox(win, height=8, exportselection=False)
        stock_list.pack(fill="both", expand=True, padx=14, pady=10)
        for code in self.codes:
            stock_list.insert("end", code)
        if self.selected_code in self.codes:
            index = self.codes.index(self.selected_code)
            stock_list.selection_set(index)
            stock_list.see(index)

        def add_codes():
            new_codes = [normalize_code(code) for code in code_var.get().replace("，", ",").split(",") if code.strip()]
            for code in new_codes:
                if code not in self.codes:
                    self.codes.append(code)
                    stock_list.insert("end", code)
            code_var.set("")
            if new_codes:
                stock_list.selection_clear(0, "end")
                stock_list.selection_set(len(self.codes) - len(new_codes))

        ttk.Button(row, text="添加", command=add_codes).pack(side="left", padx=(6, 0))
        entry.bind("<Return>", lambda event: add_codes())

        def remove_code():
            selected = stock_list.curselection()
            if not selected:
                return
            index = selected[0]
            stock_list.delete(index)
            del self.codes[index]
            if self.codes:
                stock_list.selection_set(min(index, len(self.codes) - 1))

        buttons = tk.Frame(win)
        buttons.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(buttons, text="删除选中", command=remove_code).pack(side="left")

        def apply_and_close():
            selected = stock_list.curselection()
            self.selected_code = self.codes[selected[0]] if selected else (self.codes[0] if self.codes else None)
            win.destroy()
            self.refresh()

        ttk.Button(buttons, text="应用并关闭", command=apply_and_close).pack(side="right")
        win.lift()
        win.focus_force()
        entry.focus_force()

    def refresh(self):
        self.request_id += 1
        request_id = self.request_id
        if not self.codes or not self.selected_code:
            self.set_text("--", "--", "#d1d5db")
        else:
            threading.Thread(target=self.load_quotes, args=(request_id, list(self.codes)), daemon=True).start()
        self.root.after(REFRESH_MS, self.refresh)

    def load_quotes(self, request_id, codes):
        try:
            data = fetch_quotes(codes)
        except Exception:
            data = {}
        self.root.after(0, self.update_ui, request_id, data)

    def update_ui(self, request_id, data):
        if request_id != self.request_id or not self.selected_code:
            return
        item = data.get(self.selected_code)
        if not item:
            self.set_text("--", "--", "#d1d5db")
            return
        color = "#f87171" if item["change"] > 0 else "#4ade80" if item["change"] < 0 else "#d1d5db"
        self.set_text(f'{item["current"]:.2f}', f'{item["pct"]:+.2f}%', color)

    def set_text(self, price, pct, color):
        self.canvas.itemconfig(self.price_text, text=price, fill=color)
        self.canvas.itemconfig(self.pct_text, text=pct, fill=color)


def main():
    root = tk.Tk()
    StockFloatWindow(root)
    SimulationTracker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
