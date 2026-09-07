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

## Safety note

Always remind the user that stock trading involves risk and that levels are only reference levels, not certainty.
