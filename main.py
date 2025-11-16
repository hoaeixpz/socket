#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遍历good_stocks.json中的所有股票
"""

import json
import time
import logging
import akshare as ak
import datetime
from financial_data import FinancialData
from pe_ratio_collector import PERatioCollector
from stock_data_collector_demo import StockDataCollector
from stock_data_collector_demo import CustomJSONEncoder

# 创建全局实例
stock_data = FinancialData()
pe_collect = PERatioCollector()
stock_collect = StockDataCollector()

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('main.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def load_good_stocks():
    """加载analysis_results.json文件"""
    try:
        with open('analysis_results.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("错误：找不到analysis_results.json文件")
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
    """加载现有的analysis_results.json文件，返回所有股票代码列表"""
    try:
        with open('analysis_results.json', 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        return list(stocks.keys()), stocks
    except FileNotFoundError:
        print("错误：找不到analysis_results.json文件")
        return [], {}
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式错误 - {e}")
        return [], {}

def update_single_stock(stock_code):
    """分析单只股票数据并立即更新到文件"""
    #stock_name = stock_info.get('stock_name', '未知')
    
    # 添加市场前缀
    full_stock_code = add_stock_prefix(stock_code)
    
    try:
        '''
        print("示例1：获取ROE")
        roe = stock_data.get_indicator_value(stock_code, "净资产收益率(ROE)", "20250930")
        #roe = stock_data.get_indicator_data(stock_code, "净资产收益率(ROE)")
        #print(f"结果: {roe}\n")
        data = ("20250930", roe)
        if roe is not None:
            return data, True
        '''
        years = ['20201231', '20211231', '20221231', '20231231', '20241231', '20250930']
        hist_price = {}
        for year in years:
            price = pe_collect._get_price(full_stock_code, year)
            time.sleep(0.3)
            if price is not None:
                hist_price[year[0:4]] = price

        #print(hist_price)
        return hist_price, True
            
    except Exception as e:
        print(f" analysis {stock_name} error: {e}")
        return None, False

def save_single_stock_update(stock_code, analysis_data):
    """保存单只股票的更新到文件"""
    try:
        # 读取整个文件
        with open('analysis_results.json', 'r', encoding='utf-8') as f:
            all_stocks = json.load(f)
        
        # 更新当前股票的数据
        if stock_code in all_stocks:
            all_stocks[stock_code]['history_price'] = {}
            for year, price in analysis_data.items():
                #print(f"price {year}, {price}")
                if '2025' in year:
                    all_stocks[stock_code]['current_price'] = ('20250930' ,price)
                    continue
                all_stocks[stock_code]['history_price'][year] = price
        
        # 保存回文件
        with open('analysis_results.json', 'w', encoding='utf-8') as f:
            json.dump(all_stocks, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存股票 {stock_code} 数据失败: {e}")
        return False

def update_single_stock2(stock_code, stock_info):
    """分析单只股票数据并立即更新到文件"""
    
    # 添加市场前缀
    full_stock_code = add_stock_prefix(stock_code)
    try:
        # 获取后复权历史股价
        now = datetime.datetime.now()
        history_price_hfq = stock_info['history_price_hfq']
        history_price_bfq = stock_info['history_price_bfq']
        pe_ana = stock_info['pe_analysis']['historical_pe']
        if len(history_price_bfq.values()) == 0:
            return

        for year in range(now.year - 15, now.year):
            year = str(year)
            value = history_price_bfq.get(year)
            #print(year, value)
            if value is not None:
                continue

            date = year + "1231"
            history_price_bfq[year] = stock_collect.get_price(full_stock_code, date)
            if history_price_bfq[year] is None:
                for month in range(11, 0, -1):
                    ms = str(month)
                    if month < 10:
                        ms = "0" + str(month)
                    date = year + ms + "30"
                    if month == 2:
                        date = year + ms + "28"
                    price = stock_collect.get_price(full_stock_code, date)
                    history_price_bfq[year] = price
                    if price is not None:
                        #print(year, price)
                        history_price_hfq[year] = stock_collect.get_price(full_stock_code, date, adjust = "hfq")
                        hist_eps = stock_collect.get_history_eps(stock_code, 15)
                        for dat, eps in hist_eps:
                            if dat[0:4] == year and dat[4:6] == "12":
                                pe_ratio = price / eps
                                pe_ana[dat] = pe_ratio
                        break

        stock_info['history_price_bfq'] = history_price_bfq
        stock_info['history_price_hfq'] = history_price_hfq
        stock_info['pe_analysis']['historical_pe'] = pe_ana

    except Exception as e:
        print(f" analysis {stock_code} error: {e}")
        return None, False

def save_single_stock(stock_code, stock_info):
    """保存分析结果"""
    try:
        with open('analysis_results.json', 'r', encoding='utf-8') as f:
            all_stocks = json.load(f)

        all_stocks[stock_code] = stock_info

        with open('analysis_results.json', 'w', encoding='utf-8') as f:
            json.dump(all_stocks, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        print(f"分析结果已保存到: analysis_results.json")
    except Exception as e:
        print(f"保存结果失败: {e}")


def update_stocks():
    """分析所有good股票的PE值，每分析完一只股票就立即更新文件"""
    
    # 加载现有股票数据
    stock_codes, all_stocks = load_existing_good_stocks()
    
    if not stock_codes:
        print("没有找到good状态的股票数据")
        return 0
    
    print(f"find {len(stock_codes)} good stocks")
    
    # 记录更新数量
    updated_count = 0
    successful_count = 0
    
    # 遍历所有股票
    for i, stock_code in enumerate(stock_codes, 1):
        stock_info = all_stocks[stock_code]
        stock_name = stock_info.get('stock_name', '未知')
        
        if stock_info.get("current_price") is not None:
            continue
        print(f"\n{'='*60}")
        print(f"analysis the {i}/{len(stock_codes)} stock: {stock_name}({stock_code})")
        print(f"{'='*60}")

        
        # 分析单只股票的PE值
        analysis_data, success = update_single_stock(stock_code)
        
        # 立即保存到文件
        if save_single_stock_update(stock_code, analysis_data):
            updated_count += 1
            if success:
                successful_count += 1
            print(f"已更新 {stock_name} 的ROE数据到文件")
        else:
            print(f"更新 {stock_name} 数据到文件失败")
        
        # 清除当前股票数据以节省内存
        del all_stocks[stock_code]
        
        # 添加延时，避免请求过于频繁
        if i < len(stock_codes):  # 最后一只股票不需要延时
            wait_time = 6 
            print(f"wait {wait_time} s...")
            time.sleep(wait_time)
    
    print(f"\n分析完成！成功更新了 {updated_count} 只股票的数据，其中 {successful_count} 只成功获取ROE数据")
    return successful_count

def generate_summary_report(good_stocks):
    """生成分析报告摘要"""
    
    print("\n" + "="*80)
    print("ROE报告摘要")
    print("="*80)
    
    total_stocks = len(good_stocks)
    successful_stocks = sum(1 for stock in good_stocks.values() 
                           if stock.get('history_price') is not None)
    failed_stocks = total_stocks - successful_stocks
    
    print(f"总股票数: {total_stocks}")
    print(f"成功获取PE数据的股票数: {successful_stocks}")
    print(f"获取失败的股票数: {failed_stocks}")
    print(f"成功率: {successful_stocks/total_stocks*100:.1f}%")

def main():
    """主函数"""
    
    print("开始分析good股票的PE值并更新到原文件...")
    
    # 设置日志
    #setup_logging()
    
    # 分析股票PE并更新文件
    updated_count = update_stocks()
    
    if updated_count > 0:
        # 重新加载更新后的文件生成报告
        good_stocks = load_good_stocks()
        generate_summary_report(good_stocks)
        
def test_demo():
    '''
    test function update_single_stock
    '''

    #stock_data.get_indicator_list("000001", True)
    #update_single_stock("000001")
    #return
    stock_codes, all_stocks = load_existing_good_stocks()
    
    if not stock_codes:
        print("没有找到good状态的股票数据")
        return 0
    
    print(f"find {len(stock_codes)} good stocks")
    
    # 遍历所有股票
    count = 0
    start_t = time.time()
    for i, stock_code in enumerate(stock_codes, 1):
        stock_info = all_stocks[stock_code]
        stock_name = stock_info.get('stock_name', '未知')

        Y = len(stock_info['history_price_bfq'].values())
        if Y == 0:
            continue
        years = sorted(stock_info['history_price_bfq'].keys())
        if int(years[-1]) - int(years[0]) + 1 == Y:
            continue

        if Y == len(stock_info['history_price_hfq'].values()):
            continue

        '''
        flag = False
        for value in stock_info['history_price_hfq'].values():
            if value is None:
                flag = True

        if flag is False:
            continue
        '''
        
        print(f"\n{'='*60}")
        print(f"analysis the {i}/{len(stock_codes)} stock: {stock_name}({stock_code})")
        print(f"{'='*60}")
        count = count + 1
        if count == 10:
            break
        
        #analysis_data, success = update_single_stock(stock_code)
        #print(f"analysis {analysis_data} {success}")
        #all_stocks[stock_code]['roe_details']['current'] = analysis_data
        #stock_info = all_stocks[stock_code]
        #print(f"info {stock_info}")

        update_single_stock2(stock_code, stock_info)
        #print(f"{stock_info}")
        
        # 立即保存到文件
        save_single_stock(stock_code, stock_info)

        end_t = time.time()
        cpu = end_t - start_t
        print(cpu)
        start_t = end_t
        if cpu < 5:
            print("sleep 3s")
            time.sleep(3)

            #updated_count += 1
            #if success:
    print(count)
if __name__ == "__main__":
    #main()
    test_demo()
