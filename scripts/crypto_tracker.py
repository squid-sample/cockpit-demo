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
PLAN_ROOT = os.path.join(BASE_DIR, "crypto_plans")
with open(os.path.join(PLAN_ROOT, "active_plan.txt"), "r", encoding="utf-8") as f:
    ACTIVE_PLAN_ID = f.read().strip()
PLAN_DIR = os.path.join(PLAN_ROOT, ACTIVE_PLAN_ID)
with open(os.path.join(PLAN_DIR, "plan.json"), "r", encoding="utf-8") as f:
    PLAN_CONFIG = json.load(f)
STATE_FILE = os.path.join(PLAN_DIR, "state.json")
REPORT_FILE = os.path.join(PLAN_DIR, "report.md")
REPORT_ARCHIVE_DIR = os.path.join(BASE_DIR, "crypto_reports")
POLL_SECONDS = 120
SIM_CAPITAL = float(PLAN_CONFIG["capital"])
PUSHPLUS_TOKEN = "e39674189a874c48888292f80e0c3464"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
BINANCE = "https://data-api.binance.vision"
PLAN_VALID_DAYS = int(PLAN_CONFIG["valid_days"])
PLAN_ID = PLAN_CONFIG["plan_id"]
PLAN_DATE = PLAN_CONFIG["plan_date"]
PLANS = PLAN_CONFIG["plans"]


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
                state.setdefault("summary_pushes", {})
                state.setdefault("plan_id", PLAN_ID)
                state.setdefault("plan_date", PLAN_DATE)
                return state
            except (OSError, ValueError):
                pass
        return {
            "start_date": dt.date.today().isoformat(),
            "plan_id": PLAN_ID,
            "plan_date": PLAN_DATE,
            "cash": SIM_CAPITAL,
            "positions": {},
            "plan_expired": {},
            "trades": [],
            "last_quotes": {},
            "summary_pushes": {},
        }

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def record_trade(self, symbol, text, **fields):
        trade = {
            "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": symbol,
            "text": text,
        }
        trade.update(fields)
        self.state["trades"].append(trade)

    def period_summary(self, start, end):
        trades = []
        for trade in self.state.get("trades", []):
            if trade.get("action") != "sell":
                continue
            day = trade.get("time", "")[:10]
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
                 "- 已实现盈亏：{:+.2f} USDT".format(sum(t.get("pnl", 0) for t in trades)),
                 "- 平均盈利/平均亏损：{:+.2f} / {:+.2f} USDT".format(
                     profit / len(wins) if wins else 0, loss / len(losses) if losses else 0),
                 "- 盈亏比：{}".format("{:.2f}".format(profit / abs(loss)) if loss else ("暂无亏损样本" if not profit else "无亏损样本")),
                 "", "| 币种 | 完成卖出 | 盈利 | 亏损 | 已实现盈亏 |", "|---|---:|---:|---:|---:|"]
        for symbol in PLANS:
            items = [t for t in trades if t.get("symbol") == symbol]
            if items:
                lines.append("| {} | {} | {} | {} | {:+.2f} |".format(
                    PLANS[symbol]["name"], len(items),
                    sum(t.get("pnl", 0) > 0 for t in items),
                    sum(t.get("pnl", 0) < 0 for t in items),
                    sum(t.get("pnl", 0) for t in items)))
        return lines

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
                        event_value = pos["amount"] * price
                        event_pnl = event_value - pos["cost"]
                        event_pnl_pct = event_pnl / pos["cost"] * 100 if pos["cost"] else 0
                        reason = "触发止损（{}），清仓".format(
                            "已上移到成本价" if pos["tp1_done"] else "破止损位")
                        msg = self.close(symbol, price, pos["amount"], reason)
                        events.append({"symbol": symbol, "kind": "stop", "msg": msg,
                                       "position_pnl": event_pnl,
                                       "position_pnl_pct": event_pnl_pct,
                                       "position_value": event_value})
                    elif not pos["tp1_done"] and price >= plan["tp1"]:
                        event_value = pos["amount"] * price
                        event_pnl = event_value - pos["cost"]
                        event_pnl_pct = event_pnl / pos["cost"] * 100 if pos["cost"] else 0
                        half = pos["amount"] / 2
                        msg = self.sell(symbol, price, half, "到达止盈1，卖出一半，止损上移成本价")
                        events.append({"symbol": symbol, "kind": "tp1", "msg": msg,
                                       "position_pnl": event_pnl,
                                       "position_pnl_pct": event_pnl_pct,
                                       "position_value": event_value})
                        self.state["positions"][symbol]["tp1_done"] = True
                    elif pos["tp1_done"] and price >= plan["tp2"]:
                        event_value = pos["amount"] * price
                        event_pnl = event_value - pos["cost"]
                        event_pnl_pct = event_pnl / pos["cost"] * 100 if pos["cost"] else 0
                        msg = self.close(symbol, price, pos["amount"], "到达止盈2，清仓")
                        events.append({"symbol": symbol, "kind": "tp2", "msg": msg,
                                       "position_pnl": event_pnl,
                                       "position_pnl_pct": event_pnl_pct,
                                       "position_value": event_value})
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

        for event in events:
            position = self.state["positions"].get(event["symbol"])
            if "position_pnl" not in event:
                if position and position["amount"] and position["cost"]:
                    event["position_value"] = position["amount"] * quotes[event["symbol"]]["price"]
                    event["position_pnl"] = event["position_value"] - position["cost"]
                    event["position_pnl_pct"] = event["position_pnl"] / position["cost"] * 100
                else:
                    event["position_value"] = 0.0
                    event["position_pnl"] = 0.0
                    event["position_pnl_pct"] = 0.0
            event["total_pnl"] = self.total_asset(quotes) - SIM_CAPITAL

        self.save_state()
        self.write_report(quotes)
        self.push_scheduled_summary(quotes)
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
        coin = PLANS[symbol]["name"]
        msg = "{} 第{idx}批建仓 {pct:.0f}%：买入 {amount:.2f} 枚 @{price:.4f}，金额 {spend:.0f} USDT（已建仓 {done}/{total} 批，均价 {avg:.4f}）".format(
            coin, idx=index + 1, pct=tranche["pct"] * 100, amount=amount, price=price,
            spend=spend, done=done, total=total, avg=pos["cost"] / pos["amount"])
        self.record_trade(symbol, msg, action="buy", price=price, amount=amount, value=spend,
                          tranche=index + 1, plan_version=self.state.get("plan_id", PLAN_ID))
        return msg

    KIND_STYLE = {
        "buy": ("分批建仓成交", "#16a34a"),
        "tp1": ("到达止盈1（卖出一半，止损上移成本）", "#d97706"),
        "tp2": ("到达止盈2（清仓）", "#0d9488"),
        "stop": ("触发止损（清仓）", "#dc2626"),
        "expire": ("计划到期未建仓", "#6b7280"),
    }

    def push_scheduled_summary(self, quotes):
        now = dt.datetime.now()
        slots = ((dt.time(9, 0), "morning", "早间"), (dt.time(17, 50), "evening", "晚间"))
        today = now.date().isoformat()
        for target, key, label in slots:
            marker = "{}-{}".format(today, key)
            if now.time() < target or self.state["summary_pushes"].get(marker):
                continue
            total = self.total_asset(quotes)
            invested = sum(pos["cost"] for pos in self.state["positions"].values())
            market_value = total - self.state["cash"]
            parts = [
                "<div style='font-family:Microsoft YaHei,Arial;font-size:14px;line-height:1.7'>",
                "<h3>{}加密货币持仓汇总 · {}</h3>".format(label, now.strftime("%Y-%m-%d %H:%M")),
                "<p>计划期：{}；剩余可用资金：{:.2f} USDT；已投入资产：{:.2f} USDT；持仓市值：{:.2f} USDT；总资产：{:.2f} USDT；浮动盈亏：<b>{:+.2f} USDT</b></p>".format(
                    self.state.get("plan_id", PLAN_ID), self.state["cash"], invested, market_value, total,
                    total - SIM_CAPITAL),
            ]
            if self.state["positions"]:
                parts.append("<p><b>当前持仓</b></p><table style='border-collapse:collapse'><tr><th>币种</th><th>数量</th><th>买入总金额</th><th>平均买入价</th><th>当前价格</th><th>当前市值</th><th>浮动盈亏</th><th>收益率</th></tr>")
                for symbol, pos in self.state["positions"].items():
                    avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
                    price = quotes.get(symbol, {}).get("price", avg)
                    value = pos["amount"] * price
                    pnl = value - pos["cost"]
                    pnl_pct = pnl / pos["cost"] * 100 if pos["cost"] else 0
                    plan = PLANS[symbol]
                    parts.append("<tr><td>{}</td><td>{:.6f} 枚</td><td>{:.2f} USDT</td><td>{:.4f}</td><td>{:.4f}</td><td>{:.2f} USDT</td><td><b>{:+.2f} USDT</b></td><td>{:+.2f}%</td></tr>".format(
                        plan["name"], pos["amount"], pos["cost"], avg, price, value, pnl, pnl_pct))
                parts.append("</table>")
            else:
                parts.append("<p>当前无持仓，已投入资产：0.00 USDT。</p>")
            parts.append("<p><b>后续计划</b>：按本期 plan.json 的分批买点执行；未持仓标的等待回踩买点，持仓标的按止损/止盈规则处理。</p>")
            parts.append("<p style='color:#aaa;font-size:12px'>仅为程序模拟，不会真实下单。</p></div>")
            push_async("币·{}持仓汇总".format(label), "".join(parts))
            self.state["summary_pushes"][marker] = now.strftime("%Y-%m-%d %H:%M")
        self.save_state()

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
            pos = self.state["positions"].get(ev["symbol"])
            if price is not None and (pos or "position_pnl" in ev):
                position_value = ev.get("position_value", pos["amount"] * price if pos else 0)
                position_pnl = ev.get("position_pnl", position_value - pos["cost"] if pos else 0)
                position_pnl_pct = ev.get("position_pnl_pct", position_pnl / pos["cost"] * 100 if pos and pos["cost"] else 0)
                parts.append("<p style='margin:2px 0'>该币种浮盈：<b>{:+.2f} USDT（{:+.2f}%）</b>；持仓市值：{:.2f} USDT</p>".format(
                    position_pnl, position_pnl_pct, position_value))
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
            total, events[-1].get("total_pnl", total - SIM_CAPITAL)))
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
        self.record_trade(symbol, msg, action="sell", price=price, amount=amount,
                          value=proceeds, pnl=pnl, reason=reason,
                          plan_version=self.state.get("plan_id", PLAN_ID))
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
            "- 计划期：{}".format(self.state.get("plan_id", PLAN_ID)),
            "- 计划制定日期：{}".format(self.state.get("plan_date", PLAN_DATE)),
            "- 开始跟踪日期：{}（计划有效期 {} 天，到期未建仓自动暂停）".format(
                self.state["start_date"], PLAN_VALID_DAYS),
            "- 模拟资金：{:.0f} USDT（每币分配约 {:.0f}）".format(SIM_CAPITAL, SIM_CAPITAL / len(PLANS)),
            "- 当前总资产：{:.2f} USDT".format(self.total_asset(quotes)),
            "- 浮动盈亏：{:+.2f} USDT（{:+.2f}%）".format(
                self.total_asset(quotes) - SIM_CAPITAL,
                (self.total_asset(quotes) - SIM_CAPITAL) / SIM_CAPITAL * 100),
            "",
            "## 推荐计划（{}，{} 制定，分批建仓 50%/30%/20%）".format(
                self.state.get("plan_id", PLAN_ID), self.state.get("plan_date", PLAN_DATE)),
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

        lines += ["", "## 交易记录", "", "| 时间 | 币种 | 记录 |", "|---|---|---|"]
        for t in self.state["trades"][-30:]:
            symbol = t.get("symbol", "")
            coin = PLANS.get(symbol, {}).get("name", symbol or "-")
            lines.append("| {} | {} | {} |".format(t["time"], coin, t["text"]))

        report = "\n".join(lines) + "\n"
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report)

        now = dt.datetime.now()
        periods = (
            ("daily", now.strftime("%Y-%m-%d.md"), now.date(), now.date()),
            ("weekly", now.strftime("%Y-W%W.md"), now.date() - dt.timedelta(days=now.weekday()),
             now.date() - dt.timedelta(days=now.weekday()) + dt.timedelta(days=6)),
            ("monthly", now.strftime("%Y-%m.md"), now.date().replace(day=1),
             (now.date().replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)),
        )
        for period, filename, start, end in periods:
            directory = os.path.join(REPORT_ARCHIVE_DIR, self.state.get("plan_id") or PLAN_ID, period)
            os.makedirs(directory, exist_ok=True)
            archived = list(lines) + [""] + self.period_summary(start.isoformat(), end.isoformat()) + [""]
            archived += ["## 优化纪律", "",
                         "- 先累计样本再调参：单个周期完成卖出少于 20 笔时，只记录不改核心规则。",
                         "- 优化目标同时看胜率、盈亏比、期望值和最大回撤，不能只看一笔输赢。",
                         "- 若连续样本显示止损过密或买点过高，下一版计划只微调买入回撤、止损距离和仓位批次。"]
            with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
                f.write("\n".join(archived) + "\n")


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
