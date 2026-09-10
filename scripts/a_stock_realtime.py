import datetime as dt
import json
import os
import threading
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAN_ROOT = os.path.join(BASE_DIR, "stock_plans")
with open(os.path.join(PLAN_ROOT, "active_plan.txt"), "r", encoding="utf-8") as file:
    ACTIVE_PLAN_ID = file.read().strip()
PLAN_DIR = os.path.join(PLAN_ROOT, ACTIVE_PLAN_ID)
with open(os.path.join(PLAN_DIR, "plan.json"), "r", encoding="utf-8") as file:
    PLAN_CONFIG = json.load(file)

REFRESH_MS = 5000
SIM_POLL_MS = 60000
TRANSPARENT_COLOR = "#ff00ff"
SIM_STATE_FILE = os.path.join(PLAN_DIR, "state.json")
SIM_REPORT_FILE = os.path.join(PLAN_DIR, "report.md")
SIM_REPORT_ARCHIVE_DIR = os.path.join(BASE_DIR, "stock_reports")
SIM_CAPITAL = float(PLAN_CONFIG["capital"])
SIM_DAYS = int(PLAN_CONFIG["valid_days"])
PLAN_ID = PLAN_CONFIG["plan_id"]
PLAN_DATE = PLAN_CONFIG["plan_date"]
PUSHPLUS_TOKEN = "e39674189a874c48888292f80e0c3464"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
SIM_PLANS = PLAN_CONFIG["plans"]

# 动态调整参数
COOLDOWN_HOURS = 48          # 止损清仓后冷却小时数
TRAILING_TP_PCT = 0.08       # 止盈1后追踪止盈回撤比例
OPPORTUNITY_THRESHOLD = 0.10 # 未建仓但远离买点上限10%触发机会提示
EXTENDED_OBSERVATION_DAYS = 5  # 到期后持续观察天数


def fetch_stock_klines(code, scale="240", count=30):
    """获取A股日K线数据，scale=240表示日线"""
    url = "https://quotes.sina.cn/cn/api/jsonp.php/var_/CN_MarketDataService.getKLineData?symbol={}&scale={}&datalen={}".format(
        normalize_code(code), scale, count)
    request = urllib.request.Request(url, headers={
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0",
    })
    with urllib.request.urlopen(request, timeout=10) as response:
        text = response.read().decode("utf-8", errors="ignore")
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < 0:
        return []
    return json.loads(text[start:end + 1])


def calc_stock_momentum(code):
    """计算15天和30天动量"""
    try:
        klines = fetch_stock_klines(code, "240", 31)
        if len(klines) < 16:
            return {"pct_15d": 0.0, "pct_30d": 0.0}
        pct_15d = (float(klines[-1]["close"]) - float(klines[-16]["close"])) / float(klines[-16]["close"])
        pct_30d = (float(klines[-1]["close"]) - float(klines[0]["close"])) / float(klines[0]["close"])
        return {"pct_15d": pct_15d, "pct_30d": pct_30d}
    except Exception:
        return {"pct_15d": 0.0, "pct_30d": 0.0}


def generate_dynamic_stock_plan(code, current_price, name):
    """基于当前价格生成动态计划"""
    return {
        "name": name,
        "buy_low": round(current_price * 0.97, 2),
        "buy_high": round(current_price * 0.99, 2),
        "stop": round(current_price * 0.91, 2),
        "tp1": round(current_price * 1.08, 2),
        "tp2": round(current_price * 1.15, 2),
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
                    state = json.load(file)
                    state.setdefault("plan_id", PLAN_ID)
                    state.setdefault("plan_date", PLAN_DATE)
                    state.setdefault("summary_pushes", {})
                    state.setdefault("cooldown", {})
                    state.setdefault("cycle_done", {})
                    state.setdefault("dynamic_plans", {})
                    state.setdefault("opportunity_pushed", {})
                    state.setdefault("rescreened", {})
                    return state
            except (OSError, ValueError):
                pass
        return {
            "start_date": None,
            "plan_id": PLAN_ID,
            "plan_date": PLAN_DATE,
            "end_date": None,
            "cash": SIM_CAPITAL,
            "positions": {},
            "trades": [],
            "daily": [],
            "last_quotes": {},
            "summary_pushes": {},
            "cooldown": {},
            "cycle_done": {},
            "dynamic_plans": {},
            "opportunity_pushed": {},
            "rescreened": {},
        }

    def save_state(self):
        with open(SIM_STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(self.state, file, ensure_ascii=False, indent=2)

    def effective_plan(self, code):
        return self.state.get("dynamic_plans", {}).get(code) or SIM_PLANS[code]

    def poll(self):
        now = dt.datetime.now()
        market_open = now.weekday() < 5 and dt.time(9, 30) <= now.time() < dt.time(15, 0)
        if market_open and self.state["start_date"] is None:
            self.state["start_date"] = now.date().isoformat()
            self.state["end_date"] = (now.date() + dt.timedelta(days=SIM_DAYS)).isoformat()
            self.record("模拟周期开始，初始资金 {:.2f} 元".format(SIM_CAPITAL))
            self.save_state()

        active = self.state["start_date"] and now.date().isoformat() <= self.state["end_date"]
        if active and market_open:
            threading.Thread(target=self.load_and_process, daemon=True).start()
        elif self.state["start_date"]:
            quotes = self.state.get("last_quotes", {})
            self.write_report(quotes)
            self.push_scheduled_summary(quotes)
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
        now = dt.datetime.now()
        for code, plan in SIM_PLANS.items():
            quote = quotes.get(code)
            if not quote:
                continue
            position = self.state["positions"].get(code)
            price = quote["current"]
            ep = self.effective_plan(code)

            if position:
                # --- 持仓中 ---
                stop_price = max(ep["stop"], position["buy_price"]) if position["tp1_done"] else ep["stop"]
                if price <= stop_price:
                    event_value = position["shares"] * price
                    event_cost = position["shares"] * position["buy_price"]
                    event_pnl = event_value - event_cost
                    event_pnl_pct = event_pnl / event_cost * 100 if event_cost else 0
                    action = self.sell(code, price, position["shares"], "止损")
                    day_log["actions"].append(action)
                    alerts.append({"code": code, "kind": "stop", "price": price, "text": action,
                                   "position_pnl": event_pnl,
                                   "position_pnl_pct": event_pnl_pct,
                                   "position_value": event_value})
                    # 设冷却期
                    cooldown_until = now + dt.timedelta(hours=COOLDOWN_HOURS)
                    self.state.setdefault("cooldown", {})[code] = cooldown_until.strftime("%Y-%m-%d %H:%M")
                elif not position["tp1_done"] and price >= ep["tp1"]:
                    shares = position["shares"] // 2
                    if shares:
                        event_value = position["shares"] * price
                        event_cost = position["shares"] * position["buy_price"]
                        event_pnl = event_value - event_cost
                        event_pnl_pct = event_pnl / event_cost * 100 if event_cost else 0
                        action = self.sell(code, price, shares, "第一止盈")
                        day_log["actions"].append(action)
                        alerts.append({"code": code, "kind": "tp1", "price": price, "text": action,
                                       "position_pnl": event_pnl,
                                       "position_pnl_pct": event_pnl_pct,
                                       "position_value": event_value})
                        self.state["positions"][code]["tp1_done"] = True
                        self.state["positions"][code]["peak_price"] = price
                elif position["tp1_done"]:
                    peak = position.get("peak_price", price)
                    if price > peak:
                        position["peak_price"] = price
                        peak = price
                    trailing_stop = peak * (1 - TRAILING_TP_PCT)
                    if price >= ep["tp2"]:
                        event_value = position["shares"] * price
                        event_cost = position["shares"] * position["buy_price"]
                        event_pnl = event_value - event_cost
                        event_pnl_pct = event_pnl / event_cost * 100 if event_cost else 0
                        action = self.sell(code, price, position["shares"], "第二止盈")
                        day_log["actions"].append(action)
                        alerts.append({"code": code, "kind": "tp2", "price": price, "text": action,
                                       "position_pnl": event_pnl,
                                       "position_pnl_pct": event_pnl_pct,
                                       "position_value": event_value})
                        self.state.setdefault("cycle_done", {})[code] = True
                    elif price <= trailing_stop:
                        event_value = position["shares"] * price
                        event_cost = position["shares"] * position["buy_price"]
                        event_pnl = event_value - event_cost
                        event_pnl_pct = event_pnl / event_cost * 100 if event_cost else 0
                        action = self.sell(code, price, position["shares"],
                                          "追踪止盈（最高 {:.2f} 回撤 {:.0f}%）".format(peak, TRAILING_TP_PCT * 100))
                        day_log["actions"].append(action)
                        alerts.append({"code": code, "kind": "tp2", "price": price, "text": action,
                                       "position_pnl": event_pnl,
                                       "position_pnl_pct": event_pnl_pct,
                                       "position_value": event_value})
                        self.state.setdefault("cycle_done", {})[code] = True
            else:
                # --- 空仓 ---
                # 冷却期内不建仓
                cooldown_str = self.state.get("cooldown", {}).get(code)
                if cooldown_str:
                    try:
                        cooldown_time = dt.datetime.strptime(cooldown_str, "%Y-%m-%d %H:%M")
                        if now < cooldown_time:
                            continue
                    except ValueError:
                        pass

                # 止盈2清仓后本期不再用旧参数重建仓
                if self.state.get("cycle_done", {}).get(code):
                    continue

                # 计划到期处理
                start_date = self.state.get("start_date")
                if start_date:
                    start_dt = dt.date.fromisoformat(start_date)
                    days = (dt.date.today() - start_dt).days
                    if days >= SIM_DAYS:
                        mom = calc_stock_momentum(code)
                        has_momentum = mom["pct_15d"] >= 0.05 or mom["pct_30d"] >= 0.10

                        if has_momentum:
                            if not self.state.get("rescreened", {}).get(code):
                                new_plan = generate_dynamic_stock_plan(code, price, plan["name"])
                                self.state.setdefault("dynamic_plans", {})[code] = new_plan
                                self.state.setdefault("rescreened", {})[code] = True
                                ep = new_plan
                                alerts.append({"code": code, "kind": "rescreen", "price": price,
                                               "text": "计划到期重新筛选：15d动量 {:.2%}，30d动量 {:.2%}，已生成新买点 {:.2f}-{:.2f}，止损 {:.2f}，止盈 {:.2f}/{:.2f}".format(
                                                   mom["pct_15d"], mom["pct_30d"],
                                                   ep["buy_low"], ep["buy_high"], ep["stop"],
                                                   ep["tp1"], ep["tp2"])})
                        else:
                            if days >= SIM_DAYS + EXTENDED_OBSERVATION_DAYS:
                                alerts.append({"code": code, "kind": "expire", "price": price,
                                               "text": "计划到期后持续观察 {} 天仍无行情（15d {:.2%}，30d {:.2%}），移出本期".format(
                                                   EXTENDED_OBSERVATION_DAYS,
                                                   mom["pct_15d"], mom["pct_30d"])})
                                self.state.setdefault("plan_expired", {})[code] = True
                                continue
                            else:
                                today_str = now.date().isoformat()
                                observe_key = code + "_observe"
                                if self.state.get("opportunity_pushed", {}).get(observe_key) != today_str:
                                    self.state.setdefault("opportunity_pushed", {})[observe_key] = today_str
                                    alerts.append({"code": code, "kind": "rescreen", "price": price,
                                                   "text": "计划到期但暂无行情（15d {:.2%}，30d {:.2%}），持续观察中（第 {} 天）".format(
                                                       mom["pct_15d"], mom["pct_30d"], days)})
                                continue

                if self.state.get("plan_expired", {}).get(code):
                    continue

                # 未建仓但大涨：机会提示（每天最多1条）
                if price > ep["buy_high"] * (1 + OPPORTUNITY_THRESHOLD):
                    today_str = now.date().isoformat()
                    opp_key = code + "_opp"
                    if self.state.get("opportunity_pushed", {}).get(opp_key) != today_str:
                        mom = calc_stock_momentum(code)
                        if mom["pct_15d"] >= 0.05:
                            self.state.setdefault("opportunity_pushed", {})[opp_key] = today_str
                            alerts.append({"code": code, "kind": "opportunity", "price": price,
                                           "text": "价格 {:.2f} 已远离买点 {:.2f}（+{:.1f}%），15d动量 {:.2%}，关注回踩机会".format(
                                               price, ep["buy_high"], (price / ep["buy_high"] - 1) * 100,
                                               mom["pct_15d"])})

                # 买入区间内建仓
                if ep["buy_low"] <= price <= ep["buy_high"]:
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
                        action = "买入 {} {} 股，成交价 {:.2f} 元".format(ep["name"], shares, price)
                        self.record(action, code=code, action="buy", price=price, shares=shares,
                                    value=cost, plan_version=self.state.get("plan_id", PLAN_ID))
                        day_log["actions"].append(action)
                        alerts.append({"code": code, "kind": "buy", "price": price, "text": action})
        day_log["quotes"] = quotes
        day_log["cash"] = self.state["cash"]
        day_log["asset"] = self.calculate_asset(quotes)
        self.state["last_asset"] = day_log["asset"]
        for alert in alerts:
            position = self.state["positions"].get(alert["code"])
            if "position_pnl" not in alert:
                if position and position["shares"]:
                    alert["position_value"] = position["shares"] * quotes[alert["code"]]["current"]
                    cost = position["shares"] * position["buy_price"]
                    alert["position_pnl"] = alert["position_value"] - cost
                    alert["position_pnl_pct"] = alert["position_pnl"] / cost * 100 if cost else 0
                else:
                    alert["position_value"] = 0.0
                    alert["position_pnl"] = 0.0
                    alert["position_pnl_pct"] = 0.0
            alert["total_pnl"] = self.calculate_asset(quotes) - SIM_CAPITAL
        if not day_log["actions"]:
            day_log["actions"].append("无交易")
        self.save_state()
        self.write_report(quotes)
        self.push_scheduled_summary(quotes)
        if alerts:
            self.show_trade_popup(alerts)
            self.push_trade_alerts(alerts)

    def push_scheduled_summary(self, quotes):
        now = dt.datetime.now()
        target = dt.time(15, 5)
        marker = "{}-close".format(now.date().isoformat())
        if now.time() < target or self.state["summary_pushes"].get(marker):
            return
        total = self.calculate_asset(quotes)
        invested = sum(position["shares"] * position["buy_price"] for position in self.state["positions"].values())
        market_value = total - self.state["cash"]
        parts = [
            "<div style='font-family:Microsoft YaHei,Arial;font-size:14px;line-height:1.7'>",
            "<h3>A股收盘持仓汇总 · {}</h3>".format(now.strftime("%Y-%m-%d %H:%M")),
            "<p>计划期：{}；剩余可用资金：{:.2f} 元；已投入资产：{:.2f} 元；持仓市值：{:.2f} 元；总资产：{:.2f} 元；浮动盈亏：<b>{:+.2f} 元</b></p>".format(
                self.state.get("plan_id", PLAN_ID), self.state["cash"], invested, market_value, total, total - SIM_CAPITAL),
        ]
        if self.state["positions"]:
            parts.append("<p><b>当前持仓</b></p><table style='border-collapse:collapse'><tr><th>股票</th><th>股数</th><th>买入总金额</th><th>平均买入价</th><th>当前价格</th><th>当前市值</th><th>浮动盈亏</th><th>收益率</th></tr>")
            for code, position in self.state["positions"].items():
                plan = self.effective_plan(code)
                price = quotes.get(code, {}).get("current", position["buy_price"])
                cost = position["shares"] * position["buy_price"]
                value = position["shares"] * price
                pnl = value - cost
                pnl_pct = pnl / cost * 100 if cost else 0
                parts.append("<tr><td>{}</td><td>{} 股</td><td>{:.2f} 元</td><td>{:.2f}</td><td>{:.2f}</td><td>{:.2f} 元</td><td><b>{:+.2f} 元</b></td><td>{:+.2f}%</td></tr>".format(
                    plan["name"], position["shares"], cost, position["buy_price"], price, value, pnl, pnl_pct))
            parts.append("</table>")
        else:
            parts.append("<p>当前无持仓，已投入资产：0.00 元。</p>")
        parts.append("<p><b>后续计划</b>：持仓标的按止损/止盈规则处理；止盈2清仓后本期不再用旧参数重建仓；止损清仓后48小时冷却；计划到期后重新筛选，有行情生成新买点，无行情持续观察至末期移除。</p>")
        parts.append("<p style='color:#aaa;font-size:12px'>仅为程序模拟，不会真实下单。</p></div>")
        def worker():
            try:
                result = push_wechat("股·收盘持仓汇总", "".join(parts))
                if result.get("code") != 200:
                    raise RuntimeError("PushPlus返回码 {}".format(result.get("code")))
                self.state["summary_pushes"][marker] = now.strftime("%Y-%m-%d %H:%M")
                self.save_state()
            except Exception as exc:
                self.record("收盘持仓汇总推送失败：{}".format(exc))
                self.save_state()
        threading.Thread(target=worker, daemon=True).start()

    def push_trade_alerts(self, alerts):
        # 微信推送成交提醒（HTML，附推荐计划），放后台线程避免卡界面
        kind_style = {
            "buy": ("模拟买入成交", "#16a34a"),
            "tp1": ("到达止盈1（卖出一半）", "#d97706"),
            "tp2": ("到达止盈2/追踪止盈（清仓）", "#0d9488"),
            "stop": ("触发止损（清仓）", "#dc2626"),
            "rescreen": ("到期重新筛选", "#3b82f6"),
            "opportunity": ("大涨机会提示", "#8b5cf6"),
            "expire": ("计划到期/移除", "#6b7280"),
        }
        # 标题一眼看出：什么股、什么操作、什么价
        title_action = {"buy": "买入", "tp1": "止盈卖半", "tp2": "止盈清仓", "stop": "止损清仓",
                        "rescreen": "重新筛选", "opportunity": "机会提示", "expire": "计划到期"}

        def one_line(ev):
            name = self.effective_plan(ev["code"])["name"]
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
            plan = self.effective_plan(ev["code"])
            title, color = kind_style.get(ev["kind"], ("交易提醒", "#333"))
            parts.append("<hr style='border:none;border-top:1px solid #eee'>")
            parts.append("<h3 style='color:{};margin:8px 0 4px'>{} · {}</h3>".format(
                color, title, plan["name"]))
            position = self.state["positions"].get(ev["code"])
            current_price = ev.get("price", position["buy_price"] if position else 0)
            position_value = (position["shares"] * current_price if position else
                              ev.get("position_value", 0))
            parts.append("<p style='margin:2px 0'>该股票浮盈：<b>{:+.2f} 元（{:+.2f}%）</b>；持仓市值：{:.2f} 元</p>".format(
                ev.get("position_pnl", 0), ev.get("position_pnl_pct", 0), position_value))
            parts.append("<p style='margin:2px 0'>{}</p>".format(ev["text"]))
            if ev["kind"] in ("buy", "tp1", "tp2", "stop"):
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
        total_asset = self.state.get("last_asset", 0)
        total_pnl = alerts[-1].get("total_pnl", total_asset - SIM_CAPITAL)
        parts.append("<p style='margin:4px 0'>本金：<b>{:.0f} 元</b>；整体浮盈：<b>{:+.2f} 元</b>；当前总资产：<b>{:.2f} 元</b></p>".format(
            SIM_CAPITAL, total_pnl, total_asset))
        if self.state["positions"]:
            parts.append("<p style='margin:4px 0'><b>全部持仓浮盈</b></p>")
            parts.append("<table style='border-collapse:collapse;font-size:13px'><tr><th style='padding:2px 10px'>股票</th><th style='padding:2px 10px'>持仓市值</th><th style='padding:2px 10px'>浮盈</th><th style='padding:2px 10px'>收益率</th></tr>")
            for code, pos in self.state["positions"].items():
                cur = self.state.get("last_quotes", {}).get(code, {})
                cur_price = cur.get("current", pos["buy_price"]) if cur else pos["buy_price"]
                val = pos["shares"] * cur_price
                cost = pos["shares"] * pos["buy_price"]
                pnl = val - cost
                pct = pnl / cost * 100 if cost else 0
                parts.append("<tr><td style='padding:2px 10px'>{}</td><td style='padding:2px 10px'>{:.2f}</td><td style='padding:2px 10px'><b>{:+.2f}</b></td><td style='padding:2px 10px'>{:+.2f}%</td></tr>".format(
                    self.effective_plan(code)["name"], val, pnl, pct))
            parts.append("</table>")
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
            self.effective_plan(code)["name"], shares, price, reason, pnl)
        self.record(action, code=code, action="sell", price=price, shares=shares,
                    value=proceeds, pnl=pnl, reason=reason,
                    plan_version=self.state.get("plan_id", PLAN_ID))
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
        plan_id = self.state.get("plan_id", PLAN_ID)
        plan_date = self.state.get("plan_date", PLAN_DATE)
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
            plan = self.effective_plan(code)
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
            ep = self.effective_plan(code)
            buy_mid = (ep["buy_low"] + ep["buy_high"]) / 2
            shares = int(budget_each // buy_mid // 100) * 100
            # 止盈2的预期盈利：按"一半止盈1、一半止盈2"估算
            half = shares // 2
            win = half * (ep["tp1"] - buy_mid) + (shares - half) * (ep["tp2"] - buy_mid)
            loss = shares * (buy_mid - ep["stop"])
            expected_win += win
            expected_loss += loss
            plan_lines.append(
                "| {name} | {code} | {lo:.2f}-{hi:.2f} | {buy_mid:.2f} "
                "| {stop:.2f}（{stop_pct:+.1f}%）"
                " | {tp1:.2f}（{tp1_pct:+.1f}%） | {tp2:.2f}（{tp2_pct:+.1f}%）"
                " | {shares} | 盈利约 {win:+.0f} 元 / 亏损约 {loss:.0f} 元 |".format(
                    name=ep["name"], code=code[-6:],
                    lo=ep["buy_low"], hi=ep["buy_high"], buy_mid=buy_mid,
                    stop=ep["stop"], stop_pct=(ep["stop"] - buy_mid) / buy_mid * 100,
                    tp1=ep["tp1"], tp1_pct=(ep["tp1"] - buy_mid) / buy_mid * 100,
                    tp2=ep["tp2"], tp2_pct=(ep["tp2"] - buy_mid) / buy_mid * 100,
                    shares=shares, win=win, loss=-loss))

        lines = [
            "# A 股月内模拟交易报告", "",
            "> 仅为程序模拟，不会真实下单；行情来自公开接口，价格和结果仅供研究。", "",
            "- 计划期：{}".format(plan_id),
            "- 计划制定日期：{}".format(plan_date),
            "- 模拟有效期：{} 至 {}".format(start, end),
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
            "## 实时行情与计划状态", "",
            "| 股票 | 代码 | 最新价 | 24h涨跌 | 计划状态 |",
            "|---|---:|---:|---:|---|",
        ])
        for code, plan in SIM_PLANS.items():
            ep = self.effective_plan(code)
            quote = quotes.get(code)
            if not quote:
                lines.append("| {} | {} | - | - | 暂无行情 |".format(ep["name"], code[-6:]))
                continue
            current = quote["current"]
            if current <= ep["stop"]:
                status = "已到止损位"
            elif current >= ep["tp2"]:
                status = "已到止盈2"
            elif current >= ep["tp1"]:
                status = "已到止盈1"
            elif current < ep["buy_low"]:
                status = "低于买入区间"
            elif current <= ep["buy_high"]:
                status = "买入区间内"
            else:
                status = "高于买入区间，等回调"
            lines.append("| {} | {} | {:.2f} | {:+.2f}% | {} |".format(
                ep["name"], code[-6:], current, quote["pct"], status))
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
            directory = os.path.join(SIM_REPORT_ARCHIVE_DIR, self.state.get("plan_id") or PLAN_ID, period)
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
