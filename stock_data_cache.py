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

class StockDataCache:
    def __init__(self, cache_dir="./stock_data", cache_expire_days=70):
        """
        :param cache_dir: 缓存目录
        :param cache_expire_days: 缓存过期天数（默认70天）
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
            #print("📁 从本地缓存加载股票列表...")
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

    def get_stock_indicator(self, stock_code:str, force_update=False):
        """
        获取股票指标（优先从缓存读取）
        :param force_update: 强制更新缓存
        :return: DataFrame
        """
        cache_file = self._get_cache_path(f"stock_{stock_code}_indicator")
        
        # 如果不需要强制更新且缓存有效
        if not force_update and self._is_cache_valid(cache_file):
            #print("📁 从本地缓存加载股票指标...")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        
        # 从AkShare获取最新数据
        print("🌐 从网络获取最新股票指标...")
        try:
            stock_indicator = ak.stock_financial_abstract(symbol=stock_code)

            if stock_indicator is None or stock_indicator.empty:
                print(f"警告：未获取到 {symbol} 的指标数据")
                return None
                # 保存到缓存
            with open(cache_file, 'wb') as f:
                pickle.dump(stock_indicator, f)
                print(f"💾 {stock_code}股票指标已缓存到: {cache_file}")
                
            return stock_indicator
            
        except Exception as e:
            print(f"获取股票指标失败: {e}")
            # 尝试返回旧缓存（如果有）
            if os.path.exists(cache_file):
                print("⚠️ 使用过期缓存数据")
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            return None
# 使用示例
def main():
    # 创建筛选器实例
    cache = StockDataCache()
    
    # 步骤1: 获取过滤后的股票列表
    print("步骤1: 获取股票...")
    df = cache.get_stock_indicator("600519")
    
    if df is None:
        print("无法获取股票指标，程序退出")
        return

def test():
    cache = StockDataCache()
    df = cache.get_stock_indicator("600519")
    print(df)

if __name__ == "__main__":
    #main()
    test()