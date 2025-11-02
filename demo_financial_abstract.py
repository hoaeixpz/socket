#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示脚本：使用 stock_financial_abstract 获取近五年的财务数据
"""

import akshare as ak
import pandas as pd
import time
from datetime import datetime

def demo_stock_financial_abstract():
    """演示获取财务摘要数据"""
    
    # 测试股票代码
    test_stocks = ['600519']
    
    for stock_code in test_stocks:
        print(f"\n{'='*60}")
        print(f"正在获取股票 {stock_code} 的财务摘要数据...")
        print(f"{'='*60}")
        
        try:
            # 使用akshare获取财务摘要数据
            df = ak.stock_financial_abstract(stock_code)
            
            if df is None or df.empty:
                print(f"股票 {stock_code} 的财务摘要数据为空")
                continue
            
            print(f"成功获取股票 {stock_code} 的财务摘要数据")
            print(f"数据形状: {df.shape}")
            print(f"数据列名: {list(df.columns)}")
            
            # 显示数据结构
            print("\n数据结构:")
            print(df.head(3).T)  # 转置显示前3行数据
            
            # 分析近五年的数据
            current_year = datetime.now().year
            recent_years = range(current_year - 4, current_year + 1)
            
            print(f"\n近五年数据 ({current_year-4}-{current_year}):")
            
            # 筛选近五年的数据
            recent_data = {}
            for column in df.columns:
                try:
                    # 尝试解析日期列
                    if isinstance(column, (int, str)) and len(str(column)) == 8:
                        date_str = str(column)
                        year = int(date_str[:4])
                        
                        if year in recent_years:
                            recent_data[date_str] = df[column]
                            print(f"  {date_str}: 有数据")
                except:
                    continue
            
            if not recent_data:
                print("  未找到近五年的财务数据")
            else:
                # 显示关键财务指标
                print("\n关键财务指标:")
                for date_str, data in recent_data.items():
                    print(f"\n  {date_str}:")
                    
                    # 查找关键指标
                    key_indicators = {
                        '营业总收入': '营收',
                        '净利润': '净利润', 
                        '资产总计': '总资产',
                        '负债合计': '总负债',
                        '净资产收益率': 'ROE',
                        '基本每股收益': '每股收益'
                    }
                    
                    for indicator_key, indicator_name in key_indicators.items():
                        if indicator_key in data.index:
                            value = data[indicator_key]
                            if pd.notna(value):
                                print(f"    {indicator_name}: {value}")
            
            # 保存数据到CSV文件
            filename = f"{stock_code}_financial_abstract.csv"
            df.to_csv(filename, encoding='utf-8-sig')
            print(f"\n数据已保存到: {filename}")
            
        except Exception as e:
            print(f"获取股票 {stock_code} 财务摘要数据失败: {e}")
        
        # 添加延迟避免请求过快
        time.sleep(2)

def analyze_financial_trend():
    """分析财务趋势"""
    
    print(f"\n{'='*60}")
    print("财务趋势分析")
    print(f"{'='*60}")
    
    stock_code = '600519'  # 贵州茅台
    
    try:
        df = ak.stock_financial_abstract(stock_code)
        
        if df is None or df.empty:
            print("无法获取数据进行分析")
            return
        
        # 提取近五年的营收和净利润数据
        current_year = datetime.now().year
        revenue_data = {}
        profit_data = {}
        
        for column in df.columns:
            try:
                if isinstance(column, (int, str)) and len(str(column)) == 8:
                    date_str = str(column)
                    year = int(date_str[:4])
                    
                    if year >= current_year - 4:
                        period_data = df[column]
                        
                        # 获取营收和净利润
                        if '营业总收入' in period_data.index:
                            revenue = period_data['营业总收入']
                            if pd.notna(revenue):
                                revenue_data[year] = revenue
                        
                        if '净利润' in period_data.index:
                            profit = period_data['净利润']
                            if pd.notna(profit):
                                profit_data[year] = profit
            except:
                continue
        
        # 分析趋势
        if revenue_data and profit_data:
            print("\n营收趋势:")
            for year in sorted(revenue_data.keys()):
                print(f"  {year}年: {revenue_data[year]:.2f} 亿元")
            
            print("\n净利润趋势:")
            for year in sorted(profit_data.keys()):
                print(f"  {year}年: {profit_data[year]:.2f} 亿元")
            
            # 计算增长率
            years = sorted(revenue_data.keys())
            if len(years) > 1:
                print("\n增长率分析:")
                for i in range(1, len(years)):
                    current_year = years[i]
                    prev_year = years[i-1]
                    
                    if prev_year in revenue_data and current_year in revenue_data:
                        revenue_growth = (revenue_data[current_year] - revenue_data[prev_year]) / revenue_data[prev_year] * 100
                        print(f"  营收增长率 {prev_year}→{current_year}: {revenue_growth:.2f}%")
                    
                    if prev_year in profit_data and current_year in profit_data:
                        profit_growth = (profit_data[current_year] - profit_data[prev_year]) / profit_data[prev_year] * 100
                        print(f"  净利润增长率 {prev_year}→{current_year}: {profit_growth:.2f}%")
        
    except Exception as e:
        print(f"财务趋势分析失败: {e}")

if __name__ == "__main__":
    print("财务摘要数据获取演示")
    print("=" * 60)
    
    # 演示基本功能
    demo_stock_financial_abstract()
    
    # 分析财务趋势
    analyze_financial_trend()
    
    print(f"\n{'='*60}")
    print("演示完成")
    print(f"{'='*60}")