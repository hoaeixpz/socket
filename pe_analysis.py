#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PE分析更新程序
遍历good_stocks.json中的所有股票，计算PE值并直接更新到原文件中
"""

import json
import time
import logging
from pe_ratio_collector import PERatioCollector

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('pe_analysis_update.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def load_good_stocks():
    """加载good_stocks.json文件"""
    try:
        with open('good_stocks.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("错误：找不到good_stocks.json文件")
        return {}
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式错误 - {e}")
        return {}

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    code_str = str(stock_code).strip()
    
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    else:
        return code_str

def update_stocks_with_pe():
    """分析所有good股票的PE值并更新到原文件"""
    
    # 加载good股票数据
    good_stocks = load_good_stocks()
    
    if not good_stocks:
        print("没有找到good状态的股票数据")
        return 0
    
    print(f"找到 {len(good_stocks)} 只good状态的股票")
    
    # 创建PE收集器
    pe_collector = PERatioCollector(max_retries=3, retry_delay=2)
    
    # 记录更新数量
    updated_count = 0
    
    # 遍历所有股票
    for i, (stock_code, stock_info) in enumerate(good_stocks.items(), 1):
        if i > 2:
            break
        stock_name = stock_info.get('stock_name', '未知')
        
        print(f"\n{'='*60}")
        print(f"正在分析第 {i}/{len(good_stocks)} 只股票: {stock_name}({stock_code})")
        print(f"{'='*60}")
        
        # 添加市场前缀
        full_stock_code = add_stock_prefix(stock_code)
        
        try:
            # 获取当前PE值
            current_pe = pe_collector.get_current_pe_ratio(full_stock_code)
            
            if current_pe is not None:
                # 获取历史PE值
                historical_pe = pe_collector.get_historical_pe_ratios(full_stock_code, years=5)
                
                # 获取历史PEG
                historical_peg = pe_collector.get_historical_peg(full_stock_code, historical_pe, years=5)
                
                # 更新股票数据
                good_stocks[stock_code]['pe_analysis'] = {
                    'current_pe': current_pe,
                    'historical_pe': historical_pe,
                    'historical_peg': historical_peg,
                    'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'error': None
                }
                
                updated_count += 1
                print(f"✓ 成功获取 {stock_name} 的PE数据")
                print(f"  当前PE: {current_pe}")
                print(f"  历史PE: {historical_pe}")
                print(f"  历史PEG: {historical_peg}")
                
            else:
                print(f"✗ 获取 {stock_name} 的PE数据失败")
                good_stocks[stock_code]['pe_analysis'] = {
                    'current_pe': None,
                    'historical_pe': {},
                    'historical_peg': {},
                    'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'error': '获取PE数据失败'
                }
                
        except Exception as e:
            print(f"✗ 分析 {stock_name} 时发生错误: {e}")
            good_stocks[stock_code]['pe_analysis'] = {
                'current_pe': None,
                'historical_pe': {},
                'historical_peg': {},
                'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'error': str(e)
            }
        
        # 添加延时，避免请求过于频繁
        if i < len(good_stocks):  # 最后一只股票不需要延时
            wait_time = 3
            print(f"等待 {wait_time} 秒后继续...")
            time.sleep(wait_time)
    
    # 保存更新后的文件
    try:
        with open('good_stocks.json', 'w', encoding='utf-8') as f:
            json.dump(good_stocks, f, ensure_ascii=False, indent=2)
        print(f"\n成功更新 {updated_count} 只股票的PE数据到good_stocks.json")
        return updated_count
        
    except Exception as e:
        print(f"保存更新失败: {e}")
        return 0

def generate_summary_report(good_stocks):
    """生成分析报告摘要"""
    
    print("\n" + "="*80)
    print("PE分析报告摘要")
    print("="*80)
    
    total_stocks = len(good_stocks)
    successful_stocks = sum(1 for stock in good_stocks.values() 
                           if stock.get('pe_analysis', {}).get('current_pe') is not None)
    failed_stocks = total_stocks - successful_stocks
    
    print(f"总股票数: {total_stocks}")
    print(f"成功获取PE数据的股票数: {successful_stocks}")
    print(f"获取失败的股票数: {failed_stocks}")
    print(f"成功率: {successful_stocks/total_stocks*100:.1f}%")
    
    # 统计PE分布
    pe_values = []
    for stock in good_stocks.values():
        pe_analysis = stock.get('pe_analysis', {})
        current_pe = pe_analysis.get('current_pe')
        if current_pe is not None:
            if isinstance(current_pe, list):
                # 如果是列表，取第一个值（动态PE）
                pe_values.append(current_pe[0])
            else:
                pe_values.append(current_pe)
    
    if pe_values:
        print(f"\nPE值统计:")
        print(f"  最低PE: {min(pe_values):.2f}")
        print(f"  最高PE: {max(pe_values):.2f}")
        print(f"  平均PE: {sum(pe_values)/len(pe_values):.2f}")
        
        # PE分布
        low_pe = [pe for pe in pe_values if pe < 15]
        medium_pe = [pe for pe in pe_values if 15 <= pe <= 30]
        high_pe = [pe for pe in pe_values if pe > 30]
        
        print(f"\nPE分布:")
        print(f"  PE < 15: {len(low_pe)} 只 ({len(low_pe)/len(pe_values)*100:.1f}%)")
        print(f"  15 ≤ PE ≤ 30: {len(medium_pe)} 只 ({len(medium_pe)/len(pe_values)*100:.1f}%)")
        print(f"  PE > 30: {len(high_pe)} 只 ({len(high_pe)/len(pe_values)*100:.1f}%)")
    
    # 显示PE最低的10只股票
    if pe_values:
        print(f"\nPE最低的10只股票:")
        sorted_stocks = sorted(
            [(code, stock) for code, stock in good_stocks.items() 
             if stock.get('pe_analysis', {}).get('current_pe') is not None],
            key=lambda x: x[1]['pe_analysis']['current_pe'][0] 
            if isinstance(x[1]['pe_analysis']['current_pe'], list) 
            else x[1]['pe_analysis']['current_pe']
        )[:10]
        
        for i, (code, stock) in enumerate(sorted_stocks, 1):
            pe_analysis = stock.get('pe_analysis', {})
            current_pe = pe_analysis.get('current_pe')
            pe_value = current_pe[0] if isinstance(current_pe, list) else current_pe
            print(f"  {i:2d}. {stock['stock_name']}({code}): PE = {pe_value:.2f}")

def main():
    """主函数"""
    
    print("开始分析good股票的PE值并更新到原文件...")
    
    # 设置日志
    setup_logging()
    
    # 分析股票PE并更新文件
    updated_count = update_stocks_with_pe()
    
    if updated_count > 0:
        # 重新加载更新后的文件生成报告
        good_stocks = load_good_stocks()
        if good_stocks:
            generate_summary_report(good_stocks)
        
        print(f"\n分析完成！成功更新了 {updated_count} 只股票的PE数据。")
        print("PE数据已直接添加到good_stocks.json文件中。")
    else:
        print("没有成功更新任何股票的PE数据")

if __name__ == "__main__":
    main()