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
import json
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
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        print(f"分析结果已保存到: {file_path}")
    except Exception as e:
        print(f"保存结果失败: {e}")

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
            if pct < 20:
                return False
            count += 1

    if count != 3:
        return False
    '''
    for year, pct in zzl:
        if year[4:6] == '12':
            print(year, " ", float(pct))
    '''

    return True

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

    print(code_list)
    return code_list

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
                    print(f'  警告：{name}至少需要 {price * 100} 现金不足，无法买入')
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
            print(f"{name} 订单{order.getstatusname()} - 等待执行")
            return
    
        # 2. 订单完成成交
        if order.status == order.Completed:
            if order.isbuy():
                print(f"✅ {name} {trade_date_str} 买入成交: {order.executed.size}股 @ {order.executed.price:.2f}")
                print(f"   成本: {order.executed.value:.2f}, 佣金: {order.executed.comm:.2f}")
            else:  # 卖出订单
                print(f"⭕ {name} {trade_date_str} 卖出成交: {order.executed.size}股 @ {order.executed.price:.2f}")
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

    def __init__(self):
        # 记录上一个交易日的月份，用于检测月份变化
        self.last_month = None
        self.record = {}
        self.selected_codes = []
        self.last_selected_codes = []
        for data in self.datas:
            self.record[data] = {
                'name': data._name,
                'buy_executed_this_month': False,
                'buy_price': 0,
                'buy_date': None,
                'sell_date': None
            }
        self.each_cash = self.broker.getcash() / 5

    def next(self):
        # 获取当前交易日
        current_date = self.data.datetime.date(0)
        current_month = current_date.month
        #print(current_date)
        
        # 初始化last_month（只在第一个交易日）
        if self.last_month is None:
            self.last_month = current_month
            return
        
        # ========== 检测月份是否变更 ==========
        month_changed = (current_month != self.last_month)
        if month_changed:
            self.rebalance()
            self.last_month = current_month

    def rebalance(self):
        #if len(self.last_selected_codes) > 0:
        #    return

        current_date = self.data.datetime.date(0)
        print("rebalance ", current_date)
        year = current_date.year
        month = current_date.month
        #if month > 1:
        #    return

        month = month - 1
        if month == 0:
            month = "12"
            year = year - 1
        elif month < 10:
            month = "0"+ str(month)
        else:
            month = str(month)
        date = str(year) + "-" + month + "-30"
        if month == "02":
            date = str(year) + "-02-28"
        print(date)

        market_dict = {}
        for data in self.datas:
            stock_code = data._name
            market_value = stock_data[stock_code].get('market_value')

            mv = market_value.get(date)
            if mv is None:
                df = ak.stock_zh_valuation_baidu(symbol=stock_code, indicator="总市值", period="全部")
                mv = stock_price.get_specify_date_price(df, date, head = 'value')
                if mv is None:
                    continue
                '''
                for mon in range(12,13):
                    if mon < 10:
                        mon = "0"+ str(mon)
                    else:
                        mon = str(mon)
                    next_date = str(year) + "-" + str(mon) + "-30"
                    next_mv = market_value.get(next_date)
                    print(next_date, " ", next_mv)
                    if next_mv is None:
                        next_mv = stock_price.get_specify_date_price(df, next_date, head = 'value')
                        print("next_mv ", next_mv)
                        if next_mv is not None:
                            market_value[next_date] = next_mv
                '''

            market_dict[data] = mv
            market_value[date] = mv

        #save_results(stock_data)
        market_dict = list(sorted(market_dict.items(), key=lambda x:float(x[1])))

        for data, mv in market_dict[0:5]:
            self.selected_codes.append(data)

        rebalanced = False
        for data in self.last_selected_codes:
            if data not in self.selected_codes:
                self.close(data=data)
                rebalanced = True

        for data in self.selected_codes:
            if data not in self.last_selected_codes:
                self.execute_buy(data, current_date)
                rebalanced = True

        if rebalanced:
            for data, mv in market_dict[0:8]:
                print(data._name, " ", mv)
        
        self.last_selected_codes = self.selected_codes
        self.selected_codes = []

    def execute_buy(self, data, current_date):
        """执行买入操作"""
        #print(f'\n[{current_date}] 执行月度买入')
        
        # 用固定金额买入（更符合传统定投）
        # 计算可买数量（向下取整）
        price = data.close[0]
        size = int(self.each_cash / price / 105) * 100
        if size > 0:
            self.buy(data=data, size=size)
            #print(f'  买入价格: {price:.2f}, 买入数量: {size}')
        else:
            name = data._name
            print(f'  ⛔警告：{name}至少需要 {price * 100} 现金不足，无法买入')

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
                print(f"⭕ {name} {trade_date_str} 卖出成交: {order.executed.size}股 @ {order.executed.price:.2f}")
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
def run_backtest():
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
    cerebro.addstrategy(MonthlyDCAStrategy)

    #code_list = ['600099','002112','002576','600234','002676']
    #code_list = ['603088','600202','002278','603988','600731']
    #code_list = ['002243','002295','002006','603326','000859']
    #code_list = ['002652','002316','002377','600322','600854']
    #code_list = ['002316']
    CURRENT_YEAR = 2024
    code_list = load_stock_list(CURRENT_YEAR)
    #code_list = code_list[0:25]
    for code in code_list:
        # 创建示例数据（这里使用虚拟数据，实际使用时替换为真实数据
        data_name = load_hfq_data(code)
        from_date = datetime(CURRENT_YEAR - 1, 12, 10)
        to_date = datetime(CURRENT_YEAR, 12 , 31)

        first_date = data_name.index[0]
        last_date = data_name.index[-1]
        if first_date > from_date or last_date < to_date:
            print(f"{code} 在指定日期内没有股价")
            continue

        data = bt.feeds.PandasData(
            dataname=data_name,  # 创建示例数据
            #fromdate=datetime(2019, 12, 31),
            #todate=datetime(2020, 12 , 31)
            fromdate=from_date,
            todate=to_date
        )
        # 添加数据
        cerebro.adddata(data, name=code)

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

# 运行回测
if __name__ == '__main__':
    run_backtest()