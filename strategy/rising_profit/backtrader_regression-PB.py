#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Author：Airyv
@Project：test 
@File：quantstats_demo.py
@Date：2024/1/1 21:45 
@desc:
'''

'''
策略规则，筛选净利润增长率连续3年大于20%的股票
对市净率PB 进行排序，选择前五的进行买入，
每个月调一次仓位

PB = 市值 / (净资产 - 商誉)

'''

from datetime import datetime
import time

import backtrader as bt  # 升级到最新版
import matplotlib.pyplot as plt  # 由于 Backtrader 的问题，此处要求 pip install matplotlib==3.2.2
import akshare as ak  # 升级到最新版
import pandas as pd
import json
import math
#import quantstats as qs
#import pyfolio as pf

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

import sys
sys.path.append("../..")
from financial_data import FinancialData
from stock_price_cache import StockPriceCache
sys.path.append("../../market_cap")
from update_market import StockMarketCache

finan_data = FinancialData()
stock_price = StockPriceCache()
market_data = StockMarketCache()

# 筛选净利润增长率 > 20%
Profit_Grown_Ratio_Threshold = 20 

def load_stock_data(file_path='../../stock_info.json'):
    """加载股票数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
            print(f"加载数据失败: {e}")
            return {}

class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理pandas和numpy数据类型"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            obj = round(obj, 2)
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):  # 处理NaN值
            return None
        elif isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d')
        # 让基类处理其他类型
        return super().default(obj)
        
def save_results(stock_data, file_path='../../stock_info.json'):
    """保存分析结果"""
    stock_code = stock_data.get('stock_code')
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        if stock_code is None:
            print(f"分析结果已保存到: {file_path}")
        else:
            print(f"{stock_code}分析结果已保存到: {file_path}")
    except Exception as e:
        if stock_code is None:
            print(f"保存结果失败: {e}")
        else:
            print(f"{stock_code}保存结果失败: {e}")

stock_data = load_stock_data()

def find_good_stocks(CURRENT_YEAR:int, stock_code):
    '''
    条件：净利润增长率连续3年大于20%
    '''
    df = finan_data.get_indicator_data(stock_code, "归属母公司净利润增长率")
    Y = 3
    zzl = finan_data.get_indicator_recent_year(df, Y, CURRENT_YEAR-1)

    count = 0
    for date, pct in zzl:
        year = int(date[0:4])
        if CURRENT_YEAR - year > Y:
            continue
        #print("year pct ", year, " ", pct)
        if date[4:6] == '12':
            if math.isnan(pct):
                continue

            if pct < Profit_Grown_Ratio_Threshold:
                return False
            count += 1

    if count < 3:
        return False
    '''
    print(stock_code)
    for year, pct in zzl:
        if year[4:6] == '12':
            print(year, " ", float(pct))
    '''

    return True

def calc_PB(stock_code, date):
    market_df = market_data.load_market_df(stock_code)
    mv = market_data.get_specify_date_market(market_df, date)
    if mv is None:
        return None

    date = date.replace("-", "")
    month = int(date[4:6])
    if month % 3 != 0:
        month = int(month / 3) * 3
        if month == 0:
            year = int(date[0:4]) - 1
            date = str(year) + "-12-30"
        else:
            if month < 10:
                date = date[0:4] + str(0) + str(month) + date[6:]
            else:
                date = date[0:4] + str(month) + date[6:]

    df = finan_data.get_indicator_data(stock_code, "股东权益合计(净资产)")
    jzc = finan_data.get_indicator_value(stock_code, "股东权益合计(净资产)", date)
    good_will = finan_data.get_indicator_value(stock_code, "商誉", date)

    print("净资产： ", jzc)
    print("商誉： ", good_will)
    print("市值： ", mv)

    if math.isnan(good_will):
        return None

    if good_will > jzc:
        return None
        
    One = 100000000
    PB = mv * One / (jzc - good_will)
    print(PB)
    return PB

def load_stock_list(CURRENT_YEAR):
    code_list = []
    if not stock_data:
        print("没有找到股票数据")
        return {}
    else:
        print("筛选净利润增长率连续3年 > 20%")
        for stock_code, stock_info in stock_data.items():
            stock_name = stock_info.get('stock_name', '')

            if find_good_stocks(CURRENT_YEAR, stock_code):
                code_list.append(stock_code)

    #print(code_list)
    return code_list

class MonthlyStrategy(bt.Strategy):

    def __init__(self):
        # 记录上一个交易日的月份，用于检测月份变化
        self.last_month = None
        self.record = {}
        self.traded_codes = set()
        self.selected_codes = []
        self.last_selected_codes = []
        self.state = "PREPARED" ##{PREPARED, SELLED, BUYED}
        for data in self.datas:
            self.record[data] = {
                'name': data._name,
                'buy_executed_this_month': False,
                'buy_size': 0,
                'buy_price': 0
            }
        self.each_cash = self.broker.getcash() / 5

    def next(self):
        # 获取当前交易日
        current_date = self.data.datetime.date(0)
        current_month = current_date.month
        
        # 初始化last_month（只在第一个交易日）
        if self.last_month is None:
            self.last_month = current_month
            return

        #print(current_date)
        
        # ========== 检测月份是否变更 ==========
        month_changed = (current_month != self.last_month)
        if month_changed:
            if self.state == "BUYED":
                self.state = None
                cash = self.broker.getcash()
                each_cash = self.each_cash + cash / 5
                self.each_cash = min(each_cash, self.broker.getvalue() / 5)
                print("")
                print("- "*25)
                print(f"调整各股现金额度 {self.each_cash:.2f}")

            self.pre_rebalance()
            self.last_month = current_month        

        if self.state == "PREPARED":
            self.execute_rebalance()
            if self.state == "BUYED":
                self.last_selected_codes = self.selected_codes
                self.selected_codes = []
        elif self.state == "SELLED":
            self.execute_rebalance()
            self.last_selected_codes = self.selected_codes
            self.selected_codes = []

    def pre_rebalance(self):
        #if len(self.last_selected_codes) > 0:
        #    return

        current_date = self.data.datetime.date(0)
        print("pre_rebalance ", current_date)
        year = current_date.year
        month = current_date.month
        #if month > 1:
        #    return

        month = month - 1
        date = ''
        if month == 0:
            date = str(year-1) + "-12-30"
        elif month < 10:
            month = "0"+ str(month)
            date = str(year) + "-" + month + "-30"
        else:
            month = str(month)
            date = str(year) + "-" + month + "-30"
        
        if month == "02":
            date = str(year) + "-02-28"

        PB_dict = {}
        for data in self.datas:
            stock_code = data._name
            PB = calc_PB(stock_code, date)
            if PB is None:
                continue
            PB_dict[data] = PB

        PB_dict = list(sorted(PB_dict.items(), key=lambda x:float(x[1])))

        if len(self.selected_codes) == 0:
            for data, PB in PB_dict[0:5]:
                self.selected_codes.append(data)
                self.traded_codes.add(data._name)

        rebalanced = False
        for data in self.last_selected_codes:
            if data not in self.selected_codes:
                rebalanced = True
        for data in self.selected_codes:
            if data not in self.last_selected_codes:
                rebalanced = True
        
        if rebalanced:
            print(date)
            for data, PB in PB_dict[0:8]:
                print(f"{data._name}  {PB:.2f}")
            '''
            print("last codes")
            for data in self.last_selected_codes:
                print(data._name)
            print("now codes")
            for data in self.selected_codes:
                print(data._name)
            '''

        if rebalanced:
            self.state = "PREPARED"
        else:
            self.state = None
            self.selected_codes = []
            
    def execute_rebalance(self):
        current_date = self.data.datetime.date(0)
        #print("exe rebalance ", current_date, " ", self.state)

        if self.state == "PREPARED":
            if len(self.last_selected_codes) > 0:
                self.execute_sell()
                #print("execute_sell ", current_date)
            elif len(self.selected_codes) > 0:
                self.execute_buy()
                #print("execute_buy ", current_date)

        elif self.state == "SELLED":
            self.execute_buy()
            #print("execute_buy ", current_date)

    def execute_buy(self):
        """执行买入操作"""
        for data in self.selected_codes:
            if data not in self.last_selected_codes:

                # 计算可买数量（向下取整）
                price = data.close[0] * 1.05     #假设下一个交易日会涨
                size = int(self.each_cash / price / 100) * 100
                if size > 0:
                    self.buy(data=data, size=size)
                    self.record[data]['buy_size'] = size
                    self.record[data]['buy_price'] = price
            
                    print(f' {data._name} 申请价格: {price:.2f}, 买入数量: {size}')
                else:
                    name = data._name
                    print(f'  ⛔警告：{name}至少需要 {price * 100:.2f} 现金不足，无法买入')
                self.state = "BUYED"

    def execute_sell(self):
        """执行卖出操作"""

        for data in self.last_selected_codes:
            if data not in self.selected_codes:
                self.close(data=data)
                self.state = "SELLED"

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
                print(f"✅ {name} {trade_date_str} 买入成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   成本: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            else:  # 卖出订单
                buy_price = self.record[data]['buy_price']
                value = (order.executed.price - buy_price) * abs(order.executed.size)
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
        total_return = (final_value / initial_cash - 1) * 100
            
        print("\n" + "="*50)
        print("策略执行总结:")
        print("="*50)
        print("交易过股票：")
        print(self.traded_codes)
        print("")
        print(f"初始资金: {initial_cash:.2f}")
        print(f"最终价值: {final_value:.2f}")
        print(f"总收益率: {total_return:.2f}%")


def load_hfq_data(symbol="600519"):
    #print(symbol)
    df = stock_price.get_stock_hfq_price(symbol)
    df.index=pd.to_datetime(df['date'])
    df = df[['close']]
    df['open'] = df['close']      # 开盘价 = 收盘价
    df['high'] = df['close']
    df['low'] = df['close']
    df['volume'] = 100000              # 固定成交量
    #print(df)
    return df


# 主函数
def run_backtest(CURRENT_YEAR):
    print("\n")
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
    cerebro.addstrategy(MonthlyStrategy)

    #code_list = ['600099','002112','002576','600234','002676']
    #code_list = ['603088','600202','002278','603988','600731']
    #code_list = ['002243','002295','002006','603326','000859']
    #code_list = ['002652','002316','002377','600322','600854']
    #code_list = ['002925']
    start_time = time.time()
    code_list = load_stock_list(CURRENT_YEAR)
    print(f"符合增长率 > 20% 的共有{len(code_list)}只")
    end_time = time.time()
    print(f"load_stock_list {end_time - start_time:.2f}s")

    start_time = end_time
    #code_list = code_list[0:1]
    code_number = 0
    for code in code_list:
        # 创建示例数据（这里使用虚拟数据，实际使用时替换为真实数据
        data_name = load_hfq_data(code)
        from_date = datetime(CURRENT_YEAR - 1, 12, 25)
        to_date = datetime(CURRENT_YEAR, 12 , 31)
        
        flag1 = False
        flag2 = False
        for date in data_name.index:
            if date < from_date or date > to_date:
                continue

            if date.year == from_date.year and date.month == from_date.month:
                flag1 = True
            if date.year == to_date.year and date.month == to_date.month:
                flag2 = True

        if not flag1 or not flag2:
            #print(f"{code} 在指定日期内没有股价")
            continue
        
        data = bt.feeds.PandasData(
            dataname=data_name,  # 创建示例数据
            #fromdate=datetime(2019, 12, 31),
            #todate=datetime(2020, 12 , 31)
            fromdate=from_date,
            todate=to_date
        )
        #print(f"feed {code}")
        # 添加数据
        cerebro.adddata(data, name=code)
        code_number += 1

    print(f"符合条件股票 {code_number} 个")
    if code_number == 0:
        return 0

    end_time = time.time()
    print(f"cerebro adddata {end_time - start_time:.2f}s")

    start_time = end_time
    # 设置初始资金
    start_cash = 60000
    cerebro.broker.setcash(start_cash * 5)
    
    
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
    if hasattr(strat, 'analyzers'):
        if hasattr(strat.analyzers.returns.get_analysis(), 'rnorm100'):
            print(f'年化收益率: {strat.analyzers.returns.get_analysis()["rnorm100"]:.2f}%')
        
        if hasattr(strat.analyzers.sharpe.get_analysis(), 'sharperatio'):
            print(f'夏普比率: {strat.analyzers.sharpe.get_analysis()["sharperatio"]:.3f}')
        
        #if hasattr(strat.analyzers.drawdown.get_analysis(), 'max'):
        #    print(f'最大回撤: {strat.analyzers.drawdown.get_analysis()["max"]:.2f}%')
    
    # 绘图
    #cerebro.plot()
    #cerebro.plot(style='candlestick')

    # Use quantstats to output backtrader backtest results
    #qs.reports.html(returns, output='temp.html')

    #stock = qs.utils.download_returns(returns)
    print("\n" + "="*50)

    return total_return

def test():
    calc_PB("002437", "2015-12-30")
    exit(0)
    for month in range(1,2):
        month = str(month)
        if int(month) < 10:
            month = str(0) + month
        for day in range(4,28,4):
            day = str(day)
            if int(day) < 10:
                day = str(0) + day
            
            date = "2009-" + month + "-" + day
            print(date)
            calc_PB("300014", date)

# 运行回测
if __name__ == '__main__':
    test()
    exit()
    START_TIME = time.time()

    if False:
        run_backtest(2023)
    else:
        return_dict = {}
        for CURRENT_YEAR in range(2010,2026):
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


    print(f"\n耗时 {time.time() - START_TIME:.2f}s")
