#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("检查akshare最新接口...")

import akshare as ak
import re

# 获取所有接口名称
all_interfaces = dir(ak)

# 查找行业相关接口
print("\n🔍 查找行业相关接口:")
industry_related = []
for interface in all_interfaces:
    if not interface.startswith('_'):
        if any(keyword in interface.lower() for keyword in ['industr', 'board', 'sector', 'sw_', '申万']):
            industry_related.append(interface)

print(f"找到 {len(industry_related)} 个行业相关接口:")
for interface in sorted(industry_related):
    print(f"  - {interface}")

# 查找股票板块相关接口
print(f"\n🔍 查找板块相关接口:")
board_related = []
for interface in all_interfaces:
    if not interface.startswith('_'):
        if 'board' in interface.lower():
            board_related.append(interface)

print(f"找到 {len(board_related)} 个板块相关接口:")
for interface in sorted(board_related):
    print(f"  - {interface}")

# 查找申万相关接口
print(f"\n🔍 查找申万相关接口:")
sw_related = []
for interface in all_interfaces:
    if not interface.startswith('_'):
        if 'sw_' in interface.lower() or '申万' in interface:
            sw_related.append(interface)

print(f"找到 {len(sw_related)} 个申万相关接口:")
for interface in sorted(sw_related):
    print(f"  - {interface}")

# 测试一些可能的接口
print(f"\n🧪 测试常见接口:")

test_interfaces = [
    'stock_board_industry_name_em',
    'stock_board_industry_detail_em', 
    'stock_board_concept_name_em',
    'index_realtime_sw',
    'sw_index_spot',
    'sw_index_second_spot',
    'index_component_sw',
    'stock_board_industry_summary_em'
]

for interface in test_interfaces:
    if hasattr(ak, interface):
        print(f"✅ {interface}")
        
        # 尝试调用（无参数的接口）
        if 'name' in interface and 'board' in interface:
            try:
                result = getattr(ak, interface)()
                print(f"   📊 返回数据: {len(result)} 条记录")
                print(f"   📋 列名: {list(result.columns)[:5]}...")  # 只显示前5列
            except Exception as e:
                print(f"   ❌ 调用失败: {str(e)[:50]}...")
    else:
        print(f"❌ {interface}")