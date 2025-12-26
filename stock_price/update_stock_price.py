import akshare as ak
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import json
import os
from datetime import datetime, timedelta

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

def save_daily_prices():
    """
    获取A股股票从2023年初至今的收盘价
    """
    # 定义时间范围
    start_date = "20100101"
    end_date = "20161231"
    
    all_stocks = load_existing_stocks()
    stock_codes = list(all_stocks.keys())
    
    for i, stock_code in enumerate(stock_codes, 1):
        stock_code = add_stock_prefix(stock_code)
        try:
            print(f"正在获取股票 {stock_code} 的数据...")
            
            # 获取日线数据
            stock_df = ak.stock_zh_a_daily(symbol=stock_code, start_date=start_date, end_date=end_date, adjust="hfq")
            if stock_df.empty:
                print(stock_df)
                continue
            
            # 确保数据按日期排序
            stock_df['date'] = pd.to_datetime(stock_df['date'])
            stock_df = stock_df.sort_values('date')
            stock_df = stock_df[['date', 'close']]

            filename = f"{stock_code}_daily_hfq.parquet"
            file_size = os.path.getsize(filename) / (1024 )
            print(f" {filename}, 原先大小: {file_size:.2f} KB {datetime.now()}")
            
            old_df = pd.read_parquet(filename)
            combined_df = pd.concat([stock_df, old_df], ignore_index=True)
            combined_df.to_parquet(filename, index=False, compression='snappy')
    
            file_size = os.path.getsize(filename) / (1024)
            print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} KB {datetime.now()}")
        except Exception as e:
            print(f"获取股票 {stock_code} 数据时出错: {e}")
            continue

def save_index_prices():
    #index_list = ['510300', '513500', '518880']
    index_list = ['000300', '000852']
    for symbol in index_list:
        try:
            filename = f"sh{symbol}_index_daily.parquet"
            df = ak.stock_zh_index_daily(f"sh{symbol}")

            #df = pd.read_parquet(filename)
            #df.to_parquet(filename, index=False, compression='snappy')
            print(df)
            file_size = os.path.getsize(filename) / 1024
            print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} KB {datetime.now()}")
        except Exception as e:
            print(f"获取指数 {symbol} 数据时出错: {e}")
            continue

def save_fund_peices():
    index_list = ['513500', '159915', '510300', '518880', '513100', '000852', '000300', '399300']
    for symbol in index_list:
        if not symbol == '399300':
            continue
        try:
            df = ak.fund_etf_hist_em(symbol=symbol,period="daily",adjust='qfq')
            filename = f"{symbol}_index_daily.parquet"
            #df = pd.read_parquet(filename)
            print(df)

            new_df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume'
            })
            print(new_df)
            new_df.to_parquet(filename, index=False, compression='snappy')
            file_size = os.path.getsize(filename) / 1024
            print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} KB {datetime.now()}")
            
        except Exception as e:
            print(f"{e}")
            continue

#save_daily_prices()
#save_index_prices()
save_fund_peices()
exit()

filename = f"sh513500_index_daily.parquet"
df = pd.read_parquet(filename)
print(df[1980:2010])

filename = f"513500_index_daily.parquet"
df = pd.read_parquet(filename)
print(df[1980:2010])

#filename = f"sh513500_index_daily.parquet"
#df = pd.read_parquet(filename)
#print(df[1950:2010])