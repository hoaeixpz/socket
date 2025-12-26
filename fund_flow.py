#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# 测试沪深300与中证1000的资金流向对比
# 用来分析当前市场资金是流向大盘股还是小盘股

from datetime import datetime
import time

import matplotlib.pyplot as plt  # 由于 Backtrader 的问题，此处要求 pip install matplotlib==3.2.2
import akshare as ak  # 升级到最新版
import pandas as pd
import json
import math
import numpy as np

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

from stock_price_cache import StockPriceCache

stock_price = StockPriceCache()

def get_cz1000_price():
	data = stock_price.get_index_price("000852")
	data.index = pd.to_datetime(data['date'])
	print("000852")
	print(data[0:5])
	return data

def get_hs300_price():
	data = stock_price.get_index_price("399300")
	data.index = pd.to_datetime(data['date'])
	print("399300[]")
	print(data[0:5])
	return data

def compare_price():
	hs300 = get_hs300_price()
	cz1000 = get_cz1000_price()
	common_dates = hs300.index.intersection(cz1000.index)

	# 提取收盘价
	hs300_close = hs300.loc[common_dates, 'close']
	hs300_vol   = hs300.loc[common_dates, '成交额']
	cz1000_close = cz1000.loc[common_dates, 'close']
	cz1000_vol   = cz1000.loc[common_dates, '成交额']

	# 计算比值
	ratio_close =  cz1000_close / hs300_close
	ratio_volume =  cz1000_vol / hs300_vol

	# 创建包含所有数据的DataFrame
	ratio_df = pd.DataFrame({
    	'沪深300': hs300_close,
    	'中证1000': cz1000_close,
    	'ratio_close': ratio_close,
    	'ratio_volume': ratio_volume
	})

	plt.figure(figsize=(8, 6))

	
	#plt.plot(ratio_df.index, ratio_df['沪深300'] / 5000, label='沪深300', linewidth=1.5, color='red')
	#plt.plot(ratio_df.index, ratio_df['中证1000'] / 5000, label='中证1000比值', linewidth=1.5, color='green')
	plt.plot(ratio_df.index, ratio_df['ratio_volume'], linewidth=1.5, color='red')
	plt.plot(ratio_df.index, ratio_df['ratio_close'], label='中证1000比值/沪深300', linewidth=1.5, color='blue')
	plt.show()

def compare_capital():
	# 获取北向资金净流入数据
	#north_net_flow = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")

	# 获取北向资金累计净流入
	#north_acc_flow = ak.stock_hsgt_north_acc_flow_in_em("北上")

	# 获取北向资金个股持仓
	north_hold_stock = ak.stock_hsgt_hold_stock_em("北向", indicator="今日排行")

	#print(north_net_flow)
	#print(north_acc_flow)
	print(north_hold_stock)

	# 获取个股主力资金流向
	stock_fund_flow = ak.stock_individual_fund_flow_rank(indicator="今日")

	# 获取行业资金流向
	sector_fund_flow = ak.stock_sector_fund_flow_rank(indicator="今日")

	print(stock_fund_flow)
	print(sector_fund_flow)

compare_price()
#compare_capital()