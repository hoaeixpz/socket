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
import concurrent.futures
import os
import numpy as np
from datetime import datetime, timedelta

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    code_str = str(stock_code).strip()
    
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    else:
        return code_str

def save_compact_format(stock_data):
    compact_data = {}
    
    for stock_code, data_list in stock_data.items():
        # 转换为紧凑格式: [[日期, 价格], ...]
        compact_data[stock_code] = [
            [item['date'], item['price']] 
            for item in data_list
        ]
    
    with open("stocks_prices_compact.json", 'w', encoding='utf-8') as f:
        json.dump(compact_data, f, separators=(',', ':'))
    
    print(f"紧凑格式数据已保存到 stocks_prices_compact.json")

def load_compact_format(filename):
    """加载紧凑格式数据并还原"""
    with open(filename, 'r', encoding='utf-8') as f:
        compact_data = json.load(f)
    
    # 还原为原始格式
    restored_data = {}
    for stock_code, compact_list in compact_data.items():
        restored_data[stock_code] = [
            {'date': item[0], 'price': item[1]} 
            for item in compact_list
        ]
    
    return restored_data

def save_to_csv(stock_data, filename="stock_prices_MA5.csv"):
    """保存为CSV格式（文件最小）"""
    all_data = []
    
    for stock_code, data_list in stock_data.items():
        for item in data_list:
            all_data.append({
                'code': stock_code,
                'date': item['date'],
                'MA5': item['MA5']
            })
    
    df = pd.DataFrame(all_data)
    df.to_csv(filename, index=False)
    
    file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
    print(f"CSV数据已保存到 {filename}, 大小: {file_size:.2f} MB")
    return df

def load_from_csv(filename):
    """从CSV加载数据"""
    df = pd.read_csv(filename)
    print(df.head())
    # 转换回字典格式
    stock_data = {}
    for stock_code in df['code'].unique():
        print(stock_code)
        stock_df = df[df['code'] == stock_code]
        stock_data[stock_code] = [
            {'date': row['date'], 'price': row['MA5']}
            for _, row in stock_df.iterrows()
        ]
    print("load csv finish")
    return stock_data
 
def save_to_parquet(stock_data, filename="stock_prices_MA5.parquet"):
    """保存为Parquet格式（高性能压缩）"""
    all_data = []
    
    for stock_code, data_list in stock_data.items():
        for item in data_list:
            all_data.append({
                'stock_code': stock_code,
                'date': item['date'],
                'MA5': item['MA5']
            })
    
    df = pd.DataFrame(all_data)
    df['date'] = pd.to_datetime(df['date'])
    
    # 保存为Parquet（自动压缩）
    df.to_parquet(filename, index=False, compression='snappy')
    
    file_size = os.path.getsize(filename) / (1024 * 1024)
    print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} MB")
    return df

def load_from_parquet(filename):
    """从Parquet加载数据"""
    df = pd.read_parquet(filename)
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    
    stock_data = df.groupby('stock_code')[['date', 'MA5']].apply(
        lambda x: x.to_dict('records'), include_groups=False
    ).to_dict()
    '''
    for stock_code in df['stock_code'].unique():
        stock_df = df[df['stock_code'] == stock_code]
        stock_data[stock_code] = [
            {'date': row['date'], 'price': row['price']}
            for _, row in stock_df.iterrows()
        ]
    '''
    
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
    
    return stock_df[['date', 'open', 'high', 'low', 'close', 'volume', 'MA5']]

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
                    "MA5": round(float(row['MA5']), 2)
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
    weekly_data = get_weekly_monday_prices()
    
    # 保存为JSON文件
    filename = save_to_json(weekly_data)
    
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

def analyze_single_stock(stock_item, consecutive_weeks):
    stock_code, weekly_data = stock_item

    try:
        # 确保数据按日期排序
        weekly_data.sort(key=lambda x: x['date'])

        # 确保有足够的数据点进行分析
        if len(weekly_data) < consecutive_weeks:
            print(f"股票 {stock_code} 数据点不足({len(weekly_data)}个)，跳过分析")
            return stock_code, []

        # 提取收盘价
        close_prices = [item['MA5'] for item in weekly_data]
        dates = [item['date'] for item in weekly_data]

        # 查找所有连续上涨的序列
        consecutive_periods = []

        for i in range(len(close_prices) - consecutive_weeks + 1):
            # 检查从i开始的连续consecutive_weeks周是否都上涨
            # 第一周上涨幅度不能大于3%，最后一周上涨幅度>3%且<10%
            is_consecutive_rising = True
            
            for j in range(i, i + consecutive_weeks - 1):
                if close_prices[j + 1] <= close_prices[j]:
                    is_consecutive_rising = False
                    break
            
            if is_consecutive_rising:
                # 计算涨幅和百分比
                start_price = close_prices[i]
                first_week_pct = (close_prices[i+1] - start_price)/start_price  * 100
                #if first_week_pct >= 3.0:
                #    continue
                end_price = close_prices[i + consecutive_weeks - 1]
                last_week_pct = ((end_price - close_prices[i + consecutive_weeks - 2]) /
                                 close_prices[i + consecutive_weeks - 2] * 100)
                #if last_week_pct < 3.0 or last_week_pct > 10.0:
                #    continue
                future_pct = 0
                if i + consecutive_weeks + 4 < len(close_prices):
                    future_price = close_prices[i + consecutive_weeks + 3]
                    future_pct = (future_price - end_price) / end_price * 100
                
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
                    'future_pct': round(future_pct, 2)
                })
        
        return  stock_code, consecutive_periods
    
    except Exception as e:
        print(f"分析股票 {stock_code} 时出错: {e}")
        return stock_code, []

def analyze_stocks_multithread(stock_data, consecutive_weeks = 5, max_workers=None):
    """使用多线程分析股票"""
    start_time = time.time()
    
    # 准备数据：将字典转换为(股票代码, 数据)的元组列表
    stock_items = list(stock_data.items())
    total_stocks = len(stock_items)
    
    print(f"开始多线程分析 {total_stocks} 支股票...")
    print(f"线程数: {max_workers if max_workers else '自动'}")
    
    rising_stocks = {}
    analyzed_count = 0
    
    # 使用线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_stock = {
            executor.submit(analyze_single_stock, item, consecutive_weeks): item[0] 
            for item in stock_items
        }
        
        # 处理完成的任务
        for future in concurrent.futures.as_completed(future_to_stock):
            stock_code = future_to_stock[future]
            try:
                stock_code, periods = future.result()
                analyzed_count += 1
                
                if periods:
                    rising_stocks[stock_code] = periods
                
                # 显示进度
                if analyzed_count % 100 == 0 or analyzed_count == total_stocks:
                    print(f"进度: {analyzed_count}/{total_stocks} ({analyzed_count/total_stocks*100:.1f}%)")
                    
            except Exception as e:
                print(f"股票 {stock_code} 分析失败: {e}")
                analyzed_count += 1
    
    end_time = time.time()
    print(f"\n分析完成! 耗时: {end_time - start_time:.2f}秒")
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

    last_six_month_prices = []
    for w in range(week_index - six_month_weeks, week_index):
        last_six_month_prices.append(close_prices[w])

    max_price = max(last_six_month_prices)
    min_price = min(last_six_month_prices)
    six_month_r = (max_price - min_price) / min_price * 100

    if six_month_r > 20:
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

    return is_consecutive_rising, six_month_r


def find_consecutive_rising_stocks(stock_data, consecutive_weeks=4):
    """
    找出连续N周股价都上涨的股票
    
    参数:
    stock_data: 股票数据字典
    consecutive_weeks: 连续上涨周数要求
    
    返回:
    符合条件的股票字典
    """
    rising_stocks = {}
    
    for stock_code, weekly_data in stock_data.items():
        #if not (stock_code == "sh600021" or stock_code == "sh601216" or stock_code == "sz000554"):
        #   continue
        # 确保数据按日期排序
        weekly_data.sort(key=lambda x: x['date'])
        
        # 确保有足够的数据点进行分析
        if len(weekly_data) < consecutive_weeks:
            print(f"股票 {stock_code} 数据点不足({len(weekly_data)}个)，跳过分析")
            continue
        
        # 提取收盘价
        close_prices = [item['MA5'] for item in weekly_data]
        dates = [item['date'] for item in weekly_data]
        
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
                future_pct = 0
                if i + consecutive_weeks + 4 < len(close_prices):
                    future_price = close_prices[i + consecutive_weeks + 3]
                    future_pct = (future_price - end_price) / end_price * 100
                '''
                if future_pct < 10:
                    print(f"stock_code {stock_code} {future_pct}")
                    last_six_month_prices = []
                    for w in range(i - six_month_weeks, i):
                        last_six_month_prices.append(close_prices[w])
                    print(last_six_month_prices)
                    print(dates[i-25])
                    print(close_prices[i-25])
                '''
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
                    'future_pct': round(future_pct, 2),
                    'six_month_pct': round(six_month_r, 2)
                })
        
        if consecutive_periods:
            rising_stocks[stock_code] = consecutive_periods

    
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
    plt.figure(figsize=(10, 8))
    
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
    plt.show()

def categorize_and_plot_histogram(data_list, bin_width=20, block=False):
    """
    绘制单个直方图（不包含子图）
    
    参数:
    data_list: 包含数值的列表
    bin_width: 档次宽度，默认为10
    """
    # 转换为numpy数组
    data = np.array(data_list)
    
    # 确定分档范围
    min_val = np.floor(data.min() / bin_width) * bin_width
    max_val = np.ceil(data.max() / bin_width) * bin_width
    
    # 创建分档边界
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
    plt.title(f'数值分布直方图 (分档宽度: {bin_width})', fontsize=14, fontweight='bold')
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
    
    plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes,
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
    
    for stock_code, periods in rising_stocks.items():
        #print(f"\n📈 股票代码: {stock_code}")
        #print(f"   发现 {len(periods)} 个连续{consecutive_weeks}周上涨的时期")
        
        for i, period in enumerate(periods, 1):
            #if period['future_pct'] > 0:
            #    continue
            future_pct_list.append(period['future_pct'])
            six_month_pct_list.append(period['six_month_pct'])
            continue
            #if len(future_pct_list) > 200:
            #    break
            print(f"\n📈 股票代码: {stock_code}")
            print(f"\n   时期 {i}:")
            print(f"     时间段: {period['start_date']} 至 {period['end_date']}")
            print(f"     起始价: {period['start_price']}")
            print(f"     结束价: {period['end_price']}")
            print(f"     未来一月涨幅: {period['future_pct']}%")
            print(f"     过去六个月波动: {period['six_month_pct']}%")
            
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
    categorize_and_plot_histogram(future_pct_list,10)
    categorize_and_plot_histogram(six_month_pct_list,2)
    plot_scatter(six_month_pct_list, future_pct_list)

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
    #stock_data = load_existing_stocks(JSON_FILENAME)
    stock_data = load_from_parquet("stock_prices_MA5.parquet")
    #stock_data = load_from_csv('stock_prices_MA5.csv')
    if stock_data is None:
        print("未找到可用的股票数据文件，请检查文件路径")
        return
    
    # 显示数据基本信息
    print(f"\n数据概览:")
    for stock_code, data in list(stock_data.items())[:5]:  # 只显示前5支股票
        if data:
            dates = [item['date'] for item in data]
            print(f"  {stock_code}: {len(data)}周数据, 时间范围: {min(dates)} 至 {max(dates)}")
    
    # 2. 分析连续上涨的股票
    print(f"\n正在分析连续{CONSECUTIVE_WEEKS}周上涨的股票...")
    rising_stocks = find_consecutive_rising_stocks(stock_data, CONSECUTIVE_WEEKS)
    #rising_stocks = analyze_stocks_multithread(stock_data, CONSECUTIVE_WEEKS, 8)
    # 3. 显示结果
    display_results(rising_stocks, CONSECUTIVE_WEEKS)
    
    # 4. 保存结果
    if rising_stocks:
        result_file = save_analysis_results(rising_stocks, CONSECUTIVE_WEEKS)
        
        # 显示统计信息
        print(f"\n📊 分析统计:")
        print(f"   分析股票数量: {len(stock_data)}")
        print(f"   符合条件股票: {len(rising_stocks)}")
        print(f"   总连续上涨期数: {sum(len(periods) for periods in rising_stocks.values())}")
    else:
        print(f"\n未找到连续{CONSECUTIVE_WEEKS}周上涨的股票，尝试分析连续3周上涨的股票...")
        rising_stocks_3 = find_consecutive_rising_stocks(stock_data, 3)
        #rising_stocks_3 = analyze_stocks_multithread(stock_data, 3)
        display_results(rising_stocks_3, 3)


def main():
    #analysis_price()
    #collect_stocks_price()
    #stock_data = load_existing_stocks("stocks_prices_MA5.json")
    #save_compact_format(stock_data)
    #save_to_csv(stock_data)
    #save_to_parquet(stock_data)
    #load_from_parquet("stock_prices_MA5.parquet")
    analysis_price()

if __name__ == "__main__":
    main()
    
