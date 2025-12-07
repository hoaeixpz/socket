#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"""

import json
import time
import logging
import statistics
import akshare as ak
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D 
import concurrent.futures
import os
import numpy as np
import math
from datetime import datetime, timedelta
import least_squares_mothod as lsq

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    code_str = str(stock_code).strip()
    
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    else:
        return code_str

def save_to_parquet(stock_data, filename="stock_prices_MA5.parquet"):
    """保存为Parquet格式（高性能压缩）"""
    all_data = []
    
    for stock_code, data_list in stock_data.items():
        for item in data_list:
            all_data.append({
                'stock_code': stock_code,
                'date': item['date'],
                'MA5': item['MA5'],
                'MA5_vol': item['MA5_vol']
            })
    
    df = pd.DataFrame(all_data)
    df['date'] = pd.to_datetime(df['date'])
    #print(df)
    
    # 保存为Parquet（自动压缩）
    df.to_parquet(filename, index=False, compression='snappy')
    
    file_size = os.path.getsize(filename) / (1024 * 1024)
    print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} MB")
    return df

def load_from_parquet(filename):
    """从Parquet加载数据"""
    df = pd.read_parquet(filename)
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    
    stock_data = df.groupby('stock_code')[['date', 'MA5', 'MA5_vol']].apply(
        lambda x: x.to_dict('records'), include_groups=False
    ).to_dict()
    
    return stock_data


def load_existing_stocks(file = 'analysis_results.json'):
    """加载现有的analysis_results.json文件，返回所有股票代码列表"""
    try:
        with open(file, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        return stocks
    except FileNotFoundError:
        print(f"错误：找不到{file}文件")
        return {}
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式错误 - {e}")
        return {}

def get_5_day_ma(stock_code, start_date, end_date):
    """
    获取股票5日均线数据
    """
    # 定义时间范围
    #start_date = "20230101"
    #end_date = "20251130"
    
    # 获取日线数据
    stock_df = ak.stock_zh_a_daily(symbol=stock_code, start_date=start_date, end_date=end_date, adjust = 'hfq')
    
    # 确保数据按日期排序
    stock_df['date'] = pd.to_datetime(stock_df['date'])
    stock_df = stock_df.sort_values('date')
    
    # 计算5日均线
    stock_df['MA5'] = stock_df['close'].rolling(window=5, min_periods=1).mean()
    stock_df['MA5_vol'] = stock_df['volume'].rolling(window=5, min_periods=1).mean()
    
    return stock_df[['date', 'open', 'high', 'low', 'close', 'volume', 'MA5', 'MA5_vol']]

def get_daily_prices():
    """
    获取A股股票从2023年初至今的收盘价
    """
    # 定义时间范围
    start_date = "20170101"
    end_date = "20200101"
    
    
    result_dict = {}
    all_stocks = load_existing_stocks()
    stock_codes = list(all_stocks.keys())
    
    for i, stock_code in enumerate(stock_codes, 1):
        stock_code = add_stock_prefix(stock_code)
        try:
            print(f"正在获取股票 {stock_code} 的数据...")
            
            # 获取日线数据
            stock_df = ak.stock_zh_a_daily(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="hfq")

            # 确保数据按日期排序
            stock_df['date'] = pd.to_datetime(stock_df['date'])
            stock_df = stock_df.sort_values('date')

            stock_df = stock_df[['date', 'close']]
            filename = f"test_stock_price/{stock_code}_daily_hfq.parquet"
            stock_df.to_parquet(filename, index=False, compression='snappy')
    
            file_size = os.path.getsize(filename) / (1024 * 1024)
            print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} MB {datetime.now()}")
        except Exception as e:
            print(f"获取股票 {stock_code} 数据时出错: {e}")
            continue


def get_weekly_monday_prices():
    """
    获取A股股票从2023年初至今的每周一收盘价
    """
    # 定义时间范围
    start_date = "20200101"
    end_date = "20251130"
    
    
    result_dict = {}
    all_stocks = load_existing_stocks()
    stock_codes = list(all_stocks.keys())
    
    for i, stock_code in enumerate(stock_codes, 1):
        stock_code = add_stock_prefix(stock_code)
        try:
            print(f"正在获取股票 {stock_code} 的数据...")
            
            # 获取日线数据
            #stock_df = ak.stock_zh_a_daily(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="hfq")
            stock_df = get_5_day_ma(stock_code, start_date, end_date)

            # 确保日期列为datetime类型
            stock_df['date'] = pd.to_datetime(stock_df['date'])
            
            # 设置日期为索引
            stock_df.set_index('date', inplace=True)
            
            # 筛选周一的收盘价
            # 方法1: 直接筛选周一的数据
            monday_data = stock_df[stock_df.index.weekday == 0]
            
            # 方法2: 使用重采样确保每周有一个数据点（如果某周一没有交易数据，则使用前一个有效数据）
            # monday_data = stock_df['close'].resample('W-MON').last().dropna()
            
            # 创建包含日期和收盘价的列表
            weekly_data = []
            for date, row in monday_data.iterrows():
                weekly_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "MA5": round(float(row['MA5']), 2),
                    "MA5_vol": round(float(row['MA5_vol']), 2)
                })
            
            result_dict[stock_code] = weekly_data
            save_to_json(result_dict)
            
            print(f"股票 {stock_code} 获取完成，共 {len(weekly_data)} 个周一数据点")

            # 添加延迟避免请求过于频繁
            time.sleep(1)
            
        except Exception as e:
            print(f"获取股票 {stock_code} 数据时出错: {e}")
            continue
    
    return result_dict

def save_to_json(data_dict, filename=None):
    """
    将数据保存为JSON文件
    """
    if filename is None:
        filename = f"stocks_prices_MA5.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=2)
    
    print(f"数据已保存到 {filename}")
    return filename

def collect_stocks_price():
    """
    主函数
    """
    print("开始获取A股每周一收盘价数据...")
    
    # 获取数据
    #weekly_data = get_weekly_monday_prices()
    get_daily_prices()
    exit()
    
    # 保存为JSON文件
    #filename = save_to_json(weekly_data)
    
    # 打印统计信息
    print("\n数据统计:")
    for stock_code, data in weekly_data.items():
        print(f"股票 {stock_code}: 共 {len(data)} 个数据点")
        if data:
            print(f"  时间范围: {data[0]['date']} 到 {data[-1]['date']}")
    
    # 显示示例数据
    if weekly_data:
        sample_stock = list(weekly_data.keys())[0]
        print(f"\n示例数据（股票 {sample_stock} 的前5个数据点）:")
        for i, item in enumerate(weekly_data[sample_stock][:5]):
            print(f"  {i+1}. 日期: {item['date']}, 收盘价: {item['MA5']}")

def analyze_single_stock(stock_code, consecutive_days):
    try:
        stock_code = add_stock_prefix(stock_code)
        filename = f"stock_price/{stock_code}_daily_hfq.parquet"
        stock_df = pd.read_parquet(filename)
        stock_df['date'] = stock_df['date'].dt.strftime('%Y-%m-%d')
        #print(stock_df)

        close_prices = stock_df['close'].tolist()
        dates =  stock_df['date'].tolist()

        # 确保有足够的数据点进行分析
        if len(close_prices) < consecutive_days:
            print(f"股票 {stock_code} 数据点不足({len(close_prices)}个)，跳过分析")
            return stock_code, []
        

        # 查找所有连续上涨的序列
        consecutive_periods = []

        for i in range(len(close_prices) - consecutive_days + 1):
            #if dates[i] != "2024-03-20":
            #if dates[i] != "2024-10-16":
            #if dates[i] != "2025-08-14":
            #if dates[i] != "2022-02-07":
            #if dates[i] != "2020-06-12":
            #if dates[i] != "2023-12-15":
            #    continue    
            period_data = close_prices[i: i + consecutive_days]
            pct_change = np.diff(period_data) / period_data[:-1] * 100
            #print(period_data)
            k, b, se = lsq.simple_linear_regression(period_data)
            k2, b2, se2 = lsq.simple_linear_regression(pct_change)
            '''
            print(f"y = {k:.2f} x + {b:.2f} + e({se:.2f})")
            
            X = list(range(0, consecutive_days+15))
            #print(X)
            x_line = np.linspace(0, consecutive_days, 100)
            y_line = b + k * x_line

            plt.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {b:.2f} + {k:.2f}x')
            plt.scatter(X, close_prices[i: i + consecutive_days+15], alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
            plt.show()
            
            print(f"y = {k2:.2f} x + {b2:.2f} + e({se2:.2f})")
            X = list(range(0, consecutive_days-1))
            x_line = np.linspace(0, consecutive_days, 100)
            y_line = b2 + k2 * x_line
            plt.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {b2:.2f} + {k2:.2f}x')
            plt.scatter(X, pct_change, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
            plt.show()
            
            exit()
            '''
            
            is_consecutive_rising = True
            is_consecutive_rising = k > 0.1 and k < 1 and se < 1 and se2 < 0.5 and b2 < 1
            #is_consecutive_rising = k > 0.1 and k < 1
            
            if is_consecutive_rising:
                # 计算涨幅和百分比
                future_pct = 0
                future_day = 15
                future_price = future_date = None
                if i + consecutive_days + future_day < len(close_prices):
                    future_date = dates[i + consecutive_days + future_day]
                    future_price = close_prices[i + consecutive_days + future_day]
                    future_pct = (future_price - period_data[-1]) / period_data[-1] * 100

                '''
                if future_pct < -25 and b2 < 0.25:
                    print(f"{stock_code} {dates[i]}")
                    exit()
                '''
                # 收集这个连续上涨期的详细数据                
                consecutive_periods.append({
                    'period_data': period_data,
                    'start_date': dates[i],
                    'end_date': dates[i + consecutive_days - 1],
                    'start_price': round(period_data[0], 2),
                    'end_price': round(period_data[-1], 2),
                    "future_date": future_date,
                    "future_price": future_price,
                    'future_pct': round(future_pct, 2),
                    'slope': k,
                    'se': se,
                    'pct_se': se2,
                    'pct_b': b2
                })
        
        return  stock_code, consecutive_periods
    
    except Exception as e:
        print(f"分析股票 {stock_code} 时出错: {e}")
        return stock_code, []

def multi_task(stock_code_list, consecutive_days):
    rising_stocks = []
    for stock_code in stock_code_list:
        code, result = analyze_single_stock(stock_code, consecutive_days)
        rising_stocks.append((code, result))

    return rising_stocks

def analyze_stocks_multithread(stock_codes, consecutive_days, max_workers=2):
    """使用多线程分析股票"""
    
    total_stocks = len(stock_codes)

    print(f"开始多线程分析 {total_stocks} 支股票...")
    print(f"线程数: {max_workers if max_workers else '自动'}")
    
    rising_stocks = {}
    analyzed_count = 0
    
    # 使用线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        from functools import partial
        future_to_stock = []
        task_num = 20
        code_num = 0
        stock_list = []
        while code_num < total_stocks:
            if code_num + task_num > total_stocks:
                stock_list.append(stock_codes[code_num:])
            else:
                stock_list.append(stock_codes[code_num:code_num + task_num])
            num = 0
            for a in stock_list:
                num += len(a)
            print(f"stock list num {num}")
            code_num += task_num

        for task_list in stock_list:
            task_func = partial(multi_task, task_list, consecutive_days)
            future = executor.submit(task_func)
            future_to_stock.append(future)
        
        # 处理完成的任务
        for future in concurrent.futures.as_completed(future_to_stock):
            try:
                stock_result_list = future.result()
                analyzed_count += len(stock_result_list)
                
                for stock_code, periods in stock_result_list:
                    if periods:
                        rising_stocks[stock_code] = periods
                
                # 显示进度
                if analyzed_count % 100 == 0 or analyzed_count == total_stocks:
                    print(f"进度: {analyzed_count}/{total_stocks} ({analyzed_count/total_stocks*100:.1f}%)")
                    
            except Exception as e:
                print(f"股票 {stock_code} 分析失败: {e}")
                analyzed_count += 1
    
    
    print(f"分析股票总数: {total_stocks}")
    print(f"符合条件股票: {len(rising_stocks)}")
    
    return rising_stocks

def trend_requirement(week_index, close_prices, consecutive_weeks, six_month_weeks = 25):
    # 检查过去半年内是否出现过巨大波动
    # 检查从week_index开始的连续consecutive_weeks周是否都上涨
    # 第一周上涨幅度不能大于3%，最后一周上涨幅度>3%且<10%

    is_consecutive_rising = True
    if week_index <= six_month_weeks:
        return False, 0

    for j in range(week_index, week_index + consecutive_weeks - 1):
        if close_prices[j + 1] <= close_prices[j]:
            return False, 0
    close_prices[week_index]

    last_six_month_prices = []
    rise_num = 1
    fall_num = 1
    for w in range(week_index - six_month_weeks, week_index):
        if len(last_six_month_prices) > 0:
            if close_prices[w] > close_prices[w-1]:
                rise_num +=1
            else:
                fall_num +=1
        last_six_month_prices.append(close_prices[w])

    max_price = max(last_six_month_prices)
    min_price = min(last_six_month_prices)
    six_month_r = (max_price - min_price) / min_price * 100
    rise_fall_r = rise_num / fall_num

    if six_month_r > 15:
        return False, 0

    start_price = close_prices[week_index]
    first_week_pct = (close_prices[week_index+1] - start_price)/start_price  * 100
    #if first_week_pct >= 3.0:
    #    return False, 0
    
    end_price = close_prices[week_index + consecutive_weeks - 1]
    last_week_pct = ((end_price - close_prices[week_index + consecutive_weeks - 2]) /
                    close_prices[week_index + consecutive_weeks - 2] * 100)
    #if last_week_pct < 6.0 or last_week_pct > 12.0:
    #    return False, 0
    #if first_week_pct > last_week_pct:
    #    return False, 0

    return is_consecutive_rising, six_month_r


def find_consecutive_rising_stocks(stock_data, industry, consecutive_weeks=4):
    """
    找出连续N周股价都上涨的股票
    
    参数:
    stock_data: 股票数据字典
    consecutive_weeks: 连续上涨周数要求
    
    返回:
    符合条件的股票字典
    """
    rising_stocks = {}
    stock_indicator = load_existing_stocks()
    

    code_num = 0
    for stock_code, weekly_data in stock_data.items():
        clean_code = stock_code[2:]
        #if stock_indicator[clean_code]['industry'] != industry:
        #    continue
        code_num += 1
        #if not (stock_code == "sh600021" or stock_code == "sh601216" or stock_code == "sz000554"):
        #   continue
        #if not (stock_code == "sh600021"):
        #    continue
        # 确保数据按日期排序
        weekly_data.sort(key=lambda x: x['date'])
        
        # 确保有足够的数据点进行分析
        if len(weekly_data) < consecutive_weeks:
            print(f"股票 {stock_code} 数据点不足({len(weekly_data)}个)，跳过分析")
            continue
        
        # 提取收盘价
        close_prices = [item['MA5'] for item in weekly_data]
        dates = [item['date'] for item in weekly_data]
        volume = [item['MA5_vol'] for item in weekly_data]
        
        # 查找所有连续上涨的序列
        consecutive_periods = []
        
        for i in range(len(close_prices) - consecutive_weeks + 1):
            # 检查过去半年内是否出现过巨大波动

            # 检查从i开始的连续consecutive_weeks周是否都上涨
            # 第一周上涨幅度不能大于3%，最后一周上涨幅度>3%且<10%
            '''
            if i > 3:
                is_pre_rising = True
                for j in range(i - 3, i):
                    if close_prices[j + 1] <= close_prices[j]:
                        is_pre_rising = False
                        break
                if is_pre_rising:
                    is_consecutive_rising = False
            '''
            six_month_weeks = 13
            is_consecutive_rising, six_month_r =\
            trend_requirement(i, close_prices, consecutive_weeks, six_month_weeks)
            
            if is_consecutive_rising:
                # 计算涨幅和百分比

                start_price = close_prices[i]
                end_price = close_prices[i + consecutive_weeks - 1]
                pct = (end_price - start_price) / start_price * 100
                future_pct = 0
                if i + consecutive_weeks + 4 < len(close_prices):
                    future_price = close_prices[i + consecutive_weeks + 3]
                    future_pct = (future_price - end_price) / end_price * 100
                
                '''
                if future_pct < -35:
                    print(f"stock_code {stock_code} {future_pct}")
                    last_six_month_prices = []
                    for w in range(i - six_month_weeks, i):
                        last_six_month_prices.append(close_prices[w])
                    print(last_six_month_prices)
                    print(dates[i-six_month_weeks])
                    print(close_prices[i-six_month_weeks])
                    exit()
                '''

                rise_num = 1
                fall_num = 1
                for w in range(i - six_month_weeks, i):
                    if w > i - six_month_weeks:
                        if close_prices[w] > close_prices[w-1]:
                            rise_num +=1
                        else:
                            fall_num +=1
                rise_fall_r = rise_num / fall_num
                #print(f"rise {rise_num} fail {fall_num}   {rise_fall_r}")
                
                
                #分析上涨期间成交量与半年前成交量对比
                current_vol = []
                last_six_month_vol = []
                for w in range(i, i + consecutive_weeks - 1):
                    current_vol.append(volume[w])

                for w in range(i - six_month_weeks, i):
                    last_six_month_vol.append(volume[w])

                vol_ratio = statistics.mean(current_vol) / statistics.mean(last_six_month_vol)


                #分析这只股票近3年的扣非ROE
                date = dates[i]
                year = date[0:4]
                if year != "2025":
                    continue
                month = date[5:7]
                if int(month) < 10:
                    continue

                #if month == '10':
                #    if int(date[8:10]) < 21:
                #        continue
                
                #print(clean_code)
                stock_info = stock_indicator.get(clean_code)
                roe_dict = stock_info.get('roe_details').get('kf_roe')
                last_3year_roe = {}
                for year, roe_list in roe_dict.items():
                    if int(year) >= int(date[0:4]) or int(year) < int(date[0:4]) - 3:
                        continue
                    if roe_list[3] is None or math.isnan(roe_list[3]) or abs(roe_list[3]) > 200:
                        continue
                    last_3year_roe[int(year)] = roe_list[3]

                last_3year_roe = dict(sorted(last_3year_roe.items()))
                roe_list = list(last_3year_roe.values())
                #print(roe_list)

                roe_ava = 0
                roe_rising = 0
                if len(roe_list) > 1:
                    roe_ava = sum(roe_list) / len(roe_list)
                    roe_rising = (roe_list[-1] - roe_list[0]) / (len(roe_list) - 1)
                elif len(roe_list) == 1:
                    roe_ava = roe_list[0]

                if abs(roe_rising) > 50:
                    continue
                #print(f"mean {roe_ava} rising {roe_rising}")


                # 收集这个连续上涨期的详细数据
                period_data = []
                for k in range(i, i + consecutive_weeks):
                    period_data.append({
                        'date': dates[k],
                        'close_price': close_prices[k],
                        'week_number': k - i + 1
                    })
                
                consecutive_periods.append({
                    'start_date': dates[i],
                    'end_date': dates[i + consecutive_weeks - 1],
                    'start_price': round(start_price, 2),
                    'end_price': round(end_price, 2),
                    'period_data': period_data,
                    'pct': round(pct, 2),
                    'future_pct': round(future_pct, 2),
                    'six_month_pct': round(six_month_r, 2),
                    'rise_fall_r': round(rise_fall_r, 2),
                    'vol_ratio': round(vol_ratio, 2),
                    'roe_mean': round(roe_ava, 2),
                    'roe_rising': round(roe_rising, 2)
                })
        
        if consecutive_periods:
            rising_stocks[stock_code] = consecutive_periods

    print(industry, "  ", code_num)
    return rising_stocks

def plot_scatter(x_data, y_data, title="散点图", xlabel="X轴", ylabel="Y轴"):
    """
    绘制散点图
    
    参数:
    x_data: 横坐标数据列表
    y_data: 纵坐标数据列表
    title: 图表标题
    xlabel: X轴标签
    ylabel: Y轴标签
    """
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 创建图形
    plt.figure(figsize=(8, 6))
    
    # 绘制散点图
    plt.scatter(x_data, y_data, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    
    # 设置图表属性
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # 添加趋势线（可选）
    # z = np.polyfit(x_data, y_data, 1)
    # p = np.poly1d(z)
    # plt.plot(x_data, p(x_data), "r--", alpha=0.8, linewidth=2)
    
    # 调整布局
    plt.tight_layout()
    
    # 显示图表
    plt.show(block=False)

def plot_3D_sactter(x_data, y_data, z_data, title="三维散点图", xlabel="X轴", ylabel="Y轴", zlabel="z轴"):
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # 绘制 3D 散点图
    scatter = ax.scatter(x_data, y_data, z_data, c=z_data, cmap='viridis', s=50, alpha=0.8)

    ax.set_xlabel(xlabel, fontsize=12, labelpad=10)
    ax.set_ylabel(ylabel, fontsize=12, labelpad=10)
    ax.set_zlabel(zlabel, fontsize=12, labelpad=10)
    ax.set_title(title, fontsize=14, fontweight='bold')

    # 添加颜色条
    cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
    cbar.set_label('V 值', rotation=270, labelpad=15)

    plt.tight_layout()
    plt.show()


def categorize_and_plot_histogram(data_list, title, bin_width=20, block=False):
    """
    绘制单个直方图（不包含子图）
    
    参数:
    data_list: 包含数值的列表
    bin_width: 档次宽度，默认为10
    """
    # 转换为numpy数组
    data = np.array(data_list)
    if bin_width < 1:
        data = data * 10
        bin_width = bin_width * 10
    
    # 确定分档范围
    min_val = np.floor(data.min() / bin_width) * bin_width
    max_val = np.ceil(data.max() / bin_width) * bin_width
    
    # 创建分档边界
    #print(f"min max {min_val} {max_val} {bin_width}")
    bins = np.arange(min_val, max_val + bin_width, bin_width)
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 创建图形和坐标轴
    plt.figure(figsize=(6, 4))
    
    # 绘制直方图
    n, bins, patches = plt.hist(data, bins=bins, color='skyblue', 
                               edgecolor='black', alpha=0.7, rwidth=0.8)
    
    # 设置图表属性
    plt.xlabel('数值范围', fontsize=12)
    plt.ylabel('频次', fontsize=12)
    plt.title(f'{title} (分档宽度: {bin_width})', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # 设置x轴刻度标签
    bin_labels = []
    for i in range(len(bins) - 1):
        bin_labels.append(f"{int(bins[i])}-{int(bins[i+1])}")
    
    # 设置x轴刻度位置和标签
    bin_centers = (bins[:-1] + bins[1:]) / 2
    plt.xticks(bin_centers, bin_labels, rotation=45)
    
    # 在每个柱子上方显示数量
    for i, (count, bin_center) in enumerate(zip(n, bin_centers)):
        if count > 0:
            plt.text(bin_center, count + 0.5, str(int(count)), 
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 添加统计信息文本框
    stats_text = f"""统计信息:
样本数: {len(data)}
最小值: {data.min():.1f}
最大值: {data.max():.1f}
平均值: {data.mean():.1f}
中位数: {np.median(data):.1f}"""
    
    plt.text(0.8, 0.98, stats_text, transform=plt.gca().transAxes,
             fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # 调整布局
    plt.tight_layout()
    
    # 显示图表
    plt.show(block=block)
    
    # 返回统计信息
    return n, bins

def display_results(rising_stocks, consecutive_weeks=4):
    """显示分析结果"""
    if not rising_stocks:
        print(f"\n未找到连续{consecutive_weeks}周股价上涨的股票")
        return
    
    print(f"\n{'='*60}")
    print(f"连续{consecutive_weeks}周股价上涨的股票分析结果")
    print(f"{'='*60}")

    future_pct_list = []
    six_month_pct_list = []
    pct_list = []
    vol_ratio_list = []
    roe_mean_list = []
    roe_rising_list = []
    rise_fall_list = []
    
    for stock_code, periods in rising_stocks.items():
        #print(f"\n📈 股票代码: {stock_code}")
        #print(f"   发现 {len(periods)} 个连续{consecutive_weeks}周上涨的时期")
        
        for i, period in enumerate(periods, 1):
            #if period['future_pct'] > 0:
            #    continue
            future_pct_list.append(period['future_pct'])
            six_month_pct_list.append(period['six_month_pct'])
            pct_list.append(period['pct'])
            vol_ratio_list.append(period['vol_ratio'])
            roe_mean_list.append(period['roe_mean'])
            roe_rising_list.append(period['roe_rising'])
            rise_fall_list.append(period['rise_fall_r'])
            #continue
            #if len(future_pct_list) > 200:
            #    break
            print(f"\n📈 股票代码: {stock_code}")
            print(f"\n   时期 {i}:")
            print(f"     时间段: {period['start_date']} 至 {period['end_date']}")
            print(f"     起始价: {period['start_price']}")
            print(f"     结束价: {period['end_price']}")
            print(f"     未来一月涨幅: {period['future_pct']}%")
            print(f"     过去六个月波动: {period['six_month_pct']}%")
            print(f"     成交比: {period['vol_ratio']}")
            print(f"     ROE平均: {period['roe_mean']}")
            print(f"     ROE涨幅: {period['roe_rising']}")
            
            print(f"     详细周数据:")
            for week_data in period['period_data']:
                #print(week_data)
                if week_data['week_number'] == 1:
                    print(f"       第{week_data['week_number']}周({week_data['date']}): {week_data['close_price']}")
                    continue
                
                last_week_price = period['period_data'][week_data['week_number']-2]['close_price']
                pct = (week_data['close_price'] - last_week_price) / last_week_price * 100
                pct = round(pct, 2)
                trend = "↑" if week_data['week_number'] == 1 or last_week_price < week_data['close_price'] else "→"
                print(f"       第{week_data['week_number']}周({week_data['date']}): {week_data['close_price']} {trend} {pct}%")

    max_pct = max(future_pct_list)
    min_pct = min(future_pct_list)
    mean_pct = statistics.mean(future_pct_list)
    print(f"max涨幅{max_pct}\nmin涨幅{min_pct}\n平均涨幅{mean_pct}")
    
    plot_scatter(six_month_pct_list, future_pct_list, '涨幅 - 股价')
    plot_scatter(rise_fall_list, future_pct_list, '涨叠 - 股价')
    #plot_scatter(pct_list, future_pct_list, '当月涨幅 - 股价')
    #plot_scatter(roe_mean_list, future_pct_list, 'ROE_m - 股价')
    #plot_scatter(roe_rising_list, future_pct_list, 'ROE_r - 股价')
    #plot_scatter(vol_ratio_list, future_pct_list, 'Vol - Price')

    categorize_and_plot_histogram(future_pct_list,'股价分布', 5)
    categorize_and_plot_histogram(rise_fall_list,'涨跌分布', 0.4)
    #categorize_and_plot_histogram(pct_list,'当月涨幅分布', 5)
    #categorize_and_plot_histogram(roe_mean_list,'ROE 平均', 15)
    #categorize_and_plot_histogram(roe_rising_list,'ROE 涨幅', 10)
    categorize_and_plot_histogram(six_month_pct_list,'过去六月涨幅',20, True)
    #categorize_and_plot_histogram(vol_ratio_list,'成交量比值',2, True)

def save_analysis_results(rising_stocks, consecutive_weeks=4, filename=None):
    """保存分析结果到JSON文件"""
    if filename is None:
        filename = f"consecutive_rising_stocks_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    results = {
        'analysis_info': {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'consecutive_weeks': consecutive_weeks,
            'total_stocks_analyzed': len(rising_stocks)
        },
        'rising_stocks': rising_stocks
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n分析结果已保存到: {filename}")
        return filename
    except Exception as e:
        print(f"保存结果时出错: {e}")
        return None

def analysis_price():
    """主函数"""
    # 配置参数
    JSON_FILENAME = "stocks_prices_MA5.json"  # 修改为你的JSON文件名
    CONSECUTIVE_WEEKS = 5
    
    print("开始分析连续上涨股票...")
    print(f"目标: 连续{CONSECUTIVE_WEEKS}周股价上涨")
    
    # 1. 加载数据
    stock_data = load_existing_stocks(JSON_FILENAME)
    if stock_data is None:
        print("未找到可用的股票数据文件，请检查文件路径")
        return
    
    # 显示数据基本信息
    print(f"\n数据概览:")
    for stock_code, data in list(stock_data.items())[:5]:  # 只显示前5支股票
        if data:
            dates = [item['date'] for item in data]
            print(f"  {stock_code}: {len(data)}周数据, 时间范围: {min(dates)} 至 {max(dates)}")
            MA5 = [item['MA5'] for item in data]
            print(f"  {stock_code}: MA5{MA5[0:4]}")

    
    # 2. 分析连续上涨的股票
    industry_info = load_existing_stocks("industry_info.json")
    
    industrys = industry_info.keys()
    for industry in industrys:
        break
        if industry != "电机":
            continue
    #print(f"\n正在分析连续{CONSECUTIVE_WEEKS}周上涨的股票...")
        rising_stocks = find_consecutive_rising_stocks(stock_data, industry, CONSECUTIVE_WEEKS)
        future_pct_list = []
        for stock_code, periods in rising_stocks.items():
            for i, period in enumerate(periods, 1):
                future_pct_list.append(period['future_pct'])

        #max_pct = max(future_pct_list)
        #min_pct = min(future_pct_list)
        mean_pct = statistics.mean(future_pct_list)
        n1 = len([pct for pct in future_pct_list if pct > -5 and pct < 0])
        n2 = len([pct for pct in future_pct_list if pct > 0 and pct < 5])
        if n1 < n2:
            print(f"{industry}  平均涨幅{mean_pct:.2f} {n2} {n1}")

    #exit()
    rising_stocks = find_consecutive_rising_stocks(stock_data, None, CONSECUTIVE_WEEKS)
    #rising_stocks = analyze_stocks_multithread(stock_data, CONSECUTIVE_WEEKS, 8)
    # 3. 显示结果
    display_results(rising_stocks, CONSECUTIVE_WEEKS)
    
    # 4. 保存结果
    if rising_stocks:
        #result_file = save_analysis_results(rising_stocks, CONSECUTIVE_WEEKS)
        
        # 显示统计信息
        print(f"\n📊 分析统计:")
        print(f"   分析股票数量: {len(stock_data)}")
        print(f"   符合条件股票: {len(rising_stocks)}")
        print(f"   总连续上涨期数: {sum(len(periods) for periods in rising_stocks.values())}")

def analysis_daily_price():
    all_stocks = load_existing_stocks()
    stock_codes = list(all_stocks.keys())
    stock_codes = stock_codes[0:600]

    rising_stocks = {}
    start_time = time.time()
    rising_stocks = analyze_stocks_multithread(stock_codes, 20)

    for i, stock_code in enumerate(stock_codes, 1):
        break
        #if stock_code != "600000":
        #if stock_code != "000017":
        #if stock_code != "000010":
        #if stock_code != "000411":
        #if stock_code != "000506":
        #if stock_code != "000655":
        #    continue
        #print(stock_code)
        
        code, result = analyze_single_stock(stock_code, 20)
        rising_stocks[code] = result
        #print(result)

    end_time = time.time()
    print(f"\n分析完成! 耗时: {end_time - start_time:.2f}秒")

    k_list = []
    se_list = []
    pct_se_list = []
    pct_b_list = []
    future_pct_list = []

    for code, result in rising_stocks.items():
        for i, period in enumerate(result, 1):
            future_pct_list.append(period['future_pct'])
            k_list.append(period['slope'])
            se_list.append(period['se'])
            pct_se_list.append(period['pct_se'])
            pct_b_list.append(period['pct_b'])

    if len(future_pct_list) != 0:
        plot_scatter(k_list, future_pct_list, 'slope - 股价')
        plot_scatter(se_list, future_pct_list, '标准差 - 股价')
        plot_scatter(pct_b_list, future_pct_list, 'pct平均 - 股价')
        plot_scatter(pct_se_list, future_pct_list, 'pct标准差 - 股价')
        #plot_3D_sactter(k_list, pct_se_list, future_pct_list, '', '斜率', '标准差', 'pct')

        categorize_and_plot_histogram(future_pct_list,'股价分布', 10)
        categorize_and_plot_histogram(k_list,'斜率',0.1)
        categorize_and_plot_histogram(pct_se_list,'pct标准差',0.1)
        categorize_and_plot_histogram(pct_b_list,'pct平均',0.1)
        categorize_and_plot_histogram(se_list,'标准差',0.1, True)
        exit()

def main():

    #file_path = "stocks_prices_MA5.json"
    #if not os.path.exists(file_path):
    #    df = load_from_parquet("stock_prices_MA5.parquet")
    #    save_to_json(df)
    #start_time = time.time()
    #analysis_price()
    collect_stocks_price()
    #stock_data = load_existing_stocks("stocks_prices_MA5.json")
    #save_compact_format(stock_data)
    #save_to_csv(stock_data)
    #save_to_parquet(stock_data)
    #load_from_parquet("test.par")
    #end_time = time.time()
    #print(f"load parquet {end_time - start_time}s")
    #analysis_price()
    #analysis_daily_price()

if __name__ == "__main__":
    main()
    
