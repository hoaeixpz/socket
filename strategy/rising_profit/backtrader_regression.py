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
# 扣非ROE > 15
Profit_Grown_Ratio_Threshold = 30
KF_ROE_Threshold = 15


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
            print("year ", year, " ", float(pct))
    '''
    return True



    count = 0
    df = finan_data.get_indicator_data(stock_code, "权益乘数")
    ROE = finan_data.get_indicator_recent_year(df, Y, CURRENT_YEAR-1)
    for date, roe in ROE:
        year = int(date[0:4])
        if CURRENT_YEAR - year > Y:
            continue
        if date[4:6] == '12':
            if math.isnan(roe):
                continue


            count += 1
            print("year ", year, " roe ", roe)

    if count < 3:
        return False

    return True

def load_stock_list(CURRENT_YEAR):
    code_list = []
    if not stock_data:
        print("没有找到股票数据")
        return {}
    else:
        print(f"筛选净利润增长率连续3年 > {Profit_Grown_Ratio_Threshold}%")
        for stock_code, stock_info in stock_data.items():
            stock_name = stock_info.get('stock_name', '')

            if find_good_stocks(CURRENT_YEAR, stock_code):
                code_list.append(stock_code)

    #print(code_list)
    #exit()
    return code_list

def filter_date_code_list(codes_list, CURRENT_YEAR):
    result_codes = []
    for code in codes_list:
        data_name = load_hfq_data(code)
        from_date = datetime(CURRENT_YEAR - 1, 12, 20)
        to_date = datetime(CURRENT_YEAR, 12 , 31)
        
        flag1 = False
        flag2 = False
        last_month = None
        for date in data_name.index:
            if date < from_date or date > to_date:
                continue

            if last_month is None:
                last_month = date.month
            elif date.month != last_month:
                if date.month - last_month > 2:
                    break
                # 停牌超过2个月的过滤掉
                last_month = date.month            

            if date.year == from_date.year and date.month == from_date.month:
                flag1 = True
            if date.year == to_date.year and date.month == to_date.month:
                flag2 = True

        if not flag1 or not flag2:
            #print(f"{code} 在指定日期内没有股价")
            continue

        result_codes.append(code)

    return result_codes

def choose_low_market_codes(codes_list, date):
    NUM = 30
    market_dict = {}
    result_list = []
    for stock_code in codes_list:
        market_df = market_data.load_market_df(stock_code)
        mv = market_data.get_specify_date_market(market_df, date)
        if mv is None:
            continue
        market_dict[stock_code] = mv

    market_dict = sorted(market_dict.items(), key=lambda x:float(x[1]))
    for code, mv in market_dict[0:NUM]:
        result_list.append(code)


    print(f"筛选市值最小的 {NUM} 只股票")
    return result_list

def get_indicator(stock_code, current_year, indicator="权益乘数"):
    df = finan_data.get_indicator_data(stock_code, indicator)
    Y = 3
    ind_list = finan_data.get_indicator_recent_year(df, Y, current_year)
    if indicator == "净资产收益率_平均_扣除非经常损益":
        indicator = "KF_ROE"
    for date, ind in ind_list:
        year = int(date[0:4])
        if current_year - year > Y:
            continue
        if date[4:6] == '12':
            if math.isnan(ind):
                continue

            print("year ", year, " ", indicator, " ", ind)

class MonthlyStrategy(bt.Strategy):

    def __init__(self):
        # 记录上一个交易日的月份，用于检测月份变化
        self.last_month = None
        self.record = {}
        self.rank_dict = {}
        self.traded_codes = set()
        self.selected_codes = []
        self.last_selected_codes = []
        self.state = "PREPARED" ##{PREPARED, SELLED, BUYED}
        for data in self.datas:
            self.record[data] = {
                'name': data._name,
                'buy_executed_this_month': False,
                'buy_size': 0,
                'buy_price': 0,
                'sell_price': 0,
                'is_buyed': False,
                'is_selled': False,
                'return_rate': None
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
        #if month > 4:
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

        market_dict = {}
        for data in self.datas:
            stock_code = data._name
            market_df = market_data.load_market_df(stock_code)
            mv = market_data.get_specify_date_market(market_df, date)
            if mv is None:
                continue
            market_dict[data] = mv

        market_dict = list(sorted(market_dict.items(), key=lambda x:float(x[1])))
        #if current_date.month == 1:
        #    self.record_sort_rank(market_dict)

        if len(self.selected_codes) == 0:
            for data, mv in market_dict[0:5]:
                self.selected_codes.append(data)
                self.traded_codes.add(data)

        rebalanced = False
        for data in self.last_selected_codes:
            if data not in self.selected_codes:
                rebalanced = True
        for data in self.selected_codes:
            if data not in self.last_selected_codes:
                rebalanced = True
        '''
        if rebalanced:
            print(date)
            for data, mv in market_dict[0:8]:
                print(data._name, " ", mv)

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
          
    def record_sort_rank(self, market_dict):
        rank = 1
        for data, mv in market_dict:
            code = data._name
            self.rank_dict[code] = rank
            rank += 1

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
                print(f"sell {data._name}")
                self.close(data=data)
                self.state = "SELLED"

        for data in self.last_selected_codes:
            for selected in self.selected_codes:
                if data == selected:
                    if data._name != selected._name:
                        print("#"*50)
                        print(f"{data._name} = {selected._name}")
                        print(f"{data} = {selected}")

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
        if len(self.datas) < 5:
            initial_cash = initial_cash / 5 * len(self.datas)
            final_value = initial_cash + profit
            total_return = (profit / initial_cash) * 100
            
        print("\n" + "="*50)
        print("策略执行总结:")
        print("="*50)
        print("交易过股票：")
        current_date = self.data.datetime.date(0)
        current_year = current_date.year
        for data in self.traded_codes:
            code = data._name
            stock_info = stock_data[code]
            stock_name = stock_info.get('stock_name')
            industry = stock_info.get('industry')
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

            print(f"{code} {stock_name} {industry} 收益率 {return_rate * 100:.2f}%")
            #get_indicator(code, current_year - 1)
            #get_indicator(code, current_year - 1, "净资产收益率_平均_扣除非经常损益")
            #get_indicator(code, current_year - 1, "净利润")
            #et_indicator(code, current_year - 1, "扣非净利润")
            #print(f"{code} rank {self.rank_dict[code]}")
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

    start_time = time.time()
    code_list = load_stock_list(CURRENT_YEAR)
    print(f"符合增长率 > 20% 的共有{len(code_list)}只")
    end_time = time.time()
    print(f"load_stock_list {end_time - start_time:.2f}s")

    start_time = end_time
    code_list = filter_date_code_list(code_list, CURRENT_YEAR)
    code_number = len(code_list)
    print(f"符合条件股票 {code_number} 个")
    if code_number == 0:
        return 0

    #code_list = ['600099','002112','002576','600234','002676']
    #code_list = ['603088','600202','002278','603988','600731']
    #code_list = ['002243','002295','002006','603326','000859']
    #code_list = ['002652','002316','002377','600322','600854']
    #code_list = ['002925']

    date = datetime(CURRENT_YEAR - 1, 12, 31)
    code_list = choose_low_market_codes(code_list, date)
    end_time = time.time()
    print(f"filter codes {end_time - start_time:.2f}s")

    for code in code_list:
        data_name = load_hfq_data(code)
        from_date = datetime(CURRENT_YEAR - 1, 12, 25)
        to_date = datetime(CURRENT_YEAR, 12, 31)
        data = bt.feeds.PandasData(
            dataname=data_name,  # 创建示例数据
            #fromdate=datetime(2019, 12, 31),
            #todate=datetime(2020, 12 , 31)
            fromdate=from_date,
            todate=to_date
        )

        # 添加数据
        cerebro.adddata(data, name=code)


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
    if len(cerebro.datas) < 5:
        total_return = total_return / len(cerebro.datas) * 5

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

# 运行回测
if __name__ == '__main__':
    START_TIME = time.time()

    Test_single_year = True
    Test_single_year = False

    if Test_single_year:
        run_backtest(2011)
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
