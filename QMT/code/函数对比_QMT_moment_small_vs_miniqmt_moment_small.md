# `QMT_moment_small_1.py` vs `miniqmt_moment_small_0_1.py` 小市值策略逻辑差异对比

对比日期：2026-08-25

- 左侧：`QMT_moment_small_1.py`（QMT 全平台版，`ContextInfo` + `handlebar` + `passorder`，仅小市值策略）
- 右侧：`miniqmt_moment_small_0_1.py`（MiniQMT 版，`xtquant` + APScheduler，小市值 + 动量双策略）

对比范围：两文件共有的**小市值策略函数**。动量策略、手续费/tick 等仅存在于 miniqmt 版的函数不在范围内。

已忽略的差异（不视为逻辑差异）：

- 纯变量名改写（如 `stock` vs `stock_code`、`cash` vs `c`）
- 多余空格、空行、注释、docstring、f-string 改写
- API 调用方式差异（`passorder` vs `order_stock_async`、`ContextInfo.get_xxx` vs `xtdata.get_xxx`、`get_trade_detail_data` vs `query_stock_positions`、`m_dAvailable` vs `info.cash`、`get_instrumentdetail` vs `get_instrument_detail`、`get_stock_name` 等）
- 资金隔离改造本身（`info.total_asset` → `get_strategy_total(SC_IDX)` 之类，属双策略架构的预期改动）

---

## 一、miniqmt 版新增的功能（QMT 版没有）

### 🔴 1. 行业分散选股（`get_small_cap_stocks`）

```python
# QMT:1129 —— 直接取市值最小 n 只
selected_stocks = list(sorted_market)[0:n]

# miniqmt:978 —— 从前 100 只里按申万二级行业分散选 n 只
selected_stocks = small_cap_get_stock_industry(list(sorted_market)[:100], n)
```

miniqt 版通过 `get_sw2_industry()` + `small_cap_get_stock_industry()` 实现「每个申万二级行业只取 1 只」的分散，QMT 版没有该功能。这是两版本最核心的差异。

### 🔴 2. 止损 3 日禁买（`g.stoploss_map`）

QMT 版完全没有该机制。miniqmt 版：

- `sc_stop_loss:1583` —— 止损卖出时 `g.stoploss_map[stock] = g.stoploss_map.setdefault(stock, 3)`
- `sc_prepare_stock_list:1088` —— 每日递减 `g.stoploss_map = {k: v-1 for k, v in g.stoploss_map.items() if v-1 > 0}`
- `sc_rebalance_sell:1201-1204` / `sc_check_remain_amount:1519-1522` —— 从选中池剔除被禁股票

### 🟠 3. 当日涨停跟踪（`g.today_HL_list`）

miniqmt 版新增 `g.today_HL_list`（今日上午涨停股票），用于：

- `collect_sell_buy_stocks` —— 当日涨停的持仓不卖
- `sc_calc_position` —— 当日涨停股按不可调仓处理

QMT 版只有 `g.yesterday_HL_list`，无此概念。

---

## 二、miniqmt 版修复的 bug（QMT 版仍存在）

### 🔴 4. `is` 误用（`check_remain_amount`）

```python
# QMT:887 / 929 —— 字符串用 is 判断身份，依赖 interning，不可靠
if g.reason_to_sell is 'limitup':
elif g.reason_to_sell is 'stoploss':

# miniqmt:1500 / 1541 —— 正确
if g.reason_to_sell == 'limitup':
elif g.reason_to_sell in ('stoploss', 'takeprofit'):
```

### 🟠 5. `g.stocks_fail_sell` 不重置（`sell_stocks`）

```python
# QMT:1228 —— 只在 init 初始化一次，跨调仓周期累积
def sell_stocks(ContextInfo):
    for stock in g.stocks_to_sell:
        ...

# miniqmt:1642 —— 每次卖出前重置
def sell_stocks():
    g.stocks_fail_sell = []
    for stock in g.stocks_to_sell:
        ...
```

### 🟠 6. `stop_loss` 策略1 缺少跳过条件

```python
# QMT:947-969 —— 策略1（个股止损）对 ETF/全天候标的一并做止损判断，且无除零保护
for stock in current_positions.keys():
    if current_positions[stock]['total_amount'] == 0:
        continue
    price = ...
    avg_cost = ...
    if price >= avg_cost * 2: ...
    elif price < avg_cost * (1 - g.stoploss_limit): ...

# miniqmt:1566-1585 —— 新增两个跳过条件
for stock in list(current_positions.keys()):
    if current_positions[stock].volume == 0:
        continue
    if stock in g.all_weather_list or stock == g.etf:
        continue
    price = get_last_price(stock)
    avg_cost = current_positions[stock].avg_price
    if avg_cost <= 0:
        continue
    ...
```

### 🟠 7. `judge_date` 里 `weekday` 少括号（TypeError）

```python
# QMT:441 —— 5 - 方法对象 + 日 → 运行到 3月底/12月底 分支时抛 TypeError
if 5 - current_date.weekday + current_date.day > 31:   # 应为 weekday()
```

---

## 三、miniqmt 版引入的疑似 bug / 回退（QMT 版是对的）

### ⚪ 8. ~~`check_remain_amount` 止盈止损分支丢失 `g.stocks_to_buy = [g.etf]`~~（撤回 — 复核不成立）

经复核，miniqmt 版第 1544 行**确有** `g.stocks_to_buy = [g.etf]` 赋值，与 QMT 版一致，此项**不构成逻辑差异**：

```python
# miniqmt:1541-1545 —— 赋值实际存在
elif g.reason_to_sell in ('stoploss', 'takeprofit'):
    avi_cash = get_strategy_available_cash(SC_IDX)
    print(f'止盈止损后余额{avi_cash:.2f}元，买入{g.etf}')
    g.stocks_to_buy = [g.etf]   # ← 赋值存在
    buy_stocks()
```

该分支与 QMT 版的真实差异仅为：① `is 'stoploss'` → `in ('stoploss', 'takeprofit')`（见第 4、11 项）；② 可用资金变量名 `available_cash` vs `avi_cash`（忽略项）。

### 🔴 9. `check_remain_amount` 循环变量残留（NameError 风险）

```python
# miniqmt:1519-1522
for stock in list(g.stoploss_map.keys()):
    if stock in g.selected_stocks:
        g.selected_stocks.remove(stock)
        print(f"{stock} {get_stock_name(stock)} 前{3 - g.stoploss_map[stock_code]}日止损卖出，3日内不再买入")
                                            #  ^^^^^^^^^^ stock_code 是上面 1504/1508 两个循环的残留变量
```

- 当 `g.hold_list` 与 `g.limitup_stocks` 都为空时 → `NameError`
- 否则取到别的股票的禁买天数 → 打印内容错误

---

## 四、行为改变（需确认是否有意）

### 🟡 10. `judge_date` 月末预清仓分支被删

```python
# QMT:440-444 —— 3月底/12月底 提前清仓，保证 1/4 月开盘已空仓
elif (current_month == 12 or current_month == 3) and current_date.day > 27:
    if 5 - current_date.weekday + current_date.day > 31:
        if g.trade == True:
            print('GGG========== 一月和四月份清仓，日期：%s ==========' % current_date)
        g.trade = False

# miniqmt:1047-1052 —— 删掉了该分支，只剩 1/4 月整月清仓
if current_month == 1 or current_month == 4:
    if g.trade:
        print(...)
    g.trade = False
else:
    g.trade = True
```

### 🟡 11. `stop_loss` 大盘上涨时 reason 改变

```python
# QMT:983 —— 大跌大涨统一设 'stoploss'
if abs(down_ratio) >= g.stoploss_market:
    g.reason_to_sell = 'stoploss'
    g.refresh_hold = True
    if down_ratio < 0: ...
    else: ...

# miniqmt:1612-1619 —— 大涨单独设 'takeprofit'
if abs(down_ratio) >= g.stoploss_market:
    g.refresh_hold = True
    if down_ratio < 0:
        g.reason_to_sell = 'stoploss'
    else:
        g.reason_to_sell = 'takeprofit'
```

下游影响：`sc_rebalance_buy` 遇到 `'takeprofit'` 会跳过买入（QMT 版无此分支，`'stoploss'` 仍会继续买入）。

### 🟡 12. `stop_loss` 大盘分支的跳过条件

```python
# QMT:987-998 —— 大跌分支：只跳 etf + 全天候，不跳昨日涨停
if down_ratio < 0:
    for stock in current_positions.keys():
        if stock == g.etf: continue
        if stock in g.all_weather_list: continue
        sell_target_value(stock, 0)

# QMT:999-1014 —— 大涨分支：跳 etf + 全天候 + 昨日涨停
else:
    for stock in current_positions.keys():
        if stock == g.etf: continue
        if stock in g.all_weather_list: continue
        if stock in g.yesterday_HL_list: continue
        sell_target_value(stock, 0)

# miniqmt:1620-1626 —— 合并成一个循环，大跌大涨统一：跳 etf + 全天候 + 昨日涨停 + 当日涨停
for stock in list(current_positions.keys()):
    if stock in g.all_weather_list or stock == g.etf: continue
    if stock in g.yesterday_HL_list or is_limit_up(stock): continue
    sell_target_value(stock, 0, SC_IDX)
```

### 🟡 13. `collect_sell_buy_stocks` 加涨停判断

```python
# QMT:486-488 —— 无涨停判断
for stock in current_holdings:
    if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
        g.stocks_to_sell.append(stock)

# miniqmt:1098-1105 —— 先判涨停，涨停不卖并记入 today_HL_list
for stock in current_holdings:
    if not is_limit_up(stock):
        if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
            g.stocks_to_sell.append(stock)
    else:
        print(f"⭕ {stock} {get_stock_name(stock)} 转为涨停股，今日不卖出。")
        g.today_HL_list.append(stock)
```

### 🟡 14. `buy_stocks` 的买入上限

```python
# QMT:1275-1277 —— 上限 = 可用资金
if g.excepted_position.get(stock) is not None:
    target_value_per_stock = g.excepted_position[stock] * total_value
    target_value_per_stock = min(account_info[0].m_dAvailable, target_value_per_stock)

# miniqmt:1687-1693 —— 上限 = 可用资金 + 现有持仓市值
if g.excepted_position.get(stock) is not None:
    target_value_per_stock = g.excepted_position[stock] * strategy_total
    current_value = positions[stock].market_value if stock in positions else 0
    target_value_per_stock = min(available_cash + current_value, target_value_per_stock)
```

miniqmt 把现有持仓市值计入上限，现金不足时可凭已有持仓补足到目标仓位。

### 🟡 15. `calc_position` 两处

**15a. 倾斜项被删**

```python
# QMT:685 —— 有 position_step 倾斜项
g.excepted_position[stock] = p + ((holding_num - 1) / 2 - i) * g.position_step

# miniqmt:1311 —— 删掉倾斜项
g.excepted_position[stock] = p
```

因 `g.position_step = 0.00`，目前两版结果相同，但 QMT 版保留了倾斜机制，miniqmt 版结构上删掉了。

**15b. 手数微调精度不同**

```python
# QMT:835
if abs(round(diff_v,2)) <= abs(round(diff_value,2)):

# miniqmt:1452
if abs(round(diff_v,1)) <= abs(round(diff_value,1)):
```

`round(...,2)` vs `round(...,1)` 会影响最终追加手数。

### 🟡 16. `get_specified_date_price` 周期不同

```python
# QMT:1071 —— 1 分钟线
price_data = ContextInfo.get_market_data_ex(['close'], [stock], period='1m', ...)

# miniqmt:244 —— 日线
history_data = xtdata.get_market_data_ex(['close'], [stock], period='1d', ...)
```

影响 `is_specified_date_limit_up` 拿到的昨收价。

### 🟡 17. `get_normal_stocks` 的 ST 判断

```python
# QMT:1163-1180 —— 查历史 ST 区间（更严格，能过滤曾 ST 过的股票）
ST = ContextInfo.get_his_st_data(stock)
if ST:
    for stkey, time_period in ST.items():
        for tp in time_period:
            if is_date_in_range(current_time, tp[0], tp[1]):
                is_st = True
                break
...
else:
    stock_name = ContextInfo.get_stock_name(stock)
    if "ST" in stock_name:
        continue

# miniqmt:1010 —— 仅按当前名称含 ST 判断
if 'ST' in stock_name or 'st' in stock_name:
    continue
```

### 🟡 18. `is_weekday_job` 参考指数不同

```python
# QMT:365
last_date = ContextInfo.get_trading_dates('000300.SH', '', dt_str, 1, '1d')

# miniqmt:186
date = get_trading_dates('399101.SZ', dt_str)
```

交易日历相同，影响极小。

### 🟡 19. 停牌/退市信号不同（`get_normal_stocks` / `filter_paused_stocks`）

```python
# QMT:1199-1205 —— is_suspended_stock() + InstrumentID is None
if ContextInfo.is_suspended_stock(stock):
    continue
info = ContextInfo.get_instrumentdetail(stock)
if info['InstrumentID'] is None:
    print(f"可能退市 {stock} ...")
    continue

# miniqmt:1014-1020 —— ExpireDate + InstrumentStatus
if detail['ExpireDate'] != '99999999':
    print(stock, " 可能退市 ", detail['ExpireDate'])
    continue
if detail['InstrumentStatus'] < 0:
    print(stock, " 可能停牌 ", detail['InstrumentStatus'])
    continue
```

### 🟡 20. 下单函数逻辑差异

```python
# QMT:1300-1301 —— 清仓前不检查跌停
if target_value == 0:
    passorder(24, 1101, ..., pos['total_amount'], ..., 'qingkong', ...)

# miniqmt:580 —— 跌停不清仓
if target_value == 0 and not is_limit_down(stock):
    ...

# QMT:1326 —— 下单量多 5 股缓冲
volume = target_value - current_value + current_price * 5

# miniqmt:639-642 —— 下单量被可用现金封顶
volume = target_value - current_value
if strat_idx is not None:
    volume = min(volume, get_strategy_available_cash(strat_idx))
```

### 🟡 21. `get_market` 字段名（需核实）

```python
# QMT:1094 —— 拼写带 n
guben[stock] = info['TotalVolumn']

# miniqmt:324 —— 无 n
TotalVolume = xtdata.get_instrument_detail(stock)['TotalVolume']
```

两者平台不同（`get_instrumentdetail` vs `get_instrument_detail`），字段名可能本就不同，也可能是 QMT 侧笔误，建议核实。

---

## 五、优先级建议

1. **修 miniqmt 版 bug**（第 9 项）—— `stock_code` 残留变量，有 NameError / 打印错误风险。（第 8 项经复核不成立，已撤回。）
2. **确认第 10 项**（月末预清仓分支删除）—— 是否仍需要「1/4 月开盘前空仓」的效果。
3. **确认第 11、12 项**（`takeprofit` + 大盘分支跳过条件）—— 止损/止盈语义是否按 miniqmt 版为准。
4. **确认第 1 项**（行业分散选股）—— 这是你提到的已知功能差异，QMT 版如需对齐需补 `get_sw2_industry` / `small_cap_get_stock_industry`。
5. 其余（第 14、15、16、17 等）多为精修，按需对齐。
