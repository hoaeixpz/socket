# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **QMT (迅投QMT) automated trading system** using the `xtquant` Python SDK. It contains **three independent strategy families**:

1. **Small-cap rotation** — holds the N smallest market-cap A-share stocks, rebalanced weekly on Tuesdays. During January and April (seasonal underperformance months), switches to all-weather ETFs.
2. **All-weather ETF** — monthly rebalance across 5 assets (gold, soybean meal, Nasdaq, AgBank, Yangtze Power) using ES-based risk-parity weighting.
3. **All-weather + bond** — same as all-weather plus bond ETFs with drawdown-graded bond liquidation.

## Key Files

### Small-cap strategy family

| File | Platform | Scheduling | Role |
|------|----------|------------|------|
| `code/miniqmt_small_cap_0_1.py` | MiniQMT (`xtquant`) | APScheduler cron (12 tasks) | **Main active small-cap strategy** |
| `code/strategy_scheduler.py` | MiniQMT | APScheduler cron | **Process manager daemon** — kills and restarts the small-cap strategy on the first Friday evening of each month |
| `code/qmt_shipan.py` | Full QMT (`ContextInfo`) | `handlebar()` K-line callback | Full QMT version — bar-driven, meant for in-platform execution |
| `code/small_cap_1_0.py` | Full QMT (`ContextInfo`) | `handlebar()` K-line callback | Near-identical to `qmt_shipan.py` (duplicate variant) |
| `code/miniqmt_test2.py` | MiniQMT | Main loop with manual scheduling | **Earlier prototype** of the small-cap strategy — uses index `'932000'` not `'399101.SZ'`, implements all-weather ETF trading via ES within `trade_etf()`. ~1200 lines. |

### All-weather strategy family (`code/all_weather/`)

| File | Type | Role |
|------|------|------|
| `code/all_weather/all_weather_0_1.py` | QMT live | **All-weather ETF** — 5 assets, ES-weight `∝ ES * (1 - AR)`, monthly rebalance, daily take-profit at 14:55 |
| `code/all_weather/all_weather_bond_0_1.py` | QMT live | **All-weather + bond** — 7 assets (same 5 + 十年地方债 511270.SH + 城投债ETF 511220.SH), weight `∝ -1/ES` with fixed bonuses for Nasdaq (3%) and gold (2%), 4-level drawdown-graded bond liquidation |
| `code/all_weather/sim_all_weather_0_1.py` | Simulation | **Offline planner** — no QMT connection, takes hardcoded positions + cash, computes target weights and buy/sell lists with CJK-aligned table output |
| `code/all_weather/sim_all_weather_bond_0_1.py` | Simulation | **Offline planner** — same as above but for the bond variant, includes drawdown detection and bond trade calculations |

### Utility / tutorial files

| File | Role |
|------|------|
| `code/qmt_test.py` | Full QMT helper — print position/order/deal/account info; complete enum dictionaries (`ENTRUST_STATUS_MAP`, `TASK_STATUS_MAP`, `PRICE_TYPE_MAP`, etc.) |
| `code/my_enum.py` | `ORDER_TYPE_MAP`, `OPERATION_TYPE_MAP` dictionaries (duplicated inline in other files too) |
| `code/login.py` + `code/login.ps1` | Auto-login to QMT client using pyautogui + Windows CredentialManager |
| `code/miniqmt_test.py` | **Tutorial**: simple timed buy-sell strategy (buys 000001.SZ at 10:00, sells next day at 14:00) using a `StrategyState` class. Demonstrates basic MiniQMT loop pattern. Uses local data dir `安装目录\userdata_mini` (session 6689). |
| `code/miniqmt_test1.py` | **Tutorial**: xtdata API — download history for 513100.SH, subscribe to real-time quotes, callback pattern |
| `code/miniqmt_get_price.py` | **Tutorial**: xtdata API — download history for 512220.SH, subscribe to quotes, demonstrates both polling and callback patterns |

### Reference docs

| Directory | Contents |
|-----------|----------|
| `gjzqqmt/QMT操作说明文档/` | Official 国金证券 QMT platform PDF manuals — including Python API reference (`模型资料_Python_API_说明文档_Python3.pdf`), VBA model editor, grid strategy, algorithm trading docs |
| `安装目录/userdata_mini/` | Local copy of MiniQMT data directory (contains `down_queue_6689`, a 75 MB binary message queue file). Used by `miniqmt_test.py` for testing against local data. |

## Architecture

### Common patterns across all strategies

All MiniQMT strategies share the same architecture:

- **Connection**: `XtQuantTrader(path, session_id)` with `StockAccount('8885388757')`
- **Scheduling**: `APScheduler` (`BackgroundScheduler`) with cron jobs at specific market hours
- **State**: Module-level `g` object (instance of empty class `G`) holding all shared state
- **Logging**: `Tee` class writes stdout to both console and log files; ANSI escape codes stripped
- **Callbacks**: `MyXtQuantTraderCallback(XtQuantTraderCallback)` for order/trade/disconnection events
- **Debug toggle**: `DEBUG_DAILY_MODE = False` by default; set to `True` to skip actual order placement and ignore trading-day checks (a commented-out `#DEBUG_DAILY_MODE = True` line sits below each declaration as a toggle hint)
- **Order execution**: `g.xt_trader.order_stock_async()` with `FIX_PRICE` (slightly above/below current price) or `MARKET_PEER_PRICE_FIRST`

### Full QMT pattern

`qmt_shipan.py` / `small_cap_1_0.py` execute inside the QMT platform's Python runtime using `init(ContextInfo)` → `handlebar(ContextInfo)` callback pattern (聚宽-style). All functions take `ContextInfo` as first argument. Order execution via `order_target_value()` / `order_shares()`.

### Process Manager (`strategy_scheduler.py`)

- Separate daemon process with its own `BackgroundScheduler`
- On the **first Friday evening of each month**: stops the strategy at 18:00, restarts it at 18:30
- Uses `taskkill /f /t` to kill the entire process tree, then verifies no orphan processes remain (3 checks at 5s intervals)
- Has a watchdog function (currently commented out) that would auto-restart if the strategy process crashes

### QMT Client Paths

- Installation: `C:\QMT\bin.x64\XtItClient.exe`
- MiniQMT data dir (production): `C:\QMT\国金证券QMT交易端\userdata_mini`
- MiniQMT data dir (fallback): `C:\QMT\userdata_mini`
- MiniQMT data dir (local test): `安装目录\userdata_mini` (session 6689, used by `miniqmt_test.py`)
- Trading account: `8885388757`

### Small-Cap Strategy Task Schedule

```
09:30 judge_date()          — Check if trading day, set Jan/Apr no-trade flag
09:31 prepare_stock_list()  — Build stock pool (中小综指 399101.SZ), check yesterday's limit-up holdings
09:35 trade_etf()           — If no-trade month, switch to all-weather ETFs (risk-parity via ES)
10:00 rebalance_sell()      — Weekly rebalance: select small-cap stocks by market cap, sell unwanted
10:15 stop_loss()           — Check stop-loss conditions, sell if triggered
10:30 rebalance_buy()       — Buy new stocks with equal-weight position sizing
14:00 check_limit_up()      — Sell holdings that hit limit-up intraday
14:02 check_remain_amount() — Verify all orders filled, retry if needed
15:01 info_position()       — Log final positions and daily P&L
15:10 closeQMT()            — Kill XtMiniQmt.exe (Fridays only)
18:00 reopenQMT()           — Restart QMT via login.py (Fridays only)
18:10 reconnect()           — Re-establish trading connection (Fridays only)
```

### All-Weather ETF Task Schedule (`all_weather_0_1.py`)

```
09:30 before_market_open()  — Calculate weights
10:00 rebalance_sell()      — Monthly rebalance: sell overweight positions (deviating >6% from target)
10:02 rebalance_buy()       — Monthly rebalance: buy underweight positions
14:55 take_profit()         — Sell half if daily gain > 120d 3rd-highest gain AND 30d return >10%
15:01 after_trading_end()   — Log positions, update drawdown records
```

### All-Weather + Bond Task Schedule (`all_weather_bond_0_1.py`)

```
09:30 before_market_open()           — Update stock pool + calculate weights
10:00 rebalance_sell()               — Monthly rebalance: sell overweight
10:02 rebalance_buy()                — Monthly rebalance: buy underweight
14:50 rebalance_drawdown()           — Check max drawdown, 4-level graded bond liquidation
14:55 take_profit()                  — Take-profit check (excluding bonds)
15:01 after_trading_end()            — Log positions, update drawdown records
```

### All-Weather Strategy Logic

**`all_weather_0_1.py`** (5 assets: 黄金ETF 518880.SH, 豆粕ETF 159985.SZ, 纳指ETF 513100.SH, 农业银行 601288.SH, 长江电力 600900.SH):
- Weight formula: `weight ∝ ES * (1 - AR)` where ES = mean of worst 5% daily returns (120-day window), AR = mean of all 120 daily returns
- Monthly rebalance on the first trading day, with 6% tolerance band (only trade if deviation > 6%)
- Daily take-profit at 14:55: if today's gain > 120d 3rd-highest gain AND 30d return > 10%, sell half

**`all_weather_bond_0_1.py`** (same 5 + 十年地方债 511270.SH + 城投债ETF 511220.SH):
- Weight formula: `weight ∝ -1/ES` (inverse risk parity) with fixed bonuses: 纳指 +3%, 黄金 +2%
- Monthly rebalance on the first trading day, 6% tolerance band
- **Drawdown management**: records rolling max of last 120 days' total asset value. When drawdown crosses thresholds [1.2%, 1.8%, 2.4%, 3.0%], sells bonds proportionally (1/4, 2/4, 3/4, 4/4). `last_level` prevents re-triggering at same level.
- 城投债ETF (511220.SH) is managed by `buy_bond()`/`sell_bond()` separately and excluded from weight calculation
- Daily take-profit at 14:55 (same logic, excludes bond holdings)

**Simulation files** (`sim_all_weather_*.py`): offline planners using the same weight calculations. Take hardcoded `ACTUAL_POSITIONS` dict and `AVAILABLE_CASH`, output target weights, current-vs-target comparison, and buy/sell lists with CJK-width-aligned tables. Used for planning before executing trades manually.

### Small-Cap Strategy Logic

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

### Logging

- Small-cap: `code/logfiles/YYYYMMDD.log`
- All-weather: `code/all_weather/logfiles/aw_YYYYMMDD.log`
- All-weather + bond: `code/all_weather/logfiles/awb_YYYYMMDD.log`
- All use the same `Tee` class pattern (duplicated across files) — writes stdout to both console and log, strips ANSI codes
- `strategy_scheduler.py` has its own simple `log()` function printing to stdout with timestamps (no file output)

### Login Automation

- `login.py` launches `XtItClient.exe`, then uses `pyautogui` to Alt+Tab to the QMT window
- `login.ps1` uses Windows `CredentialManager` module to retrieve stored password (target: `QMT_AutoLogin`), then `SendKeys` to type password and press Enter
- Requires: Import-Module CredentialManager, stored Windows credential named `QMT_AutoLogin`

## Running the Strategies

```bash
# Main small-cap strategy (standalone)
cd code && python miniqmt_small_cap_0_1.py

# Process manager daemon (auto-restarts small-cap strategy on first Friday of month)
cd code && python strategy_scheduler.py

# All-weather ETF strategy (standalone)
cd code\all_weather && python all_weather_0_1.py

# All-weather + bond strategy (standalone)
cd code\all_weather && python all_weather_bond_0_1.py

# Simulation / offline planning (no QMT connection needed)
cd code\all_weather && python sim_all_weather_0_1.py
cd code\all_weather && python sim_all_weather_bond_0_1.py

# Enable debug mode (daily execution, no real orders)
# Set DEBUG_DAILY_MODE = True at the top of the strategy file

# Full QMT platform versions (qmt_shipan.py / small_cap_1_0.py)
# These are pasted into the QMT client's strategy editor and run inside QMT
```

## Key Dependencies

- **`xtquant`** — 迅投 QMT Python SDK (proprietary, ships with QMT installation at `C:\QMT\`)
- `apscheduler` — Task scheduling for all MiniQMT strategies and scheduler daemon
- `psutil` / `pyautogui` — Process management and GUI automation for auto-login
- Standard: `pandas` (via xtquant's returned DataFrames), `subprocess`, `signal`, `re`, `unicodedata` (for CJK-width alignment in sim files)

## Git Branches

| Branch | Purpose |
|--------|---------|
| `master` | Active development |
| `edge_branch` | Experimental |
| `master_bak` | Backup |
| `qmt_simulate` | Simulation variant |
| `tmp_branch` | Temporary work |

## Important Notes

- The QMT client must be running (MiniQMT or full QMT) for `xtquant` to connect — the SDK is a bridge to the local QMT process
- Three Full QMT files (`qmt_test.py`, `small_cap_1_0.py`, `qmt_shipan.py`) use `#coding:gbk` — they run inside the QMT platform's Python runtime which expects GBK. All MiniQMT strategy files use UTF-8 without a coding declaration.
- Friday-only QMT restart logic (`closeQMT`/`reopenQMT`/`reconnect`) checks `current_date.weekday() != 4` and returns early on other days
- Many enum maps are duplicated across files rather than imported from `my_enum.py` or `qmt_test.py`
- `strategy_scheduler.py` and `miniqmt_small_cap_0_1.py` run as **separate processes** — the scheduler kills the strategy process externally, so signal handlers in the strategy (SIGINT/SIGTERM → `shutdown_scheduler`) only handle direct termination
- `buy_target_value()` uses `current_price + 0.1` and `sell_target_value()` uses `current_price - 0.1` as fixed prices to reduce slippage; full liquidation uses `MARKET_PEER_PRICE_FIRST`
- All three strategy families (small-cap, all-weather, all-weather+bond) are designed to run as **independent standalone processes** — each has its own `init()`, APScheduler, `g` global state, and `Tee` logging. They can coexist but do not share state.
- The simulation files (`sim_all_weather_*.py`) do not require a running QMT client — they only use `xtdata` for historical prices (which works as long as miniQMT data is downloaded locally)

## Codebase Health Notes

- **No `.gitignore` exists** — log files in `code/logfiles/`, `__pycache__/` directories, and the 75 MB binary `安装目录/userdata_mini/down_queue_6689` are unprotected from accidental commits.
- **No `requirements.txt` or `pyproject.toml`** — dependencies are documented only in this CLAUDE.md. The runtime dependency is `xtquant` (proprietary, ships with QMT), plus `apscheduler`, `psutil`, and `pyautogui`.
- **No formal test infrastructure** — no test runner, no test directory, no CI. Files named `*test*.py` are tutorial/exploratory scripts. The two `sim_*.py` files serve as offline dry-run planners but are not automated tests.
- **Each strategy file is fully self-contained** — no shared imports between strategy files. The `Tee` class (stdout-to-log redirection) is copy-pasted into all 3 live strategy files. `my_enum.py` exists but is **never imported** by any strategy file — enum maps (`ORDER_TYPE_MAP`, `OPERATION_TYPE_MAP`, etc.) are duplicated inline wherever needed.
- **QMT data dir paths are inconsistent** across files: some use `C:\QMT\国金证券QMT交易端\userdata_mini`, others use `C:\QMT\userdata_mini`. When adding new strategies, use the 国金证券 path (the production install) with the fallback commented out.
- **This QMT directory is one project within the broader `socket` repo** (remote: `https://github.com/hoaeixpz/socket.git`). The parent directory also contains JoinQuant scripts (`JoinQuant/`), market cap data, and other trading tools that are untracked.
