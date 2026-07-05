# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **QMT (迅投QMT) automated trading system** using the `xtquant` Python SDK. It implements a **small-cap stock rotation strategy** — holding the N smallest market-cap A-share stocks, rebalanced weekly on Tuesdays. During January and April (seasonal underperformance months), it switches to an all-weather ETF portfolio (gold, bond, Nasdaq, dividend ETFs).

## Key Files

| File | Platform | Scheduling | Role |
|------|----------|------------|------|
| `code/miniqmt_small_cap_0_1.py` | MiniQMT (`xtquant`) | APScheduler cron | **Main active strategy** — standalone script with cron-based task scheduling |
| `code/strategy_scheduler.py` | MiniQMT | APScheduler cron | **Process manager** — runs as a separate daemon; kills and restarts the strategy script on the first Friday evening of each month |
| `code/qmt_shipan.py` | Full QMT (`ContextInfo`) | `handlebar()` K-line callback | Full QMT version — bar-driven, meant for in-platform execution |
| `code/small_cap_1_0.py` | Full QMT (`ContextInfo`) | `handlebar()` K-line callback | Near-identical to `qmt_shipan.py` (duplicate variant) |
| `code/qmt_test.py` | Full QMT | N/A (utility) | Helper functions for printing position/order/deal/account info; full enum dictionaries (ENTRUST_STATUS_MAP, TASK_STATUS_MAP, PRICE_TYPE_MAP, etc.) |
| `code/login.py` + `code/login.ps1` | Both | Manual | Auto-login to QMT client using GUI automation |

## Architecture

### Two Platform Models

**MiniQMT (`miniqmt_small_cap_0_1.py`)**:
- Connects via `XtQuantTrader(path, session_id)` with `StockAccount('8885388757')`
- Uses `APScheduler` (`BackgroundScheduler`) to schedule 12 timed tasks at specific market hours
- All functions are module-level and access shared state via a global `g` object (instance of empty class `G`)
- Runs as a standalone Python process; logs to `code/logfiles/YYYYMMDD.log` via custom `Tee` class
- Uses `xtdata.get_full_tick()` for real-time prices and `xtdata.get_market_data_ex()` for historical data
- Order execution via `g.xt_trader.order_stock_async()` with `FIX_PRICE` (slightly above/below current price) or `MARKET_PEER_PRICE_FIRST`

**Full QMT (`qmt_shipan.py`, `small_cap_1_0.py`)**:
- Executed inside the QMT platform's Python runtime
- `init(ContextInfo)` → `handlebar(ContextInfo)` callback pattern (聚宽-style)
- Same strategy logic, but all functions take `ContextInfo` as first argument
- `ContextInfo` provides API: `get_market_data_ex()`, `get_trading_dates()`, `get_stock_name()`, `get_trade_detail_data()`, order functions, etc.
- Order execution via `order_target_value()` / `order_shares()` and confirmed via querying ORDER/DEAL data

**Process Manager (`strategy_scheduler.py`)**:
- Separate daemon process using its own `BackgroundScheduler`
- On the **first Friday evening of each month**: stops the strategy at 18:00, restarts it at 18:30
- Uses `taskkill /f /t` to kill the entire process tree, then verifies no orphan processes remain (3 checks at 5s intervals)
- Has a watchdog function (currently commented out) that would auto-restart if the strategy process crashes

### QMT Client Paths
- Installation: `C:\QMT\bin.x64\XtItClient.exe`
- MiniQMT data dir (production): `C:\QMT\国金证券QMT交易端\userdata_mini`
- MiniQMT data dir (fallback): `C:\QMT\userdata_mini`
- Trading account: `8885388757`

### Daily Task Schedule (MiniQMT)

```
09:30 judge_date()        — Check if trading day, set Jan/Apr no-trade flag
09:31 prepare_stock_list() — Build stock pool (中小综指 399101.SZ), check yesterday's limit-up holdings
09:35 trade_etf()          — If no-trade month, switch to all-weather ETFs (risk-parity via ES)
10:00 rebalance_sell()     — Weekly rebalance: select small-cap stocks by market cap, sell unwanted
10:15 stop_loss()          — Check stop-loss conditions, sell if triggered
10:30 rebalance_buy()      — Buy new stocks with equal-weight position sizing
14:00 check_limit_up()     — Sell holdings that hit limit-up intraday
14:02 check_remain_amount()— Verify all orders filled, retry if needed
15:01 info_position()      — Log final positions and daily P&L
15:10 closeQMT()           — Kill XtMiniQmt.exe (Fridays only)
18:00 reopenQMT()          — Restart QMT via login.py (Fridays only)
18:10 reconnect()          — Re-establish trading connection (Fridays only)
```

### Strategy Logic

1. **Stock selection**: `get_normal_stocks()` filters A-share stocks from 中小综指 (399101.SZ) — excludes ST, stocks with expiry dates, suspended stocks, and already limit-up/down stocks. Then `get_small_cap_stocks()` picks N smallest by total market cap with **industry diversification** via `small_cap_get_stock_industry()`: selects from top 100 by market cap, ensures each stock belongs to a different 申万二级 (SW2) industry sector.

2. **Position sizing**: Equal weight across all holdings, with adjustments for failed sells (suspended/limit-down stocks) and limit-up locked stocks via `calc_position()`. Uses a `position_step` parameter for tilt within the equal-weight framework.

3. **All-weather (Jan/Apr)**: Risk-parity weighting based on Expected Shortfall (ES) of daily returns over 120 days. ETFs: 黄金ETF (518880.SH), 城投ETF (511220.SH), 纳指ETF (513100.SH), 红利低波ETF (512890.SH). Otherwise holds 银华日利ETF (511880.SH).

4. **Stop-loss** (3 strategies selectable via `g.stoploss_strategy`):
   - Strategy 1: Fixed stop-loss line (`g.stoploss_limit`, default 10%)
   - Strategy 2: Market trend stop-loss — clears all positions if 中小综指 daily move ≥ `g.stoploss_market` (5%)
   - Strategy 3: Combined — both conditions must trigger
   - After stop-loss triggers on a stock, it's added to `g.stoploss_map` with a 3-day ban (decremented daily in `prepare_stock_list`); stocks with remaining ban days are excluded from `g.selected_stocks`

5. **Limit-up handling**: Stocks that hit limit-up yesterday are held (not sold during rebalance). Stocks that hit limit-up intraday are sold at 14:00 (`check_limit_up`).

6. **Buy/sell execution**: `buy_target_value()` / `sell_target_value()` use `FIX_PRICE` orders at `current_price ± 0.1` to avoid slippage. `DEBUG_DAILY_MODE` skips actual order placement. Market (对手价) orders used only for full liquidation.

### Global State (`g` object)

All strategy state lives on a shared `G()` instance. Key fields initialized in `init()`:
- `stock_num` (9), `weekday` (2=Tuesday), `stoploss_strategy` (3), `stoploss_limit` (0.1), `stoploss_market` (0.05)
- `trade` — false during Jan/Apr (no-trade months)
- `is_trading_day` — false on weekends/holidays (tasks return early)
- `stock_pool`, `selected_stocks`, `stocks_to_buy`, `stocks_to_sell`, `stocks_fail_sell`
- `yesterday_HL_list`, `today_HL_list` — limit-up tracking
- `stoploss_map` — dict of `{stock_code: days_remaining}`, 3-day ban list for stop-loss-triggered stocks
- `excepted_position` — target position weights per stock
- `industry_dict` — SW2 industry classification for all 中小综指 stocks
- `last_pos_value` — previous day's total asset value (for daily P&L calculation)

### Logging

- `Tee` class writes stdout to both console and `code/logfiles/YYYYMMDD.log`
- ANSI escape codes are stripped before writing to log files
- Daily log rotation via filename date
- `strategy_scheduler.py` has its own simple `log()` function printing to stdout with timestamps

### Login Automation

- `login.py` launches `XtItClient.exe`, then uses `pyautogui` to Alt+Tab to the QMT window
- `login.ps1` uses Windows `CredentialManager` module to retrieve stored password (target: `QMT_AutoLogin`), then `SendKeys` to type password and press Enter
- Requires: Import-Module CredentialManager, stored Windows credential named `QMT_AutoLogin`

### Supporting Files

- `code/my_enum.py` — `ORDER_TYPE_MAP`, `OPERATION_TYPE_MAP` dictionaries (duplicated inline in other files too)
- `code/qmt_test.py` — Full enum dictionaries (`ENTRUST_STATUS_MAP`, `TASK_STATUS_MAP`, `PRICE_TYPE_MAP`) plus print helpers for debugging order/position/deal/account objects
- `code/miniqmt_test1.py` — xtdata API usage example (downloading history, subscribing to quotes)
- `code/miniqmt_test2.py` — xttrader API usage example (connecting, placing orders)

## Running the Strategy

```bash
# Main MiniQMT strategy (standalone) — runs the strategy directly
cd code && python miniqmt_small_cap_0_1.py

# Process manager — runs as daemon, auto-restarts strategy on first Friday of month
cd code && python strategy_scheduler.py

# Enable debug mode (daily execution regardless of actual trading days, no real orders)
# Set DEBUG_DAILY_MODE = True at the top of miniqmt_small_cap_0_1.py

# Manual debug: call specific functions inline (see __main__ block for examples)

# QMT platform versions (qmt_shipan.py / small_cap_1_0.py)
# These are pasted into the QMT client's strategy editor and run inside QMT
```

## Key Dependencies

- **`xtquant`** — 迅投 QMT Python SDK (proprietary, ships with QMT installation at `C:\QMT\`)
- `apscheduler` — Task scheduling for MiniQMT and scheduler daemon
- `psutil` / `pyautogui` — Process management and GUI automation for auto-login
- Standard: `pandas` (via xtquant's returned DataFrames), `subprocess`, `signal`, `re`

## Important Notes

- The QMT client must be running (MiniQMT or full QMT) for `xtquant` to connect — the SDK is a bridge to the local QMT process
- `miniQMT_small_cap_0_1.py` has `#coding:gbk` but the codebase uses UTF-8 encoding
- Friday-only QMT restart logic (`closeQMT`/`reopenQMT`/`reconnect`) checks `current_date.weekday() != 4` and returns early on other days
- Many enum maps are duplicated across files rather than imported from `my_enum.py` or `qmt_test.py`
- `strategy_scheduler.py` and `miniqmt_small_cap_0_1.py` run as **separate processes** — the scheduler kills the strategy process externally, so signal handlers in the strategy (SIGINT/SIGTERM → `shutdown_scheduler`) only handle direct termination
- `buy_target_value()` uses `current_price + 0.1` and `sell_target_value()` uses `current_price - 0.1` as fixed prices to reduce slippage; full liquidation uses `MARKET_PEER_PRICE_FIRST`
