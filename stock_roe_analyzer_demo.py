#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司ROE分析器 - Demo版本
基于akshare获取所有上市公司财务数据，分析ROE指标
支持断点续传，避免重复分析
"""

import akshare as ak
import pandas as pd
import time
import json
import os
import numpy as np
from datetime import datetime
import logging

class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理pandas和numpy数据类型"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):  # 处理NaN值
            return None
        elif isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d')
        # 让基类处理其他类型
        return super().default(obj)
from typing import Dict, List, Optional
import pickle

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('roe_analysis.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class StockROEAnalyzer:
    """上市公司ROE分析器"""
    
    def __init__(self, result_file='roe_analysis_results.json', 
                 progress_file='analysis_progress.json',
                 max_retries=3, retry_delay=2):
        """初始化分析器"""
        self.result_file = result_file
        self.progress_file = progress_file
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
        
        # 加载已有结果和进度
        self.results = self._load_results()
        self.progress = self._load_progress()
    
    def _load_results(self) -> Dict:
        """加载已有分析结果"""
        if os.path.exists(self.result_file):
            try:
                with open(self.result_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"加载结果文件失败: {e}")
        return {}
    
    def _load_progress(self) -> Dict:
        """加载分析进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"加载进度文件失败: {e}")
        return {'analyzed_stocks': [], 'last_analyzed_index': 0}
    
    def _save_results(self):
        """保存分析结果"""
        try:
            with open(self.result_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            self.logger.info(f"分析结果已保存到: {self.result_file}")
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
    
    def _save_progress(self):
        """保存分析进度"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        except Exception as e:
            self.logger.error(f"保存进度失败: {e}")
    
    def get_filtered_stock_list(self) -> Optional[pd.DataFrame]:
        """获取过滤后的股票列表（排除科创板、北交所、ST股等）"""
        try:
            # 获取所有A股股票列表
            stock_list = ak.stock_info_a_code_name()
            
            if stock_list is None or stock_list.empty:
                self.logger.error("获取股票列表失败")
                return None
            
            self.logger.info(f"原始股票列表数量: {len(stock_list)}")
            
            # 执行过滤
            filtered = stock_list.copy()
            
            # 排除科创板 (688开头)
            filtered = filtered[~filtered['code'].str.startswith('688')]
            
            # 排除北交所 (8开头)
            filtered = filtered[~filtered['code'].str.startswith('8')]
            
            # 排除创业板 (30开头)
            filtered = filtered[~filtered['code'].str.startswith('30')]
            
            # 排除ST股
            filtered = filtered[~filtered['name'].str.contains('ST|\\*ST')]
            
            # 排除B股 (200, 900开头)
            filtered = filtered[~filtered['code'].str.startswith(('200', '900'))]
            
            filtered = filtered.reset_index(drop=True)
            self.logger.info(f"过滤后股票列表数量: {len(filtered)}")
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"获取过滤股票列表失败: {e}")
            return None
    
    def get_financial_abstract(self, stock_code: str, years: int = 5) -> Optional[pd.DataFrame]:
        """获取财务摘要数据"""
        clean_code = stock_code.replace('.SZ', '').replace('.SH', '')
        
        for attempt in range(self.max_retries):
            try:
                df = ak.stock_financial_abstract(clean_code)
                
                if df is None or df.empty:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        return None
                
                # 处理数据，筛选近几年的数据
                return self._process_financial_data(df, years)
                
            except Exception as e:
                self.logger.warning(f"第{attempt+1}次尝试获取 {stock_code} 财务数据失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    return None
    
    def _process_financial_data(self, df: pd.DataFrame, years: int) -> pd.DataFrame:
        """处理财务数据，筛选近几年的数据"""
        if df.empty:
            return df
        
        current_year = datetime.now().year
        processed_data = []
        index_list = {}
        
        # 获取指标名称
        if '指标' in df.columns:
            for idx, value in df['指标'].items():
                index_list[idx] = value
        
        # 遍历DataFrame的列（日期）
        for column in df.columns:
            try:
                if isinstance(column, (int, str)) and len(str(column)) == 8:
                    date_str = str(column)
                    year = int(date_str[:4])
                    
                    # 筛选近几年的数据
                    if year >= current_year - years:
                        period_data = df[column]
                        
                        data_dict = {
                            'report_date': date_str,
                            'year': str(year),
                            'quarter': self._get_quarter_from_date(date_str)
                        }
                        
                        # 添加财务指标
                        for idx, value in period_data.items():
                            if pd.notna(value) and idx in index_list:
                                data_dict[index_list[idx]] = value
                        
                        processed_data.append(data_dict)
                        
            except Exception as e:
                continue
        
        if processed_data:
            return pd.DataFrame(processed_data)
        else:
            return pd.DataFrame()
    
    def _get_quarter_from_date(self, date_str: str) -> int:
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
    
    def analyze_roe(self, stock_code: str, stock_name: str, years: int = 5) -> Dict:
        """分析股票的ROE指标"""
        self.logger.info(f"开始分析 {stock_code} {stock_name}")
        
        # 获取财务数据
        df = self.get_financial_abstract(stock_code, years)
        
        if df.empty:
            self.logger.warning(f"{stock_code} 财务数据为空")
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'status': 'failed',
                'reason': '财务数据获取失败'
            }
        
        # 提取ROE数据
        roe_data = {}
        for year in sorted(df['year'].unique(), reverse=True):
            year_data = df[df['year'] == year]
            # 取年报数据（第4季度）
            annual_data = year_data[year_data['quarter'] == 4]
            
            if not annual_data.empty:
                roe_values = []
                for _, row in annual_data.iterrows():
                    roe = row.get('净资产收益率(ROE)')
                    if pd.notna(roe):
                        roe_values.append(float(roe))
                
                if roe_values:
                    roe_data[year] = sum(roe_values) / len(roe_values)
        
        # print("-------------------------------------------------------------")
        # for year, roe in roe_data.items():
        #     print(f"{stock_code} {stock_name} {year} 年ROE: {roe}")
        
        # 判断ROE条件
        years_with_low_roe = 0
        roe_details = {}
        
        for year, roe in roe_data.items():
            roe_details[year] = roe
            if roe < 5:  # ROE小于5%
                years_with_low_roe += 1
        
        # 判断结果
        if years_with_low_roe >= 2:
            status = 'bad'
            reason = f"近{years}年中有{years_with_low_roe}年ROE小于5%"
        else:
            status = 'good'
            reason = f"近{years}年中ROE小于5%的年份数: {years_with_low_roe}"
        
        result = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'status': status,
            'reason': reason,
            'roe_details': roe_details,
            'years_with_low_roe': years_with_low_roe,
            'total_years_analyzed': len(roe_data),
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.logger.info(f"{stock_code} 分析完成: {status} - {reason}")
        return result
    
    def batch_analyze_stocks(self, batch_size: int = 10, delay: int = 1):
        """批量分析股票"""
        
        # 获取股票列表
        stock_list = self.get_filtered_stock_list()
        if stock_list is None:
            self.logger.error("无法获取股票列表")
            return
        
        total_stocks = len(stock_list)
        self.logger.info(f"开始批量分析，总共 {total_stocks} 只股票")
        
        # 获取已分析的股票
        analyzed_stocks = set(self.progress.get('analyzed_stocks', []))
        last_index = self.progress.get('last_analyzed_index', 0)
        
        # 从上次中断的位置继续
        stocks_to_analyze = []
        for i, (_, row) in enumerate(stock_list.iterrows()):
            if i >= last_index and row['code'] not in analyzed_stocks:
                stocks_to_analyze.append((row['code'], row['name']))
        
        self.logger.info(f"需要分析的股票数量: {len(stocks_to_analyze)}")
        
        # 分批分析
        for i in range(0, len(stocks_to_analyze), batch_size):
            batch = stocks_to_analyze[i:i + batch_size]
            
            self.logger.info(f"分析第 {i//batch_size + 1} 批，共 {len(batch)} 只股票")
            
            for stock_code, stock_name in batch:
                try:
                    # 分析股票
                    result = self.analyze_roe(stock_code, stock_name)
                    
                    # 保存结果
                    self.results[stock_code] = result
                    analyzed_stocks.add(stock_code)
                    
                    # 更新进度
                    current_index = stock_list[stock_list['code'] == stock_code].index[0]
                    self.progress['last_analyzed_index'] = current_index
                    self.progress['analyzed_stocks'] = list(analyzed_stocks)
                    
                    # 保存进度和结果
                    self._save_results()
                    self._save_progress()
                    
                    # 延迟避免频繁请求
                    time.sleep(delay)
                    
                except Exception as e:
                    self.logger.error(f"分析 {stock_code} 时出错: {e}")
                    # 记录失败但继续分析下一只
                    self.results[stock_code] = {
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'status': 'failed',
                        'reason': str(e)
                    }
                    analyzed_stocks.add(stock_code)
                    self._save_results()
                    self._save_progress()
            
            self.logger.info(f"第 {i//batch_size + 1} 批分析完成")
        
        self.logger.info("批量分析完成")
    
    def get_summary(self) -> Dict:
        """获取分析摘要"""
        total = len(self.results)
        good_stocks = [r for r in self.results.values() if r.get('status') == 'good']
        bad_stocks = [r for r in self.results.values() if r.get('status') == 'bad']
        failed_stocks = [r for r in self.results.values() if r.get('status') == 'failed']
        
        return {
            'total_analyzed': total,
            'good_stocks': len(good_stocks),
            'bad_stocks': len(bad_stocks),
            'failed_stocks': len(failed_stocks),
            'good_ratio': len(good_stocks) / total if total > 0 else 0,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def demo_test():
    """Demo测试函数"""
    print("=== 上市公司ROE分析器 Demo测试 ===\n")
    
    # 创建分析器
    analyzer = StockROEAnalyzer()
    
    # 测试几只股票
    test_stocks = [
        ('600519', '贵州茅台'),
        ('000001', '平安银行'),
        ('300750', '宁德时代'),
        ('601318', '中国平安'),
        ('603660', '苏州科达')
    ]
    
    print("开始测试分析单只股票...")
    for stock_code, stock_name in test_stocks:
        print(f"\n分析 {stock_code} {stock_name}:")
        result = analyzer.analyze_roe(stock_code, stock_name)
        
        # 将结果保存到分析器中
        analyzer.results[stock_code] = result
        
        print(f"  状态: {result['status']}")
        print(f"  原因: {result['reason']}")
        if 'roe_details' in result:
            print(f"  ROE详情: {result['roe_details']}")
        print("-" * 50)
    
    # 显示摘要
    summary = analyzer.get_summary()
    print(f"\n分析摘要:")
    print(f"  总分析股票数: {summary['total_analyzed']}")
    print(f"  Good股票数: {summary['good_stocks']}")
    print(f"  Bad股票数: {summary['bad_stocks']}")
    print(f"  失败股票数: {summary['failed_stocks']}")
    print(f"  Good比例: {summary['good_ratio']:.2%}")
    
    print("\nDemo测试完成！")
    print("如需批量分析所有股票，请运行: analyzer.batch_analyze_stocks(batch_size=10, delay=1)")

def batch_analyze_main():
    #analysis all stocks

    analyzer = StockROEAnalyzer()
    analyzer.batch_analyze_stocks(10,3)

if __name__ == "__main__":
    #demo_test()
    batch_analyze_main()