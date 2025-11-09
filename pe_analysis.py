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

def load_existing_good_stocks():
    """加载现有的good_stocks.json文件，返回所有股票代码列表"""
    try:
        with open('good_stocks.json', 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        return list(stocks.keys()), stocks
    except FileNotFoundError:
        print("错误：找不到good_stocks.json文件")
        return [], {}
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式错误 - {e}")
        return [], {}

def update_single_stock_pe(stock_code, stock_info, pe_collector):
    """分析单只股票的PE值并立即更新到文件"""
    stock_name = stock_info.get('stock_name', '未知')
    
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
            
            # 创建PE分析数据
            pe_analysis_data = {
                'current_pe': current_pe,
                'historical_pe': historical_pe,
                'historical_peg': historical_peg,
                'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'error': None
            }
            
            print(f" SUCCESS {stock_name} PE data")
            print(f" current PE: {current_pe}")
            print(f" hist PE: {historical_pe}")
            print(f" hist PEG: {historical_peg}")
            
            return pe_analysis_data, True
            
        else:
            print(f" FAIL {stock_name} PE data")
            pe_analysis_data = {
                'current_pe': None,
                'historical_pe': {},
                'historical_peg': {},
                'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'error': '获取PE数据失败'
            }
            return pe_analysis_data, False
            
    except Exception as e:
        print(f" analysis {stock_name} error: {e}")
        pe_analysis_data = {
            'current_pe': None,
            'historical_pe': {},
            'historical_peg': {},
            'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'error': str(e)
        }
        return pe_analysis_data, False

def save_single_stock_update(stock_code, stock_info, pe_analysis_data):
    """保存单只股票的更新到文件"""
    try:
        # 读取整个文件
        with open('good_stocks.json', 'r', encoding='utf-8') as f:
            all_stocks = json.load(f)
        
        # 更新当前股票的数据
        if stock_code in all_stocks:
            all_stocks[stock_code]['pe_analysis'] = pe_analysis_data
        
        # 保存回文件
        with open('good_stocks.json', 'w', encoding='utf-8') as f:
            json.dump(all_stocks, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存股票 {stock_code} 数据失败: {e}")
        return False

def update_stocks_with_pe():
    """分析所有good股票的PE值，每分析完一只股票就立即更新文件"""
    
    # 加载现有股票数据
    stock_codes, all_stocks = load_existing_good_stocks()
    
    if not stock_codes:
        print("没有找到good状态的股票数据")
        return 0
    
    print(f"find {len(stock_codes)} good stocks")
    
    # 创建PE收集器
    pe_collector = PERatioCollector(max_retries=3, retry_delay=2)
    
    # 记录更新数量
    updated_count = 0
    successful_count = 0
    
    # 遍历所有股票
    for i, stock_code in enumerate(stock_codes, 1):
        stock_info = all_stocks[stock_code]
        stock_name = stock_info.get('stock_name', '未知')
        
        print(f"\n{'='*60}")
        print(f"analysis the {i}/{len(stock_codes)} stock: {stock_name}({stock_code})")
        print(f"{'='*60}")
        
        # 分析单只股票的PE值
        pe_analysis_data, success = update_single_stock_pe(stock_code, stock_info, pe_collector)
        
        # 立即保存到文件
        if save_single_stock_update(stock_code, stock_info, pe_analysis_data):
            updated_count += 1
            if success:
                successful_count += 1
            print(f"已更新 {stock_name} 的PE数据到文件")
        else:
            print(f"更新 {stock_name} 数据到文件失败")
        
        # 清除当前股票数据以节省内存
        del all_stocks[stock_code]
        
        # 添加延时，避免请求过于频繁
        if i < len(stock_codes):  # 最后一只股票不需要延时
            wait_time = 3
            print(f"wait {wait_time} s...")
            time.sleep(wait_time)
    
    print(f"\n分析完成！成功更新了 {updated_count} 只股票的数据，其中 {successful_count} 只成功获取PE数据")
    return successful_count

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