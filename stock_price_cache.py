import akshare as ak
import pandas as pd
import time
import os
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    code_str = str(stock_code).strip()
    
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    else:
        return code_str

class StockPriceCache:
    def __init__(self, cache_dir="./stock_price", cache_expire_days=30):
        """
        :param cache_dir: 缓存目录
        :param cache_expire_days: 缓存过期天数（默认70天）
        """
        self.cache_dir = cache_dir
        self.cache_expire_days = cache_expire_days
        os.makedirs(cache_dir, exist_ok=True)
    
    def _is_cache_valid(self, file_path):
        """检查缓存是否有效"""
        #print("file: ", file_path)
        if not os.path.exists(file_path):
            print("path is not exist!")
            return False
            
        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        return (datetime.now() - file_time) < timedelta(days=self.cache_expire_days)
    
    def get_stock_hfq_price(self, stock_code:str, force_update=False):
        """
        获取股票股价（优先从缓存读取）
        :param force_update: 强制更新缓存
        :return: DataFrame
        """
        # "sh600007_daily_hfq.parquet"
        stock_code = add_stock_prefix(stock_code)
        cache_file = os.path.join(self.cache_dir, f"{stock_code}_daily_hfq.parquet")
        
        # 如果不需要强制更新且缓存有效
        if not force_update and self._is_cache_valid(cache_file):
            #print("📁 从本地缓存加载股票价格...")
            return pd.read_parquet(cache_file)

        
        # 从AkShare获取最新数据
        print("🌐 从网络获取最新股票价格...")
        try:
            df = ak.stock_zh_a_daily(symbol=stock_code, adjust="hfq")

            if df is None or df.empty:
                print(f"警告：未获取到 {symbol} 的股价")
                return None
                # 保存到缓存

            if 'date' in df.columns and 'close' in df.columns:
                df = df[['date', 'close']]
            else:
                print(f"⚠️ {stock_code} 股价数据异常，不存在date, close列表")
            df.to_parquet(cache_file, index=False, compression='snappy')
            print(f"💾 {stock_code} 价格已缓存到: {cache_file}")
                
            return df
            
        except Exception as e:
            print(f"获取股票价格失败: {e}")
            # 尝试返回旧缓存（如果有）
            if os.path.exists(cache_file):
                print("⚠️ 使用过期缓存数据")
                return pd.read_parquet(cache_file)
            return None

    def get_index_price(self, stock_code:str, force_update=False):
        """
        获取指数股价（优先从缓存读取）
        :param force_update: 强制更新缓存
        :return: DataFrame
        """

        # "sh000001_index_daily.parquet"
        cache_file = os.path.join(self.cache_dir, f"{stock_code}_index_daily.parquet")
        
        # 如果不需要强制更新且缓存有效
        if not force_update and self._is_cache_valid(cache_file):
            #print("📁 从本地缓存加载指数价格...")
            return pd.read_parquet(cache_file)
        
        # 从AkShare获取最新数据
        print("🌐 从网络获取最新指数价格...")
        try:
            df = ak.stock_zh_index_daily(stock_code)

            if df is None or df.empty:
                print(f"警告：未获取到 {symbol} 的股价")
                return None
                # 保存到缓存
            df.to_parquet(cache_file, index=False, compression='snappy')
            print(f"💾 {stock_code}指数价格已缓存到: {cache_file}")
                
            return df
            
        except Exception as e:
            print(f"获取股价失败: {e}")
            # 尝试返回旧缓存（如果有）
            if os.path.exists(cache_file):
                print("⚠️ 使用过期缓存数据")
                return pd.read_parquet(cache_file)
            return None

    def get_specify_date_price(self, df, target_date_str:str, head = 'close', force_update=False):
        if df is None or df.empty:
            print("input df is None")
            return None

        if df.index.name == 'date':
            df['date'] = df.index

        if 'date' in df.columns:
            target_date = pd.to_datetime(target_date_str)
            first_date = pd.to_datetime(df['date'].iloc[0])
            last_date = pd.to_datetime(df['date'].iloc[-1])
            if target_date < first_date or target_date > last_date:
                #print(f"请求日期 {target_date}  缓存只包含从 {first_date} 到 {last_date} 期间股价，请执行stock_zh_a_daily获取股价")
                return None

            df = df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            try:
                price_series = df.loc[[target_date], [head]]
                return price_series.iloc[0][head]
            except KeyError:
                print(f"未找到目标日 {target_date.date()} 的数据，尝试查前几日数据。")

            first_day_of_month = target_date.replace(day=1)
            all_days_in_month = pd.date_range(start=first_day_of_month, end=target_date, freq='D')
            for current_date in reversed(all_days_in_month):
                try:
                    return df.at[current_date, head]
                except KeyError:
                    continue
            
            print(f"警告：目标日期所在月份 {first_day_of_month.date()} 没有任何数据。")
            return None
        else:
            print("df not has cloumn date")
            return None

# 使用示例
def main():
    # 创建筛选器实例
    cache = StockPriceCache()
    
    # 步骤1: 获取过滤后的股票列表
    print("步骤1: 获取股票...")
    df = cache.get_index_price("sz000001")
    price = cache.get_specify_date_price(df, "19000201")
    print(price)
    df = cache.get_stock_hfq_price("600362")
    price = cache.get_specify_date_price(df, "2016-12-10")
    print(price)


    
    if df is None:
        print("无法获取股票价格，程序退出")
        return

if __name__ == "__main__":
    main()
