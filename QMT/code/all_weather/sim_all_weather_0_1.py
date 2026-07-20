# -*- coding: utf-8 -*-
"""
全天候 ETF 策略 — 模拟版（无需 QMT 交易连接）
母版：C:\socket\JoinQuant\全天候策略\all_weather.py

用法：修改下方 ACTUAL_POSITIONS 和 AVAILABLE_CASH，然后运行：
      python sim_all_weather_0_1.py

输出：目标权重、当前持仓 vs 目标、需要买入/卖出的股票和数量。
"""
from xtquant import xtdata
import math
import unicodedata
from datetime import datetime, timedelta

# ======================== 手动输入你的实际持仓 ========================

ACTUAL_POSITIONS = {
    "518880.SH": 3000,      # 黄金ETF — 填你的实际持仓股数
    "159985.SZ": 8100,      # 豆粕ETF
    "513100.SH": 8300,      # 纳指ETF
    "601288.SH": 3100,      # 农业银行
    "600900.SH": 400,      # 长江电力
}

AVAILABLE_CASH = 11690   # 账户可用资金（元）

# ======================== 策略参数（与母版一致） ========================

stocks = [
    "518880.SH",  # 黄金ETF
    "159985.SZ",  # 豆粕ETF
    "513100.SH",  # 纳指ETF
    "601288.SH",  # 农业银行
    "600900.SH",  # 长江电力
    "601225.SH",  # 陕西煤业
    '000429.SZ',  # 粤高速A
    '601899.SH'   # 紫金矿业
]

base_days = 120
rebalance_tolerance = 0.06  # 偏离 6% 才交易
weights = {}

# ======================== 数据获取 ========================

def get_stock_name(stock):
    detail = xtdata.get_instrument_detail(stock)
    if detail:
        return detail['InstrumentName']
    return stock


def get_last_price(stock):
    try:
        tick = xtdata.get_full_tick([stock])
        if stock in tick and tick[stock] and tick[stock]['lastPrice'] > 0:
            return tick[stock]['lastPrice']
    except Exception as e:
        print(f"get_last_price error: {stock} {e}")

    return None



def cjk_len(s):
    """计算字符串在终端中的显示宽度（全角字符算2，半角算1）"""
    width = 0
    for ch in s:
        w = unicodedata.east_asian_width(ch)
        if w in ('F', 'W'):   # Fullwidth / Wide
            width += 2
        else:
            width += 1
    return width


def cjk_ljust(s, width):
    """按显示宽度左对齐"""
    return s + ' ' * max(0, width - cjk_len(s))


def cjk_rjust(s, width):
    """按显示宽度右对齐"""
    return ' ' * max(0, width - cjk_len(s)) + s


# 表格列宽定义
COL_WIDTHS = {
    'code':   12,   # 代码
    'name':   18,   # 名称
    'price':   8,   # 股价
    'shares':  8,   # 持仓
    'cur_val': 10,  # 当前市值
    'tgt_val': 10,  # 目标市值
    'diff':    10,  # 差值
}


def make_row(code, name, price, shares, cur_val, tgt_val, diff, action):
    """构建表格行（所有列 CJK 宽度对齐）"""
    cols = [
        cjk_ljust(code, COL_WIDTHS['code']),
        cjk_ljust(name, COL_WIDTHS['name']),
        cjk_rjust(price, COL_WIDTHS['price']),
        cjk_rjust(shares, COL_WIDTHS['shares']),
        cjk_rjust(cur_val, COL_WIDTHS['cur_val']),
        cjk_rjust(tgt_val, COL_WIDTHS['tgt_val']),
        cjk_rjust(diff, COL_WIDTHS['diff']),
    ]
    return '  ' + ' '.join(cols) + '  ' + action


def make_header():
    """构建表头"""
    return make_row('代码', '名称', '股价', '持仓', '当前市值', '目标市值', '差值', '操作')


# ======================== 权重计算（与母版完全一致） ========================

def calc_ES_weights():
    alpha = 0.05
    num = int(base_days * alpha)
    print(f"样本数: {num}（{base_days}天 × {alpha}）")

    for s in stocks:
        xtdata.download_history_data(s, period='1d', incrementally=True)

    query_date = datetime.now().strftime('%Y%m%d')
    price_data = xtdata.get_market_data_ex(['close'], stocks, period='1d',
                                           start_time='', end_time=query_date,
                                           count=base_days, dividend_type='front')

    for code in stocks:
        df = price_data.get(code)
        if df is None or len(df) < base_days:
            weights[code] = 0
            print(f"{code} {get_stock_name(code)} 数据不足，权重=0")
        else:
            df['daily_return'] = df['close'].pct_change() * 100
            df = df.iloc[1:].dropna(subset=['daily_return'])
            srt = df['daily_return'].sort_values()
            ES = srt.tail(num).mean()
            AR = srt.mean()
            weight = ES * (1 - AR)
            weights[code] = weight
            print(f"{code} {get_stock_name(code)}  ES={ES:.3f}  AR={AR:.3f}  raw={weight:.4f}")
            #print(srt.tail(num))

    # 归一化
    total = sum(weights.values())
    if total > 0:
        for code in stocks:
            weights[code] /= total

    # 计算当前权重（基于实际持仓和最新价格）
    total_value = 0
    current_prices = {}
    for code in stocks:
        price = get_last_price(code)
        current_prices[code] = price
        if price:
            total_value += ACTUAL_POSITIONS.get(code, 0) * price
    total_asset = total_value + AVAILABLE_CASH

    print(f"\n{'='*60}")
    print(f"目标权重 vs 当前权重")
    print(f"{'='*60}")
    print(f"  {'代码':<14s} {'名称':<12s} {'目标权重':>8s} {'当前权重':>8s}")
    print(f"  {'-'*14} {'-'*12} {'-'*8} {'-'*8}")
    for code in stocks:
        name = get_stock_name(code)
        target_wt = weights[code] * 100
        cur_shares = ACTUAL_POSITIONS.get(code, 0)
        cur_price = current_prices.get(code)
        cur_value = cur_shares * cur_price if cur_price else 0
        cur_wt = cur_value / total_asset * 100 if total_asset > 0 else 0
        print(f"  {code:<14s} {name:<12s} {target_wt:7.2f}% {cur_wt:7.2f}%")
    print(f"  {'':>28s} {'现金':>8s} {AVAILABLE_CASH/total_asset*100:7.2f}%")
    print()


# ======================== 调仓计算 ========================

def calc_trades():
    """根据权重和实际持仓，计算买卖计划"""
    # 计算当前价格和实际市值
    print(f"{'='*60}")
    print(f"当前持仓 vs 目标")
    print(f"{'='*60}")

    positions_value = {}
    total_current_value = 0
    prices = {}

    for code in stocks:
        price = get_last_price(code)
        prices[code] = price
        shares = ACTUAL_POSITIONS.get(code, 0)
        value = shares * price if price else 0
        positions_value[code] = value
        total_current_value += value
        if price is None:
            print(f"  !! {code} {get_stock_name(code)} 无法获取价格，跳过")

    total_asset = total_current_value + AVAILABLE_CASH
    print(f"  持仓市值: {total_current_value:,.2f}")
    print(f"  可用资金: {AVAILABLE_CASH:,.2f}")
    print(f"  总资产:   {total_asset:,.2f}\n")

    # 计算买卖
    sells = []
    buys = []

    header = make_header()
    print(f"\n{header}")
    # 分隔线长度 = header 的显示宽度
    print(f"  {'-'*cjk_len(header)}")

    for code in stocks:
        w = weights.get(code, 0)
        price = prices[code]
        if price is None:
            continue
        current_shares = ACTUAL_POSITIONS.get(code, 0)
        current_value = current_shares * price
        target_value = total_asset * w
        diff = target_value - current_value

        action = ""
        if diff > 500 and abs(diff) / target_value > rebalance_tolerance:
            action = f"<<< 买入 {(diff/price/100):.2f}手"
            buys.append((code, target_value, current_value, price))
        elif diff < -500 and abs(diff) / target_value > rebalance_tolerance:
            action = f">>> 卖出 {(-diff/price/100):.2f}手"
            sells.append((code, target_value, current_value, price))
        else:
            action = "-"

        name = get_stock_name(code)
        print(make_row(code, name,
                       f"{price:.2f}",
                       str(current_shares),
                       f"{current_value:.0f}",
                       f"{target_value:.0f}",
                       f"{diff:+.0f}",
                       action))

    # 卖出清单
    if sells:
        print(f"\n{'='*60}")
        print(f"【需要卖出】")
        print(f"{'='*60}")
        for code, target, current, price in sells:
            name = get_stock_name(code)
            diff_value = current - target
            sell_amount = int(diff_value / price / 100) * 100
            print(f"  卖出 {code} {name}: \033[31m{sell_amount}\033[0m股 × {price:.2f}元 = {sell_amount*price:,.0f}元")
            print(f"    当前市值 {current:,.0f} → 目标市值 {target:,.0f}")

    # 买入清单
    if buys:
        print(f"\n{'='*60}")
        print(f"【需要买入】")
        print(f"{'='*60}")
        for code, target, current, price in buys:
            name = get_stock_name(code)
            diff_value = target - current
            buy_amount = int(diff_value / price / 100) * 100
            print(f"  买入 {code} {name}: \033[31m{buy_amount}\033[0m股 × {price:.2f}元 = {buy_amount*price:,.0f}元")
            print(f"    当前市值 {current:,.0f} → 目标市值 {target:,.0f}")

    # 止盈检查
    print(f"\n{'='*60}")
    print(f"【止盈检查】")
    print(f"{'='*60}")
    take_profit_check(prices)

    if not sells and not buys:
        print(f"\n  无需调仓（偏离小于 {rebalance_tolerance*100:.0f}% 或金额不足500元）")


def take_profit_check(prices):
    """检查是否需要止盈卖出"""
    query_date = datetime.now().strftime('%Y%m%d')
    price_data = xtdata.get_market_data_ex(['close'], stocks, period='1d',
                                           start_time='', end_time=query_date, count=base_days, dividend_type='front')

    for code in stocks:
        shares = ACTUAL_POSITIONS.get(code, 0)
        if shares <= 0:
            continue
        df = price_data.get(code)
        if df is None or len(df) < base_days:
            continue
        df['daily_return'] = df['close'].pct_change() * 100
        df = df.iloc[1:].dropna(subset=['daily_return'])
        srt = df['daily_return'].sort_values()
        #print(srt[-6:])
        last_close = df['close'].iloc[-2]
        price = prices.get(code)
        if price is None:
            continue

        pct = (price - last_close) / last_close * 100
        last_3th = srt.iloc[-3]
        idx_30 = -30 if len(df) >= 30 else 0
        pct_30 = (price - df['close'].iloc[idx_30]) / df['close'].iloc[idx_30] * 100
        
        if pct >= last_3th:
            T = 10
            if code == '601899.SH':
                T = 20
            if pct_30 > T and pct < 9.8:
                sell_amount = int((shares / 2) / 100) * 100
                print(f"  {code} {get_stock_name(code)}: 触发止盈!")
                print(f"    今日涨幅 {pct:.2f}% > 120天第3高 {last_3th:.2f}%, 30日涨幅 {pct_30:.2f}%")
                print(f"    建议卖出 1/2 = {sell_amount}股")
            else:
                print(f"  {code} {get_stock_name(code)}: 涨幅达标但未触发({pct_30:.1f}%/30d) < {T}%")
                print(f"    今日涨幅 {pct:.2f}% > 120天第3高 {last_3th:.2f}%, 30日涨幅 {pct_30:.2f}%")
        else:
            print(f"  {code} {get_stock_name(code)}: 今日涨幅 {pct:.2f}% <= 阈值 {last_3th:.2f}% , 30日涨幅 {pct_30:.2f}%")


# ======================== 主流程 ========================

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"全天候 ETF 策略 — 模拟计算")
    print(f"{'='*60}\n")

    calc_ES_weights()
    calc_trades()

    print(f"\n{'='*60}")
    print(f"提示：修改文件顶部 ACTUAL_POSITIONS 和 AVAILABLE_CASH 后重新运行即可")
    print(f"{'='*60}")
