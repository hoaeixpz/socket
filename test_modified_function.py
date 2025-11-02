#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改后的 _process_financial_data 函数
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from financial_abstract_collector import FinancialAbstractCollector
import akshare as ak
import pandas as pd
import logging

def test_modified_function():
    """测试修改后的函数"""
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建收集器
    collector = FinancialAbstractCollector()
    
    # 测试股票代码
    stock_code = '600519'
    
    print("=== 测试修改后的 _process_financial_data 函数 ===")
    
    try:
        # 获取原始数据
        print("1. 获取原始财务摘要数据...")
        df = ak.stock_financial_abstract(stock_code)
        
        if df is None or df.empty:
            print("获取原始数据失败")
            return
        
        print(f"原始数据形状: {df.shape}")
        print(f"原始数据索引（财务指标）: {len(df.index)} 个")
        print(f"原始数据列（报告期）: {len(df.columns)} 个")
        
        # 显示前几个财务指标
        print("\n前5个财务指标:")
        for i in range(min(5, len(df.index))):
            print(f"  {i}: {df.index[i]}")
        
        # 显示前几个报告期
        print("\n前5个报告期:")
        for i in range(min(5, len(df.columns))):
            print(f"  列{i}: {df.columns[i]}")
        
        # 测试修改后的函数
        print("\n2. 使用修改后的 _process_financial_data 函数处理数据...")
        processed_df = collector._process_financial_data(df, years=5)
        
        if processed_df.empty:
            print("处理后的数据为空")
            return
        
        print(f"处理后的数据形状: {processed_df.shape}")
        print(f"处理后的数据列名:")
        for i, col in enumerate(processed_df.columns):
            print(f"  {i}: {col}")
        
        # 显示处理后的数据
        print("\n3. 处理后的数据预览:")
        print(processed_df.head())
        
        # 检查关键指标是否存在
        print("\n4. 检查关键指标:")
        key_indicators = ['营业总收入', '净利润', '资产总计', '负债合计', '净资产收益率', '基本每股收益']
        
        for indicator in key_indicators:
            found = False
            for col in processed_df.columns:
                if indicator in str(col):
                    print(f"  ✓ 找到指标: {col}")
                    found = True
                    break
            if not found:
                print(f"  ✗ 未找到指标: {indicator}")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

def compare_old_new_approach():
    """比较新旧处理方法的差异"""
    
    print("\n=== 比较新旧处理方法的差异 ===")
    
    stock_code = '600519'
    
    try:
        # 获取原始数据
        df = ak.stock_financial_abstract(stock_code)
        
        if df.empty:
            return
        
        print("原始数据结构:")
        print(f"  行数（财务指标）: {len(df.index)}")
        print(f"  列数（报告期）: {len(df.columns)}")
        print(f"  数据形状: {df.shape}")
        
        # 新方法：转置处理
        print("\n新方法（转置处理）:")
        collector = FinancialAbstractCollector()
        new_df = collector._process_financial_data(df, years=5)
        
        if not new_df.empty:
            print(f"  处理后的行数（报告期）: {len(new_df)}")
            print(f"  处理后的列数（财务指标+元数据）: {len(new_df.columns)}")
            print(f"  数据形状: {new_df.shape}")
            
            # 显示列名示例
            print("  列名示例:")
            for i, col in enumerate(new_df.columns[:10]):
                print(f"    {i}: {col}")
        
    except Exception as e:
        print(f"比较过程中出错: {e}")

if __name__ == "__main__":
    test_modified_function()
    compare_old_new_approach()