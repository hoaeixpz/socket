import akshare as ak
import pandas as pd
import numpy as np
import time
import random
import os
import pickle
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class RisingStockFilter:
    def __init__(self):
        self.cache = StockListCache()  # 使用缓存系统
        self.today = datetime.now().strftime('%Y%m%d')
        self.half_year_ago = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')

    def safe_akshare_call(self, func, *args, **kwargs):
        """安全的AkShare调用，避免频繁请求被限制"""
        try:
            time.sleep(random.uniform(1.5, 3.0))  # 随机延时
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            print(f"调用失败: {e}")
            time.sleep(10)  # 失败后等待更久
            return None

    def get_filtered_stock_list(self):
        """获取过滤后的股票列表（排除科创板、ST股等）"""        
        """使用缓存获取过滤后的股票列表"""
        print("正在获取股票列表（优先使用缓存）...")
        return self.cache.get_filtered_stocks()

    def get_stock_history(self, symbol):
        """获取单只股票历史数据"""
        try:
            hist_data = self.safe_akshare_call(
                ak.stock_zh_a_hist,
                symbol=symbol,
                period="daily",
                start_date=self.half_year_ago,
                end_date=self.today,
                adjust="qfq"
            )
            return hist_data
        except Exception as e:
            print(f"获取 {symbol} 历史数据失败: {e}")
            return None

    def analyze_trend(self, hist_data):
        """分析股票趋势"""
        if hist_data is None or len(hist_data) < 60:  # 至少需要60个交易日
            return False, None, None

        try:
            # 计算技术指标
            hist_data = hist_data.sort_values('日期')  # 确保日期顺序

            # 1. 基本趋势：当前价格高于半年前价格
            start_price = hist_data.iloc[0]['收盘']
            end_price = hist_data.iloc[-1]['收盘']
            total_increase = (end_price - start_price) / start_price * 100
            #print("end_price  start_price", end_price, start_price)

            # 2. 均线系统：20日线上穿60日线
            hist_data['ma20'] = hist_data['收盘'].rolling(window=20, min_periods=1).mean()
            hist_data['ma60'] = hist_data['收盘'].rolling(window=60, min_periods=1).mean()

            # 3. 动量判断：近期表现强势
            recent_20 = hist_data['收盘'].iloc[-20:].mean()
            prev_20 = hist_data['收盘'].iloc[-40:-20].mean()
            momentum_positive = recent_20 > prev_20

            # 4. 趋势确认：价格在20日线之上
            above_ma20 = end_price > hist_data['ma20'].iloc[-1]

            # 综合判断条件
            condition1 = total_increase > 10  # 总体上涨
            condition2 = hist_data['ma20'].iloc[-1] > hist_data['ma60'].iloc[-1]  # 多头排列
            #print("ma20  ma60", hist_data['ma20'].iloc[-1], hist_data['ma60'].iloc[-1])
            condition3 = momentum_positive  # 近期动量向上
            #print("recent_20 prev_20", recent_20, prev_20)
            condition4 = above_ma20  # 价格在均线之上
            
            is_rising = condition1 and condition2 and condition3 and condition4
            
            return is_rising, total_increase, hist_data
            
        except Exception as e:
            print(f"分析趋势时出错: {e}")
            return False, None, None
    
    def batch_analyze_stocks(self, stock_list, sample_size=None, batch_size=15):
        """批量分析股票"""

        if sample_size and sample_size < len(stock_list):
            stock_list = stock_list.sample(sample_size)

        rising_stocks = []
        total = len(stock_list)
        
        print(f"开始分析 {total} 只股票...")
        print("=" * 60)
        
        for i, (code, name) in enumerate(zip(stock_list['code'], stock_list['name'])):
            # 显示进度
            if (i + 1) % 10 == 0 or (i + 1) == total:
                print(f"进度: {i+1}/{total} ({((i+1)/total)*100:.1f}%)")
            
            # 获取历史数据
            hist_data = self.get_stock_history(code)
            
            # 分析趋势
            is_rising, increase_rate, hist_data = self.analyze_trend(hist_data)
            
            if is_rising:
                # 计算更多技术指标
                current_price = hist_data.iloc[-1]['收盘']
                ma20 = hist_data['ma20'].iloc[-1]
                ma60 = hist_data['ma60'].iloc[-1]
                
                # 计算波动率
                volatility = hist_data['收盘'].pct_change().std() * 100
                
                rising_stocks.append({
                    '代码': code,
                    '名称': name,
                    '半年涨幅%': round(increase_rate, 2),
                    '当前价格': round(current_price, 2),
                    '20日均线': round(ma20, 2),
                    '60日均线': round(ma60, 2),
                    '波动率%': round(volatility, 2),
                    '数据天数': len(hist_data)
                })
                
                print(f"✅ 发现上涨股: {name}({code}) 涨幅: {increase_rate:.2f}%")
            
            # 批量控制
            if (i + 1) % batch_size == 0:
                wait_time = random.uniform(20, 30)
                print(f"已完成{batch_size}只股票，休息{wait_time:.1f}秒...")
                time.sleep(wait_time)
        
        return rising_stocks
    
    def save_results(self, results, filename=None):
        """保存结果到文件"""
        if not results:
            print("没有数据可保存")
            return
        
        if filename is None:
            filename = f'rising_stocks_{self.today}.xlsx'
        
        df = pd.DataFrame(results)
        
        # 按涨幅排序
        df = df.sort_values('半年涨幅%', ascending=False)
        
        # 保存到Excel
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='上涨趋势股票', index=False)
            
            # 添加统计信息
            stats = pd.DataFrame({
                '统计项目': ['总数量', '平均涨幅', '最大涨幅', '最小涨幅', '筛选时间'],
                '数值': [
                    len(df),
                    f"{df['半年涨幅%'].mean():.2f}%",
                    f"{df['半年涨幅%'].max():.2f}%",
                    f"{df['半年涨幅%'].min():.2f}%",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            })
            stats.to_excel(writer, sheet_name='统计信息', index=False)
        
        print(f"结果已保存到: {filename}")
        return df
    
    def generate_report(self, results):
        """生成分析报告"""
        if not results:
            print("没有找到符合条件的股票")
            return
        
        df = pd.DataFrame(results)
        
        print("\n" + "="*60)
        print("📈 上涨趋势股票筛选报告")
        print("="*60)
        
        print(f"📊 统计信息:")
        print(f"   筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"   总股票数: {len(df)} 只")
        print(f"   平均涨幅: {df['半年涨幅%'].mean():.2f}%")
        print(f"   最大涨幅: {df['半年涨幅%'].max():.2f}%")
        print(f"   最小涨幅: {df['半年涨幅%'].min():.2f}%")
        print(f"   平均波动率: {df['波动率%'].mean():.2f}%")
        
        print(f"\n🏆 涨幅前十股票:")
        top_10 = df.head(10)
        for _, stock in top_10.iterrows():
            print(f"   {stock['代码']} {stock['名称']:6} : {stock['半年涨幅%']:6.2f}%")
        
        # 按交易所分类
        sh_stocks = df[df['代码'].str.startswith(('6', '5'))]
        sz_stocks = df[df['代码'].str.startswith(('0', '3'))]
        
        print(f"\n🏢 交易所分布:")
        print(f"   上交所: {len(sh_stocks)} 只")
        print(f"   深交所: {len(sz_stocks)} 只")

class StockListCache:
    def __init__(self, cache_dir="./stock_data", cache_expire_days=7):
        """
        :param cache_dir: 缓存目录
        :param cache_expire_days: 缓存过期天数（默认7天）
        """
        self.cache_dir = cache_dir
        self.cache_expire_days = cache_expire_days
        os.makedirs(cache_dir, exist_ok=True)
        
    def _get_cache_path(self, cache_type):
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_type}_cache.pkl")
    
    def _is_cache_valid(self, file_path):
        """检查缓存是否有效"""
        #print("file: ", file_path)
        if not os.path.exists(file_path):
            print("path is not exist!")
            return False
            
        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        return (datetime.now() - file_time) < timedelta(days=self.cache_expire_days)
    
    def get_stock_list(self, force_update=False):
        """
        获取股票列表（优先从缓存读取）
        :param force_update: 强制更新缓存
        :return: DataFrame
        """
        cache_file = self._get_cache_path("stock_list")
        
        # 如果不需要强制更新且缓存有效
        if not force_update and self._is_cache_valid(cache_file):
            print("📁 从本地缓存加载股票列表...")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        
        # 从AkShare获取最新数据
        print("🌐 从网络获取最新股票列表...")
        try:
            stock_list = ak.stock_info_a_code_name()
            
            # 保存到缓存
            with open(cache_file, 'wb') as f:
                pickle.dump(stock_list, f)
                print(f"💾 股票列表已缓存到: {cache_file}")
                
            return stock_list
            
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            # 尝试返回旧缓存（如果有）
            if os.path.exists(cache_file):
                print("⚠️ 使用过期缓存数据")
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            return None

    def get_filtered_stocks(self, exclude_types=None):
        """
        获取过滤后的股票列表
        :param exclude_types: 要排除的类型 
               (默认排除: ['科创板', 'ST', 'B股'])
        """
        if exclude_types is None:
            exclude_types = ['科创板', 'ST', 'B股', '创业板']
            
        df = self.get_stock_list()
        if df is None:
            return None
            
        # 执行过滤
        filtered = df.copy()
        
        if '科创板' in exclude_types:
            filtered = filtered[~filtered['code'].str.startswith('688')]
            
        if '创业板' in exclude_types:
            filtered = filtered[~filtered['code'].str.startswith('30')]
            
        if 'ST' in exclude_types:
            filtered = filtered[~filtered['name'].str.contains('ST|\\*ST')]
            
        if 'B股' in exclude_types:
            filtered = filtered[~filtered['code'].str.startswith(('200', '900'))]
            
        return filtered.reset_index(drop=True)

# 使用示例
def main():
    # 创建筛选器实例
    filter = RisingStockFilter()
    
    # 步骤1: 获取过滤后的股票列表
    print("步骤1: 获取股票列表...")
    filtered_stocks = filter.get_filtered_stock_list()
    
    if filtered_stocks is None:
        print("无法获取股票列表，程序退出")
        return
    
    # 步骤2: 批量分析股票（使用小样本测试，实际使用时可以调整）
    print("\n步骤2: 分析股票趋势...")
    sample_size = 100  # 测试用100只，实际使用可以设为None分析全部
    rising_stocks = filter.batch_analyze_stocks(filtered_stocks, sample_size=sample_size)
    
    # 步骤3: 保存结果和生成报告
    if rising_stocks:
        print("\n步骤3: 生成报告...")
        results_df = filter.save_results(rising_stocks)
        filter.generate_report(rising_stocks)
    else:
        print("没有找到符合条件的上涨趋势股票")

if __name__ == "__main__":
    main()