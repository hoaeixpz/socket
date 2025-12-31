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

import sys
sys.path.append("market_cap")
from update_market import StockMarketCache
market_data = StockMarketCache()

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    
    # 确保是字符串类型
    code_str = str(stock_code).strip()
    
    # 判断规则
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    elif code_str.startswith('4') or code_str.startswith('8'):
        return f"bj{code_str}"      # 北证
    else:
        raise ValueError(f"无法识别的股票代码格式: {stock_code}")


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

def get_hs300_stock():
    stocks_to_analyze = None
    with open("hs_300_code.txt", 'r', encoding='utf-8') as f:
        # 读取所有行，并去除每行的换行符
        stocks_to_analyze = [line.strip() for line in f.readlines()]
    return stocks_to_analyze
    
    
def get_cz1000_stock():
    '''
    cz1000_df = ak.index_stock_cons_weight_csindex(symbol="000852")
    series = cz1000_df['成分券代码'].str.cat(cz1000_df['成分券名称'], sep=',')
    stocks_to_analyze = series.tolist()
    with open("cz_1000_code.txt", 'w', encoding='utf-8') as f:
        for item in stocks_to_analyze:
            f.write(item)
            f.write("\n")
    '''
    stocks_to_analyze = None
    with open("cz_1000_code.txt", 'r', encoding='utf-8') as f:
        # 读取所有行，并去除每行的换行符
        stocks_to_analyze = [line.strip() for line in f.readlines()]

    return stocks_to_analyze
    print(stocks_to_analyze)

def get_history_market(stocks_to_analyze, reverse = True):
    start_year = 2011
    end_year = 2025
    date_list = []
    market_result = []
    
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year == 2025 and month == 12:
                break
            date = None
            if month != 2:
                date = datetime(year, month , 30)
            if month == 2:
                date = datetime(year, month , 28)
            date_str = date.strftime('%Y-%m-%d')
            print(date_str)
            date_list.append(date)
            mv = get_average_market(stocks_to_analyze, date_str, reverse)
            market_result.append(float(mv))

    #print("market_result")
    #print(market_result)
    #plt.plot(date_list, market_result, marker='o', linewidth=2)
    #plt.show()
    return date_list, market_result

def get_average_market(stocks_to_analyze, date, reverse = True):
    market_dict = {}
    for info in stocks_to_analyze:
        stock_code = info.split(",")[0]
        name = info.split(",")[1]
        #print(stock_code, " ", name)
        market_df = market_data.load_market_df(stock_code)
        if market_df is None:
            continue
        mv = market_data.get_specify_date_market(market_df, date)
        #print(" 市值 ", mv)
        if mv is not None:
            market_dict[stock_code] = [name,mv]
            

    sorted_market = sorted(market_dict.items(), key=lambda x:x[1][1], reverse=reverse)
    head_market = sorted_market[0:30]
    #print(head_market)

    market_sum = 0
    for stock_code, data in head_market:
        market = data[1]
        market_sum += market

    result = market_sum / 30
    return result


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
    #plt.plot(ratio_df.index, ratio_df['ratio_volume'], linewidth=1.5, color='red')
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



#compare_price()
#compare_capital()
#get_hs300_stock()
#get_cz1000_stock()

def main():
    compare_price()
    exit()

    cz1000 = get_cz1000_stock()
    hs300  = get_hs300_stock()

    date, hs300_market =  get_history_market(hs300)
    date2,cz1000_market = get_history_market(cz1000, False)
    print("date")
    print(date)
    print(hs300_market)
    print("\ndate2")
    print(date2)
    print(cz1000_market)

    ratio = []
    ratio_base = cz1000_market[0] / hs300_market[0]
    for i in range(0, len(date)):
        ratio.append(cz1000_market[i] / hs300_market[i] / ratio_base)

    plt.plot(date, ratio, marker='o', linewidth=2)
    plt.show()

main()