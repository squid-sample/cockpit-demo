---
name: "stock-month-trader"
description: "Screens A-share stocks for 1-month trading setups with entry, stop-loss, and staggered take-profit levels. Invoke when the user asks for short-term stock recommendations or trade plans."
---

# Stock Month Trader

Use this skill when the user wants short-term A-share stock ideas with explicit buy/sell levels.

## Goal

Provide a concise trading plan for stocks expected to have actionable movement within about one month.

## What to output

For each candidate stock, include:
- Stock name and code
- Why it is on the list
- Suggested buy zone
- First take-profit zone
- Second take-profit zone
- Stop-loss level
- Whether the stock is suitable for users who cannot trade创业板/科创板

## Selection rules

Prefer:
- Main-board A-shares first
- Strong sector leaders
- Stocks with clear trend, volume support, and recent catalyst
- Stocks that match the user's account permissions

Avoid:
- Illiquid small caps
- Pure rumor-driven pumps
- Stocks requiring permissions the user does not have
- Promising guaranteed returns

## Response style

- Be direct and practical
- Use simple price ranges
- If the market is weak, say to wait instead of forcing a pick
- Do not claim the strategy can guarantee 8–10 points
- Frame 8–10 points only as a target range when conditions are favorable

## Suggested format

1. Overall view
2. Candidate list
3. Buy zone / sell zone / stop-loss table
4. Short conclusion

## 持续记录、分层报告与复盘优化

- 跟踪脚本持续保存状态和成交明细，不覆盖历史；每笔成交保留时间、股票名称、代码、动作、成交价、股数、金额、触发原因和计划版本。
- 报告按时间周期分层保存：主报告为 `scripts/stock_simulation_report.md`，日报为 `scripts/stock_reports/daily/YYYY-MM-DD.md`，周报为 `scripts/stock_reports/weekly/YYYY-Www.md`，月报为 `scripts/stock_reports/monthly/YYYY-MM.md`。
- 周期复盘至少统计完成卖出笔数、胜率、止盈/止损分布、已实现盈亏、平均盈利、平均亏损和盈亏比，并按股票、计划版本和信号类型拆分。
- 完成卖出少于 20 笔时只记录结果，不根据单笔交易修改买入区间、止损距离、止盈比例或持仓分配。
- 达到样本量后使用滚动时间窗口和样本外数据验证候选调整，同时检查胜率、盈亏比、期望值、最大回撤和收益稳定性；样本外表现恶化则不采用。
- 每次采用新规则递增计划版本并保留旧版本记录，避免只按胜率或单个强势股票调参造成过拟合。

## Safety note

Always remind the user that stock trading involves risk and that levels are only reference levels, not certainty.
