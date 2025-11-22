#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析有潜力的股票
基于ROE和PE指标进行综合评估
"""

import json
import math
import pandas as pd
import numpy as np
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
    
    def load_stock_data(self, file_path='analysis_results.json'):
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
        this_year = int(datetime.now().year)
        if YEAR >= this_year:
            return 0, 0

        history_price = stock_info.get('history_price_hfq')
        price = history_price[str(YEAR)]
        next_price = history_price[str(YEAR + 1)]
        if price is None or next_price is None:
            return 0, 0
        profit = (next_price - price) / price * 100

        if YEAR >= this_year - 1:
            return profit, None

        next_next_price = history_price[str(YEAR + 2)]
        profit2 = math.sqrt(next_next_price / price) - 1
        profit2 = profit2 * 100
        return profit, profit2

    def cal_pe(self, YEAR, pe_data):
        '''
        计算YEAR年份的PE在历史PE中排名第几，
        给出排名百分位
        '''

        historical_pe = pe_data.get('historical_pe', {})
        if len(historical_pe) < 2:
            return 100

        this_pe = historical_pe.get(str(YEAR))
        if this_pe is None:
            return 100

        if this_pe < 0:
            return 100

        valid_pe_num = 0
        rank = 1
        for year, pe in historical_pe.items():
            if int(year) > YEAR:
                break
            #print(f"{year}: {pe}")
            if pe > 0:
                valid_pe_num = valid_pe_num + 1
                if pe < this_pe:
                    rank = rank + 1

        #print(rank, valid_pe_num)
        if rank == 1 and valid_pe_num > 3:
            return 1
        return rank * 100.0 / valid_pe_num

    def cal_roe(sel, YEAR, stock_info):
        '''
        扣非ROE连续5年上涨，且有3年 > 5
        '''
        roe_values = stock_info.get('roe_details').get('history_roe')
        this_year = int(datetime.now().year)
        count = 0
        last_roe = None
        if YEAR < this_year:
            for i in range(5):
                roe = roe_values.get(str(YEAR-i))
                if roe is None or len(roe) == 0:
                    continue
                kf_roe = roe[1]
                #print(kf_roe)
                if last_roe is not None:
                    if last_roe < kf_roe:
                        return False
                last_roe = kf_roe
                if kf_roe is not None and kf_roe > 5:
                    #print("count + 1")
                    count += 1

            if count < 3:
                return False
        return True

    def roe_distrub(sel, YEAR, stock_info):
        roe_values = stock_info.get('roe_details').get('history_roe')
        this_year = int(datetime.now().year)
        roe_list = []
        if YEAR < this_year:
            for i in range(5):
                roe = roe_values.get(str(YEAR-i))
                if roe is None or len(roe) == 0:
                    continue
                kf_roe = roe[1]
                if math.isnan(kf_roe):
                    continue

                roe_list.append(kf_roe)
                #print(f"ROE {type(kf_roe)}{kf_roe}")

        if len(roe_list) < 3:
            return False, []

        mean = np.mean(roe_list)
        std = np.std(roe_list)
        #print(f"mean std {mean} {std}")

        if mean < 10:
            return False, roe_list

        if std > 2:
            return False, roe_list

        return True, roe_list

    def find_good_stocks(self, YEAR:int, stock_info):
        '''
        条件：连续3年至YEAR，3年内股价上涨，PE下跌的公司
              连续5年至YEAR，存在3年ROE > 5
        '''

        pe_data= stock_info.get('pe_analysis', {})
        current_pe_list = pe_data.get('current_pe', [])
        historical_pe = pe_data.get('historical_pe', {})

        r = self.cal_pe(YEAR, pe_data)
        if r > 30:
            return False

        roe_values = stock_info.get('roe_details').get('history_roe')
        success, roelist = self.roe_distrub(YEAR, stock_info)
        if success:
            print(roelist)
            print(np.mean(roelist))
            print(np.std(roelist))
        return success
        #return self.cal_roe(YEAR, stock_info)
        this_year = int(datetime.now().year)
        

        if len(historical_pe) < 2:
            return False

        if len(current_pe_list) == 0:
            return False
            
        years = sorted([int(year) for year in historical_pe.keys() if year.isdigit()])
        #print(f"years {years}")
        if int(str(years[0])[0:4]) > int(YEAR) - 2:
            return False
        pe_values = [historical_pe[str(year)] for year in years if historical_pe[str(year)]]
        
        current_price = stock_info.get('current_price')
        if current_price is None:
            return False
        current_price = current_price[1]
        history_price = stock_info.get('history_price_hfq')
        price_values = [history_price[str(year)[0:4]] for year in years if history_price[str(year)[0:4]]]
        #print(f"price_values {price_values}")
        if len(price_values) != len(years):
            return False

        
        for i, year in enumerate(years):
            if str(year)[0:4] == str(YEAR):
                if pe_values[i] > 30:
                    return False
                    
                if int(YEAR) < this_year:
                    trend = pe_values[i] > 0 and pe_values[i-2] > pe_values[i-1] and pe_values[i-1] > pe_values[i]
                    if not trend:
                        return False
                    if price_values[i-2] > price_values[i-1] and price_values[i-1] < price_values[i]:
                        #print(f"{YEAR - 4} roe: {roe_values[str(YEAR-4)]}, {roe_values[str(YEAR-3)]}, {roe_values[str(YEAR-2)]}, {roe_values[str(YEAR-1)]}, {roe_values[str(YEAR)]}")
                        #print(f"{YEAR - 2} pe {pe_values[i-2]:.2f} {pe_values[i-1]:.2f} {pe_values[i]:.2f}")
                        #print(f"{YEAR - 2} price {price_values[i-2]} {price_values[i-1]} {price_values[i]}")
                        return True
                    else:
                        return False
                elif int(YEAR) == this_year:
                    pe = min(current_pe_list)
                    trend = pe > 0 and pe_values[i-2] > pe_values[i-1] and pe_values[i-1] > pe
                    if not trend:
                        return False
                    if current_price > price_values[i-1] and price_values[i-1] < price_values[i-2]:
                        #print(f"{YEAR - 4} roe: {roe_values[str(YEAR-4)]}, {roe_values[str(YEAR-3)]}, {roe_values[str(YEAR-2)]}, {roe_values[str(YEAR-1)]}, {roe_values[str(YEAR)]}")
                        #print(f"{YEAR - 2} pe {pe_values[i-2]:.2f} {pe_values[i-1]:.2f} {pe:.2f}")
                        #print(f"{YEAR - 2} price {price_values[i-2]} {price_values[i-1]} {current_price}")
                        return True
                    else:
                        return False


    def analyze_all_stocks(self, year:int):
        """分析某年所有股票"""
        stock_data = self.load_stock_data()
        plottor = simple_stock_plotter.SimpleStockPlotter()
        
        if not stock_data:
            print("没有找到股票数据")
            return {}
        
        analysis_results = {}
        
        count = 0
        print("pe处于历史pe中前30%")
        print("扣非ROE连续5年上涨")
        print("扣非ROE连续5年中有3年>5\n")
        for stock_code, stock_info in stock_data.items():
            stock_name = stock_info.get('stock_name', '')
            #if stock_code != "002015":
                #continue
            #print(f"分析股票: {stock_code} {stock_name}")
            
            if self.find_good_stocks(year, stock_info):
                #print(f"{stock_code}: {stock_name} 符合标准")
                p, p2 = self.cal_profit(year, stock_info)
                count = count + 1
                #if p < 0:
                #    continue
                
                
                if p2 is not None:
                    print(f"{stock_code}: {stock_name}自{year}年起一年增长率{p:.2f},两年复合增长率{p2:.2f}")
                else:
                    print(f"{stock_code}: {stock_name}自{year}年起一年增长率{p:.2f}")
                
                #if count == 6:
                #    break
            
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
        for year in range(2014, 2024):
            if year != 2017:
                continue
            analysis_results = self.analyze_all_stocks(year)
            if len(analysis_results) == 0:
                continue

            profit_values = [info['profit'] for info in analysis_results.values() if 'profit' in info]
            print(f"{profit_values}")
            profit_ava = sum(profit_values) / len(profit_values)
            profit2_values = [info['profit2'] for info in analysis_results.values() if 'profit2' in info]
            #print(f"{profit_values}")
            if len(profit2_values) == 0 or profit2_values[0] is None:
                print(f"{year} 平均增长率{profit_ava:.2f}")
            else:
                profit2_ava = sum(profit2_values) / len(profit2_values)
                print(f"{year} 平均增长率{profit_ava:.2f},平均两年复合增长率{profit2_ava:.2f}")
        
            # 筛选有潜力的股票
        
        
        return None
    
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
