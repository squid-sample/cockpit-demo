# -*- coding: utf-8 -*-
# 加密货币（币安USDT现货）短线模拟跟踪 + 微信推送
# 7x24 小时轮询；纯标准库，无第三方依赖
import datetime as dt
import json
import os
import threading
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "crypto_simulation_state.json")
REPORT_FILE = os.path.join(BASE_DIR, "crypto_simulation_report.md")
POLL_SECONDS = 120
SIM_CAPITAL = 100000.0  # 模拟资金 10 万 USDT
PUSHPLUS_TOKEN = "e39674189a874c48888292f80e0c3464"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
BINANCE = "https://data-api.binance.vision"

# 推荐计划（2026-09-07 数据制定，半个月维度，分批建仓）
# tranches：三批买点，价格跌到对应点位买入对应仓位（占该币预算比例）
# 短周期前重后轻：第一批 50% 保证浅回调也能吃到主升浪，后两批是加仓福利
PLAN_VALID_DAYS = 10  # 计划有效期：10 天未触发任何一批建仓则到期提醒并暂停
PLANS = {
    "LINKUSDT": {"name": "LINK（Chainlink）",
                 "tranches": [{"price": 12.70, "pct": 0.50},
                              {"price": 12.40, "pct": 0.30},
                              {"price": 12.10, "pct": 0.20}],
                 "stop": 11.70, "tp1": 14.20, "tp2": 15.00,
                 "logic": "预言机龙头，放量突破后回踩，首批重仓"},
    "NEARUSDT": {"name": "NEAR",
                 "tranches": [{"price": 2.22, "pct": 0.50},
                              {"price": 2.15, "pct": 0.30},
                              {"price": 2.08, "pct": 0.20}],
                 "stop": 2.02, "tp1": 2.55, "tp2": 2.75,
                 "logic": "L1公链动量最强，首批重仓防踏空"},
    "TIAUSDT": {"name": "TIA（Celestia）",
                "tranches": [{"price": 0.420, "pct": 0.50},
                             {"price": 0.400, "pct": 0.30},
                             {"price": 0.385, "pct": 0.20}],
                "stop": 0.372, "tp1": 0.480, "tp2": 0.520,
                "logic": "模块化区块链，波动大，买点拉开间距"},
    "SOLUSDT": {"name": "SOL",
                "tranches": [{"price": 102.0, "pct": 0.50},
                             {"price": 99.5, "pct": 0.30},
                             {"price": 97.0, "pct": 0.20}],
                "stop": 94.5, "tp1": 112.0, "tp2": 117.0,
                "logic": "主流L1，稳健底仓，浅回踩分批"},
}


def plan_buy_low(plan):
    return plan["tranches"][-1]["price"]


def plan_buy_high(plan):
    return plan["tranches"][0]["price"]


def fetch_ticker(symbol):
    url = "{}/api/v3/ticker/24hr?symbol={}".format(BINANCE, symbol)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        d = json.loads(resp.read().decode("utf-8"))
    return {"price": float(d["lastPrice"]),
            "pct24": float(d["priceChangePercent"]),
            "high24": float(d["highPrice"]),
            "low24": float(d["lowPrice"])}


def push_wechat(title, content, template="html"):
    data = urllib.parse.urlencode({
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": template,
    }).encode("utf-8")
    req = urllib.request.Request(PUSHPLUS_URL, data=data, method="POST",
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def push_async(title, content):
    # 微信(PushPlus)推送；失败静默，不影响主流程
    def worker():
        try:
            push_wechat(title, content)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()


class CryptoTracker:
    def __init__(self):
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                state.setdefault("plan_expired", {})
                state.setdefault("positions", {})
                state.setdefault("trades", [])
                state.setdefault("last_quotes", {})
                return state
            except (OSError, ValueError):
                pass
        return {
            "start_date": dt.date.today().isoformat(),
            "cash": SIM_CAPITAL,
            "positions": {},
            "plan_expired": {},
            "trades": [],
            "last_quotes": {},
        }

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def record_trade(self, text):
        self.state["trades"].append({
            "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "text": text})

    def run_once(self):
        quotes = {}
        for symbol in PLANS:
            try:
                quotes[symbol] = fetch_ticker(symbol)
            except Exception:
                continue
        if quotes:
            self.state["last_quotes"] = quotes
        else:
            quotes = self.state.get("last_quotes", {})

        events = []
        budget_each = SIM_CAPITAL / len(PLANS)
        for symbol, plan in PLANS.items():
            q = quotes.get(symbol)
            if not q:
                continue
            price = q["price"]
            pos = self.state["positions"].get(symbol)

            if pos:
                # 持仓中：止损价之上才允许补仓（破位时不补，直接走止损）
                for i, tr in enumerate(plan["tranches"]):
                    if not pos["tranches_done"][i] and plan["stop"] < price <= tr["price"]:
                        msg = self.buy_tranche(symbol, price, i, tr, budget_each)
                        if msg:
                            events.append({"symbol": symbol, "kind": "buy", "msg": msg})
                # 注意：补仓后 pos 引用仍有效；止损止盈判断用最新持仓
                pos = self.state["positions"].get(symbol)
                if pos:
                    # 止盈1后止损上移到综合成本价（最坏不亏）
                    avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
                    stop_price = max(plan["stop"], avg) if pos["tp1_done"] else plan["stop"]
                    if price <= stop_price:
                        reason = "触发止损（{}），清仓".format(
                            "已上移到成本价" if pos["tp1_done"] else "破止损位")
                        msg = self.close(symbol, price, pos["amount"], reason)
                        events.append({"symbol": symbol, "kind": "stop", "msg": msg})
                    elif not pos["tp1_done"] and price >= plan["tp1"]:
                        half = pos["amount"] / 2
                        msg = self.sell(symbol, price, half, "到达止盈1，卖出一半，止损上移成本价")
                        events.append({"symbol": symbol, "kind": "tp1", "msg": msg})
                        self.state["positions"][symbol]["tp1_done"] = True
                    elif pos["tp1_done"] and price >= plan["tp2"]:
                        msg = self.close(symbol, price, pos["amount"], "到达止盈2，清仓")
                        events.append({"symbol": symbol, "kind": "tp2", "msg": msg})
            elif self.state["plan_expired"].get(symbol):
                # 计划已到期暂停，不再建仓
                pass
            else:
                # 空仓
                days = (dt.date.today() - dt.date.fromisoformat(self.state["start_date"])).days
                if days >= PLAN_VALID_DAYS:
                    # 计划超时未建仓：到期提醒并暂停
                    self.state["plan_expired"][symbol] = True
                    events.append({
                        "symbol": symbol, "kind": "expire",
                        "msg": "建仓计划 {} 天未触发任何买点，已暂停自动建仓，建议重新评估行情后更新计划".format(days)})
                elif price <= plan["stop"]:
                    # 还没建仓就跌破止损位：形态失效，计划作废不再买入
                    self.state["plan_expired"][symbol] = True
                    events.append({
                        "symbol": symbol, "kind": "expire",
                        "msg": "价格 {:.4f} 已跌破止损位 {}，建仓形态失效，计划作废不再买入".format(
                            price, plan["stop"])})
                else:
                    # 计划有效期内，按分批买点逐批建仓（价格跌破哪个点位就买对应批次）
                    for i, tr in enumerate(plan["tranches"]):
                        if price <= tr["price"]:
                            msg = self.buy_tranche(symbol, price, i, tr, budget_each)
                            if msg:
                                events.append({"symbol": symbol, "kind": "buy", "msg": msg})

        self.save_state()
        self.write_report(quotes)
        if events:
            content = self.build_push_html(events, quotes)
            push_async(self.build_push_title(events, quotes), content)
            print("[{}] 推送 {} 条预警".format(
                dt.datetime.now().strftime("%m-%d %H:%M"), len(events)))

    TITLE_ACTION = {
        "buy": "建仓",
        "tp1": "止盈卖半",
        "tp2": "止盈清仓",
        "stop": "止损清仓",
        "expire": "计划到期",
    }

    def build_push_title(self, events, quotes):
        # 标题一眼看出：什么币、什么操作、什么价
        def coin(symbol):
            return symbol.replace("USDT", "")

        def one_line(ev):
            name = coin(ev["symbol"])
            action = self.TITLE_ACTION.get(ev["kind"], "提醒")
            price = quotes.get(ev["symbol"], {}).get("price")
            if ev["kind"] == "expire" or price is None:
                return "{} {}".format(name, action)
            return "{} {} @{:g}".format(name, action, price)

        if len(events) == 1:
            return "币·" + one_line(events[0])
        # 同一币同一动作（如连续两批建仓）标题去重
        lines = []
        for e in events:
            line = one_line(e)
            if line not in lines:
                lines.append(line)
        return "币·{}条信号：".format(len(events)) + "、".join(lines[:3])

    def buy_tranche(self, symbol, price, index, tranche, budget_each):
        # 买入第 index+1 批仓位；预算不足返回 None
        spend = budget_each * tranche["pct"]
        if self.state["cash"] < spend:
            return None
        amount = spend / price
        pos = self.state["positions"].setdefault(symbol, {
            "amount": 0.0, "cost": 0.0,
            "tranches_done": [False] * len(PLANS[symbol]["tranches"]),
            "buy_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tp1_done": False})
        self.state["cash"] -= spend
        pos["amount"] += amount
        pos["cost"] += spend
        pos["tranches_done"][index] = True
        done = sum(pos["tranches_done"])
        total = len(pos["tranches_done"])
        msg = "第{idx}批建仓 {pct:.0f}%：买入 {amount:.2f} 枚 @{price:.4f}，金额 {spend:.0f} USDT（已建仓 {done}/{total} 批，均价 {avg:.4f}）".format(
            idx=index + 1, pct=tranche["pct"] * 100, amount=amount, price=price,
            spend=spend, done=done, total=total, avg=pos["cost"] / pos["amount"])
        self.record_trade(msg)
        return msg

    KIND_STYLE = {
        "buy": ("分批建仓成交", "#16a34a"),
        "tp1": ("到达止盈1（卖出一半，止损上移成本）", "#d97706"),
        "tp2": ("到达止盈2（清仓）", "#0d9488"),
        "stop": ("触发止损（清仓）", "#dc2626"),
        "expire": ("计划到期未建仓", "#6b7280"),
    }

    def build_push_html(self, events, quotes):
        total = self.total_asset(quotes)
        parts = [
            "<div style='font-family:Microsoft YaHei,Arial;font-size:14px;line-height:1.7'>",
            "<p style='color:#888;margin:0'>{} · 加密货币模拟跟踪</p>".format(
                dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ]
        for ev in events:
            plan = PLANS[ev["symbol"]]
            title, color = self.KIND_STYLE[ev["kind"]]
            price = quotes.get(ev["symbol"], {}).get("price")
            parts.append("<hr style='border:none;border-top:1px solid #eee'>")
            parts.append("<h3 style='color:{};margin:8px 0 4px'>{} · {}</h3>".format(
                color, title, plan["name"]))
            if price:
                parts.append("<p style='margin:2px 0'>当前价格：<b>{:.4f} USDT</b>（24h {:+.2f}%）</p>".format(
                    price, quotes[ev["symbol"]]["pct24"]))
            parts.append("<p style='margin:2px 0'>{}</p>".format(ev["msg"]))
            budget_each = SIM_CAPITAL / len(PLANS)
            rows = []
            cn = ["第一批", "第二批", "第三批"]
            for i, tr in enumerate(plan["tranches"]):
                rows.append(
                    "<tr><td style='padding:3px 14px;color:#888'>{name}（{pct:.0f}%仓位）</td>"
                    "<td style='padding:3px 14px'><b>{price}</b> 买入，约 {money:.0f} U</td></tr>".format(
                        name=cn[i] if i < len(cn) else "第{}批".format(i + 1),
                        pct=tr["pct"] * 100, price=tr["price"], money=budget_each * tr["pct"]))
            parts.append(
                "<table style='border-collapse:collapse;margin:6px 0;font-size:13px'>"
                + "".join(rows) +
                "<tr><td style='padding:3px 14px;color:#888'>止损价（清仓）</td>"
                "<td style='padding:3px 14px;color:#dc2626'><b>{stop}</b></td></tr>"
                "<tr><td style='padding:3px 14px;color:#888'>止盈1（卖一半）</td>"
                "<td style='padding:3px 14px;color:#16a34a'><b>{tp1}</b></td></tr>"
                "<tr><td style='padding:3px 14px;color:#888'>止盈2（清仓）</td>"
                "<td style='padding:3px 14px;color:#16a34a'><b>{tp2}</b></td></tr>"
                "</table>".format(stop=plan["stop"], tp1=plan["tp1"], tp2=plan["tp2"]))
        parts.append("<hr style='border:none;border-top:1px solid #eee'>")
        parts.append("<p style='margin:4px 0'>账户总资产：<b>{:.2f} USDT</b>（浮动盈亏 {:+.2f}）</p>".format(
            total, total - SIM_CAPITAL))
        parts.append("<p style='color:#aaa;font-size:12px;margin:2px 0'>仅为程序模拟，不会真实下单，仅供研究参考</p>")
        parts.append("</div>")
        return "".join(parts)

    def sell(self, symbol, price, amount, reason):
        pos = self.state["positions"][symbol]
        amount = min(amount, pos["amount"])
        avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
        proceeds = amount * price
        cost_part = amount * avg
        self.state["cash"] += proceeds
        pos["amount"] -= amount
        pos["cost"] -= cost_part
        pnl = proceeds - cost_part
        msg = "{} {}，卖出 {:.2f} 枚 @{:.4f}，本批盈亏 {:+.2f} USDT".format(
            reason, PLANS[symbol]["name"], amount, price, pnl)
        self.record_trade(msg)
        if pos["amount"] < 1e-8:
            del self.state["positions"][symbol]
        return "【模拟成交】" + msg

    def close(self, symbol, price, amount, reason):
        return self.sell(symbol, price, amount, reason)

    def total_asset(self, quotes):
        asset = self.state["cash"]
        for symbol, pos in self.state["positions"].items():
            avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
            price = quotes.get(symbol, {}).get("price", avg)
            asset += pos["amount"] * price
        return asset

    def write_report(self, quotes):
        lines = [
            "# 加密货币短线模拟跟踪报告（半个月维度）",
            "",
            "> 仅为程序模拟，不会真实下单；行情来自币安公开接口，7x24 小时轮询，仅供研究。",
            "",
            "- 开始日期：{}（计划有效期 {} 天，到期未建仓自动暂停）".format(
                self.state["start_date"], PLAN_VALID_DAYS),
            "- 模拟资金：{:.0f} USDT（每币分配约 {:.0f}）".format(SIM_CAPITAL, SIM_CAPITAL / len(PLANS)),
            "- 当前总资产：{:.2f} USDT".format(self.total_asset(quotes)),
            "- 浮动盈亏：{:+.2f} USDT（{:+.2f}%）".format(
                self.total_asset(quotes) - SIM_CAPITAL,
                (self.total_asset(quotes) - SIM_CAPITAL) / SIM_CAPITAL * 100),
            "",
            "## 推荐计划（2026-09-07 制定，分批建仓 50%/30%/20%）",
            "",
            "| 币种 | 第一批50% | 第二批30% | 第三批20% | 止损 | 止盈1 | 止盈2 | 逻辑 |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for symbol, p in PLANS.items():
            tr = p["tranches"]
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
                p["name"], tr[0]["price"], tr[1]["price"], tr[2]["price"],
                p["stop"], p["tp1"], p["tp2"], p["logic"]))

        lines += ["", "## 实时行情与状态", "",
                  "| 币种 | 最新价 | 24h涨跌 | 状态 |",
                  "|---|---:|---:|---|"]
        for symbol, p in PLANS.items():
            q = quotes.get(symbol)
            if not q:
                lines.append("| {} | - | - | 无行情 |".format(p["name"]))
                continue
            price = q["price"]
            pos = self.state["positions"].get(symbol)
            if pos:
                done = sum(pos["tranches_done"])
                status = "持仓中（已建仓 {}/{} 批）".format(done, len(pos["tranches_done"]))
            elif self.state["plan_expired"].get(symbol):
                status = "⚠️ 计划已暂停（到期未建仓或破位作废）"
            elif price <= p["stop"]:
                status = "已破止损位（计划作废）"
            elif price <= plan_buy_low(p):
                status = "**第三批买点内**"
            elif price <= plan_buy_high(p):
                status = "**建仓区间内（等分批触发）**"
            else:
                status = "高于第一批买点（等回踩）"
            lines.append("| {} | {:.4f} | {:+.2f}% | {} |".format(
                p["name"], price, q["pct24"], status))

        lines += ["", "## 当前持仓", "",
                  "| 币种 | 数量 | 均价 | 最新价 | 市值 | 成本 | 浮动盈亏 | 建仓批次 |",
                  "|---|---:|---:|---:|---:|---:|---:|---|"]
        if self.state["positions"]:
            for symbol, pos in self.state["positions"].items():
                avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
                price = quotes.get(symbol, {}).get("price", avg)
                value = pos["amount"] * price
                pnl = value - pos["cost"]
                done = sum(pos["tranches_done"])
                lines.append("| {} | {:.2f} | {:.4f} | {:.4f} | {:.2f} | {:.2f} | {:+.2f}（{:+.2f}%） | {}/{} 批 |".format(
                    PLANS[symbol]["name"], pos["amount"], avg, price, value, pos["cost"],
                    pnl, (price - avg) / avg * 100 if avg else 0,
                    done, len(pos["tranches_done"])))
        else:
            lines.append("| 无持仓 | - | - | - | - | - | - | - |")

        lines += ["", "## 交易记录", ""]
        for t in self.state["trades"][-30:]:
            lines.append("- {}：{}".format(t["time"], t["text"]))

        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def main():
    tracker = CryptoTracker()
    print("crypto tracker started, poll every {}s".format(POLL_SECONDS))
    while True:
        try:
            tracker.run_once()
        except Exception as e:
            print("loop error:", e)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
