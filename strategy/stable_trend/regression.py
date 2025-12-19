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
        self.state = "PREPARED" ##{PREPARED, SELLED, BUYED}
        self.buyed_code = None
        self.each_cash = self.broker.getcash() / 5
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
        #for data in self.last_selected_codes:
        #    self.forced_liquidation(data)
        
        # ========== 检测月份是否变更 ==========
        month_changed = (current_month != self.last_month)
        week_changed = (current_week != self.last_week)
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
            self.last_week = current_week
            self.last_month = current_month        

        if self.state == "PREPARED":
            self.execute_rebalance()  #头一个月交易，execute会执行买入，后面几个月都执行卖出
            if self.state == "BUYED":
                #若是执行买入，更新交易过的code列表
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

        R2_dict = {}
        for data in self.datas:
        	R2_dict[data] = self.calc_annualized_return_R2(data)

        R2_dict = list(sorted(R2_dict.items(), key=lambda x:float(x[1])))

        data = R2_dict[0][1]
        if data != self.buyed_code:
        	if buyed_code is None:
        		price = data.close[0] * 1.05
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
            else:
            	self.close(data=data)
                self.state = "SELLED"
    '''     
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
            data_in_delected = False
            for selected in self.selected_codes:
                if data == selected and data._name == selected._name:
                    data_in_delected = True
                    break
            if not data_in_delected:
                self.close(data=data)
                self.state = "SELLED"
	'''
    def calc_annualized_return_R2(self, data, period = 25):
    	price = data.close[-period:0]
    	log_price = list(math.log(p) for p in price)
    	annualized_return = lsq.simple_linear_regression(log_price)
    	R2 = calc_R_squared(log_price)
    	return R2 * annualized_return

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

        print("")
        print(f"初始资金: {initial_cash:.2f}")
        print(f"最终价值: {final_value:.2f}")
        print(f"总收益率: {total_return:.2f}%")
