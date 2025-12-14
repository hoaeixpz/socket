#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试框架backtrader
"""
import backtrader as bt
import backtrader.indicators as btind
import datetime
import pandas as pd

import sys
sys.path.append("..")
from financial_data import FinancialData
from stock_price_cache import StockPriceCache

finan_data = FinancialData()
stock_price = StockPriceCache()

# 定义简单的SMA策略
class SimpleSMAStrategy(bt.Strategy):
    params = (
        ('sma_period', 20),
    )
    
    def __init__(self):
        # 保存收盘价引用
        self.dataclose = self.datas[0].close
        
        # 添加SMA指标
        self.sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.sma_period
        )
        
        # 跟踪订单状态
        self.order = None
    
    def log(self, txt):
        '''日志函数'''
        print(f'{self.datas[0].datetime.date(0)}: {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交/接受 - 无需操作
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入成交, 价格: {order.executed.price:.2f}')
            elif order.issell():
                self.log(f'卖出成交, 价格: {order.executed.price:.2f}')
            
            # 记录交易成本
            self.bar_executed = len(self)
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/被拒绝')
            
        # 重置订单状态
        self.order = None
    
    def next(self):
        # 如果有未完成订单，跳过
        if self.order:
            return
        
        # 检查是否有足够的数据计算SMA
        if len(self) < self.params.sma_period:
            return
        
        # 获取当前现金和持仓
        cash = self.broker.getcash()
        value = self.broker.getvalue()
        position = self.position
        
        # 简单的SMA策略逻辑
        if not position:  # 没有持仓
            if self.dataclose[0] > self.sma[0]:  # 收盘价上穿SMA，买入信号
                print(f"{self.dataclose[0]} > {self.sma[0]}")
                # 计算购买数量（使用95%的资金）
                #size = int((cash * 0.95) / self.dataclose[0])
                size = 100
                if size > 0:
                    self.log(f'创建买入订单, 数量: {size}')
                    self.order = self.buy(size=size)
        
        else:  # 有持仓
            if self.dataclose[0] < self.sma[0]:  # 收盘价下穿SMA，卖出信号
                print(f"{self.dataclose[0]} < {self.sma[0]}")
                s = 100
                self.log(f'创建卖出订单, 数量: {s}')
                self.order = self.sell(size = s)
                #self.log(f'创建卖出订单, 数量: {position.size}')
                #self.order = self.sell(size=position.size)

# 主函数
def run_backtest():
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 设置初始资金
    cerebro.broker.setcash(100000000.0)
    
    # 设置佣金
    cerebro.broker.setcommission(commission=0.001)  # 0.1%佣金
    
    # 添加策略
    cerebro.addstrategy(SimpleSMAStrategy, sma_period=20)
    
    # 创建示例数据（这里使用虚拟数据，实际使用时替换为真实数据）
    data = bt.feeds.PandasData(
        dataname=real_data(),  # 创建示例数据
        fromdate=datetime.datetime(2020, 1, 1),
        todate=datetime.datetime(2020, 3 , 30)
    )
    
    # 添加数据
    cerebro.adddata(data)
    
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
    cerebro.plot(style='candlestick')

# 创建示例数据的函数（实际使用时替换为真实数据）
def create_sample_data():
    import pandas as pd
    import numpy as np
    
    # 创建日期范围
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='D')
    
    # 创建示例价格数据（随机游走）
    np.random.seed(42)
    n = len(dates)
    returns = np.random.normal(0.0005, 0.02, n)  # 日均收益0.05%，波动2%
    prices = 100 * np.exp(np.cumsum(returns))  # 起始价格100
    
    # 创建DataFrame

    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.01, n)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.015, n))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.015, n))),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, n)
    }, index=dates)
    
    return df

def real_data():
    df = stock_price.get_stock_hfq_price("600519")
    df.index=pd.to_datetime(df['date'])
    df = df[['close']]
    df['open'] = df['close']      # 开盘价 = 收盘价
    df['high'] = df['close'] * 1.001  # 稍微高一点
    df['low'] = df['close'] * 0.999   # 稍微低一点
    df['volume'] = 1000000              # 固定成交量
    print(df)
    return df

# 运行回测
if __name__ == '__main__':
    run_backtest()