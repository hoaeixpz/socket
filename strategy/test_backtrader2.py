#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Author：Airyv
@Project：test 
@File：quantstats_demo.py
@Date：2024/1/1 21:45 
@desc:
'''

from datetime import datetime

import backtrader as bt  # 升级到最新版
import matplotlib.pyplot as plt  # 由于 Backtrader 的问题，此处要求 pip install matplotlib==3.2.2
import akshare as ak  # 升级到最新版
import pandas as pd
#import quantstats as qs
#import pyfolio as pf

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

import sys
sys.path.append("..")
from financial_data import FinancialData
from stock_price_cache import StockPriceCache

finan_data = FinancialData()
stock_price = StockPriceCache()

def real_data():
    df = stock_price.get_stock_hfq_price("002576")
    df.index=pd.to_datetime(df['date'])
    df = df[['close']]
    df['open'] = df['close']      # 开盘价 = 收盘价
    df['high'] = df['close']
    df['low'] = df['close']
    df['volume'] = 1000000000000              # 固定成交量
    #print(df.iloc[705:750])
    return df


class MyStrategy(bt.Strategy):
    """
    主策略程序
    """
    params = (
        ("MA20", 20),
        ("MA05", 5))  # 全局设定交易策略的参数

    def __init__(self):
        """
        初始化函数
        """
        self.data_close = self.datas[0].close  # 指定价格序列
        # 初始化交易指令、买卖价格和手续费
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        # 添加移动均线指标
        self.sma_20 = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.MA20
        )
        self.sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.MA05
        )

    def next(self):
        """
        执行逻辑
        """
        if self.order:  # 检查是否有指令等待执行,
            return
        #print(self.position)
        # 检查是否持仓
        if not self.position:  # 没有持仓
            if self.sma[0] > self.sma_20[0]:  # 执行买入条件判断：收盘价格上涨突破20日均线
                self.order = self.buy(size=100)  # 执行买入
        else:
            if self.sma[0] < self.sma_20[0]:  # 执行卖出条件判断：收盘价格跌破20日均线
                self.order = self.sell(size=100)  # 执行卖出
        # 更新指令状态
        if self.order:
            self.buy_price = self.data_close[0]
            self.buy_comm = self.broker.getcommissioninfo(self.data).getcommission(self.buy_price, 100)
            self.order = None  # 在这里将订单设置为None，表示没有正在执行的订单
        else:
            self.buy_price = None
            self.buy_comm = None

class SimpleBuyAndHoldStrategy(bt.Strategy):
    """
    简单的买入持有策略 - 使用索引判断
    第一天买入，最后一天卖出
    """
    params = (
        ('verbose', True),
    )
    
    def __init__(self):
        self.has_bought = False
        self.has_sold = False
        self.buy_price = 0
        self.buy_date = None
        self.sell_date = None

    def next(self):
        current_bar = len(self.data)  # 当前bar的索引
        
        # 第一天买入（索引为0）
        if not self.has_bought and current_bar == 1:            
            self.order_target_percent(target=0.95)
            self.has_bought = True
            self.buy_date = self.data.datetime.date(0)
                
            if self.params.verbose:
                print(f"第一天买入: {self.buy_date}")
        
        # 最后一天卖出（索引为总长度-1）
        elif (self.has_bought and 
              not self.has_sold and 
              self.position and 
              current_bar == self.data.buflen()-1):
            
            self.close()
            self.has_sold = True
            self.sell_date = self.data.datetime.date(0)
            sell_price = self.data.close[0]
            
            if self.params.verbose:
                days_held = (self.sell_date - self.buy_date).days
                print(f"最后一天卖出: {self.sell_date}, 价格: {sell_price:.2f}")

    
    def notify_order(self, order):
        """基本的订单状态处理"""
    
        # 1. 订单已提交/接受 - 无需特殊处理
        if order.status in [order.Submitted, order.Accepted]:
            # 订单正在处理中，等待后续状态
            print(f"订单{order.getstatusname()} - 等待执行")
            return
    
        # 2. 订单完成成交
        if order.status == order.Completed:
            if order.isbuy():
                print(f"✅ 买入成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   成本: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            else:  # 卖出订单
                print(f"✅ 卖出成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   收入: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
    
        # 3. 订单失败情况
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print(f"❌ 订单失败: {order.getstatusname()}")
        
            # 根据不同失败原因处理
            if order.status == order.Canceled:
                print("   订单已被取消")
            elif order.status == order.Margin:
                print("   保证金不足")
            elif order.status == order.Rejected:
                print("   订单被拒绝")
    
        # 4. 重置订单变量（重要！）
        self.order = None  # 允许提交新订单

    '''

    def next(self):
    # 第一天：提交买入订单
        current_bar = len(self.data)  # 当前bar的索引
        if current_bar == 1 and not self.has_bought:
            cash = self.broker.getcash()
            price = self.data.close[0]
            size = int(cash / price / 100 - 1) * 100
            self.order = self.buy(size=size)
            print("提交买入订单")  # 订单已提交，但尚未成交
    
    def notify_order(self, order):
    # 订单成交回调
        if order.status == order.Completed and order.isbuy():
            print("买入订单成交！")  # 此时仓位才会更新
            print(f"当前仓位: {self.position.size}")  # 现在不为空了
    '''
    def stop(self):
        """策略结束时的总结"""
        if self.params.verbose and self.has_bought:
            final_value = self.broker.getvalue()
            initial_cash = self.broker.startingcash
            total_return = (final_value / initial_cash - 1) * 100
            
            print("\n" + "="*50)
            print("策略执行总结:")
            print("="*50)
            print(f"初始资金: {initial_cash:.2f}")
            print(f"最终价值: {final_value:.2f}")
            print(f"总收益率: {total_return:.2f}%")
            
            if self.has_sold:
                print(f"买入日期: {self.buy_date}")
                print(f"卖出日期: {self.sell_date}")

class MonthlyDCAStrategy(bt.Strategy):
    """
    月度定投策略 (Dollar-Cost Averaging)
    规则：每月第一个交易日买入，最后一个交易日清仓。
    """
    params = (
        ('monthly_cash', 8000),  # 每月定投金额
    )

    def __init__(self):
        # 记录上一个交易日的月份，用于检测月份变化
        self.last_month = None
        # 标记是否已执行本月买入
        self.buy_executed_this_month = False
        # 获取持仓对象
        self.myposition = self.getposition(self.data)

    def next(self):
        # 获取当前交易日
        current_date = self.data.datetime.date(0)
        current_month = current_date.month
        
        # 初始化last_month（只在第一个交易日）
        if self.last_month is None:
            self.last_month = current_month
            return
        
        # ========== 检测月份是否变更 ==========
        month_changed = current_month != self.last_month
        if month_changed:
            # 新月份开始，重置买入标记
            self.buy_executed_this_month = False
            self.last_month = current_month
        
        # ========== 买入逻辑：每月第一个交易日 ==========
        # 条件：月份刚变更（即第一个交易日）且尚未买入
        if month_changed and not self.buy_executed_this_month:
            self.execute_buy(current_date)
            self.buy_executed_this_month = True

        # ========最后一个交易日卖出===========
        current_bar = len(self.data)  # 当前bar的索引
        if current_bar == self.data.buflen()-1:
            self.close()

    def execute_buy(self, current_date):
        """执行买入操作"""
        print(f'\n[{current_date}] 执行月度买入')
        
        # 用固定金额买入（更符合传统定投）
        # 计算可买数量（向下取整）
        price = self.data.close[0]
        size = int(self.params.monthly_cash / price)
        if size > 0:
            self.buy(size=size)
            print(f'  买入方式: 固定金额 {self.params.monthly_cash}元')
            print(f'  买入价格: {price:.2f}, 买入数量: {size}')
        else:
            print('  警告：现金不足，无法买入')

    def notify_order(self, order):
        """基本的订单状态处理"""
    
        # 1. 订单已提交/接受 - 无需特殊处理
        if order.status in [order.Submitted, order.Accepted]:
            # 订单正在处理中，等待后续状态
            print(f"订单{order.getstatusname()} - 等待执行")
            return
    
        # 2. 订单完成成交
        if order.status == order.Completed:
            if order.isbuy():
                print(f"✅ 买入成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   成本: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            else:  # 卖出订单
                print(f"✅ 卖出成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   收入: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
    
        # 3. 订单失败情况
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print(f"❌ 订单失败: {order.getstatusname()}")
        
            # 根据不同失败原因处理
            if order.status == order.Canceled:
                print("   订单已被取消")
            elif order.status == order.Margin:
                print("   保证金不足")
            elif order.status == order.Rejected:
                print("   订单被拒绝")
    
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
        print(f"初始资金: {initial_cash:.2f}")
        print(f"最终价值: {final_value:.2f}")
        print(f"总收益率: {total_return:.2f}%")

cerebro = bt.Cerebro()  # 初始化回测系统
start_date = datetime(2020,12,31)  # 回测开始时间
end_date = datetime(2021,12,31)  # 回测结束时间
data = bt.feeds.PandasData(dataname=real_data(), fromdate=start_date, todate=end_date)  # 加载数据
# data=bt.feeds.PandasData(dataname=df,fromdate=start_date,todate=end_date)#加银数据
cerebro.adddata(data)  # 将数据传入回测系统

#cerebro.addstrategy(MonthlyDCAStrategy)  # 将交易策略加载到回测系统中
cerebro.addstrategy(SimpleBuyAndHoldStrategy)


# 加入pyfolio分析者
cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')
start_cash = 100000
cerebro.broker.setcash(start_cash)  # 设置初始资本为 100000
cerebro.broker.setcommission(
        commission=0.002,      # 佣金率
        margin=0,           # 关键：设置为None禁用保证金
        mult=1.0,
        stocklike=True         # 股票模式
    )

result = cerebro.run()  # 运行回测系统

port_value = cerebro.broker.getvalue()  # 获取回测结束后的总资金
pnl = port_value - start_cash  # 盈亏统计

print(f"初始资金: {start_cash}\n回测期间：{start_date.strftime('%Y%m%d')}:{end_date.strftime('%Y%m%d')}")
print(f"总资金: {round(port_value, 2)}")
print(f"净收益: {round(pnl, 2)}")

# cerebro.plot(style='candlestick')  # 画图

cerebro.broker.getvalue()

strat = result[0]
pyfoliozer = strat.analyzers.getbyname('pyfolio')
returns, positions, transactions, gross_lev = pyfoliozer.get_pf_items()
cerebro.plot()

# Use quantstats to output backtrader backtest results
qs.reports.html(returns, output='temp.html')

stock = qs.utils.download_returns(returns)