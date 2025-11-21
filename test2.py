import akshare as ak

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

# 使用示例
symbol = "000001"  # 平安银行
#stock_financial_abstract_df = ak.stock_financial_abstract("600519")
#indictor = ak.stock_fhps_detail_em("600519")
#print(stock_financial_abstract_df)
#print(indictor)
df = ak.stock_individual_info_em(symbol)
print(df)
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
#listing_date = get_stock_listing_date(symbol)
#print(f"{symbol} 上市日期: {listing_date}")
