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
REVIEW_DIR = os.path.join(BASE_DIR, "crypto_reviews")
SIM_CAPITAL = float(PLAN_CONFIG["capital"])
PUSHPLUS_TOKEN = "e39674189a874c48888292f80e0c3464"
PUSHPLUS_URL = "https://www.pushplus.plus/send"
BINANCE = "https://data-api.binance.vision"
PLAN_ID = PLAN_CONFIG["plan_id"]
PLAN_DATE = PLAN_CONFIG["plan_date"]
PLANS = PLAN_CONFIG["plans"]

# 动态调整参数（固定策略参数，不随风格变化）
COOLDOWN_HOURS = 48          # 止损清仓后冷却小时数
OPPORTUNITY_THRESHOLD = 0.10 # 未建仓但远离买点10%触发机会提示
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


# ====== 交易风格驱动体系 ======
# 用户只需指定风格，所有参数自动推导

STYLE_PROFILES = {
    "超短线": {
        "desc": "1-3天，抓短线爆发",
        "kline_interval": "1h",    # 1小时K线
        "atr_period": 24,           # 24小时ATR
        "ema_short": 24,            # 24小时EMA
        "ema_long": 48,             # 48小时EMA
        "rsi_period": 14,
        "fib_lookback": 480,        # 20天×24小时高低点（最少20天）
        "stop_atr_mult": 1.5,       # 止损=1.5×ATR
        "tp1_atr_mult": 2.0,        # 止盈1=2×ATR
        "tp2_atr_mult": 3.5,        # 止盈2=3.5×ATR
        "valid_days": 3,            # 计划有效期3天
        "tranche_spacing": 0.5,    # 批次间距=0.5×ATR
        "poll_seconds": 60,         # 1分钟轮询
    },
    "短线": {
        "desc": "1-2周，波段交易",
        "kline_interval": "4h",     # 4小时K线
        "atr_period": 30,           # 30根4h K线≈5天ATR
        "ema_short": 30,            # 30根EMA
        "ema_long": 90,             # 90根≈15天EMA
        "rsi_period": 14,
        "fib_lookback": 120,        # 120根4h≈20天高低点（最少20天）
        "stop_atr_mult": 2.0,
        "tp1_atr_mult": 3.0,
        "tp2_atr_mult": 5.0,
        "valid_days": 14,
        "tranche_spacing": 1.0,
        "poll_seconds": 120,
    },
    "中线": {
        "desc": "1-3月，趋势跟踪",
        "kline_interval": "1d",     # 日线
        "atr_period": 30,           # 30天ATR
        "ema_short": 30,            # 30日EMA
        "ema_long": 60,             # 60日EMA
        "rsi_period": 14,
        "fib_lookback": 90,         # 90天高低点（3个月）
        "stop_atr_mult": 3.0,
        "tp1_atr_mult": 5.0,
        "tp2_atr_mult": 8.0,
        "valid_days": 90,
        "tranche_spacing": 1.5,
        "poll_seconds": 300,        # 5分钟轮询
    },
    "长线": {
        "desc": "3-12月，长周期布局",
        "kline_interval": "1d",     # 日线（周线辅助确认）
        "atr_period": 60,           # 60天ATR
        "ema_short": 50,            # 50日EMA
        "ema_long": 120,            # 120日EMA
        "rsi_period": 14,
        "fib_lookback": 365,        # 365天高低点（1年）
        "stop_atr_mult": 4.0,
        "tp1_atr_mult": 8.0,
        "tp2_atr_mult": 15.0,
        "valid_days": 365,
        "tranche_spacing": 2.0,
        "poll_seconds": 600,        # 10分钟轮询
    },
}


def get_style_profile():
    """从plan.json读取风格，默认短线"""
    style = PLAN_CONFIG.get("style", "短线")
    return STYLE_PROFILES.get(style, STYLE_PROFILES["短线"]), style


STYLE, STYLE_NAME = get_style_profile()

# 风格驱动的参数（不再硬编码）
POLL_SECONDS = STYLE["poll_seconds"]
PLAN_VALID_DAYS = STYLE["valid_days"]
TRAILING_TP_PCT = 0.04 + STYLE["stop_atr_mult"] * 0.02  # 追踪止盈回撤比例，随风格波动率自适应


# ====== 多时间框架技术分析 ======

def calc_ema(closes, period):
    """指数移动平均"""
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema


def calc_atr(klines, period=None):
    """ATR（真实波动幅度），period默认用风格配置"""
    if period is None:
        period = STYLE["atr_period"]
    if len(klines) < period + 1:
        period = len(klines) - 1
    if period < 5:
        return None
    trs = []
    for i in range(1, len(klines)):
        k = klines[i]
        prev_close = float(klines[i - 1][4])
        high = float(k[2])
        low = float(k[3])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period


def calc_rsi(klines, period=None):
    """RSI相对强弱指标，period默认用风格配置"""
    if period is None:
        period = STYLE["rsi_period"]
    closes = [float(k[4]) for k in klines]
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_fibonacci(klines, lookback=None):
    """斐波那契回调位：取最近一波行情的高低点"""
    if lookback is None:
        lookback = STYLE["fib_lookback"]
    n = min(lookback, len(klines))
    highs = [float(k[2]) for k in klines[-n:]]
    lows = [float(k[3]) for k in klines[-n:]]
    recent_high = max(highs)
    recent_low = min(lows)
    high_idx = n - 1 - highs[::-1].index(recent_high)
    low_idx = n - 1 - lows[::-1].index(recent_low)
    diff = recent_high - recent_low
    if diff <= 0:
        return None
    direction = "up" if high_idx > low_idx else "down"
    if direction == "up":
        return {
            "direction": "up", "high": recent_high, "low": recent_low,
            "0.236": recent_high - diff * 0.236,
            "0.382": recent_high - diff * 0.382,
            "0.5": recent_high - diff * 0.5,
            "0.618": recent_high - diff * 0.618,
            "0.786": recent_high - diff * 0.786,
        }
    else:
        return {
            "direction": "down", "high": recent_high, "low": recent_low,
            "0.236": recent_low + diff * 0.236,
            "0.382": recent_low + diff * 0.382,
            "0.5": recent_low + diff * 0.5,
            "0.618": recent_low + diff * 0.618,
            "0.786": recent_low + diff * 0.786,
        }


def find_swing_levels(klines, lookback=None):
    """识别关键支撑阻力位"""
    if lookback is None:
        lookback = min(STYLE["fib_lookback"], 20)
    highs = [float(k[2]) for k in klines[-lookback:]]
    lows = [float(k[3]) for k in klines[-lookback:]]
    return {
        "resistance": max(highs),
        "support": min(lows),
        "swing_highs": sorted(set(highs), reverse=True)[:3],
        "swing_lows": sorted(set(lows))[:3],
    }


def detect_candle_patterns(klines):
    """裸K形态识别"""
    if len(klines) < 3:
        return []
    patterns = []
    k = klines[-1]
    prev = klines[-2]
    o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
    po, ph, pl, pc = float(prev[1]), float(prev[2]), float(prev[3]), float(prev[4])
    body = abs(o - c)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    range_total = h - l
    if range_total <= 0:
        return []
    # 看涨Pin bar（长下影线）
    if lower_wick > body * 2 and lower_wick > upper_wick * 2:
        patterns.append("看涨Pin bar")
    # 看跌Pin bar（长上影线）
    if upper_wick > body * 2 and upper_wick > lower_wick * 2:
        patterns.append("看跌Pin bar")
    # 看涨吞没
    if c > po and o < pc and c > o and pc < po:
        patterns.append("看涨吞没")
    # 看跌吞没
    if c < po and o > pc and c < o and pc > po:
        patterns.append("看跌吞没")
    # 锤子线（底部反转）
    if lower_wick > body * 2 and upper_wick < body * 0.5:
        patterns.append("锤子线")
    # 射击之星（顶部反转）
    if upper_wick > body * 2 and lower_wick < body * 0.5:
        patterns.append("射击之星")
    return patterns


def analyze_trend(klines):
    """判断趋势方向：bull/bear/range，EMA周期由风格决定"""
    closes = [float(k[4]) for k in klines]
    es, el = STYLE["ema_short"], STYLE["ema_long"]
    if len(closes) < es:
        return "unknown"
    ema_short = calc_ema(closes, es)
    current = closes[-1]
    if not ema_short:
        return "unknown"
    if len(closes) >= el:
        ema_long = calc_ema(closes, el)
        if ema_long and ema_short > ema_long and current > ema_short:
            return "bull"
        if ema_long and ema_short < ema_long and current < ema_short:
            return "bear"
    if current > ema_short:
        return "bull_weak"
    return "range"


def calc_momentum(symbol):
    try:
        k15 = fetch_klines(symbol, "1d", 16)
        k30 = fetch_klines(symbol, "1d", 31)
        pct_15d = (float(k15[-1][4]) - float(k15[0][4])) / float(k15[0][4])
        pct_30d = (float(k30[-1][4]) - float(k30[0][4])) / float(k30[0][4])
        return {"pct_15d": pct_15d, "pct_30d": pct_30d}
    except Exception:
        return {"pct_15d": 0.0, "pct_30d": 0.0}


def check_btc_crash():
    """BTC暴跌过滤器：20日EMA 5天内跌幅>5%才拦截，盘整不拦"""
    try:
        klines = fetch_klines("BTCUSDT", "1d", 50)
        closes = [float(k[4]) for k in klines]
        if len(closes) < 25:
            return False
        ema20_now = calc_ema(closes, 20)
        ema20_5ago = calc_ema(closes[:-5], 20)
        if not ema20_now or not ema20_5ago or ema20_5ago <= 0:
            return False
        slope = (ema20_now - ema20_5ago) / ema20_5ago
        return slope < -0.05
    except Exception:
        return False


def analyze_symbol(symbol):
    """综合多时间框架技术分析，所有参数由交易风格驱动"""
    interval = STYLE["kline_interval"]
    try:
        # 主时间框架：按风格选择K线周期
        klines = fetch_klines(symbol, interval, max(STYLE["fib_lookback"], STYLE["ema_long"] + STYLE["atr_period"] + 10))
        # 辅助：日线始终获取用于多时间框架确认
        daily = fetch_klines(symbol, "1d", 60)
        weekly = fetch_klines(symbol, "1w", 26)
    except Exception:
        return None
    if not klines or len(klines) < max(STYLE["ema_short"], 10):
        return None

    current_price = float(klines[-1][4])
    atr = calc_atr(klines)
    rsi = calc_rsi(klines)
    fib = calc_fibonacci(klines)
    swings = find_swing_levels(klines)
    patterns = detect_candle_patterns(klines)
    trend_main = analyze_trend(klines)
    # 日线和周线作为辅助趋势确认
    trend_d = analyze_trend(daily) if daily and len(daily) >= 20 else "unknown"
    trend_w = analyze_trend(weekly) if weekly and len(weekly) >= 20 else "unknown"

    if not atr or atr <= 0:
        return None

    atr_pct = atr / current_price

    # 买点：斐波那契0.382-0.618回调区间，或ATR回撤
    if fib and fib["direction"] == "up":
        buy_zone_high = fib["0.382"]
        buy_zone_low = fib["0.618"]
    else:
        buy_zone_high = current_price - atr * STYLE["tranche_spacing"]
        buy_zone_low = current_price - atr * STYLE["tranche_spacing"] * 2

    # 止损：斐波那契0.786下方 或 买点下方-0.5×ATR
    if fib:
        stop = min(fib["0.786"], buy_zone_low - atr * 0.5)
    else:
        stop = buy_zone_low - atr * 0.5

    # 止盈：由风格乘数决定
    tp1 = current_price + atr * STYLE["tp1_atr_mult"]
    tp2 = current_price + atr * STYLE["tp2_atr_mult"]

    # 分批买点
    tranche1 = round_price(buy_zone_high)
    tranche2 = round_price((buy_zone_high + buy_zone_low) / 2)
    tranche3 = round_price(buy_zone_low)

    # 趋势评分：多时间框架对齐
    trend_score = 0
    # 周线权重最高（2分），日线次之（2分），主时间框架（2分）
    if trend_w == "bull":
        trend_score += 2
    elif trend_w == "bull_weak":
        trend_score += 1
    if trend_d == "bull":
        trend_score += 2
    elif trend_d == "bull_weak":
        trend_score += 1
    if trend_main == "bull":
        trend_score += 2
    elif trend_main == "bull_weak":
        trend_score += 1

    # 是否适合建仓
    can_buy = (
        trend_main not in ("bear",) and
        trend_d not in ("bear",) and
        trend_w not in ("bear",) and
        trend_score >= 2 and
        rsi < 65  # 不在严重超买区追高
    )

    has_bullish_pattern = any(p in ("看涨Pin bar", "看涨吞没", "锤子线") for p in patterns)

    return {
        "current_price": current_price,
        "atr": atr,
        "atr_pct": atr_pct,
        "rsi": rsi,
        "trend": {"main": trend_main, "daily": trend_d, "weekly": trend_w},
        "trend_score": trend_score,
        "fibonacci": fib,
        "swings": swings,
        "patterns": patterns,
        "can_buy": can_buy,
        "has_bullish_pattern": has_bullish_pattern,
        "buy_zone": {"high": buy_zone_high, "low": buy_zone_low},
        "tranches": [
            {"price": tranche1, "pct": 0.5},
            {"price": tranche2, "pct": 0.3},
            {"price": tranche3, "pct": 0.2},
        ],
        "stop": round_price(stop),
        "tp1": round_price(tp1),
        "tp2": round_price(tp2),
    }


def generate_dynamic_plan(symbol, current_price, name, logic=""):
    """基于综合技术分析生成动态计划，所有参数由交易风格驱动"""
    analysis = analyze_symbol(symbol)
    if analysis:
        return {
            "name": name,
            "style": STYLE_NAME,
            "tranches": analysis["tranches"],
            "stop": analysis["stop"],
            "tp1": analysis["tp1"],
            "tp2": analysis["tp2"],
            "logic": "[{}] 主框架{} 日线{} 周线{}；ATR {:.4f}({:.2%})；RSI {:.1f}；趋势评分{}；斐波那契{}；裸K{}；{}".format(
                STYLE_NAME,
                analysis["trend"]["main"], analysis["trend"]["daily"], analysis["trend"]["weekly"],
                analysis["atr"], analysis["atr_pct"], analysis["rsi"], analysis["trend_score"],
                "回调" + analysis["fibonacci"]["direction"] if analysis["fibonacci"] else "无",
                "/".join(analysis["patterns"]) if analysis["patterns"] else "无明显形态",
                logic),
            "start_date": dt.date.today().isoformat(),
            "atr": analysis["atr"],
            "trend_score": analysis["trend_score"],
        }
    # 降级：用简单ATR
    try:
        klines = fetch_klines(symbol, STYLE["kline_interval"], STYLE["atr_period"] + 5)
        atr = calc_atr(klines) or current_price * 0.05
    except Exception:
        atr = current_price * 0.05
    return {
        "name": name,
        "style": STYLE_NAME,
        "tranches": [
            {"price": round_price(current_price - atr * STYLE["tranche_spacing"]), "pct": 0.5},
            {"price": round_price(current_price - atr * STYLE["tranche_spacing"] * 1.5), "pct": 0.3},
            {"price": round_price(current_price - atr * STYLE["tranche_spacing"] * 2), "pct": 0.2},
        ],
        "stop": round_price(current_price - atr * (STYLE["stop_atr_mult"] + 0.5)),
        "tp1": round_price(current_price + atr * STYLE["tp1_atr_mult"]),
        "tp2": round_price(current_price + atr * STYLE["tp2_atr_mult"]),
        "logic": "[{}] 降级ATR计划：{}".format(STYLE_NAME, logic),
        "start_date": dt.date.today().isoformat(),
        "atr": atr,
        "trend_score": 0,
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
        # 取前10名做综合分析
        for c in candidates[:10]:
            analysis = analyze_symbol(c["symbol"])
            if analysis and analysis["trend_score"] >= 2:
                c["trend_score"] = analysis["trend_score"]
                c["atr_pct"] = analysis["atr_pct"]
                c["rsi"] = analysis["rsi"]
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
                state.setdefault("review_pushed", {})
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
            "review_pushed": {},
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

    def check_monthly_review(self):
        """每月15号和30号自动生成复盘报告"""
        now = dt.datetime.now()
        day = now.day
        # 判断是否复盘日：15号、30号、或短月最后一天（>=28号且次日为下月1号）
        if day == 15:
            marker = now.strftime("%Y-%m-15")
            start_day, end_day = 1, 15
        elif day == 30:
            marker = now.strftime("%Y-%m-30")
            start_day, end_day = 16, 30
        else:
            tomorrow = (now + dt.timedelta(days=1)).date()
            if tomorrow.day == 1 and day >= 28:
                marker = now.strftime("%Y-%m-EOM")
                start_day, end_day = 16, day
            else:
                return
        if self.state.get("review_pushed", {}).get(marker):
            return
        year, month = now.year, now.month
        start = dt.date(year, month, start_day).isoformat()
        end = dt.date(year, month, end_day).isoformat()
        self.generate_review_report(start, end, marker)
        self.state.setdefault("review_pushed", {})[marker] = now.strftime("%Y-%m-%d %H:%M")
        self.save_state()

    def generate_review_report(self, start, end, marker):
        """生成策略复盘报告并写入独立文件"""
        # 收集区间内卖出记录
        sells = []
        for trade in self.state.get("trades", []):
            if trade.get("action") != "sell":
                continue
            day = trade.get("time", "")[:10]
            if start <= day <= end:
                sells.append(trade)
        wins = [t for t in sells if t.get("pnl", 0) > 0]
        losses = [t for t in sells if t.get("pnl", 0) < 0]
        profit = sum(t.get("pnl", 0) for t in wins)
        loss = sum(t.get("pnl", 0) for t in losses)
        total_pnl = sum(t.get("pnl", 0) for t in sells)
        win_rate = len(wins) / len(sells) * 100 if sells else 0
        avg_win = profit / len(wins) if wins else 0
        avg_loss = loss / len(losses) if losses else 0
        pl_ratio = profit / abs(loss) if loss else 0

        # 当前持仓浮动盈亏
        quotes = self.state.get("last_quotes", {})
        open_positions = []
        for symbol, pos in self.state.get("positions", {}).items():
            price = quotes.get(symbol, {}).get("price", pos["cost"] / pos["amount"] if pos["amount"] else 0)
            value = pos["amount"] * price
            pnl = value - pos["cost"]
            open_positions.append({
                "name": self.effective_plan(symbol)["name"],
                "pnl": pnl,
                "pct": pnl / pos["cost"] * 100 if pos["cost"] else 0,
                "cost": pos["cost"], "value": value})

        # 机会提示次数（未建仓但大涨）
        opportunity_count = sum(1 for t in self.state.get("trades", [])
                                if t.get("action") == "opportunity"
                                and start <= t.get("time", "")[:10] <= end)
        # 计划到期/移除次数
        expired = sum(1 for t in self.state.get("trades", [])
                      if t.get("action") == "expire"
                      and start <= t.get("time", "")[:10] <= end)
        # 止损清仓次数
        stop_count = sum(1 for t in sells if "止损" in t.get("reason", "") or t.get("kind") == "stop")
        # 止盈清仓次数
        tp2_count = sum(1 for t in sells if "止盈" in t.get("reason", "") or t.get("kind") == "tp2")

        now = dt.datetime.now()
        lines = [
            "# 加密货币策略复盘报告 · {}".format(now.strftime("%Y-%m-%d")),
            "",
            "> 复盘区间：{} 至 {}".format(start, end),
            "> 计划期：{}".format(self.state.get("plan_id", PLAN_ID)),
            "> 生成时间：{}".format(now.strftime("%Y-%m-%d %H:%M:%S")),
            "",
            "## 一、交易统计",
            "",
            "| 指标 | 数值 |",
            "|---|---:|",
            "| 完成卖出笔数 | {} |".format(len(sells)),
            "| 盈利笔数 | {} |".format(len(wins)),
            "| 亏损笔数 | {} |".format(len(losses)),
            "| 胜率 | {:.1f}% |".format(win_rate),
            "| 已实现盈亏 | {:+.2f} USDT |".format(total_pnl),
            "| 平均盈利 | {:+.2f} USDT |".format(avg_win),
            "| 平均亏损 | {:+.2f} USDT |".format(avg_loss),
            "| 盈亏比 | {:.2f} |".format(pl_ratio),
            "| 止损清仓次数 | {} |".format(stop_count),
            "| 止盈清仓次数 | {} |".format(tp2_count),
            "| 机会提示次数 | {} |".format(opportunity_count),
            "| 计划到期/移除 | {} |".format(expired),
            "",
        ]

        # 各币种明细
        all_symbols = set(PLANS.keys()) | set(self.state.get("dynamic_plans", {}).keys())
        lines += ["## 二、各币种表现", "",
                  "| 币种 | 卖出笔数 | 盈利 | 亏损 | 已实现盈亏 |",
                  "|---|---:|---:|---:|---:|"]
        for symbol in all_symbols:
            items = [t for t in sells if t.get("symbol") == symbol]
            if items:
                lines.append("| {} | {} | {} | {} | {:+.2f} |".format(
                    self.effective_plan(symbol)["name"], len(items),
                    sum(t.get("pnl", 0) > 0 for t in items),
                    sum(t.get("pnl", 0) < 0 for t in items),
                    sum(t.get("pnl", 0) for t in items)))
        if not sells:
            lines.append("| 无交易记录 | - | - | - | - |")

        # 持仓浮动盈亏
        if open_positions:
            lines += ["", "## 三、当前持仓浮动盈亏", "",
                      "| 币种 | 投入成本 | 当前市值 | 浮动盈亏 | 收益率 |",
                      "|---|---:|---:|---:|---:|"]
            for p in open_positions:
                lines.append("| {} | {:.2f} | {:.2f} | {:+.2f} | {:+.2f}% |".format(
                    p["name"], p["cost"], p["value"], p["pnl"], p["pct"]))

        # 策略优点分析
        lines += ["", "## 四、策略优点", ""]
        pros = []
        if sells and win_rate >= 50:
            pros.append("胜率 {:.1f}% 表现良好，多空判断方向准确。".format(win_rate))
        if pl_ratio and pl_ratio >= 1.5:
            pros.append("盈亏比 {:.2f}，盈利时幅度大于亏损，截亏让盈策略有效。".format(pl_ratio))
        if tp2_count > 0:
            pros.append("止盈2清仓 {} 次，趋势跟踪成功捕获到较大涨幅。".format(tp2_count))
        if total_pnl > 0:
            pros.append("本期已实现盈亏 {:+.2f} USDT，整体盈利。".format(total_pnl))
        pros.append("自动化轮询执行消除了情绪干扰，严格执行止损止盈纪律。")
        pros.append("分批建仓（50%/30%/20%）降低了择时风险，平均成本更优。")
        if opportunity_count > 0:
            pros.append("机会提示机制触发 {} 次，有效识别了未建仓但行情启动的标的。".format(opportunity_count))
        pros.append("止损清仓后48小时冷却机制避免了频繁追涨杀跌。")
        for p in pros:
            lines.append("- {}".format(p))

        # 策略缺点分析
        lines += ["", "## 五、策略缺点", ""]
        cons = []
        if sells and win_rate < 40:
            cons.append("胜率仅 {:.1f}%，买点判断偏乐观，回调幅度可能不够。".format(win_rate))
        if loss and abs(avg_loss) > avg_win and avg_win > 0:
            cons.append("平均亏损 {:+.2f} 大于平均盈利 {:+.2f}，止损偏松或止盈偏紧。".format(avg_loss, avg_win))
        if stop_count > len(sells) * 0.6 if sells else False:
            cons.append("止损清仓占比 {:.0f}%，止损可能过于密集。".format(stop_count / len(sells) * 100))
        if expired > 2:
            cons.append("计划到期/移除 {} 次，买点设置可能过于保守，错失行情。".format(expired))
        if opportunity_count > 3:
            cons.append("机会提示 {} 次但未建仓，趋势过滤条件可能过严。".format(opportunity_count))
        if not sells:
            cons.append("本期无完成卖出，交易频率偏低，策略参数可能不适配当前行情。")
        if total_pnl < 0:
            cons.append("本期已实现盈亏 {:+.2f} USDT，整体亏损，需审视买点和止损参数。".format(total_pnl))
        for c in cons:
            lines.append("- {}".format(c))
        if not cons:
            lines.append("- 暂未发现明显缺陷。")

        # 改进建议
        lines += ["", "## 六、改进建议", ""]
        suggestions = []
        if sells and win_rate < 40:
            suggestions.append("适当放宽买入回调幅度（如从3-6%扩至4-7%），降低买入后被止损概率。")
        if loss and abs(avg_loss) > avg_win and avg_win > 0:
            suggestions.append("收紧止损距离或放宽止盈距离，使盈亏比回升至1.5以上。")
        if expired > 2:
            suggestions.append("降低买点保守度或缩短计划有效期，减少过期未触发的情况。")
        if opportunity_count > 3:
            suggestions.append("适度放宽趋势评分门槛，让更多机会转化为实际建仓。")
        if not sells:
            suggestions.append("检查当前风格参数是否匹配行情节奏，考虑切换风格或调整标的。")
        if total_pnl < 0:
            suggestions.append("复盘止损标的的行情特征，下一期计划剔除类似走势的标的。")
        suggestions.append("持续累积样本数据，样本数达到20笔以上再考虑调整核心参数。")
        for s in suggestions:
            lines.append("- {}".format(s))

        lines += ["", "## 七、优化纪律", "",
                  "- 先累计样本再调参：单个周期完成卖出少于20笔时，只记录不改核心规则。",
                  "- 优化目标同时看胜率、盈亏比、期望值和最大回撤，不能只看一笔输赢。",
                  "- 若连续样本显示止损过密或买点过高，下一版计划只微调买入回撤、止损距离和仓位批次。",
                  "", "> 仅为程序模拟复盘，不构成投资建议。"]

        os.makedirs(REVIEW_DIR, exist_ok=True)
        filename = "复盘_{}_币.md".format(now.strftime("%Y-%m-%d"))
        filepath = os.path.join(REVIEW_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("[{}] 复盘报告已生成：{}".format(now.strftime("%m-%d %H:%M"), filepath))

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

        # BTC暴跌过滤器：盘整不拦，只有暴跌才拦
        btc_crashing = check_btc_crash()

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

                # BTC暴跌时只卖不买
                if btc_crashing:
                    continue

                days = (dt.date.today() - dt.date.fromisoformat(ep.get("start_date") or self.state["start_date"])).days
                buy_high = ep["tranches"][0]["price"]

                # 计划到期：用多时间框架重新分析
                if days >= PLAN_VALID_DAYS:
                    analysis = analyze_symbol(symbol)
                    if analysis and analysis["can_buy"]:
                        if not self.state.get("rescreened", {}).get(symbol):
                            new_plan = generate_dynamic_plan(
                                symbol, price, plan["name"], plan.get("logic", ""))
                            self.state.setdefault("dynamic_plans", {})[symbol] = new_plan
                            self.state.setdefault("rescreened", {})[symbol] = True
                            ep = new_plan
                            buy_high = ep["tranches"][0]["price"]
                            events.append({
                                "symbol": symbol, "kind": "rescreen",
                                "msg": "到期重新分析：日线{} 周线{} 月线{}；ATR {:.4f}({:.2%})；RSI {:.1f}；趋势评分{}；已生成新买点（{}/{}/{}, 止损{}, 止盈{}/{}, {}）".format(
                                    analysis["trend"]["daily"], analysis["trend"]["weekly"], analysis["trend"]["monthly"],
                                    analysis["atr"], analysis["atr_pct"], analysis["rsi"], analysis["trend_score"],
                                    ep["tranches"][0]["price"], ep["tranches"][1]["price"], ep["tranches"][2]["price"],
                                    ep["stop"], ep["tp1"], ep["tp2"],
                                    "看涨形态:" + "/".join(analysis["patterns"]) if analysis["patterns"] else "无明显形态")})
                    elif analysis and not analysis["can_buy"]:
                        if days >= PLAN_VALID_DAYS + EXTENDED_OBSERVATION_DAYS:
                            self.state["plan_expired"][symbol] = True
                            events.append({
                                "symbol": symbol, "kind": "expire",
                                "msg": "到期后持续观察 {} 天，趋势评分{}（日线{} 周线{} 月线{}），不适合建仓，移出本期".format(
                                    EXTENDED_OBSERVATION_DAYS,
                                    analysis["trend_score"],
                                    analysis["trend"]["daily"], analysis["trend"]["weekly"], analysis["trend"]["monthly"])})
                            self.try_replacement(symbol, plan["name"], events)
                            continue
                        else:
                            today_str = now.date().isoformat()
                            observe_key = symbol + "_observe"
                            if self.state.get("opportunity_pushed", {}).get(observe_key) != today_str:
                                self.state.setdefault("opportunity_pushed", {})[observe_key] = today_str
                                events.append({
                                    "symbol": symbol, "kind": "rescreen",
                                    "msg": "到期但暂不适合建仓（趋势评分{}，日线{} 周线{} RSI {:.1f}），持续观察中（第 {} 天）".format(
                                        analysis["trend_score"],
                                        analysis["trend"]["daily"], analysis["trend"]["weekly"],
                                        analysis["rsi"], days)})
                            continue
                    else:
                        # 分析失败，退回简单动量筛选
                        mom = calc_momentum(symbol)
                        has_momentum = (mom["pct_15d"] >= 0.03 or mom["pct_30d"] >= 0.06)
                        if has_momentum:
                            if not self.state.get("rescreened", {}).get(symbol):
                                new_plan = generate_dynamic_plan(
                                    symbol, price, plan["name"], plan.get("logic", ""))
                                self.state.setdefault("dynamic_plans", {})[symbol] = new_plan
                                self.state.setdefault("rescreened", {})[symbol] = True
                                ep = new_plan
                                buy_high = ep["tranches"][0]["price"]
                        else:
                            if days >= PLAN_VALID_DAYS + EXTENDED_OBSERVATION_DAYS:
                                self.state["plan_expired"][symbol] = True
                                events.append({
                                    "symbol": symbol, "kind": "expire",
                                    "msg": "到期后持续观察 {} 天仍无行情，移出本期".format(EXTENDED_OBSERVATION_DAYS)})
                                self.try_replacement(symbol, plan["name"], events)
                                continue
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
                        analysis = analyze_symbol(symbol)
                        if analysis and analysis["trend_score"] >= 2:
                            self.state.setdefault("opportunity_pushed", {})[opp_key] = today_str
                            events.append({
                                "symbol": symbol, "kind": "opportunity",
                                "msg": "价格 {:.4f} 已远离买点 {:.4f}（+{:.1f}%），趋势评分{}（日线{} 周线{}），RSI {:.1f}，关注回踩机会".format(
                                    price, buy_high, (price / buy_high - 1) * 100,
                                    analysis["trend_score"],
                                    analysis["trend"]["daily"], analysis["trend"]["weekly"],
                                    analysis["rsi"])})

                # 按分批买点建仓（仅当多时间框架允许建仓时）
                analysis = analyze_symbol(symbol)
                if analysis and analysis["can_buy"]:
                    for i, tr in enumerate(ep["tranches"]):
                        if price <= tr["price"]:
                            msg = self.buy_tranche(symbol, price, i, tr, budget_each)
                            if msg:
                                events.append({"symbol": symbol, "kind": "buy", "msg": msg})
                else:
                    # 趋势不允许建仓时，推送提示（每天最多1条）
                    today_str = now.date().isoformat()
                    block_key = symbol + "_block"
                    if analysis and self.state.get("opportunity_pushed", {}).get(block_key) != today_str:
                        self.state.setdefault("opportunity_pushed", {})[block_key] = today_str
                        events.append({
                            "symbol": symbol, "kind": "opportunity",
                            "msg": "价格在买点区间但趋势不允许建仓（评分{}，日线{} 周线{}，RSI {:.1f}），等待趋势确认".format(
                                analysis["trend_score"],
                                analysis["trend"]["daily"], analysis["trend"]["weekly"],
                                analysis["rsi"])})

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
        self.check_monthly_review()
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
