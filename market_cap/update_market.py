import akshare as ak
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import json
import os
from datetime import datetime, timedelta

current_dir = os.path.dirname(__file__)

def add_stock_prefix(stock_code):
    """为股票代码添加市场前缀"""
    code_str = str(stock_code).strip()
    
    if code_str.startswith('6'):
        return f"sh{code_str}"      # 上证
    elif code_str.startswith('0') or code_str.startswith('3'):
        return f"sz{code_str}"      # 深证
    else:
        return code_str

def load_existing_stocks(file = '../stock_info.json'):
    """加载现有的stock_info.json文件，返回所有股票代码列表"""
    try:
        with open(file, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        return stocks
    except FileNotFoundError:
        print(f"错误：找不到{file}文件")
        return {}
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式错误 - {e}")
        return {}

def save_markets():
    """
    获取A股股票市值历史数据
    """
    #with open('market_list.txt', 'r', encoding='utf-8') as f:
    #    stock_codes = [line.strip() for line in f.readlines()]

    all_stocks = load_existing_stocks()
    stock_codes = list(all_stocks.keys())
    
    for i, stock_code in enumerate(stock_codes, 1):
        filename = f"{stock_code}_market_cap.parquet"
        if os.path.exists(filename):
            continue
        try:
            print(f"正在获取股票 {stock_code} 的数据...")
            
            # 获取日线数据
            df = ak.stock_zh_valuation_baidu(symbol=stock_code, indicator="总市值", period="全部")
            #print(df)
            if df.empty:
                print(df)
                continue

            filename = f"{stock_code}_market_cap.parquet"
            df.to_parquet(filename, index=False, compression='snappy')
    
            file_size = os.path.getsize(filename) / (1024)
            print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} KB {datetime.now()}")
        except Exception as e:
            print(f"获取股票 {stock_code} 数据时出错: {e}")
            continue

class StockMarketCache:
    def __init__(self):
        self.cache_dir = current_dir

    def load_market_df(self, stock_code):
        try:
            clean_code = stock_code.replace('sz', '').replace('sh', '')
            filename = f"{self.cache_dir}/{clean_code}_market_cap.parquet"
            df = pd.read_parquet(filename)
            return df
        except Exception as e:
            print(f'{stock_code} has not market data {e}')
            return None

    def get_specify_date_market(self, df, target_date_str:str, head = 'value'):
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
                #print(f"请求日期: {target_date},  缓存只包含从 {first_date} 到 {last_date} 期间市值")
                return None

            df = df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            try:
                price_series = df.loc[[target_date], [head]]
                return price_series.iloc[0][head]
            except KeyError:
                #print(f"未找到目标日 {target_date.date()} 的数据，尝试查前几日数据。")
                date_sequence  = pd.date_range(end=target_date, periods=30, freq='D')
                for current_date in reversed(date_sequence):
                    try:
                        result = df.at[current_date, head]
                        return result
                    except KeyError:
                        continue
            
                print(f"警告：目标日期所在月份 {first_day_of_month.date()} 没有任何数据。")
                return None
        else:
            print("df not has cloumn date")
            return None


if __name__ == "__main__":
    save_markets()
    exit()

    mc = StockMarketCache()
    df = mc.load_market_df('002006')
    print(df[500:550])
    exit()
    for day in range(20,31):
        date = "2018-01-" + str(day)
        print(date, mc.get_specify_date_market(df, date))
    #print(df[100: 150])
