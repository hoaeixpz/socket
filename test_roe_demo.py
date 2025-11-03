#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROE分析器简单测试
"""

import akshare as ak
import pandas as pd
import time
from datetime import datetime

def test_single_stock_analysis():
    """测试单只股票分析"""
    
    print("=== ROE分析器简单测试 ===\n")
    
    # 测试股票
    test_stocks = [
        ('600519', '贵州茅台'),
        ('000001', '平安银行'),
        ('601318', '中国平安')
    ]
    
    for stock_code, stock_name in test_stocks:
        print(f"\n分析 {stock_code} {stock_name}:")
        
        try:
            # 获取财务摘要数据
            df = ak.stock_financial_abstract(stock_code)
            
            if df is None or df.empty:
                print("  财务数据获取失败")
                continue
            
            print(f"  原始数据形状: {df.shape}")
            print(f"  数据列: {df.columns.tolist()[:10]}...")  # 显示前10列
            
            # 检查是否有ROE指标
            if '指标' in df.columns:
                # 查找ROE相关的指标
                roe_indicators = df[df['指标'].str.contains('ROE|净资产收益率', na=False)]
                if not roe_indicators.empty:
                    print(f"  找到ROE指标: {roe_indicators['指标'].tolist()}")
                    
                    # 显示最近几年的ROE数据
                    current_year = datetime.now().year
                    recent_years = []
                    
                    for col in df.columns:
                        if isinstance(col, (int, str)) and len(str(col)) == 8:
                            year = int(str(col)[:4])
                            if year >= current_year - 5:
                                recent_years.append(col)
                    
                    if recent_years:
                        print(f"  近5年数据列: {recent_years[:5]}")
                        
                        # 显示ROE数据
                        for idx, row in roe_indicators.iterrows():
                            indicator_name = row['指标']
                            print(f"  \n指标: {indicator_name}")
                            for year_col in recent_years[:3]:  # 显示最近3年
                                if year_col in df.columns:
                                    value = row[year_col]
                                    if pd.notna(value):
                                        print(f"    {year_col}: {value}")
                else:
                    print("  未找到ROE指标")
            else:
                print("  数据格式异常，缺少'指标'列")
            
        except Exception as e:
            print(f"  分析失败: {e}")
        
        print("-" * 50)
        time.sleep(1)  # 避免频繁请求

def test_stock_list():
    """测试股票列表获取"""
    print("\n=== 测试股票列表获取 ===\n")
    
    try:
        stock_list = ak.stock_info_a_code_name()
        
        if stock_list is not None and not stock_list.empty:
            print(f"成功获取股票列表，共 {len(stock_list)} 只股票")
            print(f"前5只股票:")
            for i, (_, row) in enumerate(stock_list.head().iterrows()):
                print(f"  {row['code']}: {row['name']}")
            
            # 测试过滤
            filtered = stock_list.copy()
            
            # 排除科创板
            filtered = filtered[~filtered['code'].str.startswith('688')]
            print(f"\n排除科创板后: {len(filtered)} 只")
            
            # 排除北交所
            filtered = filtered[~filtered['code'].str.startswith('8')]
            print(f"排除北交所后: {len(filtered)} 只")
            
            # 排除创业板
            filtered = filtered[~filtered['code'].str.startswith('30')]
            print(f"排除创业板后: {len(filtered)} 只")
            
            # 排除ST股
            filtered = filtered[~filtered['name'].str.contains('ST|\\*ST', na=False)]
            print(f"排除ST股后: {len(filtered)} 只")
            
            print(f"\n最终过滤后股票数量: {len(filtered)}")
            
        else:
            print("获取股票列表失败")
            
    except Exception as e:
        print(f"测试股票列表失败: {e}")

if __name__ == "__main__":
    # 先测试股票列表
    test_stock_list()
    
    # 再测试单只股票分析
    test_single_stock_analysis()
    
    print("\n=== 测试完成 ===")
    print("\n下一步可以运行完整的ROE分析器:")
    print("python stock_roe_analyzer_demo.py")