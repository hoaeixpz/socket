#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建good_stocks.json文件，筛选并保存所有status为"good"的股票信息
"""

import json
import os

def create_good_stocks_file():
    """创建good_stocks.json文件"""
    
    # 读取roe_analysis_results.json文件
    input_file = "roe_analysis_results.json"
    output_file = "good_stocks.json"
    
    if not os.path.exists(input_file):
        print(f"错误：找不到文件 {input_file}")
        return
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 筛选status为"good"的股票
        good_stocks = {}
        for stock_code, stock_info in data.items():
            if stock_info.get('status') == 'good':
                good_stocks[stock_code] = stock_info
        
        # 保存到good_stocks.json文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(good_stocks, f, ensure_ascii=False, indent=2)
        
        print(f"成功创建 {output_file}")
        print(f"共筛选出 {len(good_stocks)} 只good状态的股票")
        
        # 显示前几只股票作为示例
        print("\n前10只good股票示例：")
        count = 0
        for stock_code, stock_info in list(good_stocks.items())[:10]:
            print(f"{stock_code}: {stock_info.get('stock_name', 'N/A')} - ROE: {stock_info.get('roe_details', {})}")
            count += 1
            if count >= 10:
                break
                
    except Exception as e:
        print(f"处理文件时出错：{e}")

if __name__ == "__main__":
    create_good_stocks_file()