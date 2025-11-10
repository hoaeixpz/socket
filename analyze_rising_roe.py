#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析ROE逐年上升的股票
从roe_analysis_results.json中筛选出status为"good"的股票，
并找出ROE逐年上升的股票
"""

import json
import os
from datetime import datetime

def load_analysis_results():
    """加载ROE分析结果"""
    results_file = "roe_analysis_results.json"
    if not os.path.exists(results_file):
        print(f"错误：找不到文件 {results_file}")
        return None
    
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"读取文件错误: {e}")
        return None

def is_roe_rising(roe_details):
    """
    判断ROE是否逐年上升
    要求：近5年ROE逐年递增（2020-2024年）
    """
    # 检查是否有完整的5年数据
    required_years = ['2020', '2021', '2022', '2023', '2024']
    for year in required_years:
        if year not in roe_details:
            return False
    
    # 获取各年ROE值
    roe_values = [roe_details[year] for year in required_years]
    
    # 检查是否逐年上升
    for i in range(len(roe_values) - 1):
        if roe_values[i] >= roe_values[i + 1]:
            return False
    
    return True

def analyze_rising_roe_stocks():
    """分析ROE逐年上升的股票"""
    print("正在加载ROE分析结果...")
    data = load_analysis_results()
    if not data:
        return
    
    print(f"总共分析了 {len(data)} 只股票")
    
    # 筛选出status为"good"的股票
    good_stocks = {}
    for stock_code, stock_info in data.items():
        if stock_info.get('status') == 'good':
            good_stocks[stock_code] = stock_info
    
    print(f"其中status为'good'的股票有 {len(good_stocks)} 只")
    
    # 筛选ROE逐年上升的股票
    rising_roe_stocks = {}
    for stock_code, stock_info in good_stocks.items():
        roe_details = stock_info.get('roe_details', {})
        if is_roe_rising(roe_details):
            rising_roe_stocks[stock_code] = stock_info
    
    print(f"\nROE逐年上升的股票有 {len(rising_roe_stocks)} 只：")
    print("=" * 80)
    
    # 按ROE增长率排序
    sorted_stocks = sorted(rising_roe_stocks.items(), 
                          key=lambda x: x[1]['roe_details']['2024'] - x[1]['roe_details']['2020'], 
                          reverse=True)
    
    for stock_code, stock_info in sorted_stocks:
        roe_details = stock_info['roe_details']
        stock_name = stock_info['stock_name']
        
        # 计算ROE增长率
        roe_growth = roe_details['2024'] - roe_details['2020']
        roe_growth_rate = (roe_growth / roe_details['2020']) * 100 if roe_details['2020'] > 0 else float('inf')
        
        print(f"股票代码: {stock_code}")
        print(f"股票名称: {stock_name}")
        print(f"ROE变化: {roe_details['2020']:.2f}% → {roe_details['2024']:.2f}%")
        print(f"ROE增长: {roe_growth:.2f}% ({roe_growth_rate:.1f}%)")
        print(f"各年ROE: ", end="")
        for year in ['2020', '2021', '2022', '2023', '2024']:
            print(f"{year}:{roe_details[year]:.2f}% ", end="")
        print()
        print("-" * 80)
    
    # 保存结果到文件
    save_results(sorted_stocks)

def save_results(stocks):
    """保存分析结果到文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"rising_roe_stocks_{timestamp}.json"
    
    results = {
        'analysis_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_stocks_analyzed': len(stocks),
        'stocks': {}
    }
    
    for stock_code, stock_info in stocks:
        results['stocks'][stock_code] = stock_info
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n分析结果已保存到: {output_file}")
    except Exception as e:
        print(f"保存文件错误: {e}")

def get_statistics():
    """获取统计信息"""
    data = load_analysis_results()
    if not data:
        return
    
    good_stocks = [s for s in data.values() if s.get('status') == 'good']
    bad_stocks = [s for s in data.values() if s.get('status') == 'bad']
    
    print("\n" + "=" * 50)
    print("统计信息")
    print("=" * 50)
    print(f"总股票数量: {len(data)}")
    print(f"Good股票数量: {len(good_stocks)} ({len(good_stocks)/len(data)*100:.1f}%)")
    print(f"Bad股票数量: {len(bad_stocks)} ({len(bad_stocks)/len(data)*100:.1f}%)")
    
    # 统计ROE逐年上升的股票
    rising_count = 0
    for stock_info in good_stocks:
        roe_details = stock_info.get('roe_details', {})
        if is_roe_rising(roe_details):
            rising_count += 1
    
    print(f"ROE逐年上升的股票: {rising_count} ({rising_count/len(good_stocks)*100:.1f}% of good stocks)")
    print("=" * 50)

if __name__ == "__main__":
    print("ROE逐年上升股票分析工具")
    print("=" * 50)
    
    # 显示统计信息
    get_statistics()
    
    # 分析ROE逐年上升的股票
    analyze_rising_roe_stocks()