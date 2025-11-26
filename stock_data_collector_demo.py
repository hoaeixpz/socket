from typing import Any, Dict, Optional, List
import akshare as ak
import pandas as pd
import json
import time
import datetime
import logging
import os
import numpy as np

from financial_data import FinancialData
from stock_data_cache import StockDataCache
# 创建全局实例
stock_data = FinancialData()

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

    def iterencode(self, o, _one_shot=False):
        """重写iterencode方法，处理浮点数"""
        if isinstance(o, float):
        # 四舍五入到指定小数位
            o = round(o, 2)
        return super().iterencode(o, _one_shot)

class StockDataCollector:
    """股票数据收集器"""
    
    def __init__(self, result_file='analysis_results.json', 
                 progress_file='analysis_progress.json',
                 max_retries=3, retry_delay=2):
        """初始化分析器"""
        self.result_file = result_file
        self.progress_file = progress_file
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 如果还没有配置日志处理器，则添加文件处理器
        if not self.logger.handlers:
            # 创建日志目录
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 日志文件名：程序名_年月日.log
            log_filename = f"{log_dir}/stock_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.log"
            
            # 创建文件处理器
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 设置日志格式
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            
            # 添加到日志记录器
            self.logger.addHandler(file_handler)
            
            # 同时输出到控制台
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
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
            #stock_list = ak.stock_info_a_code_name()
            stock_list = StockDataCache().get_stock_list()
            
            if stock_list is None or stock_list.empty:
                self.logger.error("获取股票列表失败")
                return None
            
            self.logger.info(f"原始股票列表数量: {len(stock_list)}")
            
            # 执行过滤
            filtered = stock_list.copy()
            
            # 排除科创板 (688开头)
            filtered = filtered[~filtered['code'].str.startswith('68')]
            
            # 排除北交所 (8开头)
            filtered = filtered[~filtered['code'].str.startswith('8')]

            # 排除北交所 (920开头)
            filtered = filtered[~filtered['code'].str.startswith(('920'))]
            
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
    
    def get_historical_pe_ratios(self, stock_code, years=15):
        """
        获取历史市盈率数据
        
        Args:
            stock_code (str): 股票代码
            years (int): 获取最近几年的数据
            
        Returns:
            dict: 年份到市盈率的映射
        """
        
        pe_result = {}
        price_result = {}
        try:
            # 获取历史市盈率数据
            hist_eps = self.get_history_eps(stock_code, years)
            #print(f"hist_eps {hist_eps}")
            for date, eps in hist_eps:
                if date[4:6] == "12":
                    # 延迟避免频繁请求
                    time.sleep(0.2)
                    price: Any | float | None = self.get_price(stock_code, date)
                    if price is not None and eps is not None:
                        pe_ratio = price / eps
                        #print(f"date {date} eps {eps} price {price} pe_ratio {pe_ratio}")
                        pe_result[date[0:4]] = pe_ratio
                        price_result[date[0:4]] = price
            print("获取历史市盈率数据结束")
            
            return pe_result, price_result
            
        except Exception as e:
            self.logger.error(f"获取历史市盈率失败: {e}")
            return {}

    def get_current_pe_ratio(self, stock_code, current_price):
        """
        手动计算市盈率：PE = 股价 / 每股收益
        
        Args:
            stock_code (str): 股票代码
            
        Returns:
            float: (动态市盈率值, 静态市盈率值,TTM市盈率)，获取失败返回None
        """
        
        result = []
        
        try:            
            # 获取每股收益
            hist_eps = self.get_history_eps(stock_code, years = 1)
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

    def get_current_price(self, stock_code):
        """获取当前股价"""
        
        today = "20250930"
        return [today, self.get_price(stock_code, today)]

    def get_price(self, stock_code, target_date, adjust = ""):
        '''
        获取指定日期的股价(默认不复权)
        target_date格式: "20241219"
        '''

        '''
        clean_code = stock_code.replace('sz', '').replace('sh', '')
        listing_date = get_stock_listing_date(clean_code)
        #print(f"listing_date {listing_date}")
        if listing_date is not None and int(target_date) < listing_date:
            self.logger.warning(f"获取{stock_code} {target_date} 的股价日期早于上市日期 {listing_date}")
            return None
        '''

        startdate = target_date
        day = int(startdate[6:]) - 2
        if day < 10:
            startdate = startdate[:-2] + "0" + str(day)
        else:
            startdate = startdate[:-2] + str(day)
        #print(f"start end {startdate} {target_date}")
        try:
            df = ak.stock_zh_a_daily(
                stock_code, 
                start_date=startdate, 
                end_date=target_date, 
                adjust=adjust)
            #print(df)
            if df is not None and not df.empty:
                return df['close'].iloc[-1]
            else:
                self.logger.warning(f"获取{stock_code} {target_date} 的股价为空,尝试2周前股价")
                startdate = startdate[0:6] + "01"
                print(f"start end {startdate} {target_date}")
                df = ak.stock_zh_a_daily(
                    stock_code, 
                    start_date=startdate, 
                    end_date=target_date, 
                    adjust=adjust)
                #print(df)
                if df is not None and not df.empty:
                    return df['close'].iloc[-1]
                else:
                    self.logger.warning(f"获取{stock_code} {target_date} 的股价为空")
                    return None
            

        except Exception as e:
            self.logger.error(f"stock_zh_a_daily获取指定日期股价失败: {e}")
            return None

    def get_history_eps(self, stock_code: str, years: int = 15):
        df = stock_data.get_indicator_data(stock_code, "基本每股收益")
        result_list = stock_data.get_indicator_recent_year(df, years)
        
        print(f"获取{stock_code} 历史每股收益结束")
        return result_list

    def get_ROE(self, stock_code: str, stock_name: str, indicator: str, year : int = 15) -> Dict:
        """获取ROE"""
        df = stock_data.get_indicator_data(stock_code, indicator)
        result_list = stock_data.get_indicator_recent_year(df, year)
        kf_roe = stock_data.get_indicator_recent_year(df, year)
        #print(kf_roe)
        
        history_roe = {}
        last_year = None
        for date, kf_roe_v in kf_roe:
            year = date[0:4]
            if year != last_year:
                last_year = year
                history_roe[year] = [None, None, None, None]
            month = date[4:6]
            if month == "03":
                history_roe[year][0] = kf_roe_v
            elif month == "06":
                history_roe[year][1] = kf_roe_v
            elif month == "09":
                history_roe[year][2] = kf_roe_v
            elif month == "12":
                history_roe[year][3] = kf_roe_v

        print(f"获取{stock_code} 历史ROE结束")

        return history_roe

    def analyze_stock(self, stock_code: str, stock_name: str, years: int = 15) -> Dict:
        """分析单只股票，记录近15年每年末的股价、ROE和PE数据"""
        stock_code = add_stock_prefix(stock_code)
        self.logger.info(f"开始分析 {stock_code} {stock_name} 的{ years}年历史数据")
        
        try:
            # 获取后复权历史股价
            now = datetime.datetime.now()
            history_price_hfq = {}
            for year in range(now.year - years, now.year):
                date = str(year) + "1231"
                history_price_hfq[year] = self.get_price(stock_code, date, adjust = "hfq")
            

            # 1. 获取ROE数据
            hist_roe = self.get_ROE(stock_code, stock_name, "净资产收益率(ROE)", years)
            hist_kf_roe = self.get_ROE(stock_code, stock_name, "净资产收益率_平均_扣除非经常损益", years)
            sorted_kfroe = dict(sorted(hist_kf_roe.items(), key=lambda x: int(x[0])))
            sorted_roe = dict(sorted(hist_roe.items(), key=lambda x: int(x[0])))

            hist_kf_roe = sorted_kfroe
            hist_roe = sorted_roe
            
            # 2. 获取PE数据,和股价
            pe_data, price_data = self.get_historical_pe_ratios(stock_code, years)
            sorted_pe = dict(sorted(pe_data.items(), key=lambda x: int(x[0])))
            pe_data = sorted_pe
            sorted_dates = dict(sorted(price_data.items(), key=lambda x: int(x[0])))
            price_data = sorted_dates
            
            # 3. 获取当前股价和PE
            current_price = self.get_current_price(stock_code)
            current_pe = self.get_current_pe_ratio(stock_code, current_price[1])
            
            pe_analysis_data = {
                'current_pe': current_pe,
                'historical_pe': pe_data,
                #'historical_peg': historical_peg,
                'analysis_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'error': None
            }

            
            # 4. 汇总结果
            roe_detail = {}
            roe_detail['kf_roe'] = hist_kf_roe
            roe_detail['roe'] = hist_roe
            result = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'history_price_hfq': history_price_hfq,
                'history_price_bfq': price_data,
                'current_price': current_price,
                'roe_details': roe_detail,
                'pe_analysis': pe_analysis_data,
                'analysis_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.logger.info(f"{stock_code} {stock_name} 分析完成")
            return result
            
        except Exception as e:
            self.logger.error(f"分析 {stock_code} {stock_name} 失败: {e}")
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'status': 'failed',
                'reason': str(e),
                'analysis_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

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
            
            #self.logger.info(f"分析第 {i//batch_size + 1} 批，共 {len(batch)} 只股票")
            
            for stock_code, stock_name in batch:
                try:
                    # 分析股票
                    if stock_code in self.results:
                        continue
                    result = self.analyze_stock(stock_code, stock_name)
                    
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
                    #time.sleep(delay)
                    
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
            
            #self.logger.info(f"第 {i//batch_size + 1} 批分析完成")
        
        #self.logger.info("批量分析完成")

    def get_summary(self):
        """获取分析摘要"""
        total = len(self.results)
        
        for result in self.results.values():
            if result.get('current_price') is None:
                self.logger.error(f"{result.get('stock_code')} {result.get('stock_name')} 没有获取到当前股价")

def demo_test():
    """Demo测试函数"""
    print("=== 上市公司ROE分析器 Demo测试 ===\n")
    
    # 创建分析器
    analyzer = StockDataCollector('analysis_results.json', '')
    
    # 测试几只股票
    test_stocks = [
        #('600519', '贵州茅台')
        #('000001', '平安银行'),
        #('300750', '宁德时代'),
        #('601318', '中国平安'),
        #('603660', '苏州科达'),
        ('600362', '江西铜业'),
        #('600519', '贵州茅台')
        #('689009', '九号公司')
    ]
    
    print("开始测试分析单只股票...")
    for stock_code, stock_name in test_stocks:
        print(f"\n分析 {stock_code} {stock_name}:")
        
        result = analyzer.analyze_stock(stock_code, stock_name, 15)
        
        # 将结果保存到分析器中
        analyzer.results[stock_code] = result
        analyzer._save_results()
        
        if 'roe_details' in result:
            print(f"  ROE详情: {result['roe_details']}")
        if 'pe_analysis' in result:
            print(f"  PE分析: {result['pe_analysis']}")
        if 'current_price' in result:
            print(f"  当前股价: {result['current_price']}")
        if 'history_price_bfq' in result:
            print(f"  历史股价: {result['history_price_bfq']}")
        if 'history_price_hfq' in result:
            print(f"  后复权历史股价: {result['history_price_hfq']}")
        print("-" * 50)

    
    # 显示摘要
    analyzer.get_summary()
    
    print("\nDemo测试完成！")
    print("如需批量分析所有股票，请运行: analyzer.batch_analyze_stocks(batch_size=10, delay=1)")

def batch_analyze_main():
    #analysis all stocks

    analyzer = StockDataCollector('analysis_results.json', '')
    analyzer.batch_analyze_stocks(15,3)

    analyzer.get_summary()

if __name__ == "__main__":
    #demo_test()
    batch_analyze_main()
