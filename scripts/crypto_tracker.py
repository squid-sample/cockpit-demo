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

# 动态调整参数
COOLDOWN_HOURS = 48          # 止损清仓后冷却小时数
TRAILING_TP_PCT = 0.08       # 止盈1后追踪止盈回撤比例
OPPORTUNITY_THRESHOLD = 0.10 # 未建仓但远离买点10%触发机会提示
MOMENTUM_15D_MIN = 0.05      # 15天动量最低5%算有行情
MOMENTUM_30D_MIN = 0.10       # 30天动量最低10%算有行情
EXTENDED_OBSERVATION_DAYS = 5  # 到期后持续观察天数

# 稳定币和杠杆代币排除
STABLECOINS = {"USDCUSDT", "BUSDUSDT", "FDUSDUSDT", "TUSDUSDT", "DAIUSDT", "USDPUSDT", "EURUSDT"}


def plan_buy_low(plan):
    return plan["tranches"][-1]["price"]


def plan_buy_high(plan):
    return plan["tranches"][0]["price"]


def round_price(price):
    if price >= 100:
        return round(price, 2)
    elif price >= 1:
        return round(price, 4)
    else:
        return round(price, 6)


def fetch_klines(symbol, interval="1d", limit=30):
    url = "{}/api/v3/klines?symbol={}&interval={}&limit={}".format(
        BINANCE, symbol, interval, limit)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def calc_momentum(symbol):
    try:
        k15 = fetch_klines(symbol, "1d", 16)
        k30 = fetch_klines(symbol, "1d", 31)
        pct_15d = (float(k15[-1][4]) - float(k15[0][4])) / float(k15[0][4])
        pct_30d = (float(k30[-1][4]) - float(k30[0][4])) / float(k30[0][4])
        return {"pct_15d": pct_15d, "pct_30d": pct_30d}
    except Exception:
        return {"pct_15d": 0.0, "pct_30d": 0.0}


def generate_dynamic_plan(symbol, current_price, name, logic=""):
    return {
        "name": name,
        "tranches": [
            {"price": round_price(current_price * 0.97), "pct": 0.5},
            {"price": round_price(current_price * 0.95), "pct": 0.3},
            {"price": round_price(current_price * 0.93), "pct": 0.2},
        ],
        "stop": round_price(current_price * 0.91),
        "tp1": round_price(current_price * 1.08),
        "tp2": round_price(current_price * 1.15),
        "logic": "动态重新筛选：" + logic,
        "start_date": dt.date.today().isoformat(),
    }


def screen_new_crypto_candidate(exclude_symbols):
    """扫描Binance USDT交易对，选出不在排除列表中的最优候选"""
    try:
        url = "{}/api/v3/ticker/24hr".format(BINANCE)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tickers = json.loads(resp.read().decode("utf-8"))
        candidates = []
        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or sym in exclude_symbols or sym in STABLECOINS:
                continue
            # 排除杠杆代币
            if any(sym.startswith(p) for p in ("BULL", "BEAR", "UP", "DOWN")):
                continue
            try:
                vol = float(t.get("quoteVolume", 0))
                pct = float(t.get("priceChangePercent", 0))
                price = float(t.get("lastPrice", 0))
            except (ValueError, TypeError):
                continue
            if vol < 50_000_000 or price <= 0:
                continue
            candidates.append({"symbol": sym, "pct24": pct, "price": price, "vol": vol})
        candidates.sort(key=lambda x: x["pct24"], reverse=True)
        # 取前10名计算动量
        for c in candidates[:10]:
            mom = calc_momentum(c["symbol"])
            if mom["pct_15d"] >= MOMENTUM_15D_MIN or mom["pct_30d"] >= MOMENTUM_30D_MIN:
                c["pct_15d"] = mom["pct_15d"]
                c["pct_30d"] = mom["pct_30d"]
                return c
        return None
    except Exception:
        return None


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
                state.setdefault("cooldown", {})
                state.setdefault("cycle_done", {})
                state.setdefault("dynamic_plans", {})
                state.setdefault("opportunity_pushed", {})
                state.setdefault("rescreened", {})
                state.setdefault("replacements", {})
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
            "cooldown": {},
            "cycle_done": {},
            "dynamic_plans": {},
            "opportunity_pushed": {},
            "rescreened": {},
            "replacements": {},
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

    def effective_plan(self, symbol):
        return self.state.get("dynamic_plans", {}).get(symbol) or PLANS[symbol]

    def try_replacement(self, expired_symbol, expired_name, events):
        """标的被移除后，自动筛选一个新标的补进来"""
        replacements = self.state.setdefault("replacements", {})
        if expired_symbol in replacements:
            return
        exclude = set(PLANS.keys()) | set(self.state.get("plan_expired", {}).keys()) | \
                  set(self.state.get("dynamic_plans", {}).keys()) | \
                  set(self.state.get("cycle_done", {}).keys())
        exclude |= {v for v in replacements.values() if v}
        candidate = screen_new_crypto_candidate(exclude)
        if candidate:
            new_name = candidate["symbol"].replace("USDT", "")
            new_plan = generate_dynamic_plan(candidate["symbol"], candidate["price"], new_name)
            self.state.setdefault("dynamic_plans", {})[candidate["symbol"]] = new_plan
            replacements[expired_symbol] = candidate["symbol"]
            events.append({
                "symbol": candidate["symbol"], "kind": "replace",
                "msg": "替换 {}：新增 {}，当前价 {:.4f}，15d动量 {:+.2%}，30d动量 {:+.2%}，"
                       "买点 {}/{}/{}, 止损 {}, 止盈 {}/{}".format(
                    expired_name, new_name, candidate["price"],
                    candidate["pct_15d"], candidate["pct_30d"],
                    new_plan["tranches"][0]["price"], new_plan["tranches"][1]["price"],
                    new_plan["tranches"][2]["price"], new_plan["stop"],
                    new_plan["tp1"], new_plan["tp2"])
            })
        else:
            replacements[expired_symbol] = None

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
                    self.effective_plan(symbol)["name"], len(items),
                    sum(t.get("pnl", 0) > 0 for t in items),
                    sum(t.get("pnl", 0) < 0 for t in items),
                    sum(t.get("pnl", 0) for t in items)))
        return lines

    def run_once(self):
        # 合并原始计划和动态新增标的
        all_symbols = set(PLANS.keys()) | set(self.state.get("dynamic_plans", {}).keys())
        quotes = {}
        for symbol in all_symbols:
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
        now = dt.datetime.now()
        all_plans = dict(PLANS)
        for sym, dp in self.state.get("dynamic_plans", {}).items():
            if sym not in all_plans:
                all_plans[sym] = dp
        for symbol, plan in all_plans.items():
            q = quotes.get(symbol)
            if not q:
                continue
            price = q["price"]
            pos = self.state["positions"].get(symbol)
            ep = self.effective_plan(symbol)

            if pos:
                # --- 持仓中 ---
                # 补仓：止损价之上才允许补仓
                for i, tr in enumerate(ep["tranches"]):
                    if i < len(pos["tranches_done"]) and not pos["tranches_done"][i] and ep["stop"] < price <= tr["price"]:
                        msg = self.buy_tranche(symbol, price, i, tr, budget_each)
                        if msg:
                            events.append({"symbol": symbol, "kind": "buy", "msg": msg})
                pos = self.state["positions"].get(symbol)
                if pos:
                    avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
                    stop_price = max(ep["stop"], avg) if pos["tp1_done"] else ep["stop"]

                    # 止损清仓
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
                        # 设冷却期：48小时内不再建仓
                        cooldown_until = now + dt.timedelta(hours=COOLDOWN_HOURS)
                        self.state.setdefault("cooldown", {})[symbol] = cooldown_until.strftime("%Y-%m-%d %H:%M")

                    # 止盈1：卖一半，止损上移成本价，记录峰值
                    elif not pos["tp1_done"] and price >= ep["tp1"]:
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
                        self.state["positions"][symbol]["peak_price"] = price

                    # 止盈2 / 追踪止盈
                    elif pos["tp1_done"]:
                        peak = pos.get("peak_price", price)
                        if price > peak:
                            pos["peak_price"] = price
                            peak = price
                        trailing_stop = peak * (1 - TRAILING_TP_PCT)
                        if price >= ep["tp2"]:
                            event_value = pos["amount"] * price
                            event_pnl = event_value - pos["cost"]
                            event_pnl_pct = event_pnl / pos["cost"] * 100 if pos["cost"] else 0
                            msg = self.close(symbol, price, pos["amount"], "到达止盈2，清仓")
                            events.append({"symbol": symbol, "kind": "tp2", "msg": msg,
                                           "position_pnl": event_pnl,
                                           "position_pnl_pct": event_pnl_pct,
                                           "position_value": event_value})
                            self.state.setdefault("cycle_done", {})[symbol] = True
                        elif price <= trailing_stop:
                            event_value = pos["amount"] * price
                            event_pnl = event_value - pos["cost"]
                            event_pnl_pct = event_pnl / pos["cost"] * 100 if pos["cost"] else 0
                            reason = "追踪止盈（最高点 {:.4f} 回撤 {:.0f}%），清仓".format(
                                peak, TRAILING_TP_PCT * 100)
                            msg = self.close(symbol, price, pos["amount"], reason)
                            events.append({"symbol": symbol, "kind": "tp2", "msg": msg,
                                           "position_pnl": event_pnl,
                                           "position_pnl_pct": event_pnl_pct,
                                           "position_value": event_value})
                            self.state.setdefault("cycle_done", {})[symbol] = True

            else:
                # --- 空仓 ---
                # 冷却期内不建仓
                cooldown_str = self.state.get("cooldown", {}).get(symbol)
                if cooldown_str:
                    try:
                        cooldown_time = dt.datetime.strptime(cooldown_str, "%Y-%m-%d %H:%M")
                        if now < cooldown_time:
                            continue
                    except ValueError:
                        pass

                # 止盈2清仓后本期不再用旧参数重建仓
                if self.state.get("cycle_done", {}).get(symbol):
                    continue

                # 计划已移除
                if self.state["plan_expired"].get(symbol):
                    continue

                days = (dt.date.today() - dt.date.fromisoformat(ep.get("start_date") or self.state["start_date"])).days
                buy_high = ep["tranches"][0]["price"]

                # 计划到期：重新跑动量筛选
                if days >= PLAN_VALID_DAYS:
                    mom = calc_momentum(symbol)
                    has_momentum = (mom["pct_15d"] >= MOMENTUM_15D_MIN or
                                    mom["pct_30d"] >= MOMENTUM_30D_MIN)

                    if has_momentum:
                        if not self.state.get("rescreened", {}).get(symbol):
                            new_plan = generate_dynamic_plan(
                                symbol, price, plan["name"], plan.get("logic", ""))
                            self.state.setdefault("dynamic_plans", {})[symbol] = new_plan
                            self.state.setdefault("rescreened", {})[symbol] = True
                            ep = new_plan
                            buy_high = ep["tranches"][0]["price"]
                            events.append({
                                "symbol": symbol, "kind": "rescreen",
                                "msg": "计划到期重新筛选：15d动量 {pct_15d:+.2%}，30d动量 {pct_30d:+.2%}，已生成新买点 @{price:.4f}（买点 {bp1:.4f}/{bp2:.4f}/{bp3:.4f}，止损 {stop:.4f}，止盈 {tp1:.4f}/{tp2:.4f}）".format(
                                    pct_15d=mom["pct_15d"], pct_30d=mom["pct_30d"], price=price,
                                    bp1=ep["tranches"][0]["price"], bp2=ep["tranches"][1]["price"],
                                    bp3=ep["tranches"][2]["price"], stop=ep["stop"],
                                    tp1=ep["tp1"], tp2=ep["tp2"])})
                    else:
                        # 无行情：末期才移除，否则持续观察
                        if days >= PLAN_VALID_DAYS + EXTENDED_OBSERVATION_DAYS:
                            self.state["plan_expired"][symbol] = True
                            events.append({
                                "symbol": symbol, "kind": "expire",
                                "msg": "计划到期后持续观察 {} 天仍无行情（15d {pct_15d:+.2%}，30d {pct_30d:+.2%}），移出本期".format(
                                    EXTENDED_OBSERVATION_DAYS,
                                    pct_15d=mom["pct_15d"], pct_30d=mom["pct_30d"])})
                            self.try_replacement(symbol, plan["name"], events)
                            continue
                        else:
                            today_str = now.date().isoformat()
                            observe_key = symbol + "_observe"
                            if self.state.get("opportunity_pushed", {}).get(observe_key) != today_str:
                                self.state.setdefault("opportunity_pushed", {})[observe_key] = today_str
                                events.append({
                                    "symbol": symbol, "kind": "rescreen",
                                    "msg": "计划到期但暂无行情（15d {pct_15d:+.2%}，30d {pct_30d:+.2%}），持续观察中（第 {day} 天）".format(
                                        pct_15d=mom["pct_15d"], pct_30d=mom["pct_30d"], day=days)})
                            continue

                # 未建仓就跌破止损位：计划作废
                if price <= ep["stop"]:
                    self.state["plan_expired"][symbol] = True
                    events.append({
                        "symbol": symbol, "kind": "expire",
                        "msg": "价格 {:.4f} 已跌破止损位 {}，建仓形态失效，计划作废不再买入".format(
                            price, ep["stop"])})
                    self.try_replacement(symbol, plan["name"], events)
                    continue

                # 未建仓但大涨：机会提示（每天最多1条）
                if price > buy_high * (1 + OPPORTUNITY_THRESHOLD):
                    today_str = now.date().isoformat()
                    opp_key = symbol + "_opp"
                    if self.state.get("opportunity_pushed", {}).get(opp_key) != today_str:
                        mom = calc_momentum(symbol)
                        if mom["pct_15d"] >= MOMENTUM_15D_MIN:
                            self.state.setdefault("opportunity_pushed", {})[opp_key] = today_str
                            events.append({
                                "symbol": symbol, "kind": "opportunity",
                                "msg": "价格 {:.4f} 已远离买点 {:.4f}（+{:.1f}%），15d动量 {:+.2%}，关注回踩机会".format(
                                    price, buy_high, (price / buy_high - 1) * 100, mom["pct_15d"])})

                # 按分批买点建仓
                for i, tr in enumerate(ep["tranches"]):
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
        "rescreen": "重新筛选",
        "opportunity": "机会提示",
        "replace": "新增替换",
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
            "tranches_done": [False] * len(self.effective_plan(symbol)["tranches"]),
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
        "tp2": ("到达止盈2/追踪止盈（清仓）", "#0d9488"),
        "stop": ("触发止损（清仓）", "#dc2626"),
        "expire": ("计划到期/移除", "#6b7280"),
        "rescreen": ("到期重新筛选", "#3b82f6"),
        "opportunity": ("大涨机会提示", "#8b5cf6"),
        "replace": ("新增替换标的", "#2563eb"),
    }

    def closed_trade_records(self):
        return [
            trade for trade in self.state.get("trades", [])
            if trade.get("action") == "sell" and "清仓" in trade.get("reason", "")
        ]

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
                "<p>计划期：{}；剩余可用资金：<b>{:.2f} USDT</b>；累计投入资产：{:.2f} USDT；当前持仓市值：{:.2f} USDT；总资产：{:.2f} USDT；账户浮动盈亏：<b>{:+.2f} USDT</b></p>".format(
                    self.state.get("plan_id", PLAN_ID), self.state["cash"], invested, market_value, total,
                    total - SIM_CAPITAL),
            ]
            if self.state["positions"]:
                parts.append("<p><b>当前持仓</b></p><table style='border-collapse:collapse'><tr><th>币种</th><th>累计投入（USDT）</th><th>平均买入价</th><th>当前价格</th><th>当前市值（USDT）</th><th>浮动盈亏</th><th>收益率</th></tr>")
                for symbol, pos in self.state["positions"].items():
                    avg = pos["cost"] / pos["amount"] if pos["amount"] else 0
                    price = quotes.get(symbol, {}).get("price", avg)
                    value = pos["amount"] * price
                    pnl = value - pos["cost"]
                    pnl_pct = pnl / pos["cost"] * 100 if pos["cost"] else 0
                    plan = self.effective_plan(symbol)
                    parts.append("<tr><td>{}</td><td>{:.2f}</td><td>{:.4f}</td><td>{:.4f}</td><td>{:.2f}</td><td><b>{:+.2f} USDT</b></td><td>{:+.2f}%</td></tr>".format(
                        plan["name"], pos["cost"], avg, price, value, pnl, pnl_pct))
                parts.append("</table>")
            else:
                parts.append("<p>当前无持仓，当前持仓投入：0.00 USDT。</p>")
            closed = self.closed_trade_records()
            if closed:
                parts.append("<p><b>已清仓记录（已实现盈亏）</b></p><table style='border-collapse:collapse'><tr><th>时间</th><th>币种</th><th>卖出金额（USDT）</th><th>投入成本（USDT）</th><th>已实现浮盈/浮亏</th></tr>")
                for trade in closed[-20:]:
                    cost = trade.get("cost", trade.get("value", 0) - trade.get("pnl", 0))
                    sym = trade.get("symbol", "")
                    name = self.effective_plan(sym).get("name", sym or "-") if sym else "-"
                    parts.append("<tr><td>{}</td><td>{}</td><td>{:.2f}</td><td>{:.2f}</td><td><b>{:+.2f} USDT</b></td></tr>".format(
                        trade.get("time", "-"), name,
                        trade.get("value", 0), cost, trade.get("pnl", 0)))
                parts.append("</table>")
            else:
                parts.append("<p>暂无已清仓记录。</p>")
            parts.append("<p><b>后续计划</b>：持仓标的按止损/止盈规则处理；止盈2清仓后本期不再用旧参数重建仓；止损清仓后48小时冷却；计划到期后重新筛选，有行情生成新买点，无行情持续观察至末期移除。</p>")
            parts.append("<p style='color:#aaa;font-size:12px'>仅为程序模拟，不会真实下单。</p></div>")
            push_async("币·{}持仓汇总（本金{:.0f}U）".format(label, SIM_CAPITAL), "".join(parts))
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
            plan = self.effective_plan(ev["symbol"])
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
            "- 开始跟踪日期：{}（计划有效期 {} 天，到期重新筛选，无行情持续观察 {} 天后移除）".format(
                self.state["start_date"], PLAN_VALID_DAYS, EXTENDED_OBSERVATION_DAYS),
            "- 模拟资金：{:.0f} USDT（每币分配约 {:.0f}）".format(SIM_CAPITAL, SIM_CAPITAL / len(PLANS)),
            "- 剩余可用资金：{:.2f} USDT".format(self.state["cash"]),
            "- 当前持仓投入：{:.2f} USDT".format(sum(pos["cost"] for pos in self.state["positions"].values())),
            "- 当前持仓市值：{:.2f} USDT".format(self.total_asset(quotes) - self.state["cash"]),
            "- 当前总资产：{:.2f} USDT".format(self.total_asset(quotes)),
            "- 总浮动盈亏：{:+.2f} USDT（{:+.2f}%）".format(
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
            ep = self.effective_plan(symbol)
            pos = self.state["positions"].get(symbol)
            if pos:
                done = sum(pos["tranches_done"])
                status = "持仓中（已建仓 {}/{} 批）".format(done, len(pos["tranches_done"]))
            elif self.state.get("cycle_done", {}).get(symbol):
                status = "已止盈2清仓（本期不再用旧参数重建仓）"
            elif self.state.get("cooldown", {}).get(symbol):
                status = "冷却中（止损后 {} 内不建仓）".format(self.state["cooldown"][symbol])
            elif self.state["plan_expired"].get(symbol):
                status = "已移除（到期无行情或破位作废）"
            elif self.state.get("dynamic_plans", {}).get(symbol):
                status = "动态计划（重新筛选后买点 {}/{}/{}, 止损 {}）".format(
                    ep["tranches"][0]["price"], ep["tranches"][1]["price"],
                    ep["tranches"][2]["price"], ep["stop"])
            elif price <= ep["stop"]:
                status = "已破止损位（计划作废）"
            elif price <= plan_buy_low(ep):
                status = "**第三批买点内**"
            elif price <= plan_buy_high(ep):
                status = "**建仓区间内（等分批触发）**"
            else:
                status = "高于第一批买点（等回踩）"
            lines.append("| {} | {:.4f} | {:+.2f}% | {} |".format(
                ep["name"], price, q["pct24"], status))

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
                    self.effective_plan(symbol)["name"], pos["amount"], avg, price, value, pos["cost"],
                    pnl, (price - avg) / avg * 100 if avg else 0,
                    done, len(pos["tranches_done"])))
        else:
            lines.append("| 无持仓 | - | - | - | - | - | - | - |")

        lines += ["", "## 交易记录", "", "| 时间 | 币种 | 记录 |", "|---|---|---|"]
        for t in self.state["trades"][-30:]:
            symbol = t.get("symbol", "")
            coin = self.effective_plan(symbol).get("name", symbol or "-") if symbol else "-"
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
