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
sys.path.append("../..")
from financial_data import FinancialData
from stock_price_cache import StockPriceCache

finan_data = FinancialData()
stock_price = StockPriceCache()

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
    
    def __init__(self):
        self.record = {}
        for data in self.datas:
            self.record[data] = {
                'name': data._name,
                'has_bought': False,
                'buy_price': 0,
                'buy_date': None,
                'sell_date': None
            }

    def next(self):
        cash = self.broker.getcash()
        cash = cash / len(self.datas)

        for data in self.datas:
            name = data._name
            record = self.record[data]
            current_bar = len(data)  # 当前bar的索引
        
            # 第一天买入（索引为0）
            if not record['has_bought'] and current_bar == 1:            
                price = data.close[0]
                size = int(cash / price / 101) * 100
                if size > 0:
                    self.buy(data=data, size=size)
                    record['has_bought'] = True
                    record['buy_date'] = data.datetime.date(0)
                    #print(f" {name} 第一天买入: {record['buy_date']}")
                    #print(f'  买入价格: {price:.2f}, 买入数量: {size} 总价 {price * size}')
                else:
                    print('  警告：现金不足，无法买入')
            # 最后一天卖出（索引为总长度-1）
            elif (record['has_bought'] and 
                self.getposition(data) and 
                current_bar == data.buflen()-1):
            
                self.close(data=data)
                record['sell_date'] = data.datetime.date(0)
                sell_price = data.close[0]

                #print(f"最后一天卖出: {record['sell_date']}, 价格: {sell_price:.2f}")

    
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
                print(f"✅ {name} {trade_date_str} 买入成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   成本: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            else:  # 卖出订单
                print(f"✅ {name} {trade_date_str} 卖出成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   收入: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            print("")
    
        # 3. 订单失败情况
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print(f"❌ {name} 订单失败: {order.getstatusname()}")
        
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
        if True:
            final_value = self.broker.getvalue()
            initial_cash = self.broker.startingcash
            total_return = (final_value / initial_cash - 1) * 100
            
            print("\n" + "="*50)
            print("策略执行总结:")
            print("="*50)
            print(f"初始资金: {initial_cash:.2f}")
            print(f"最终价值: {final_value:.2f}")
            print(f"总收益率: {total_return:.2f}%")
            

class MonthlyDCAStrategy(bt.Strategy):
    """
    月度定投策略 (Dollar-Cost Averaging)
    规则：每月第一个交易日买入，最后一个交易日清仓。
    """
    params = (
        ('monthly_cash', 200000),  # 每月定投金额
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



def load_hfq_data(symbol="600519"):
    print(symbol)
    df = stock_price.get_stock_hfq_price(symbol)
    df.index=pd.to_datetime(df['date'])
    df = df[['close']]
    df['open'] = df['close']      # 开盘价 = 收盘价
    df['high'] = df['close']
    df['low'] = df['close']
    df['volume'] = 100000              # 固定成交量
    #print(df.iloc[705:750])
    return df


# 主函数
def run_backtest():
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 设置初始资金
    cerebro.broker.setcash(50000.0)
    
    # 设置佣金
    cerebro.broker.setcommission(
        commission=0.003,      # 佣金率
        margin=None,           # 关键：设置为None禁用保证金
        mult=1.0,
        stocklike=True         # 股票模式
    )
    
    # 添加策略
    cerebro.addstrategy(SimpleBuyAndHoldStrategy)

    #code_list = ['600099','002112','002576','600234','002676']
    #code_list = ['603088','600202','002278','603988','600731']
    code_list = ['002243','002295','002006','603326','000859']
    #code_list = ['002676']
    for code in code_list:
        # 创建示例数据（这里使用虚拟数据，实际使用时替换为真实数据）
        data = bt.feeds.PandasData(
            dataname=load_hfq_data(code),  # 创建示例数据
            #fromdate=datetime(2019, 12, 31),
            #todate=datetime(2020, 12 , 31)
            fromdate=datetime(2017, 12, 31),
            todate=datetime(2018, 12 , 31)
        )
        # 添加数据
        cerebro.adddata(data, name=code)    
    
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    # 打印初始资金
    print(f'初始投资组合价值: {cerebro.broker.getvalue():.2f}')
    
    # 运行回测
    results = cerebro.run()
    
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
    cerebro.plot()
    #cerebro.plot(style='candlestick')

    # Use quantstats to output backtrader backtest results
    #qs.reports.html(returns, output='temp.html')

    #stock = qs.utils.download_returns(returns)

# 运行回测
if __name__ == '__main__':
    run_backtest()