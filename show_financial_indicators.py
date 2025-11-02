#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
显示财务指标名称映射
"""

import akshare as ak
import pandas as pd

def show_financial_indicator_names():
    """显示财务指标名称映射"""
    
    stock_code = '600519'  # 贵州茅台
    
    try:
        # 获取原始财务摘要数据
        df = ak.stock_financial_abstract(stock_code)
        
        if df is None or df.empty:
            print("无法获取财务数据")
            return
        
        print(f"股票 {stock_code} 的财务指标名称映射:")
        print("=" * 80)
        
        # 显示所有财务指标名称和对应的编号
        print("编号\t指标名称")
        print("-" * 80)
        
        for idx, indicator_name in enumerate(df.index):
            print(f"{idx}\t{indicator_name}")
        
        print("\n" + "=" * 80)
        print(f"总共 {len(df.index)} 个财务指标")
        
        # 显示一些关键指标
        print("\n关键财务指标示例:")
        print("-" * 80)
        
        # 查找常见的关键指标
        key_indicators = {
            '营业总收入': '营业收入',
            '净利润': '净利润',
            '资产总计': '总资产',
            '负债合计': '总负债',
            '净资产收益率': 'ROE',
            '基本每股收益': '每股收益',
            '营业收入': '营业收入',
            '营业成本': '营业成本',
            '销售费用': '销售费用',
            '管理费用': '管理费用',
            '财务费用': '财务费用',
            '经营活动产生的现金流量净额': '经营现金流',
            '投资活动产生的现金流量净额': '投资现金流',
            '筹资活动产生的现金流量净额': '筹资现金流'
        }
        
        for idx, indicator_name in enumerate(df.index):
            for key, display_name in key_indicators.items():
                if key in indicator_name:
                    print(f"{idx}\t{indicator_name} ({display_name})")
                    break
        
        # 显示数据结构
        print("\n数据结构信息:")
        print("-" * 80)
        print(f"数据形状: {df.shape}")
        print(f"行数（指标数量）: {len(df.index)}")
        print(f"列数（报告期数量）: {len(df.columns)}")
        
        # 显示前几个报告期
        print(f"\n前5个报告期:")
        for i, col in enumerate(df.columns[:5]):
            print(f"  列{i}: {col}")
        
        # 显示一些具体数据示例
        print(f"\n数据示例（第一个报告期）:")
        print("-" * 80)
        first_period = df.columns[0]
        print(f"报告期: {first_period}")
        
        # 显示前10个指标的值
        for i in range(min(10, len(df.index))):
            indicator_name = df.index[i]
            value = df.iloc[i, 0]
            print(f"  {i}: {indicator_name} = {value}")
        
    except Exception as e:
        print(f"获取财务指标名称失败: {e}")

def analyze_data_structure():
    """分析数据结构"""
    
    stock_code = '600519'
    
    try:
        df = ak.stock_financial_abstract(stock_code)
        
        if df is None or df.empty:
            return
        
        print("\n数据结构分析:")
        print("=" * 80)
        
        print("1. 数据索引（财务指标）:")
        print(f"   类型: {type(df.index)}")
        print(f"   长度: {len(df.index)}")
        print(f"   前5个指标: {list(df.index[:5])}")
        
        print("\n2. 数据列（报告期）:")
        print(f"   类型: {type(df.columns)}")
        print(f"   长度: {len(df.columns)}")
        print(f"   前5个报告期: {list(df.columns[:5])}")
        
        print("\n3. 数据类型:")
        print(f"   数据类型: {type(df)}")
        print(f"   数据形状: {df.shape}")
        
        # 显示具体的财务指标分类
        print("\n4. 财务指标分类:")
        indicators_by_category = {}
        
        for indicator in df.index:
            indicator_str = str(indicator)
            
            if '收入' in indicator_str:
                category = '收入类'
            elif '利润' in indicator_str or '收益' in indicator_str:
                category = '利润类'
            elif '资产' in indicator_str:
                category = '资产类'
            elif '负债' in indicator_str:
                category = '负债类'
            elif '现金流' in indicator_str or '流量' in indicator_str:
                category = '现金流类'
            elif '率' in indicator_str:
                category = '比率类'
            else:
                category = '其他'
            
            if category not in indicators_by_category:
                indicators_by_category[category] = []
            indicators_by_category[category].append(indicator_str)
        
        for category, indicators in indicators_by_category.items():
            print(f"   {category}: {len(indicators)} 个指标")
        
    except Exception as e:
        print(f"分析数据结构失败: {e}")

if __name__ == "__main__":
    print("财务指标名称映射显示")
    print("=" * 80)
    
    # 显示财务指标名称
    show_financial_indicator_names()
    
    # 分析数据结构
    analyze_data_structure()
    
    print("\n" + "=" * 80)
    print("演示完成")