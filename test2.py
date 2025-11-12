import akshare as ak

import pandas as pd
from datetime import datetime

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
stock_financial_abstract_df = ak.stock_financial_abstract("600519")
indictor = ak.stock_fhps_detail_em("600519")
#print(stock_financial_abstract_df)
print(indictor)
#listing_date = get_stock_listing_date(symbol)
#print(f"{symbol} 上市日期: {listing_date}")
