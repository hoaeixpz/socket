#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析有潜力的股票
基于ROE和PE指标进行综合评估
"""

import json
import math
import pandas as pd
from datetime import datetime
import simple_stock_plotter
from simple_stock_plotter import SimpleStockPlotter

class StockAnalyzer:
    """股票分析器"""
    
    def __init__(self):
        self.analysis_criteria = {
            'roe_threshold': 10.0,  # ROE阈值
            'pe_threshold': 20.0,   # PE阈值
            'min_good_years': 3,    # 最少良好年份数
            'max_bad_years': 1      # 最多不良年份数
        }
    
    def load_stock_data(self, file_path='good_stocks.json'):
        """加载股票数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载数据失败: {e}")
            return {}
    
    def cal_profit(self, YEAR, stock_info):
        '''
        计算自YEAR年起的一年收益率，以及两年复合收益率
        '''
        history_price = stock_info.get('history_price')
        next_price = 0
        price = history_price[str(YEAR)]
        if YEAR < 2024:
            next_price = history_price[str(YEAR + 1)]
        else:
            next_price = stock_info.get('current_price')[1]
        profit = (next_price - price) / price * 100

        next_next_price = 0
        if YEAR < 2023:
            next_next_price = history_price[str(YEAR + 2)]
        elif YEAR == 2023:
            next_next_price = stock_info.get('current_price')[1]
        else:
            return profit, None
        
        profit2 = math.sqrt(next_next_price / price) - 1
        profit2 = profit2 * 100
        return profit, profit2

    def find_good_stocks(self, YEAR, stock_info):
        '''
        找到从YEAR年起，3年内股价上涨，PE下跌的公司
        '''

        pe_data= stock_info.get('pe_analysis', {})
        current_pe_list = pe_data.get('current_pe', [])
        historical_pe = pe_data.get('historical_pe', {})

        if len(historical_pe) < 2:
            return False

        if len(current_pe_list) == 0:
            return False
            
        years = sorted([int(year) for year in historical_pe.keys() if year.isdigit()])
        #print(f"years {years}")
        if int(str(years[0])[0:4]) > int(YEAR):
            return False
        pe_values = [historical_pe[str(year)] for year in years if historical_pe[str(year)]]
        #print(f"pe_values {pe_values}")

        current_price = stock_info.get('current_price')
        history_price = stock_info.get('history_price')
        price_values = [history_price[str(year)[0:4]] for year in years if history_price[str(year)[0:4]]]
        #print(f"price_values {price_values}")

        stock_code = stock_info.get('stock_code', '')
        for i, year in enumerate(years):
            if str(year)[0:4] == str(YEAR):
                if pe_values[i] > 30:
                    return False
                    
                if int(YEAR) < 2023:
                    trend = pe_values[i+2] > 0 and pe_values[i] > pe_values[i+1] and pe_values[i+1] > pe_values[i+2]
                    if not trend:
                        return False
                    return price_values[i+2] > price_values[i+1] and price_values[i+1] > price_values[i]
                elif int(YEAR) == 2023:
                    pe = min(current_pe_list)
                    trend = pe > 0 and pe_values[i] > pe_values[i+1] and pe_values[i+1] > pe
                    if not trend:
                        return False
                    return current_price > price_values[i+1] and price_values[i+1] > price_values[i]

    def analyze_all_stocks(self):
        """分析所有股票"""
        stock_data = self.load_stock_data()
        plottor = simple_stock_plotter.SimpleStockPlotter()
        
        if not stock_data:
            print("没有找到股票数据")
            return {}
        
        analysis_results = {}
        
        year = 2020
        for stock_code, stock_info in stock_data.items():
            stock_name = stock_info.get('stock_name', '')
            #print(f"分析股票: {stock_code} {stock_name}")
            
            if self.find_good_stocks(year, stock_info):
                #print(f"{stock_code}: {stock_name} 符合标准")
                p, p2 = self.cal_profit(year + 2, stock_info)
                if p2 is not None:
                    print(f"{stock_code}: {stock_name}自{year + 2}年起一年增长率{p:.2f},两年复合增长率{p2:.2f}")
                else:
                    print(f"{stock_code}: {stock_name}自{year + 2}年起一年增长率{p:.2f}")
                    #plottor.plot_three_indicators(stock_info, stock_code)
            
            # 计算潜力分数
            #potential_score = self.calculate_potential_score(stock_info)
            
                analysis_results[stock_code] = {
                    'stock_name': stock_name,
                    'profit': p,
                    'profit2': p2
                }
        
        return analysis_results
    
    def get_promising_stocks(self, min_score=70):
        """获取有潜力的股票"""
        analysis_results = self.analyze_all_stocks()
        
        # 按潜力分数排序
        sorted_stocks = sorted(
            analysis_results.items(),
            key=lambda x: x[1]['profit'],
            reverse=True
        )

        profit_values = [info['profit'] for info in analysis_results.values() if 'profit' in info]
        #print(f"{profit_values}")
        profit_ava = sum(profit_values) / len(profit_values)
        profit2_values = [info['profit2'] for info in analysis_results.values() if 'profit2' in info]
        #print(f"{profit_values}")
        if len(profit2_values) == 0 or profit2_values[0] is None:
            print(f"平均增长率{profit_ava:.2f}")
        else:
            profit2_ava = sum(profit2_values) / len(profit2_values)
            print(f"平均增长率{profit_ava:.2f},平均两年复合增长率{profit2_ava:.2f}")
        
        # 筛选有潜力的股票
        
        
        return sorted_stocks
    
    def generate_report(self, min_score=70):
        """生成分析报告"""
        promising_stocks = self.get_promising_stocks(min_score)
        return
        
        print("\n" + "="*80)
        print("有潜力的股票分析报告")
        print("="*80)
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"筛选标准: 潜力分数 ≥ {min_score}")
        print(f"发现 {len(promising_stocks)} 只有潜力的股票")
        print("="*80)
        
        if not promising_stocks:
            print("未找到符合标准的股票")
            return
        
        # 打印详细分析
        for i, (stock_code, stock_info) in enumerate(promising_stocks.items(), 1):
            print(f"\n{i}. {stock_code} {stock_info['stock_name']}")
            print(f"   潜力分数: {stock_info['potential_score']}/100")
            print(f"   平均ROE: {stock_info['avg_roe']:.1f}%")
            print(f"   ROE趋势: {stock_info['roe_trend']:+.1f}%")
            print(f"   PE状态: {stock_info['pe_status']} ({stock_info['pe_reason']})")
            print(f"   低ROE年份数: {stock_info['years_with_low_roe']}")
            print(f"   推荐理由: {', '.join(stock_info['reasons'])}")
        
        # 保存结果到文件
        output_file = f"rising_roe_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(promising_stocks, f, ensure_ascii=False, indent=2)
        
        print(f"\n分析结果已保存到: {output_file}")

def main():
    """主函数"""
    analyzer = StockAnalyzer()
    
    # 设置筛选分数阈值
    min_score = 70  # 可以调整这个阈值
    
    # 生成分析报告
    analyzer.generate_report(min_score)

if __name__ == "__main__":
    main()