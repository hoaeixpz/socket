#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试不同的AkShare API方法
"""

import akshare as ak
import pandas as pd

def test_akshare_methods():
    """测试不同的AkShare方法"""
    print("=== 测试AkShare API方法 ===")
    
    test_stocks = ["000001", "600036", "000858"]
    
    for stock_code in test_stocks:
        print(f"\n测试股票: {stock_code}")
        
        # 方法1: stock_zh_a_hist
        print("1. 测试 stock_zh_a_hist...")
        try:
            data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                     start_date="2024-01-01", end_date="2024-10-31", adjust="qfq")
            if data is not None and not data.empty:
                print(f"   成功获取 {len(data)} 条数据")
                print(f"   数据列: {list(data.columns)}")
            else:
                print("   返回数据为空")
        except Exception as e:
            print(f"   失败: {e}")
        
        # 方法2: stock_zh_a_hist_tx
        print("2. 测试 stock_zh_a_hist_tx...")
        try:
            data = ak.stock_zh_a_hist_tx(symbol=stock_code, start_date="20240101", end_date="20241031")
            if data is not None and not data.empty:
                print(f"   成功获取 {len(data)} 条数据")
                print(f"   数据列: {list(data.columns)}")
            else:
                print("   返回数据为空")
        except Exception as e:
            print(f"   失败: {e}")
        
        # 方法3: 测试获取股票基本信息
        print("3. 测试股票基本信息...")
        try:
            info = ak.stock_individual_info_em(symbol=stock_code)
            if info is not None and not info.empty:
                print(f"   成功获取基本信息")
                print(f"   信息列: {list(info.columns)}")
                print(f"   示例数据:")
                for i in range(min(3, len(info))):
                    print(f"     {info.iloc[i]['item']}: {info.iloc[i]['value']}")
            else:
                print("   返回信息为空")
        except Exception as e:
            print(f"   失败: {e}")
        
        # 方法4: 测试获取股票列表
        print("4. 测试股票列表...")
        try:
            stock_list = ak.stock_info_a_code_name()
            if stock_list is not None and not stock_list.empty:
                print(f"   成功获取 {len(stock_list)} 只股票列表")
                # 检查测试股票是否在列表中
                if stock_code in stock_list['code'].values:
                    stock_name = stock_list[stock_list['code'] == stock_code]['name'].iloc[0]
                    print(f"   {stock_code} 在列表中: {stock_name}")
                else:
                    print(f"   {stock_code} 不在列表中")
            else:
                print("   返回列表为空")
        except Exception as e:
            print(f"   失败: {e}")

if __name__ == "__main__":
    test_akshare_methods()