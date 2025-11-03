#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务摘要数据收集器
使用 stock_financial_abstract 获取近五年的财务数据
"""

from dis import code_info
from operator import index
import akshare as ak
import pandas as pd
import time
import numpy as np
from datetime import datetime, timedelta
import logging
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']  # 支持中文显示
matplotlib.rcParams['axes.unicode_minus'] = False  # 正确显示负号

pd.set_option('display.precision', 2)

def smart_format(x):
    """
    智能格式化数字：自动识别金额单位（万、亿等）
    
    Args:
        x: 需要格式化的数字
        
    Returns:
        str: 格式化后的字符串，包含单位
    """
    if pd.isna(x) or not isinstance(x, (int, float, np.number)):
        return x
    
    # 处理零值
    if x == 0:
        return "0"
    
    abs_x = abs(x)
    sign = "-" if x < 0 else ""
    
    # 根据金额大小选择合适的单位
    if abs_x >= 1e8:  # 1亿以上
        value = abs_x / 1e8
        return f"{sign}{value:.2f}亿"
    elif abs_x >= 1e4:  # 1万以上
        value = abs_x / 1e4
        return f"{sign}{value:.2f}万"
    elif abs_x >= 1:  # 1以上
        return f"{sign}{abs_x:,.2f}"
    elif abs_x >= 0.01:  # 0.01以上
        return f"{sign}{abs_x:.2f}"
    elif abs_x >= 0.0001:  # 0.0001以上
        return f"{sign}{abs_x:.4f}"
    else:  # 极小数字
        return f"{sign}{abs_x:.6e}"

class FinancialAbstractCollector:
    """财务摘要数据收集器"""
    
    def __init__(self, max_retries=3, retry_delay=2):
        """初始化收集器"""
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
    
    def get_financial_abstract(self, stock_code, years=5):
        """
        获取近几年的财务摘要数据
        
        Args:
            stock_code (str): 股票代码，如 "600519"
            years (int): 获取最近几年的数据，默认5年
            
        Returns:
            pandas.DataFrame: 财务摘要数据
        """
        
        # 标准化股票代码（移除后缀）
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        self.logger.info(f"开始获取股票 {stock_code} 的财务摘要数据，近{years}年")
        
        for attempt in range(self.max_retries):
            try:
                # 使用akshare获取财务摘要数据
                df = ak.stock_financial_abstract(clean_code)
                
                if df is None or df.empty:
                    self.logger.warning(f"第{attempt+1}次尝试获取 {stock_code} 财务摘要数据为空")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        self.logger.error(f"获取 {stock_code} 财务摘要数据失败，所有重试次数已用完")
                        return pd.DataFrame()
                
                # 处理数据，筛选近几年的数据
                processed_df = self._process_financial_data(df, years)
                
                self.logger.info(f"成功获取 {stock_code} 的财务摘要数据，共 {len(processed_df)} 条记录")
                return processed_df
                
            except Exception as e:
                self.logger.error(f"第{attempt+1}次尝试获取 {stock_code} 财务摘要数据失败: {e}")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(f"获取 {stock_code} 财务摘要数据失败，所有重试次数已用完")
                    return pd.DataFrame()
    
    def _process_financial_data(self, df, years):
        """
        处理财务摘要数据，筛选近几年的数据
        
        Args:
            df (pandas.DataFrame): 原始财务摘要数据（行：财务指标，列：报告期）
            years (int): 筛选最近几年
            
        Returns:
            pandas.DataFrame: 处理后的数据
        """
        
        if df.empty:
            return df

        # print("print df---------------------------")
        # print(df.iloc[[0,2,11],:20].applymap(smart_format))

        # 获取当前年份
        current_year = datetime.now().year
        
        # 筛选近几年的数据
        processed_data = []
        index_list = {}
        
        # 遍历DataFrame的列（通常是日期）
        for column in df.columns:
            try:
                if column == '指标' :
                    for idx, value in df[column].items():
                        index_list[idx] = value
                    #print(index_list)

                # 尝试解析日期（假设列名是日期格式，如20240930）
                if isinstance(column, (int, str)) and len(str(column)) == 8:
                    date_str = str(column)
                    year = int(date_str[:4])
                    
                    # 筛选近几年的数据
                    if year >= current_year - years:
                        # 获取该日期的数据
                        period_data = df[column]
                        
                        # 转换为字典格式
                        data_dict = {
                            'report_date': date_str,
                            'year': str(year),
                            'quarter': self._get_quarter_from_date(date_str)
                        }
                        
                        # 添加财务指标（保留原始索引）
                        for idx, value in period_data.items():
                            if pd.notna(value):
                                data_dict[index_list[idx]] = value
                        
                        processed_data.append(data_dict)
                        
            except Exception as e:
                self.logger.warning(f"处理日期列 {column} 时出错: {e}")
                continue
        
        if processed_data:
            return pd.DataFrame(processed_data)
        else:
            self.logger.warning("未能找到近几年的财务数据")
            return pd.DataFrame()
    
    def get_financial_indicator_names(self, stock_code):
        """
        获取财务指标名称映射
        
        Args:
            stock_code (str): 股票代码
            
        Returns:
            dict: 财务指标编号到名称的映射
        """
        
        # 获取原始数据来查看指标名称
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        try:
            df = ak.stock_financial_abstract(clean_code)
            
            if df is None or df.empty:
                return {}
            
            # 获取索引名称（财务指标名称）
            indicator_names = {}
            for idx, name in enumerate(df.index):
                indicator_names[idx] = str(name)
            
            return indicator_names
            
        except Exception as e:
            self.logger.error(f"获取财务指标名称失败: {e}")
            return {}
    
    def _get_quarter_from_date(self, date_str):
        """从日期字符串获取季度信息"""
        try:
            month = int(date_str[4:6])
            if month <= 3:
                return 1
            elif month <= 6:
                return 2
            elif month <= 9:
                return 3
            else:
                return 4
        except:
            return 0
    
    def set_indictor(self, year, indicators, data, df):
        """设置财务指标，并对金额进行格式化"""
        if data.empty:
            print(f"{year}year data is empty")
            return

        def format_financial_value(value, is_ratio=False):
            """格式化财务数值：金额用单位格式化，比率用百分比"""
            if pd.isna(value) or value is None:
                return None
            
            if is_ratio:
                # 比率类指标：转换为百分比
                return f"{value:.2%}"
            else:
                # 金额类指标：使用智能格式化
                return smart_format(value)

        indicators[year] = {
            'revenue': format_financial_value(data.get('营业总收入', pd.Series()).mean() if '营业总收入' in df.columns else None),
            'net_profit': format_financial_value(data.get('净利润', pd.Series()).mean() if '净利润' in df.columns else None),
            'total_assets': format_financial_value(data.get('资产总计', pd.Series()).mean() if '资产总计' in df.columns else None),
            'liabilities': format_financial_value(data.get('资产负债率', pd.Series()).mean() if '资产负债率' in df.columns else None, is_ratio=True),
            'ros': format_financial_value(data.get('销售净利率', pd.Series()).mean() if '销售净利率' in df.columns else None, is_ratio=True),
            'total_atr': format_financial_value(data.get('总资产周转率', pd.Series()).mean() if '总资产周转率' in df.columns else None),
            'em': format_financial_value(data.get('权益乘数', pd.Series()).mean() if '权益乘数' in df.columns else None),
            'roe': format_financial_value(data.get('净资产收益率(ROE)', pd.Series()).mean() if '净资产收益率(ROE)' in df.columns else None, is_ratio=True),
            'eps': format_financial_value(data.get('基本每股收益', pd.Series()).mean() if '基本每股收益' in df.columns else None)
        }


    def get_key_financial_indicators(self, stock_code, years=5):
        """
        获取关键财务指标
        
        Args:
            stock_code (str): 股票代码
            years (int): 近几年的数据
            
        Returns:
            dict: 关键财务指标
        """
        
        df = self.get_financial_abstract(stock_code, years)
        
        if df.empty:
            print("关键指标为空")
            return {}

        # print("关键指标不为空")
        # print("-----------------------------------------------")
        # print(df)
        # print("-----------------------------------------------")
        
        # 提取关键财务指标
        indicators = {}
        
        # 按年份分组
        for year in sorted(df['year'].unique(), reverse=True):
            year_data = df[df['year'] == year]
            data = year_data[year_data['quarter'] == 4]
            # print("year data")
            # print(year_data)
            # print("--------------------------------------------------------------------------------------------------")
            # print("data")
            # print(data)
            # print("--------------------------------------------------------------------------------------------------")
            
            self.set_indictor(year, indicators, data, df)

            current_year = datetime.now().year
            if int(year) == current_year:
                for month in year_data['report_date']:
                    report_data = year_data[year_data['report_date'] == month]
                    self.set_indictor(month, indicators, report_data, df)
        
        return indicators
    
    def save_financial_data(self, stock_code, years=5, filename=None):
        """
        保存财务数据到文件
        
        Args:
            stock_code (str): 股票代码
            years (int): 近几年的数据
            filename (str): 文件名，如果为None则自动生成
            
        Returns:
            str: 保存的文件路径
        """
        
        df = self.get_financial_abstract(stock_code, years)
        
        if df.empty:
            self.logger.warning(f"没有数据可保存: {stock_code}")
            return None
        
        if filename is None:
            filename = f"{stock_code}_financial_abstract_{years}years.csv"
        
        try:
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"财务数据已保存到: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"保存财务数据失败: {e}")
            return None

def main():
    """主函数 - 演示如何使用"""
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建收集器
    collector = FinancialAbstractCollector()
    
    # 测试股票代码
    test_stocks = ['600519']
    
    for stock in test_stocks:
        print(f"\n=== 获取 {stock} 近5年财务摘要数据 ===")
        
        # 获取财务摘要数据
        df = collector.get_financial_abstract(stock, years=5)
        
        if not df.empty:
            print(f"成功获取 {len(df)} 条记录")
            print("数据列:", df.columns.tolist())
            
            # 显示前几行数据
            print("\n前5行数据:")
            print(df.head())
            
            # 获取关键财务指标
            indicators = collector.get_key_financial_indicators(stock, years=5)
            print(f"\n关键财务指标:")
            for year, data in indicators.items():
                if year == datetime.now().year:
                    continue

                revenue = data.get('revenue', 'N/A')
                net_profit = data.get('net_profit', 'N/A')
                roe = data.get('roe', 'N/A')
                ros = data.get('ros', 'N/A')
                total_atr = data.get('total_atr', 'N/A')
                em = data.get('em', 'N/A')
                total_assets = data.get('total_assets', 'N/A')
                liabilities = data.get('liabilities', 'N/A')
                eps = data.get('eps', 'N/A')
                
                if year is not None and data is not None:
                    print(f"  {year}:")
                    print(f"    营业收入: {revenue}")
                    print(f"    净利润: {net_profit}")
                    print(f"    总资产: {total_assets}")
                    print(f"    资产负债率: {liabilities}")
                    print(f"    净资产收益率(ROE): {roe}")
                    print(f"    销售净利率(ROS): {ros}")
                    print(f"    总资产周转率: {total_atr}")
                    print(f"    权益乘数: {em}")
                    print(f"    每股收益: {eps}")
            
            # 保存数据
            plot_simple_financial_charts(indicators)
            filename = collector.save_financial_data(stock, years=5)
            if filename:
                print(f"数据已保存到: {filename}")
        else:
            print("获取数据失败")
        
        print("-" * 50)

def plot_simple_financial_charts(indicators):
    """
    简单绘制财务指标图表
    
    Args:
        indicators (dict): 财务指标数据
    """
    #try:
    if True:
        # 提取年度数据（排除当前年的月度数据）
        annual_data = {}
        for year, data in indicators.items():
            print(year)
            if year != datetime.now().year:
                annual_data[year] = data
        
        if not annual_data:
            print("没有足够的年度数据绘制图表")
            return
        
        # 排序年份
        sorted_years = sorted(annual_data.keys())
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('财务指标趋势图', fontsize=16, fontweight='bold')
        
        # 1. 营业收入和净利润趋势图
        ax1 = axes[0, 0]
        revenue_values = [annual_data[year].get('revenue', 'N/A') for year in sorted_years]
        net_profit_values = [annual_data[year].get('net_profit', 'N/A') for year in sorted_years]
        
        # 提取数值部分用于绘图
        revenue_numeric = []
        net_profit_numeric = []
        
        for rev, profit in zip(revenue_values, net_profit_values):
            if rev != 'N/A' and isinstance(rev, str):
                # 提取数值部分（移除单位）
                if '亿' in rev:
                    revenue_numeric.append(float(rev.replace('亿', '')) * 1e8)
                elif '万' in rev:
                    revenue_numeric.append(float(rev.replace('万', '')) * 1e4)
                else:
                    revenue_numeric.append(float(rev.replace(',', '')))
            else:
                revenue_numeric.append(0)
                
            if profit != 'N/A' and isinstance(profit, str):
                if '亿' in profit:
                    net_profit_numeric.append(float(profit.replace('亿', '')) * 1e8)
                elif '万' in profit:
                    net_profit_numeric.append(float(profit.replace('万', '')) * 1e4)
                else:
                    net_profit_numeric.append(float(profit.replace(',', '')))
            else:
                net_profit_numeric.append(0)
        
        ax1.plot(sorted_years, revenue_numeric, 'o-', label='营业收入', linewidth=2, markersize=6)
        ax1.plot(sorted_years, net_profit_numeric, 's-', label='净利润', linewidth=2, markersize=6)
        ax1.set_title('营业收入和净利润趋势')
        ax1.set_xlabel('年份')
        ax1.set_ylabel('金额（元）')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 盈利能力指标
        ax2 = axes[0, 1]
        roe_values = [annual_data[year].get('roe', 'N/A') for year in sorted_years]
        
        roe_numeric = []
        for roe in roe_values:
            if roe != 'N/A' and isinstance(roe, str):
                roe_numeric.append(float(roe.replace('%', '')) / 100)
            else:
                roe_numeric.append(0)
        
        ax2.plot(sorted_years, roe_numeric, 'o-', label='净资产收益率(ROE)', linewidth=2, markersize=6)
        ax2.set_title('盈利能力指标')
        ax2.set_xlabel('年份')
        ax2.set_ylabel('百分比')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 资产负债率
        ax3 = axes[1, 0]
        liabilities_values = [annual_data[year].get('liabilities', 'N/A') for year in sorted_years]
        
        liabilities_numeric = []
        for liab in liabilities_values:
            if liab != 'N/A' and isinstance(liab, str):
                liabilities_numeric.append(float(liab.replace('%', '')) / 100)
            else:
                liabilities_numeric.append(0)
        
        ax3.plot(sorted_years, liabilities_numeric, alpha=0.7, label='资产负债率')
        ax3.set_title('资产负债率')
        ax3.set_xlabel('年份')
        ax3.set_ylabel('百分比')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. 每股收益
        ax4 = axes[1, 1]
        eps_values = [annual_data[year].get('eps', 'N/A') for year in sorted_years]
        
        eps_numeric = []
        for eps in eps_values:
            if eps != 'N/A' and isinstance(eps, str):
                if '亿' in eps:
                    eps_numeric.append(float(eps.replace('亿', '')) * 1e8)
                elif '万' in eps:
                    eps_numeric.append(float(eps.replace('万', '')) * 1e4)
                else:
                    eps_numeric.append(float(eps.replace(',', '')))
            else:
                eps_numeric.append(0)
        
        ax4.plot(sorted_years, eps_numeric, '^-', label='每股收益', linewidth=2, markersize=6)
        ax4.set_title('每股收益趋势')
        ax4.set_xlabel('年份')
        ax4.set_ylabel('金额（元）')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        print("图表绘制完成")
        
    #except Exception as e:
        #print(f"绘制图表失败: {e}")


if __name__ == "__main__":
    main()
