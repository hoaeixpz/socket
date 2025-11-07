#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市盈率数据收集器
获取股票的市盈率指标
"""

import akshare as ak
import pandas as pd
import time
from datetime import datetime
import logging
import financial_data
from financial_data import FinancialData

# 创建全局实例
stock_data = FinancialData()

class PERatioCollector:
    """市盈率数据收集器"""
    
    def __init__(self, max_retries=3, retry_delay=2):
        """初始化收集器"""
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
    
    def get_current_pe_ratio(self, stock_code):
        """
        获取当前市盈率
        
        Args:
            stock_code (str): 股票代码，如 "600519"
            
        Returns:
            float: 市盈率值，获取失败返回None
        """
        
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        self.logger.info(f"开始获取股票 {stock_code} 的市盈率数据")
        
        for attempt in range(self.max_retries):
            try:
                '''
                # 方法1：使用stock_a_pe接口获取市盈率
                pe_data = ak.stock_a_pe()
                
                if pe_data is not None and not pe_data.empty:
                    # 查找目标股票
                    stock_pe = pe_data[pe_data['代码'] == clean_code]
                    if not stock_pe.empty:
                        pe_ratio = stock_pe['市盈率-动态'].iloc[0]
                        if pd.notna(pe_ratio):
                            self.logger.info(f"成功获取 {stock_code} 市盈率: {pe_ratio}")
                            return float(pe_ratio)
                '''
                # 方法2：使用stock_a_lg_indicator接口获取估值指标
                '''
                indicator_data = ak.stock_a_indicator_lg(symbol=clean_code)
                if indicator_data is not None and not indicator_data.empty:
                    pe_ratio = indicator_data['pe_ttm'].iloc[0]
                    if pd.notna(pe_ratio):
                        self.logger.info(f"成功获取 {stock_code} TTM市盈率: {pe_ratio}")
                        return float(pe_ratio)
                '''
                
                # 方法3：手动计算市盈率
                return self._calculate_pe_ratio_manually(stock_code)
                
            except Exception as e:
                self.logger.error(f"第{attempt+1}次尝试获取 {stock_code} 市盈率失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(f"获取 {stock_code} 市盈率失败，所有重试次数已用完")
                    return None
    
    def _calculate_pe_ratio_manually(self, stock_code):
        """
        手动计算市盈率：PE = 股价 / 每股收益
        
        Args:
            stock_code (str): 股票代码
            
        Returns:
            float: 市盈率值
        """
        
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        try:
            # 获取当前股价
            current_price = self._get_current_price(stock_code)
            if current_price is None:
                return None
            
            # 获取每股收益
            eps = self._get_eps(stock_code)
            if eps is None or eps <= 0:
                return None
            
            # 计算市盈率
            pe_ratio = current_price / eps
            self.logger.info(f"手动计算 {stock_code} 市盈率: {pe_ratio:.2f} (股价: {current_price}, EPS: {eps})")
            return pe_ratio
            
        except Exception as e:
            self.logger.error(f"手动计算市盈率失败: {e}")
            return None
    
    def _get_current_price(self, stock_code):
        """获取当前股价"""
        
        #clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        try:
            # 获取实时行情
            '''
            print("获取实时行情")
            realtime_data = ak.stock_zh_a_spot_em()
            print("获取实时行情结束")
            if realtime_data is not None and not realtime_data.empty:
                stock_data = realtime_data[realtime_data['代码'] == clean_code]
                if not stock_data.empty:
                    return float(stock_data['最新价'].iloc[0])
            '''
            
            # 获取历史数据的最新收盘价
            print("获取历史数据的最新收盘价")
            print(stock_code)
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            print("获取历史数据的最新收盘价结束")
            if hist_data is not None and not hist_data.empty:
                return float(hist_data['收盘'].iloc[-1])
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取股价失败: {e}")
            return None
    
    def _get_eps(self, stock_code):
        """获取每股收益"""
        
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        try:
            # 获取财务摘要数据
            return stock_data.get_indicator_value(stock_code, "基本每股收益", "20250930")
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取每股收益失败: {e}")
            return None
    
    def get_historical_pe_ratios(self, stock_code, years=5):
        """
        获取历史市盈率数据
        
        Args:
            stock_code (str): 股票代码
            years (int): 获取最近几年的数据
            
        Returns:
            dict: 年份到市盈率的映射
        """
        
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        try:
            # 获取历史市盈率数据
            pe_history = ak.stock_a_pe_lg(symbol=clean_code)
            
            if pe_history is None or pe_history.empty:
                return {}
            
            # 处理数据，筛选近几年的数据
            current_year = datetime.now().year
            historical_pe = {}
            
            for _, row in pe_history.iterrows():
                date_str = row['trade_date']
                year = int(date_str[:4])
                
                if year >= current_year - years:
                    pe_ratio = row['pe']
                    if pd.notna(pe_ratio):
                        if year not in historical_pe:
                            historical_pe[year] = []
                        historical_pe[year].append(float(pe_ratio))
            
            # 计算每年的平均市盈率
            result = {}
            for year, pe_values in historical_pe.items():
                if pe_values:
                    result[year] = sum(pe_values) / len(pe_values)
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取历史市盈率失败: {e}")
            return {}
    
    def get_comprehensive_pe_data(self, stock_code):
        """
        获取全面的市盈率数据
        
        Args:
            stock_code (str): 股票代码
            
        Returns:
            dict: 包含各种市盈率指标的数据
        """
        
        result = {
            'stock_code': stock_code,
            'current_pe': None,
            'historical_pe': {},
            'pe_ttm': None,
            'pe_lyr': None
        }
        
        try:
            # 获取当前市盈率
            result['current_pe'] = self.get_current_pe_ratio(stock_code)
            
            # 获取历史市盈率
            result['historical_pe'] = self.get_historical_pe_ratios(stock_code)
            
            # 获取TTM市盈率
            clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
            indicator_data = ak.stock_a_lg_indicator(symbol=clean_code)
            if indicator_data is not None and not indicator_data.empty:
                result['pe_ttm'] = float(indicator_data['pe_ttm'].iloc[0]) if pd.notna(indicator_data['pe_ttm'].iloc[0]) else None
                result['pe_lyr'] = float(indicator_data['pe_lyr'].iloc[0]) if pd.notna(indicator_data['pe_lyr'].iloc[0]) else None
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取全面市盈率数据失败: {e}")
            return result

def main():
    """主函数 - 演示如何使用"""
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建市盈率收集器
    pe_collector = PERatioCollector()
    stock_data = financial_data.FinancialData()
    
    # 从终端输入股票代码
    stock_code = input("请输入股票代码（例如：600519）: ").strip()
    
    if not stock_code:
        print("未输入股票代码，使用默认股票代码 600519")
        stock_code = "600519"
    
    print(f"\n=== 获取 {stock_code} 市盈率数据 ===")
    print(stock_data.get_indicator_data(stock_code, "净利润"))
    
    # 获取当前市盈率
    current_pe = pe_collector.get_current_pe_ratio(stock_code)
    if current_pe is not None:
        print(f"当前市盈率: {current_pe:.2f}")
    else:
        print("获取当前市盈率失败")
    
    # 获取历史市盈率
    historical_pe = pe_collector.get_historical_pe_ratios(stock_code, years=5)
    if historical_pe:
        print(f"\n历史市盈率（近5年）:")
        for year, pe in sorted(historical_pe.items()):
            print(f"  {year}年: {pe:.2f}")
    else:
        print("获取历史市盈率失败")
    
    # 获取全面的市盈率数据
    comprehensive_data = pe_collector.get_comprehensive_pe_data(stock_code)
    print(f"\n全面市盈率数据:")
    for key, value in comprehensive_data.items():
        if key == 'historical_pe' and value:
            print(f"  {key}:")
            for year, pe in sorted(value.items()):
                print(f"    {year}年: {pe:.2f}")
        else:
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()