# `miniqmt_small_cap_0_1.py` vs `miniqmt_moment_small_0_1.py` 函数逻辑对比

对比日期：2026-08-21
对比方法：AST 提取两文件全部对应函数 → 去注释、去空白归一化 → 逐对 unified diff → 人工判读

| 结果 | 数量 |
|---|---|
| 对比的函数对 | 43 |
| 完全逐字等价 | 14 |
| 等价重构（写法不同、行为相同） | 11 |
| 资金隔离改造（预期内） | 8 |
| **真正的工作流差异** | **12** |

仅存在于 `miniqmt_moment_small_0_1.py` 的函数（动量策略、手续费、tick 等）不在对比范围内。

---

## 一、真正的逻辑差异

### 🔴 1. `check_remain_amount` → `sc_check_remain_amount`

三处差异，其中 (b)(c) 疑似改造时的疏漏。

#### (a) 门槛判断从"永远成立"变成真正生效

```python
# small_cap:857-858
flag = True
if len(g.hold_list) < g.stock_num or flag:   # flag=True → 恒为真，无条件执行

# moment_small:1502
if len(g.hold_list) < g.stock_num:           # 现在真的会挡住
```

原版靠 `flag=True` 短路，涨停卖出后**无论持仓多少都会重新选股买入**；新版只在持仓不足时才执行。行为改变。

#### (b) 循环变量改名没改全 —— 取到错值甚至 NameError

```python
# moment_small:1519-1522
for stock in list(g.stoploss_map.keys()):
    if stock in g.selected_stocks:
        g.selected_stocks.remove(stock)
        print(f"{stock} ... 前{3 - g.stoploss_map[stock_code]}日止损卖出 ...")
                                            #  ^^^^^^^^^^ 应为 stock
```

`stock_code` 是上方 1504 / 1508 两个循环的残留变量：

- 取到的是别的股票的止损天数（打印内容错误）
- 若 `g.hold_list` 与 `g.limitup_stocks` 都为空 → `NameError`

原版 `small_cap:876-879` 循环变量本身就叫 `stock_code`，所以是对的。

#### (c) 止盈止损分支丢了买入标的赋值

```python
# small_cap:903-906
elif g.reason_to_sell == 'stoploss' or g.reason_to_sell == 'takeprofit':
    print('止盈止损后，有余额可用' + str(round(available_cash, 2)) + '元。买入' + str(g.etf))
    g.stocks_to_buy = [g.etf]     # ← 新版没有这一行
    buy_stocks()

# moment_small:1541-1544
elif g.reason_to_sell in ('stoploss', 'takeprofit'):
    avi_cash = get_strategy_available_cash(SC_IDX)
    print(f'止盈止损后余额{avi_cash:.2f}元，买入{g.etf}')
    buy_stocks()                  # g.stocks_to_buy 仍是上次 collect 留下的旧值
```

已核实 `g.stocks_to_buy` 在 moment_small 中只有两处赋值：`init:388` 和 `collect_sell_buy_stocks:1095`。
因此该路径**不会买 ETF**，而会买上一轮遗留的清单 —— 打印内容与实际下单不一致。

---

### 🟠 2. `collect_sell_buy_stocks` —— 两层条件判断顺序对调

```python
# small_cap:425-431                        # moment_small:1098-1105
for stock in current_holdings:             for stock in current_holdings:
  if (not in selected) and (not in yHL):     if not is_limit_up(stock):
    if not is_limit_up: → sell                 if (not in selected) and (not in yHL): → sell
    else: → today_HL_list.append             else:
                                               → today_HL_list.append
```

差异：

- 原版只把**本来要卖但涨停了**的股票记入 `g.today_HL_list`
- 新版把**所有涨停的持仓**都记入（含本来就要继续持有的）

`today_HL_list` 会流入 `sc_calc_position`（1289、1309 行）参与仓位计算，因此会改变仓位分配结果。
另外新版对每只持仓都调用一次 `is_limit_up`，行情请求次数增加。

---

### 🟠 3. `get_market` —— 市值基准价从昨收改成实时价

```python
# small_cap:1087-1104  —— 昨日 15:00 收盘价（前复权）
query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
prev_price = get_specified_date_price(stock, query_date, 'front')
market[stock] = TotalVolume * prev_price

# moment_small:319-338 —— 当前实时 tick
price_data = xtdata.get_full_tick(stock_list)
market[key] = gb * price['lastPrice']
```

这是小市值策略的**选股排序依据**。改用实时价后盘中排名随价格波动，与 commit `12a64f6c "小市值策略可以计算前一日收盘市值"` 的意图相反。

附带问题：`sc_check_remain_amount:1514` 仍在传 `prev_date`，但 `get_market` 已完全忽略 `query_date` 参数 —— 参数成了摆设。

**需确认是否为有意改动。**

---

### 🟡 4. `stop_loss` → `sc_stop_loss` —— 策略1 新增两个跳过条件

```python
# moment_small:1568-1569（small_cap 策略1 分支中没有）
if stock in g.all_weather_list or stock == g.etf:
    continue
# moment_small:1573-1574
if avg_cost <= 0:
    continue
```

原版策略1（个股固定止损）会对 ETF 和全天候标的一并做止损判断，新版跳过。
`avg_cost <= 0` 为除零保护。

> **注意**：大盘止损那段两个 `for` 循环合并成一个，看似差异，但已核对缩进（`moment_small:1619`）——
> 合并后的循环仍在 `if abs(down_ratio) >= g.stoploss_market:` 内，且两分支原循环体逐行相同。
> **属等价重构，无问题。**

---

### 🟡 5. `prepare_stock_list` → `sc_prepare_stock_list` —— 新增 `g.today_HL_list = []`

`moment_small:1069` 每日重置。
原版 `today_HL_list` 只在 `init:176` 初始化一次，之后**跨日累积、永不清空**。新版修复了该泄漏。

### 🟡 6. `sell_stocks` —— 新增 `g.stocks_fail_sell = []`

`moment_small:1641` 每次卖出前重置。
原版同样只在 `init:172` 初始化，跨周累积。同类修复。

### 🟡 7. `info_position` → `sc_info_position` —— 日终触发条件放宽

`if current_date.hour == 15:` → `if current_date.hour >= 15:`

影响日收益统计与（新版的）资金对账逻辑的触发时机。

### 🟡 8. `run_strategy` —— 日终汇报时间 15:01 → 15:02

其余时点完全一致：9:30 / 9:31 / 9:35 / 9:55 / 10:15 / 10:30 / 14:10 / 14:12。
新版按 `g.portfolio_value_proportion` 条件注册任务；`closeQMT` / `reopenQMT` / `reconnect` 仍无条件注册。

### 🟡 9. 三个下单函数 —— 报价方式改变

`sell_target_value` / `buy_target_value` / `buy_target_shares`：

- `current_price ± 0.1` → `current_price ± get_tick_size(stock) * 10`
- 卖出额外增加 `max(..., detail['DownStopPrice'])` 跌停价兜底

对低价股（0.1 元 ≫ 10 个 tick）与高价股影响方向相反。

### 🟡 10. `buy_target_value` —— 新增买入金额上限

```python
if strat_idx is not None:
    volume = min(volume, get_strategy_available_cash(strat_idx))
```

### 🟡 11. `buy_target_shares` —— 新增空价格保护

`if not current_price: return`；原版直接拿 `None` 参与价格计算。

### 🟢 12. `reconnect` —— 路径解析

`path = 'C:\\QMT\\userdata_mini'`（硬编码）→ `get_userdata_mini_path()`。属修复。

---

## 二、看着有差异、实际等价（可忽略）

| 函数 | 表面差异 | 为何等价 |
|---|---|---|
| `stop_loss` 大盘分支 | 两个 `for` 合并成一个 | 两分支循环体逐行相同，合并后仍在阈值判断内 |
| `is_weekday_job` | `g.weekday` → 参数 `target_weekday` | 两个调用点（1187/1239）都传 `g.weekday` |
| `calc_position` | 补仓循环里 `cash` 改名 `c` | `if/elif` 互斥，原 `cash` 被覆盖后无人再读 |
| `rebalance_sell` | `g.stoploss_map.keys()` → `list(...)` | 循环体只改 `g.selected_stocks`，不改 map |
| `calc_position` | `target_value` 计算挪到 `continue` 之后 | `g.excepted_position.pop()` 两版都有，结果相同 |
| `small_cap_get_stock_industry` | 删掉 `if True:` | 恒真分支 |
| `get_small_cap_stocks` | `industry_dict[x]` → `.get(x, '未知')` | 仅用于打印 |
| `is_trading_day` | 三行合并为两行 | 表达式相同 |
| `judge_date` / `trade_etf` / `rebalance_buy` / `check_limit_up` / `get_sw2_industry` / `get_normal_stocks` / `shutdown_scheduler` | 改名、f-string、删无用变量、加 docstring | 纯写法 |

---

## 三、完全逐字等价的函数（14 个）

`get_userdata_mini_path`、`closeQMT`、`reopenQMT`、`kill_process_by_name`、`open_QMT`、
`get_stock_name`、`get_trading_dates`、`is_specified_date_limit_up`、`is_limit_up`、
`is_limit_down`、`get_specified_date_price`、`get_last_price`、`get_positions`、`get_blank`

---

## 四、资金隔离改造（预期内，非 bug）

涉及函数：`init`、`exec_all_weather`、`buy_stocks`、`calc_position`、`get_current_holding_stocks`，
以及 `sell_target_value` / `buy_target_value` / `buy_target_shares` 的记账部分。

统一模式：

- `info.total_asset` → `get_strategy_total(SC_IDX)`
- `info.cash` → `get_strategy_available_cash(SC_IDX)`
- 过滤 `g.positions[MOM_IDX]`（排除动量策略持仓）
- 下单函数增加 `strat_idx` 参数，成交后更新 `g.cash_reserved` / `g.positions`

---

## 五、处理建议（按优先级）

1. **修 `sc_check_remain_amount:1522`** —— `g.stoploss_map[stock_code]` → `g.stoploss_map[stock]`。有崩溃风险。
2. **修 `sc_check_remain_amount:1541-1544`** —— 补回 `g.stocks_to_buy = [g.etf]`。否则止盈止损后买错标的。
3. **确认 `get_market` 改用实时价是否有意** —— 与 commit `12a64f6c` 方向相反，影响选股排序。
4. **确认 `sc_check_remain_amount:1502` 去掉 `flag`** 是否有意 —— 涨停卖出后的补仓行为已改变。
5. 确认 `collect_sell_buy_stocks` 条件顺序对调是否有意 —— 影响 `today_HL_list` 内容进而影响仓位计算。
