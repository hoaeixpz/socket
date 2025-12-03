#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("🧪 测试确定可用的akshare接口...")

import akshare as ak
import pandas as pd

def test_interface(interface_name, *args, **kwargs):
    """测试单个接口"""
    try:
        print(f"\n📡 测试接口: {interface_name}")
        func = getattr(ak, interface_name)
        result = func(*args, **kwargs)
        
        print(f"✅ 成功！返回 {len(result)} 条数据")
        print(f"📋 列名: {list(result.columns)}")
        print("📄 前3行数据:")
        print(result.head(3))
        
        return result
        
    except Exception as e:
        print(f"❌ 失败: {str(e)[:100]}...")
        return None

# 已确认可用的接口
working_interfaces = [
    ('stock_board_industry_name_em', []),
    ('stock_board_concept_name_em', []),
    ('index_realtime_sw', ['一级行业']),
    ('index_component_sw', ['801780']),  # 银行指数
]

for interface_name, args in working_interfaces:
    test_interface(interface_name, *args)

print(f"\n{'='*50}")
print("🎯 测试完成！")