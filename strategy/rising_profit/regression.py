#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筛选3年净利润增长率高于20%的股票
挑选其中市值最低的5个股票
"""

import json
import math
import pandas as pd
import numpy as np
import sys
from datetime import datetime
import akshare as ak

sys.path.append("../..")
from financial_data import FinancialData
from stock_price_cache import StockPriceCache

finan_data = FinancialData()
stock_price = StockPriceCache()

class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理pandas和numpy数据类型"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            obj = round(obj, 2)
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):  # 处理NaN值
            return None
        elif isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d')
        # 让基类处理其他类型
        return super().default(obj)

import matplotlib.pyplot as plt

def plot_scatter(x_data, y_data, title="散点图", xlabel="X轴", ylabel="Y轴"):
    """
    绘制散点图
    
    参数:
    x_data: 横坐标数据列表
    y_data: 纵坐标数据列表
    title: 图表标题
    xlabel: X轴标签
    ylabel: Y轴标签
    """
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 创建图形
    plt.figure(figsize=(8, 6))
    
    # 绘制散点图
    plt.scatter(x_data, y_data, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    
    # 设置图表属性
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    
    # 添加趋势线（可选）
    # z = np.polyfit(x_data, y_data, 1)
    # p = np.poly1d(z)
    # plt.plot(x_data, p(x_data), "r--", alpha=0.8, linewidth=2)
    
    # 调整布局
    plt.tight_layout()
    
    # 显示图表
    plt.show()

class StockAnalyzer:
    """股票分析器"""
    
    def __init__(self):
        self.criteria = {
            'profit_threshold': 0.2,  # 净利润增长率
            'good_years': 3,    # 最少增长年份数
        }

    def save_results(self, stock_data, file_path='../../stock_info.json'):
        """保存分析结果"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(stock_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            print(f"分析结果已保存到: {file_path}")
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    def load_stock_data(self, file_path='../../stock_info.json'):
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
            return None, None

        history_price = stock_info.get('history_price_hfq')
        price = history_price.get(str(YEAR))
        next_price = history_price.get(str(YEAR + 1))
        if price is None or next_price is None:
            return None, None
        profit = (next_price - price) / price * 100

        if YEAR >= this_year - 1:
            return profit, None

        next_next_price = history_price.get(str(YEAR + 2))
        if next_next_price is None:
            return profit, None

        profit2 = math.sqrt(next_next_price / price) - 1
        profit2 = profit2 * 100
        return profit, profit2

    def find_good_stocks(self, CURRENT_YEAR:int, stock_code):
        '''
        条件：净利润增长率连续3年大于20%
        '''
        df = finan_data.get_indicator_data(stock_code, "归属母公司净利润增长率")
        zzl = finan_data.get_indicator_recent_year(df, self.criteria['good_years'], CURRENT_YEAR)

        count = 0
        for year, pct in zzl:
            if year[4:6] == '12':
                if pct < 20:
                    return False
                count += 1

        if count != 3:
            return False
        '''
        for year, pct in zzl:
            if year[4:6] == '12':
          
                print(year, " ", float(pct))
        '''

        return True

    def analyze_all_stocks(self, year:int):
        """分析某年所有股票"""
        stock_data = self.load_stock_data()
        
        if not stock_data:
            print("没有找到股票数据")
            return {}
        
        analysis_results = {}
        
        count = 0
        print("净利润增长率连续3年 > 20%")
        print("选择市值最小的5个\n")
        for stock_code, stock_info in stock_data.items():
            stock_name = stock_info.get('stock_name', '')
            #if stock_code != "002015":
                #continue
            #print(f"分析股票: {stock_code} {stock_name}")
            
            if self.find_good_stocks(year, stock_code):
                print(f"分析股票: {stock_code} {stock_name}")
                date = str(year) + "-01-31"
                market_value = stock_data[stock_code].get('market_value')
                mv = market_value.get(date)
                if mv is None:
                    df = ak.stock_zh_valuation_baidu(symbol=stock_code, indicator="总市值", period="全部")
                    mv = stock_price.get_specify_date_price(df, date, head = 'value')
                    if mv is not None:
                        market_value[date] = mv
                        self.save_results(stock_data)

                print(f"{date} 市值 {mv}")
                p, p2 = self.cal_profit(year, stock_info)
                count = count + 1
                #if p < 0:
                #    continue
                
                
                if p2 is not None and p is not None:
                    print(f"{stock_code}: {stock_name}自{year}年起一年增长率{p:.2f},两年复合增长率{p2:.2f}")
                elif p is not None:
                    print(f"{stock_code}: {stock_name}自{year}年起一年增长率{p:.2f}")
            
                analysis_results[stock_code] = {
                    'stock_name': stock_name,
                    'profit': p,
                    'profit2': p2,
                    'market_value': mv
                }

                #if count == 6:
                #    break
        
        return analysis_results
    
    def get_promising_stocks(self, min_score=70):
        """获取有潜力的股票"""
        for year in range(2023, 2025):
            analysis_results = self.analyze_all_stocks(year)
            if len(analysis_results) == 0:
                continue

            profit_values = []
            market_values = []
            for info in analysis_results.values():
                profit = info['profit']
                if profit is None:
                    continue
                market_value = info['market_value']
                profit_values.append(profit)
                market_values.append(market_value)


            print(f"{profit_values}")
            profit_ava = sum(profit_values) / len(profit_values)
            profit2_values = [info['profit2'] for info in analysis_results.values() if 'profit2' in info and info['profit2'] is not None]
            #print(f"{profit_values}")
            if len(profit2_values) == 0 or profit2_values[0] is None:
                print(f"{year} 平均增长率{profit_ava:.2f}")
            else:
                profit2_ava = sum(profit2_values) / len(profit2_values)
                print(f"{year} 平均增长率{profit_ava:.2f},平均两年复合增长率{profit2_ava:.2f}")

            sz_index_file = "../../stock_price/sz000001_index_daily.parquet"
            sz_index_df = pd.read_parquet(sz_index_file)
            sz_index_df.set_index('date', inplace=True)

            start_date = str(year) + "0107"
            end_date = str(year) + "1231"

            start_price = stock_price.get_specify_date_price(sz_index_df, start_date)
            end_price = stock_price.get_specify_date_price(sz_index_df, end_date)

            index_pct = (end_price / start_price - 1 ) * 100
            print(f"{year} 大盘增长{index_pct:.2f}")
            # 筛选有潜力的股票


            plot_scatter(market_values, profit_values)
            exit()
        
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
