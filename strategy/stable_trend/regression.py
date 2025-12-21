#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from datetime import datetime
import time

import backtrader as bt  # 升级到最新版
import matplotlib.pyplot as plt  # 由于 Backtrader 的问题，此处要求 pip install matplotlib==3.2.2
import akshare as ak  # 升级到最新版
import pandas as pd
import json
import math
import numpy as np
import quantstats as qs

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

import sys
sys.path.append("../..")
from financial_data import FinancialData
from stock_price_cache import StockPriceCache
import least_squares_mothod as lsq

sys.path.append("../../market_cap")
from update_market import StockMarketCache

finan_data = FinancialData()
stock_price = StockPriceCache()
market_data = StockMarketCache()

def load_stock_data(file_path='../../stock_info.json'):
    """加载股票数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
            print(f"加载数据失败: {e}")
            return {}

stock_data = load_stock_data()

class StableTrendStrategy(bt.Strategy):

    def __init__(self):
        # 记录上一个交易日的月份，用于检测月份变化
        self.last_month = None
        self.last_week = None
        self.record = {}
        self.traded_codes = set()
        self.state = "PREPARED" ##{PREPARED, SELLED, BUYED}
        self.buyed_code = None
        self.each_cash = self.broker.getcash()
        for data in self.datas:
            self.record[data] = {
                'name': data._name,
                'buy_executed_this_month': False,
                'buy_size': 0,
                'buy_price': 0,
                'sell_price': 0,
                'is_buyed': False,
                'is_selled': False,
                'return_rate': None,

            }

    def next(self):
        # 获取当前交易日
        current_date = self.data.datetime.date(0)
        current_month = current_date.month
        year, current_week, _ = current_date.isocalendar()
        #print(current_date, " ", current_week)

        
        # 初始化last_month（只在第一个交易日）
        if self.last_month is None:
            self.last_month = current_month
            return

        if self.last_week is None:
            self.last_week = current_week

        #print(current_date)        
        # ========== 检测月份是否变更 ==========
        month_changed = (current_month != self.last_month)
        #week_changed = (current_week != self.last_week)
        if month_changed:
            self.pre_rebalance()
            self.last_month = current_month

    def pre_rebalance(self):
        #if len(self.last_selected_codes) > 0:
        #    return

        current_date = self.data.datetime.date(0)
        print("pre_rebalance ", current_date)

        R2_list = []
        FZ_list = []
        VR_list = []
        data_list = []
        for data in self.datas:
            R2 = self.calc_annualized_return_R2(data)
            FZ = self.calc_fanzhuan(data)
            VR = self.calc_volumn_rate(data)
            if R2 is None or FZ is None or VR is None:
                continue
            R2_list.append(R2)
            FZ_list.append(FZ)
            VR_list.append(VR)
            data_list.append(data)

        if len(data_list) == 0:
            return

        print("before standard R2")
        print(R2_list)
        R2_list = self.calc_standard_score(R2_list)
        print("after standard R2")
        print(R2_list)
        FZ_list = self.calc_standard_score(FZ_list)
        VR_list = self.calc_standard_score(VR_list)
        indicator_dict = {}
        for i in range(0, len(data_list)):
            indicator_dict[data_list[i]] = R2_list[i] * 1 + FZ_list[i] * 0 +  VR_list[i] * 0


        indicator_dict = list(sorted(indicator_dict.items(), key=lambda x:float(x[1]), reverse=True))

        print(indicator_dict)

        data = indicator_dict[0][0]
        if data != self.buyed_code:
            if self.buyed_code is not None:
                self.close(data=self.buyed_code)
                self.state = "SELLED"

            price = data.close[0] * 1.05
            size = int(self.broker.getvalue() / price / 100) * 100
            if size > 0:
                self.buy(data=data, size=size)
                self.record[data]['buy_size'] = size
                self.record[data]['buy_price'] = price
            
                print(f' {data._name} 申请价格: {price:.2f}, 买入数量: {size}')
                self.buyed_code = data
                self.traded_codes.add(data)
            else:
                name = data._name
                print(f'  ⛔警告：{name}至少需要 {price * 100:.2f} 现金不足，无法买入')
            self.state = "BUYED"

    def calc_volumn_rate(self, data, period = 25):
        if len(data) < period + 1:
            return None

        #print("============calc_volumn_rate ", data._name)
        volume = [data.volume[-i] for i in range(period, 0, -1)]
        mv = np.mean(volume)
        current_v = volume[-1]
        vr = current_v / mv
        if data.close[-1] < data.close[-2]:
            vr = -vr
        '''
        print(volume)
        print(mv)
        print(current_v)
        print("vr ", vr)
        '''

        return vr

    def calc_fanzhuan(self, data, period = 10):
        # 计算一个周期内的涨跌幅
        # 再统计这个周期内每天的涨跌幅，计算这些涨跌幅的标准差
        # 用周期总的涨跌幅 / 标准差，得到Z_score
        # Z_score 代表着总体涨跌幅与平均涨跌幅的比值
        # Z_score 绝对值越大，说明这个周期内的涨跌幅度远超平日的涨跌幅
        # Z_score 如果大于0且值很大，那说明涨幅远超平时，很可能涨过头了，预计会跌
        # 所以返回的因子要对Z_score取负方向

        if len(data) < period + 1:
            return None

        #print("============calc_fanzhuan ", data._name)
        price = [data.close[-i] for i in range(period, 0, -1)]
        R_short = (price[-1] - price[0]) / price[0]
        return_ratio = np.diff(price) / price[:-1]
        se = np.std(return_ratio, ddof=1)
        Z_score = R_short / se
        '''
        print(price)
        print(R_short)
        print(return_ratio)
        print("SE ", se)
        print("Z ", Z_score)
        '''

        return -Z_score

    def calc_annualized_return_R2(self, data, period = 25):
        if len(data) < period + 1:  # 需要26天数据
            return None
        print("==========calc_annualized_return_R2 ", data._name)
        price = [data.close[-i] for i in range(period, 0, -1)]
        log_price = list(math.log(p) for p in price)
        k, b, se = lsq.simple_linear_regression(log_price)
        annualized_return = k * 252
        R2 = lsq.calc_R_squared(log_price)
        
        print(price)
        print(annualized_return)
        print(R2)
        print(R2 * R2 * annualized_return)
        
        return R2 * R2 * annualized_return

    def calc_standard_score(self, score_list):
        num = len(score_list)
        M = np.mean(score_list)
        Sum = 0
        for score in score_list:
            Sum += (score - M) * (score - M)
        se = math.sqrt(Sum / num)

        result = []
        for score in score_list:
            result.append((score - M) / se)

        return result

    def calc_return(self, data):
        if self.record[data]['is_buyed'] and not self.record[data]['is_selled']:
            buy_price = self.record[data]['buy_price']
            price = data.close[0]
            return_rate = (price / buy_price - 1) * 100
            return return_rate
        else:
            return None

    def notify_order(self, order):
        """基本的订单状态处理"""
        data = order.data
        name = data._name
        trade_date = data.datetime.date(0)  # 获取当前Bar的日期（date对象
        trade_date_str = data.datetime.date(0).strftime('%Y-%m-%d')
    
        # 1. 订单已提交/接受 - 无需特殊处理
        if order.status in [order.Submitted, order.Accepted]:
            # 订单正在处理中，等待后续状态
            #print(f"{name} 订单{order.getstatusname()} - 等待执行")
            return
    
        # 2. 订单完成成交
        if order.status == order.Completed:
            if order.isbuy():
                self.record[data]['buy_price'] = order.executed.price
                self.record[data]['is_buyed'] = True
                self.record[data]['is_selled'] = False

                print(f"✅ {name} {trade_date_str} 买入成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   成本: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            else:  # 卖出订单
                buy_price = self.record[data]['buy_price']
                value = (order.executed.price - buy_price) * abs(order.executed.size)
                self.record[data]['sell_price'] = order.executed.price
                self.record[data]['is_buyed'] = False
                self.record[data]['is_selled'] = True
                curr_return_rate = self.record[data]['sell_price'] / buy_price - 1
                return_rate = self.record[data]['return_rate']
                if return_rate is None:
                    return_rate = curr_return_rate
                else:
                    return_rate = (1 + return_rate) * (1 + curr_return_rate) - 1
                self.record[data]['return_rate'] = return_rate

                print(f"⭕ {name} {trade_date_str} 卖出成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   买入价格 {buy_price} 收益: {value:.2f}, 佣金: {order.executed.comm:.2f}")
            print(f"现有现金 {self.broker.getcash():.2f}")
            print("")
    
        # 3. 订单失败情况
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print(f"❌ {name} 订单失败: {order.getstatusname()}")
            #if data in self.last_selected_codes:
            #    print(f"last selected codes 中剔除 {data._name}")
            #   self.last_selected_codes.remove(data)
        
            # 根据不同失败原因处理
            if order.status == order.Canceled:
                print("   订单已被取消")
            elif order.status == order.Margin:
                print("   保证金不足")
            elif order.status == order.Rejected:
                print("   订单被拒绝")
            print("")
    
        # 4. 重置订单变量（重要！）
        self.order = None  # 允许提交新订单

    def stop(self):
        """策略结束时的总结"""
        final_value = self.broker.getvalue()
        initial_cash = self.broker.startingcash
        profit = final_value - initial_cash
        total_return = (profit / initial_cash) * 100

        print("\n" + "="*50)
        print("策略执行总结:")
        print("="*50)
        print("交易过股票：")
        current_date = self.data.datetime.date(0)
        current_year = current_date.year
        for data in self.traded_codes:
            code = data._name
            return_rate = self.record[data]['return_rate']
            if self.record[data]['is_buyed'] and not self.record[data]['is_selled']:
                buy_price = self.record[data]['buy_price']
                price = data.close[0]
                curr_return_rate = price / buy_price - 1
                if return_rate is None:
                    return_rate = curr_return_rate
                else:
                    return_rate = (1 + return_rate) * (1 + curr_return_rate) - 1
            elif return_rate is None:
                return_rate = 0

            print(f"{code}  收益率 {return_rate * 100:.2f}%")

        print("")
        print(f"初始资金: {initial_cash:.2f}")
        print(f"最终价值: {final_value:.2f}")
        print(f"总收益率: {total_return:.2f}%")

def run_backtest(CURRENT_YEAR = None):
    print("\n")
    START_YEAR = None
    END_YEAR = None
    if CURRENT_YEAR is None:
        START_YEAR = 2014
        END_YEAR = 2025
        print(f"{START_YEAR} -- {END_YEAR}")
    else:
        print(f"{CURRENT_YEAR} 年")
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 设置佣金
    cerebro.broker.setcommission(
        commission=0.003,      # 佣金率
        margin=None,           # 关键：设置为None禁用保证金
        mult=1.0,
        stocklike=True         # 股票模式
    )
    
    # 添加策略
    cerebro.addstrategy(StableTrendStrategy)

    start_time = time.time()
    code_list = ['510300', '513500', '518880', '159920']
    #code_list = ['159920']
    for code in code_list:
        data_name = stock_price.get_index_price(code)
        data_name.index = pd.to_datetime(data_name['date'])
        #print(code)
        #print(data_name)
        from_date = None
        to_date = None
        if CURRENT_YEAR is None:
            from_date = datetime(START_YEAR - 1, 11, 25)
            to_date = datetime(END_YEAR, 12, 31)
        else:
            from_date = datetime(CURRENT_YEAR - 1, 11, 25)
            to_date = datetime(CURRENT_YEAR, 12, 31)
        data = bt.feeds.PandasData(
            dataname=data_name,  # 创建示例数据
            fromdate=from_date,
            todate=to_date
        )

        # 添加数据
        cerebro.adddata(data, name=code)


    end_time = time.time()
    print(f"cerebro adddata {end_time - start_time:.2f}s")

    start_time = end_time
    # 设置初始资金
    start_cash = 10000
    cerebro.broker.setcash(start_cash)
    
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    
    # 打印初始资金
    print(f'初始投资组合价值: {cerebro.broker.getvalue() / 10000.0:.2f} 万')
    
    # 运行回测
    results = cerebro.run()

    final_value = cerebro.broker.getvalue()
    initial_cash = cerebro.broker.startingcash
    total_return = (final_value / initial_cash - 1) * 100

    end_time = time.time()
    print(f"cerebro run {end_time - start_time:.2f}s")

    start_time = end_time
    
    # 打印最终资金
    print(f'最终投资组合价值: {cerebro.broker.getvalue():.2f}')
    
    # 打印分析结果
    strat = results[0]
    timereturn = strat.analyzers.timereturn.get_analysis()
    returns = pd.Series(timereturn)
    returns.index = pd.to_datetime(returns.index)

    print("\n🔍 策略表现:")
    print(f"累计收益: {qs.stats.comp(returns):.2%}")
    print(f"年化收益: {qs.stats.cagr(returns):.2%}")
    print(f"夏普比率: {qs.stats.sharpe(returns):.3f}")
    print(f"最大回撤: {qs.stats.max_drawdown(returns):.2%}")

    # 生成完整报告
    '''
    qs.reports.html(
        returns,
        output=f'{CURRENT_YEAR}_rising_profit_sz.html',
        title='策略分析',
        rf=0.02
    )
    '''
    
    # 绘图
    cerebro.plot()
    #cerebro.plot(style='candlestick')

    # Use quantstats to output backtrader backtest results
    #qs.reports.html(returns, output='temp.html')

    #stock = qs.utils.download_returns(returns)
    print("\n" + "="*50)

    return total_return


# 运行回测
if __name__ == '__main__':
    #run_backtest()
    #exit()
    START_TIME = time.time()

    Test_single_year = True
    #Test_single_year = False

    if Test_single_year:
        run_backtest(2017)
    else:
        return_dict = {}
        for CURRENT_YEAR in range(2014,2026):
            r = run_backtest(CURRENT_YEAR)
            return_dict[CURRENT_YEAR] = r

        total_r = 1
        years = 0
        for y,r in return_dict.items():
            print(f"{y} 收益率 {r:.2f}%")
            total_r *= (1 + r / 100.0)
            years += 1

        annualized_return = math.pow(total_r, 1/years) - 1
        print(f"\n总收益率 {(total_r - 1) * 100:.2f} %")
        print(f"年化收益率 {annualized_return * 100:.2f} %")
    
    #plot_scatter(indicator_list, return_list)
    print(f"\n耗时 {time.time() - START_TIME:.2f}s")