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
sys.path.append("../../market_cap")
from update_market import StockMarketCache
import least_squares_mothod as lsq

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
industry_data =load_stock_data("../../industry_info.json")


def load_stock_list(CURRENT_YEAR):
    code_list = []
    if not stock_data:
        print("没有找到股票数据")
        return {}
    else:
        print(f"筛选净利润增长率连续3年 > {Profit_Grown_Ratio_Threshold}%")
        print(f"总共{len(stock_data.keys())}")
        for stock_code, stock_info in stock_data.items():
            #if not find_ST_stock(CURRENT_YEAR, stock_code):
            #    code_list.append(stock_code)
            if find_good_stocks(CURRENT_YEAR, stock_code):
                code_list.append(stock_code)

    #print(code_list)
    #exit()
    return code_list

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

def cal_volatility(stock_code, last_year):
    from_date = datetime(last_year, 1, 1)
    to_date = datetime(last_year, 12, 31)
    df = stock_price.get_stock_hfq_price(stock_code)
    log_price = []
    for index, row in df.iterrows():
        date = pd.to_datetime(row['date'])
        if date < from_date:
            continue
        if date <= to_date:
            log_price.append(math.log(row['close']))
        else:
            break

    if len(log_price) == 0:
    	return None
    return_ratio = np.diff(log_price)
    #lsq.simple_linear_regression(return_ratio)
    volatility = np.std(return_ratio, ddof = 1)
    
    #print("volatility: ", volatility)
    return volatility

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

    jzc = finan_data.get_indicator_value(stock_code, "股东权益合计(净资产)", date)
    #good_will = finan_data.get_indicator_value(stock_code, "商誉", date)
    #print(date)
    #print("净资产： ", jzc)
    #print("市值： ", mv)
    #print("商誉： ", good_will)

    Billion = 100000000
    '''
    if math.isnan(good_will):
        return None

    if good_will > jzc:
        return None
    PB = mv * Billion / (jzc - good_will)
    '''
    PB = mv * Billion / jzc
    #print(PB)
    return PB

def cal_assessment(stock_code, last_year):
	PB_list = []
	for month in range(12, 0, -3):
		date = datetime(last_year , month, 30)
		PB = calc_PB(stock_code, str(date))
		if PB is None:
			continue
		PB_list.append(PB)

	for month in range(12, 0, -3):
		date = datetime(last_year - 1, month, 30)
		PB = calc_PB(stock_code, str(date))
		if PB is None:
			continue
		PB_list.append(PB)

	if len(PB_list) < 7:
		return None

	indicator = np.std(PB_list, ddof = 1)
	return indicator

def calc_industry_indicator(current_year):
	for industry, industry_info in industry_data.items():
		print(industry)
		#if industry == "文化传媒":
		#	continue
		industry_code_list = industry_info.get("code")
		code_list = []
		for stock_code in industry_code_list:
			if stock_code in stock_data:
				code_list.append(stock_code)
		number = len(code_list)
		if number < 40:
			continue
		print(number)
		
		vol_dict = {}
		ass_dict = {}
		for stock_code in code_list:
			#print("\n",stock_code)
			volatility = cal_volatility(stock_code, current_year - 1)
			assessment = cal_assessment(stock_code, current_year - 1)
			stock_info = stock_data[stock_code]
			vd = stock_info.get("volatility")
			if vd is None:
				stock_info["volatility"] = {}

			ad = stock_info.get("assessment")
			if ad is None:
				stock_info["assessment"] = {}

			stock_info["volatility"][current_year] = volatility
			stock_info["assessment"][current_year] = assessment


			'''
			print("vol ", volatility)
			print("ass ", assessment)
			vol_dict[stock_code] = volatility
			if assessment is not None:
				ass_dict[stock_code] = assessment
			'''
		#print(stock_data)
		save_results(stock_data)

		'''
		sorted_vol = sorted(vol_dict.items(), key=lambda x:float(x[1]))
		sorted_ass = sorted(ass_dict.items(), key=lambda x:float(x[1]))

		rank = 1
		code_num = len(code_list)
		print("\nafter sort vol=-========\n")
		for stock_code, vol in sorted_vol:
			#print(stock_code, "  ", rank)
			vol_dict[stock_code] = rank #/ code_num
			rank += 1

		rank = 1
		print("\nafter sort ass=-========\n")
		for stock_code, ass in sorted_ass:
			ass_dict[stock_code] = rank #/ code_num
			#print(stock_code, "  ", rank)
			rank += 1

		for stock_code, vol in sorted_vol:
			print(stock_code, " ", vol_dict[stock_code], " ", ass_dict[stock_code])
		break
		'''

def main():
    """主函数"""
    for year in range(2011,2026):
    	print(year)
    	calc_industry_indicator(year)

if __name__ == "__main__":
    main()


