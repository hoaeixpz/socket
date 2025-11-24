import akshare as ak
import json
import time
import pandas as pd
from datetime import datetime
from financial_data import FinancialData

stock_data = FinancialData()

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
  bankai = ak.stock_board_industry_name_em()
  codes = []
  for index, row in bankai.iterrows():
    for col in bankai.columns:
      if col == "板块名称":
        print(row[col])
        codes.append(row[col])

  stock_dict = {}
  count = 0
  for code in codes:
    print(code)
    count = count + 1
    if count < 16:
      continue
    stocks = ak.stock_board_industry_cons_em(code)
    for index, row in stocks.iterrows():
      for col in stocks.columns:
        if col == "代码":
          stock_dict[row[col]] = code
    with open('industry.json', 'w', encoding='utf-8') as f:
      json.dump(stock_dict, f, ensure_ascii=False, indent=2)
    print(stock_dict)
    print("sleep 300s")
    time.sleep(300)

        
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

# 使用示例
symbol = "000001"  # 平安银行
#test_stock_individual_basic_info_xq(symbol)
test_stock_board_industry_name_em()
#test_stock_board_industry_summary_ths()
listing_date = get_stock_listing_date(symbol)
print(f"{symbol} 上市日期: {listing_date}")
exit()
#df = ak.stock_yjbb_em("20121231")
#print(df)

#stock_financial_abstract_df = ak.stock_financial_abstract("600519")
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

df = ak.stock_financial_analysis_indicator(symbol, "2012")
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

