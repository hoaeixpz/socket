# -*- coding: utf-8 -*-
"""
全天候 ETF 策略 — QMT 实盘版
母版：C:\socket\JoinQuant\全天候策略\all_weather.py

策略原理：
  根据每只 ETF 前 120 个交易日的日收益率，取最大的 5%（6个交易日），
  计算其均值 ES，以及全部 120 日均值 AR。
  权重 weight ∝ ES * (1 - AR)。
  每月初调仓（先卖后买），偏离目标仓位 6% 以上才交易。
  每日尾盘检测止盈：若当日涨幅超过过去 120 天第 3 高涨幅，且 30 日涨幅 > 10%，卖出一半。
"""
from xtquant import xtdata
from xtquant.xttype import StockAccount
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant import xtconstant
import time
from datetime import datetime, timedelta
import math
import sys
import subprocess
import psutil
from apscheduler.schedulers.background import BackgroundScheduler
import signal
import re
import os

DEBUG_DAILY_MODE = False
#DEBUG_DAILY_MODE = True

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class Tee:
    """将输出同时写入终端和日志文件"""
    def __init__(self, log_file_path):
        self.terminal = sys.__stdout__
        self.log = open(log_file_path, 'a', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        clean_message = ansi_escape.sub('', message)
        self.log.write(clean_message)
        self.log.flush()

    def flush(self):
        try:
            self.terminal.flush()
            self.log.flush()
        except ValueError:
            pass

    def close(self):
        self.log.close()

if not DEBUG_DAILY_MODE:
    log_name = datetime.now().strftime('%Y%m%d')
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logfiles')
    os.makedirs(log_dir, exist_ok=True)
    tee = Tee(os.path.join(log_dir, f"aw_{log_name}.log"))
    sys.stdout = tee

red_c = '\033[31m'
green_c = '\033[32m'

scheduler = BackgroundScheduler()

class G():
    pass
g = G()

class MyXtQuantTraderCallback(XtQuantTraderCallback):
    def on_disconnected(self):
        print(datetime.now(), '连接断开回调')

    def on_stock_order(self, order):
        print(datetime.now(), '委托回调 投资备注', order.order_remark)

    def on_stock_trade(self, trade):
        print(datetime.now(), '成交回调', trade.order_remark,
              f"委托方向(48买 49卖) {trade.offset_flag} 成交价格 {trade.traded_price} 成交数量 {trade.traded_volume}")

    def on_order_error(self, order_error):
        print(f"委托报错回调 {order_error.order_remark} {order_error.error_msg}")

    def on_cancel_error(self, cancel_error):
        print(datetime.now(), 'on_cancel_error')

    def on_order_stock_async_response(self, response):
        print(f"异步委托回调 投资备注: {response.order_remark}")

    def on_cancel_order_stock_async_response(self, response):
        print(datetime.now(), 'on_cancel_order_stock_async_response')

    def on_account_status(self, status):
        print(datetime.now(), 'on_account_status')


def sleep_sec(seconds):
    time.sleep(seconds)


def sleep_mins(minutes):
    time.sleep(minutes * 60 + 1)


def init():
    print("全天候策略 init")
    path = 'C:\\QMT\\国金证券QMT交易端\\userdata_mini'
    #path = 'C:\\QMT\\userdata_mini'
    session_id = int(time.time())
    g.xt_trader = XtQuantTrader(path, session_id)
    g.callback = MyXtQuantTraderCallback()
    g.xt_trader.register_callback(g.callback)
    g.xt_trader.start()
    connect_result = g.xt_trader.connect()
    print('建立交易连接，返回0表示连接成功', connect_result)

    g.account = StockAccount('8885388757')

    info = g.xt_trader.query_stock_asset(g.account)
    available_cash = info.cash

    # 标的池（JoinQuant 代码格式 → QMT 格式：XSHG→SH, XSHE→SZ）
    g.stocks = [
        "518880.SH",  # 黄金ETF
        "159985.SZ",  # 豆粕ETF
        "513100.SH",  # 纳指ETF
        "601288.SH",  # 农业银行
        "600900.SH",  # 长江电力
    ]

    g.base_days = 120
    g.weights = {}
    g.refreshed = False

    g.recordlist = []
    g.record_max = 0

    g.rebalance_day = 1      # 每月第1个交易日调仓
    g.rebalance_tolerance = 0.06  # 偏离 6% 才交易

    g.last_pos_value = info.total_asset

    print(f"{red_c}⭕\033[0m全天候策略初始化完成：{len(g.stocks)}只标的, 初始资产{g.last_pos_value}")


def is_trading_day():
    if DEBUG_DAILY_MODE:
        return True
    current_date = datetime.now()
    today = current_date.strftime('%Y%m%d')
    date = get_trading_dates('399101.SZ', today)
    return today == date[-1]


def get_trading_dates(stock, dt_str, days=7):
    xtdata.download_history_data(stock, period='1d', incrementally=True)
    history_data = xtdata.get_market_data_ex(['close'], [stock],
                                             period='1d', start_time='', end_time=dt_str, count=days)
    dates = history_data[stock].index.tolist()
    return dates


def get_stock_name(stock):
    detail = xtdata.get_instrument_detail(stock)
    if detail:
        return detail['InstrumentName']
    return stock


def get_last_price(stock):
    full_tick = xtdata.get_full_tick([stock])
    if stock in full_tick and full_tick[stock]:
        lp = full_tick[stock]['lastPrice']
        if lp == 0:
            print(stock, " 获取当前价格异常,股价为0")
        return lp
    print(stock, " 获取当前价格异常")
    return None


def get_positions():
    positions = {}
    objlist = g.xt_trader.query_stock_positions(g.account)
    for obj in objlist:
        if obj.volume > 0:
            positions[obj.stock_code] = obj
    return positions


def get_current_holding_stocks():
    positions = g.xt_trader.query_stock_positions(g.account)
    return [pos.stock_code for pos in positions if pos.volume > 0]


def info_position():
    current_date = datetime.now()
    positions = g.xt_trader.query_stock_positions(g.account)

    if len(positions) > 0:
        info = g.xt_trader.query_stock_asset(g.account)
        available_cash = info.cash
        position_value = info.market_value
        total_value = info.total_asset
        print(f'******************当日({current_date}) (周{current_date.weekday()+1}) 持仓市值: {position_value:.2f}元*******************')

        for pos in positions:
            stock = pos.stock_code
            stock_name = get_stock_name(stock)
            if pos.volume == 0:
                continue
            if pos.avg_price <= 0:
                continue
            price = pos.market_value / pos.volume
            ratio = (price / pos.avg_price - 1) * 100
            color = red_c if ratio > 0 else green_c
            print(f"{green_c}✅\033[0m持仓: {stock_name}({stock}), "
                  f"占比 {pos.market_value / total_value * 100:.1f}%, "
                  f"涨跌幅: {color}{ratio:.2f}%\033[0m, "
                  f"数量: {pos.volume}, 市值: {pos.market_value:.1f}元")

        print(f'{green_c}✅\033[0m*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')

        if current_date.hour == 15:
            daily_return = total_value - g.last_pos_value
            rate_of_return = daily_return / g.last_pos_value * 100
            color = red_c if daily_return > 0 else green_c
            print('==============================')
            print(f'今日收益: {color}{daily_return:.2f}\033[0m 元')
            print(f'收益率:   {color}{rate_of_return:.2f} %\033[0m')
            print('==============================\n\n')
            g.last_pos_value = total_value


def buy_target_value(stock, target_value):
    if DEBUG_DAILY_MODE:
        return
    positions = get_positions()
    current_value = positions[stock].market_value if stock in positions else 0
    volume = target_value - current_value
    if volume > 0:
        current_price = get_last_price(stock)
        if current_price is None or current_price == 0:
            return
        amount = int(volume / current_price / 100) * 100
        if amount < 100:
            print(f"{stock} {get_stock_name(stock)} 买入金额不足1手，跳过")
            return
        buy_price = current_price + 0.1
        async_seq = g.xt_trader.order_stock_async(
            g.account, stock, xtconstant.STOCK_BUY, amount,
            xtconstant.FIX_PRICE, buy_price, '',
            f'Buy {stock} {target_value:.0f}元'
        )
        print(f"买入 {stock} {get_stock_name(stock)} {amount}股 * {buy_price:.2f} 目标{target_value:.2f}")
        if async_seq == -1:
            print(f"买入 {stock} 失败")


def sell_target_value(stock, target_value):
    if DEBUG_DAILY_MODE:
        return
    positions = g.xt_trader.query_stock_positions(g.account)
    for pos in positions:
        if stock != pos.stock_code or pos.volume == 0:
            continue
        if target_value == 0:
            async_seq = g.xt_trader.order_stock_async(
                g.account, stock, xtconstant.STOCK_SELL, pos.volume,
                xtconstant.MARKET_PEER_PRICE_FIRST, 0, '',
                f'清仓{stock}'
            )
            print(f"清仓 {stock} {get_stock_name(stock)} {pos.volume}股")
        else:
            volume = pos.market_value - target_value
            if volume > 0:
                current_price = get_last_price(stock)
                if current_price is None or current_price == 0:
                    return
                amount = int(volume / current_price / 100) * 100
                if amount < 100:
                    print(f"{stock} {get_stock_name(stock)} 卖出金额不足1手，跳过")
                    return
                async_seq = g.xt_trader.order_stock_async(
                    g.account, stock, xtconstant.STOCK_SELL, amount,
                    xtconstant.FIX_PRICE, current_price - 0.1, '',
                    f'Sell {stock} {target_value:.0f}元'
                )
                print(f"卖出 {stock} {get_stock_name(stock)} {amount}股 目标{target_value:.2f}")
        if async_seq == -1:
            print(f"卖出 {stock} 失败")


def sell_shares(stock, shares):
    """卖出指定股数"""
    if DEBUG_DAILY_MODE:
        return
    positions = g.xt_trader.query_stock_positions(g.account)
    for pos in positions:
        if stock != pos.stock_code:
            continue
        available = min(pos.volume, shares)
        if available < 100:
            print(f"{stock} 可卖股数不足100，跳过")
            return
        async_seq = g.xt_trader.order_stock_async(
            g.account, stock, xtconstant.STOCK_SELL, available,
            xtconstant.MARKET_PEER_PRICE_FIRST, 0, '',
            f'止盈{stock} {available}股'
        )
        print(f"止盈卖出 {stock} {get_stock_name(stock)} {available}股")
        if async_seq == -1:
            print(f"止盈卖出 {stock} 失败")


def is_first_trading_day_of_month():
    """判断今天是否为本月第一个交易日

    原理：如果上一个交易日属于上个月，则今天是本月第一个交易日。
    例如 8月3日是周一，上一个交易日是7月31日（7月），则8月3日是8月第一个交易日。
    """
    if DEBUG_DAILY_MODE:
        return True
    current_date = datetime.now()
    today_str = current_date.strftime('%Y%m%d')
    dates = get_trading_dates('399101.SZ', today_str, days=28)  # 取近28个交易日

    # 最新交易日应为今天
    last_date = dates[-1]
    try:
        last_date_str = last_date.strftime('%Y%m%d')
    except AttributeError:
        last_date_str = str(last_date)[:10].replace('-', '')
    if last_date_str != today_str:
        return False  # 今天不是交易日

    # 上一个交易日的月份与本月不同 → 本月第一个交易日
    prev_trading_day = dates[-2]
    try:
        prev_month = prev_trading_day.month
    except AttributeError:
        prev_month = int(str(prev_trading_day)[5:7])
    return prev_month != current_date.month


# ======================== 权重计算 ========================

def calc_ES_weights():
    """计算 ES 权重：weight ∝ ES * (1 - AR)

    ES = 过去120天日收益率最高的 5%（6天）的均值
    AR = 过去120天全部日收益率均值
    """
    alpha = 0.05
    num = int(g.base_days * alpha)
    print(f"num = {num}")

    # 下载历史数据
    for stock in g.stocks:
        xtdata.download_history_data(stock, period='1d', incrementally=True)

    query_date = datetime.now().strftime('%Y%m%d')
    price_data = xtdata.get_market_data_ex(
        ['close'], g.stocks, period='1d',
        start_time='', end_time=query_date, count=g.base_days
    )

    weights = {}
    for code in g.stocks:
        df = price_data.get(code)
        if df is None or len(df) < g.base_days:
            weight = 0
        else:
            df['daily_return'] = df['close'].pct_change() * 100
            df = df.iloc[1:]
            df = df.dropna(subset=['daily_return'])
            sorted_returns = df['daily_return'].sort_values()
            stock_name = get_stock_name(code)
            print(f'{code} {stock_name}')
            print(sorted_returns.tail(6))
            ES = sorted_returns.tail(num).mean()
            print(f"ES {ES:.3f}")
            AR = sorted_returns.mean()
            print(f"AR {AR:.3f}")
            weight = ES * (1 - AR)
        weights[code] = weight

    print(f'权重:{weights}')

    # 标准化
    total_weight = sum([w for w in weights.values()])
    if total_weight > 0:
        for code in g.stocks:
            g.weights[code] = weights[code] / total_weight

    for stock, w in g.weights.items():
        print(f'{stock} {get_stock_name(stock)} 权重{100*w:.2f}%')


# ======================== 调仓 ========================

def before_market_open():
    """每月第一个交易日盘前：计算权重"""
    if not is_first_trading_day_of_month():
        return
    print("========== 月初计算权重 ==========")
    calc_ES_weights()


def rebalance_sell():
    """每月第一个交易日卖出：偏离目标 6% 以上的持仓先卖出"""
    if not is_first_trading_day_of_month():
        return
    print("========== 月初调仓 卖出 ==========")
    g.refreshed = True

    if not g.weights:
        print("权重未计算，先计算权重")
        calc_ES_weights()

    info = g.xt_trader.query_stock_asset(g.account)
    total_value = info.total_asset

    positions = get_positions()
    for stock, pos in positions.items():
        current_price = get_last_price(stock)
        if current_price is None or current_price == 0:
            continue
        target_value = total_value * g.weights.get(stock, 0)
        if pos.market_value > target_value * (1 + g.rebalance_tolerance):
            amount = int((pos.market_value - target_value) / current_price / 100) * 100
            if amount >= 100:
                print(f'>>>>>>>>>>>>>>>>>卖出>>>>>>>>>>>>>>>>')
                print(f'{stock} {get_stock_name(stock)} 目标市值{target_value:.2f}，'
                      f'当前市值{pos.market_value:.2f}, 卖出{amount}股 * {current_price}元')
                sell_shares(stock, amount)

    print("========== 卖出结束 ==========")


def rebalance_buy():
    """每月第一个交易日买入：偏离目标 6% 以上的持仓补仓"""
    if not is_first_trading_day_of_month():
        return
    print("========== 月初调仓 买入 ==========")
    g.refreshed = True

    if not g.weights:
        print("权重未计算，跳过买入")
        return

    info = g.xt_trader.query_stock_asset(g.account)
    total_value = info.total_asset

    positions = get_positions()
    for stock, w in g.weights.items():
        if w <= 0.00001:
            continue
        current_price = get_last_price(stock)
        if current_price is None or current_price == 0:
            continue
        target_value = total_value * w
        current_value = positions[stock].market_value if stock in positions else 0

        if current_value < target_value * (1 - g.rebalance_tolerance):
            print(f'{stock} {get_stock_name(stock)} 目标股数{target_value / current_price:.2f}')
            amount = int((target_value - current_value) / current_price / 100) * 100
            if amount >= 100:
                print(f'<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
                print(f'{stock} {get_stock_name(stock)} 目标市值{target_value:.2f}，'
                      f'当前市值{current_value:.2f}, 买入{amount}股 * {current_price}元')
                buy_target_value(stock, target_value)

    info_position()
    print("========== 买入结束 ==========")


# ======================== 止盈 ========================

def take_profit():
    """每日尾盘止盈检测

    若当日涨幅 > 过去120天日收益率第3高，且30日涨幅 > 10% 且当日未涨停，卖出一半。
    """
    if not is_trading_day():
        return

    # 下载数据
    for stock in g.stocks:
        xtdata.download_history_data(stock, period='1d', incrementally=True)

    query_date = datetime.now().strftime('%Y%m%d')
    price_data = xtdata.get_market_data_ex(
        ['close'], g.stocks, period='1d',
        start_time='', end_time=query_date, count=g.base_days
    )

    for code in g.stocks:
        df = price_data.get(code)
        if df is None or len(df) < g.base_days:
            continue

        df['daily_return'] = df['close'].pct_change() * 100
        df = df.iloc[1:]
        df = df.dropna(subset=['daily_return'])
        sorted_returns = df['daily_return'].sort_values()
        last_close = df['close'].iloc[-1]

        current_price = get_last_price(code)
        if current_price is None or current_price == 0:
            continue

        pct = (current_price - last_close) / last_close * 100
        last_3th = sorted_returns.iloc[-3]

        if pct > last_3th:
            print("=====================================")
            print(code)
            print(f"今日涨幅 {pct:.3f}% > 过去120天第3名 {last_3th:.3f}%")
            print(sorted_returns.tail(6))

            last_price_30th = df['close'].iloc[-30] if len(df) >= 30 else df['close'].iloc[0]
            pct_30 = (current_price - last_price_30th) / last_price_30th * 100
            print(f"今日相比于30天前，涨了 {pct_30:.3f}%")

            # 30日涨幅 > 10% 且未涨停（< 9.8%）
            if pct_30 > 10 and pct < 9.8:
                positions = get_positions()
                if code in positions:
                    pos = positions[code]
                    sell_amount = int((pos.volume / 2) / 100) * 100
                    print(f"卖出 1/2 股份，总计{sell_amount}股")
                    sell_shares(code, sell_amount)
                    info_position()


# ======================== 盘后 ========================

def after_trading_end():
    """盘后记录"""
    if not g.refreshed:
        return
    g.refreshed = False

    info = g.xt_trader.query_stock_asset(g.account)
    total_value = info.total_asset

    # 回撤记录
    if total_value > g.record_max:
        g.recordlist.clear()
    if g.record_max > total_value:
        max_drawdown = (1 - total_value / g.record_max) * 100
        print(f"最大回撤: {max_drawdown:.2f}%")

    g.recordlist.append(total_value)
    if len(g.recordlist) > 120:
        g.recordlist.pop(0)
    g.record_max = max(g.recordlist)

    info_position()


# ======================== 调度器 ========================

def shutdown_scheduler(signum, frame):
    print(f"\n收到信号 {signum}，正在关闭调度器...")
    scheduler.shutdown(wait=False)
    tee.close()
    sys.exit(0)


def run_strategy():
    """注册定时任务"""
    task_time = [
        [9, 30],   # before_market_open — 计算权重
        [10, 0],   # rebalance_sell — 卖出
        [10, 2],   # rebalance_buy — 买入
        [14, 55],  # take_profit — 止盈检测
        [15, 1],   # after_trading_end — 盘后记录
    ]

    signal.signal(signal.SIGINT, shutdown_scheduler)
    signal.signal(signal.SIGTERM, shutdown_scheduler)

    scheduler.add_job(before_market_open, 'cron', hour=task_time[0][0], minute=task_time[0][1])
    scheduler.add_job(rebalance_sell,     'cron', hour=task_time[1][0], minute=task_time[1][1])
    scheduler.add_job(rebalance_buy,      'cron', hour=task_time[2][0], minute=task_time[2][1])
    scheduler.add_job(take_profit,        'cron', hour=task_time[3][0], minute=task_time[3][1])
    scheduler.add_job(after_trading_end,  'cron', hour=task_time[4][0], minute=task_time[4][1])

    try:
        print("全天候策略调度器启动")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("服务已手动停止")

    while True:
        print("sleep a day")
        sleep_hours(24)


if __name__ == "__main__":
    init()
    run_strategy()