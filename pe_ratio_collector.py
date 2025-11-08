#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市盈率数据收集器
获取股票的市盈率指标
"""

from typing import Any
import akshare as ak
from numpy.random import f
import pandas as pd
import time
import datetime
import logging

from pandas._libs.tslibs.parsing import quarter_to_myear
from pandas.tseries.offsets import YearBegin
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
        f"""
        手动计算市盈率：PE = 股价 / 每股收益
        
        Args:
            stock_code (str): 股票代码
            
        Returns:
            float: (动态市盈率值, 静态市盈率值,TTM市盈率)，获取失败返回None
        """
        
        result = []
        
        try:
            # 获取当前股价
            current_price = self._get_current_price(stock_code)
            #print(f"当前股价: {current_price}")
            if current_price is None:
                return None
            
            # 获取每股收益
            hist_eps = self._get_history_eps(stock_code, years = 1)
            if hist_eps is None:
                return None
            #print("最近一年每股收益")
            #print(hist_eps)
            last_eps = hist_eps[0]
            last_date = last_eps[0]
            eps = last_eps[1]
            quater = last_date[4:6]
            #print(quater)
            eps_d = eps * 1.0 / int(quater) * 12
            pe_d = current_price / eps_d
            pe_j = pe_d
            pe_TTM = pe_j

            last_year_eps = 0
            for date, eps in hist_eps:
                if str(date[0:4]) == str(datetime.datetime.now().year):
                    continue
                last_year_eps = eps
                pe_j = current_price / last_year_eps
                break

            if quater != "12":
                for date, eps in hist_eps:
                    if str(date[0:4]) == str(datetime.datetime.now().year):
                        continue
                    if date[4:6] == quater:
                        eps_TTM = last_year_eps - eps + last_eps[1]
                        pe_TTM = current_price / eps_TTM
                        break

            #print(f"动态市盈率: {pe_d:.2f}")
            #print(f"静态市盈率: {pe_j:.2f}")
            #print(f"TTM市盈率: {pe_TTM:.2f}")
            #for date, eps in hist_eps:
            result.append(pe_d)
            result.append(pe_j)
            result.append(pe_TTM)

            # 计算动态市盈率
            self.logger.info(f"手动计算 {stock_code} 动态市盈率: {pe_d:.2f} 静态市盈率: {pe_j:.2f} TTM市盈率: {pe_TTM:.2f}")
            return result
            
        except Exception as e:
            self.logger.error(f"手动计算市盈率失败: {e}")
            return None
    
    def _get_current_price(self, stock_code):
        """获取当前股价"""
        
        try:
            today = datetime.datetime.today()
            yesterday = today - datetime.timedelta(days=7)
            stock_zh_a_daily_qfq_df = ak.stock_zh_a_daily(
                stock_code, start_date=yesterday, end_date=today, adjust="qfq")
            #print(stock_zh_a_daily_qfq_df)
            if stock_zh_a_daily_qfq_df is not None and not stock_zh_a_daily_qfq_df.empty:
                return stock_zh_a_daily_qfq_df['close'].iloc[-1]
        
        except Exception as e:
            self.logger.error(f"stock_zh_a_daily获取股价失败: {e}")

        try:       
            # 获取历史数据的最新收盘价
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
            print("获取历史数据的最新收盘价结束")
            if hist_data is not None and not hist_data.empty:
                return float(hist_data['收盘'].iloc[-1])
            
        except Exception as e:
            self.logger.error(f"stock_zh_a_hist获取股价失败: {e}")

        return None

    def _get_price(self, stock_code, target_date):
        '''
        获取指定日期的股价
        target_date格式: "20241219"
        '''

        startdate = target_date
        day = int(startdate[6:]) - 2
        startdate = startdate[:-2] + str(day)
        try:
            #start_t = time.time()
            df = ak.stock_zh_a_daily(
                stock_code, 
                start_date=startdate, 
                end_date=target_date, 
                adjust="qfq")
            #end_t = time.time()
            #print(f"获取{stock_code} {target_date} 的股价结束，耗时{end_t - start_t}")
            if df is not None and not df.empty:
                return df['close'].iloc[-1]
        
        except Exception as e:
            self.logger.error(f"stock_zh_a_daily获取指定日期股价失败: {e}")

        try:       
            # 获取历史数据的最新收盘价
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                start_date=startdate,
                end_date=target_date,
                period="daily", 
                adjust="qfq")

            #print(f"获取{stock_code} {target_date} 的股价结束")
            if df is not None and not df.empty:
                return float(df['收盘'].iloc[-1])
            
        except Exception as e:
            self.logger.error(f"stock_zh_a_hist获取指定日期股价失败: {e}")

        return None

    def _get_history_eps(self, stock_code,  years = 5): 
        '''
        获取历史每股收益
        和对应日期

        返回一个list

        格式: [(date, eps), (date, eps), ...]
        '''

        df = stock_data.get_indicator_data(stock_code, "基本每股收益")
        result_list = stock_data.get_indicator_recent_year(df, 5)
        
        print(f"获取{stock_code} 历史每股收益结束")
        return result_list


    def get_historical_pe_ratios(self, stock_code, years=5):
        """
        获取历史市盈率数据
        
        Args:
            stock_code (str): 股票代码
            years (int): 获取最近几年的数据
            
        Returns:
            dict: 年份到市盈率的映射
        """
        
        result = {}
        try:
            # 获取历史市盈率数据
            hist_eps = self._get_history_eps(stock_code, years)
            for date, eps in hist_eps:
                if date[4:6] == "12":
                    price: Any | float | None = self._get_price(stock_code, date)
                    if price is not None and eps is not None:
                        pe_ratio = price / eps
                        #print(f"date {date} eps {eps} price {price} pe_ratio {pe_ratio}")
                        result[date] = pe_ratio
            
            print("获取历史市盈率数据结束")
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取历史市盈率失败: {e}")
            return {}

    def get_historical_peg(self, stock_code, historical_pe, years = 5):
        '''
        计算PEG
        PEG = PE / 净利润增长率
        净利润增长率 = 净利润 / 上年净利润
        '''
        df = stock_data.get_indicator_data(stock_code, "净利润")
        profit_hist = stock_data.get_indicator_recent_year(df, years + 1)
        if profit_hist is None or len(profit_hist) == 0:
            return None

        profit_year = []
        for date, profit in profit_hist:
            if date[4:6] == "12":
                #print(f"profit {profit}")
                profit_year.append((date[0:4], profit))

        profit_year.sort(key=lambda x: x[0])
        #print(profit_year)
                
        last_p = profit_year[0][1]
        first_year = profit_year[0][0]
        profit_ratio = {}
        for year, p in profit_year:
            if year == first_year:
                continue
            r = (p - last_p) / last_p * 100
            profit_ratio[year] = r
            last_p = p
        
        #print(profit_ratio)

        peg_history = {}
        for year, pe in historical_pe.items():
            year = year[0:4]
            if year in profit_ratio:
                peg = pe / profit_ratio[year]
                peg_history[year] = peg
                #print(f"year {year} pe {pe} peg {peg}")

        return peg_history

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    
    # 确保是字符串类型
    code_str = str(stock_code).strip()
    
    # 判断规则
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    elif code_str.startswith('4') or code_str.startswith('8'):
        return f"bj{code_str}"      # 北证
    else:
        raise ValueError(f"无法识别的股票代码格式: {stock_code}")

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
        #stock_code = "600745"

    stock_code = add_stock_prefix(stock_code)
    
    print(f"\n=== 获取 {stock_code} 市盈率数据 ===")
    
    # 获取当前市盈率
    
    current_pe = pe_collector.get_current_pe_ratio(stock_code)
    if current_pe is not None:
        print(f"当前市盈率: {current_pe}")
    else:
        print("获取当前市盈率失败")
    
    # 获取历史市盈率
    historical_pe = pe_collector.get_historical_pe_ratios(stock_code)
    print(f"历史市盈率: {historical_pe}")

    peg = pe_collector.get_historical_peg(stock_code, historical_pe)
    print(f"历史PEG: {peg}")
    

if __name__ == "__main__":
    main()