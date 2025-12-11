import akshare as ak
import tushare as ts
import json
import time
import pandas as pd
import random
import os
import pickle
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from financial_data import FinancialData
import efinance as ef

#from test_proxy import HybridProxyCrawler

stock_data = FinancialData()
pro = ts.pro_api()

def get_stock_listing_date(symbol):
    """
    获取股票的上市日期
    """
    try:
        # 获取股票基本信息
       stock_info = ak.stock_individual_info_em(symbol=symbol)
       print(stock_info)
       # 查找上市日期信息
       for index, row in stock_info.iterrows():
           if '上市时间' in str(row['item']) or 'listing date' in str(row['item']).lower():
               listing_date = row['value']
               # 转换为datetime对象
               if len(str(listing_date)) == 8:
                   return (str(listing_date))
               return None
    except Exception as e:
        print(f"获取{symbol}上市日期失败: {e}")
    return None

def test_stock_individual_basic_info_xq(symbol):
  df = ak.stock_individual_basic_info_xq(symbol)
  print(df)

def test_stock_board_industry_name_em():
  '''
  crawler = HybridProxyCrawler()
  use_proxy = crawler.setup_session()
  bankai = ak.stock_board_industry_name_em()
  codes = []
  for index, row in bankai.iterrows():
    for col in bankai.columns:
      if col == "板块名称":
        print(row[col])
        codes.append(row[col])
  '''

  all_codes = set()
  with open('industry_list.txt', 'r', encoding='utf-8') as file:
    for line in file:
      value = line.strip()  # 去除换行符和空白字符
      if value:  # 避免空行
        all_codes.add(value)
  print(all_codes)

  stock_dict = {}
  with open('industry.json', 'r', encoding='utf-8') as f:
    stock_dict = json.load(f)
  
  code_set = set(stock_dict.values())
  print(code_set)

  for code in all_codes:
    print(code)
    if code in code_set:
      print(f"{code} in set")
      continue
    
    #use_proxy = crawler.setup_session()
    stocks = ak.stock_board_industry_cons_em(code)
    for index, row in stocks.iterrows():
      for col in stocks.columns:
        if col == "代码":
          print(row[col])
          stock_dict[row[col]] = code
    with open('industry.json', 'w', encoding='utf-8') as f:
      json.dump(stock_dict, f, ensure_ascii=False, indent=2)
    randNum = random.randint(0,6)
    t = randNum * 50 + random.uniform(20, 30)
    print(f"sleep {t/60} min")
    time.sleep(t)
    break

        
  #print(stock_dict['000001'])

def test_stock_board_industry_summary_ths():
  ths_industries = ak.stock_board_industry_summary_ths()
  codes = []
  for index, row in ths_industries.iterrows():
    for col in ths_industries.columns:
      if col == "板块":
        #print(row[col])
        codes.append(row[col])

  stock_dict = {}
  for code in codes:
    stocks = ak.stock_board_industry_cons_ths(code)
    print(stocks.head())
    for index, row in stocks.iterrows():
      for col in stocks.columns:
        if col == "代码":
          stock_dict[row[col]] = code
    break

def test_sz_index(symbol):
  '''
  df = ak.stock_zh_index_daily(f"sh{symbol}")
  filename = f"stock_price/sh{symbol}_index_daily.parquet"
  df.to_parquet(filename, index=False, compression='snappy')
    
  file_size = os.path.getsize(filename) / (1024 * 1024)
  print(f"Parquet数据已保存到 {filename}, 大小: {file_size:.2f} MB {datetime.now()}")
  '''
  index_file = f"stock_price/sh{symbol}_index_daily.parquet"
  df = pd.read_parquet(index_file)
  return df

  '''
  cache_file = f"stock_price/sz000001_index_daily.pkl"
  with open(cache_file, 'wb') as f:
    pickle.dump(df, f)
    
    file_size = os.path.getsize(cache_file) / (1024 * 1024)
    print(f"💾 股票列表已缓存到: {cache_file} 大小 {file_size:.2f} MB")
  '''

def test_get_price():
  #df = ak.stock_zh_a_daily("sh510300", start_date="20201201", end_date="20210406", adjust = 'hfq')
  #df = ak.stock_zh_index_daily("sh510300")
  #df = ak.stock_zh_index_daily("sh511260")
  #df = ak.stock_zh_index_daily("sh511010")
  #df = ak.stock_zh_index_daily("sh518800")
  #test_sz_index("510300")
  #test_sz_index("511260")
  #test_sz_index("511010")
  #test_sz_index("518800")
  print(test_sz_index("510300"))
  print(test_sz_index("511260"))
  print(test_sz_index("511010"))
  print(test_sz_index("510300"))
  
  # 首先需要获取基金的唯一代码，通常为6位数字
  #fund_code = '160416'  # 请替换为“华安标普全球石油指数”的正确代码
  #df = ef.fund.get_quote_history(fund_code)
  #df = ak.stock_zh_index_daily("sh160416​")
  #print(df)


# 使用示例
symbol = "600180"  # 平安银行
#test_sz_index()
test_get_price()
exit()
#test_stock_individual_basic_info_xq(symbol)
#test_stock_board_industry_name_em()
#test_stock_board_industry_summary_ths()
#listing_date = get_stock_listing_date(symbol)
#print(f"{symbol} 上市日期: {listing_date}")
#exit()
#df = ak.stock_yjbb_em("20121231")
#print(df)

#stock_financial_abstract_df = ak.stock_financial_abstract("600519")
'''
indictor = ak.stock_fhps_detail_em(symbol)
for index, row in indictor.iterrows():
  for col in indictor.columns:
    if col == "报告期" or col == "总股本":
      print(col, " ",row[col])
#print(stock_financial_abstract_df)

df = ak.stock_individual_info_em(symbol)
#print(df)

for index, row in df.iterrows():
  for col in df.columns:
    print(row[col])

for index, row in df.iterrows():
  for col in df.columns:
    if row[col] == "上市时间":
      print(type(col))
      print(row['value'])
'''
df = stock_data.get_financial_data(symbol)
for index,row in df.iterrows():
  if "每股收益" in row['指标']:
    print(row['指标'])
    for col in df.columns:
      if col[4:6] == "12":
        print(col, " ", row[col])
#print(df)

#df = ak.stock_zh_a_hist(symbol)
#print(df)

df = ak.stock_financial_analysis_indicator(symbol, "2010")
#print(df)
for index,row in df.iterrows():
  if str(row['日期'])[5:7] == "12":
    for col in df.columns:
      if "每股收益" in col:
        print(str(row['日期']), col, " ", row[col])
'''
df = ak.stock_financial_abstract("000001")
print(df)
for row in range (0,79):
  for col in df.columns:
    if col == "指标" or col == "20221231":
      print(df.loc[row, col])
'''

