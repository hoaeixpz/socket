import akshare as ak
import pandas as pd
from typing import Optional, Dict, List, Any
import warnings
warnings.filterwarnings('ignore')
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务摘要数据收集器
使用 stock_financial_abstract 财务数据
财务数据格式为
index 
	0	  选项		 指标		 20250930			20250630	  ......
	1   常用指标	 归母净利润	 6.462675e+10
	2   常用指标	 营业总成本
	3   常用指标	  ......
	4   常用指标	  .......
   ..   .......
   ..
   78   营运能力  流动资产周转天数
   79   营运能力   应付账款周转率


建立一个class FinancialData，支持获取特定指标的数据
"""

class FinancialData:
	def __init__(self):
		self.data_cache = {}  # 缓存股票数据：{symbol: dataframe}
		self.fetched_symbols = set()  # 记录已经获取过数据的股票代码

	def get_financial_data(self, symbol: str) -> Optional[pd.DataFrame]:
		"""
		获取指定股票的财务数据，如果已缓存则直接返回缓存数据
		
		Parameters:
		-----------
		symbol : str
			股票代码，如 '000001'
			
		Returns:
		--------
		pd.DataFrame or None
			财务数据DataFrame，获取失败返回None
		"""
		# 检查股票代码格式
		if not symbol or not isinstance(symbol, str):
			print(f"错误：股票代码格式不正确: {symbol}")
			return None
			
		# 如果数据已在缓存中，直接返回
		if symbol in self.data_cache:
			print(f"从缓存中获取 {symbol} 的财务数据")
			return self.data_cache[symbol]
		
		try:
			print(f"正在获取 {symbol} 的财务数据...")
			# 调用akshare接口获取财务摘要数据
			df = ak.stock_financial_abstract(symbol=symbol)
			
			if df is None or df.empty:
				print(f"警告：未获取到 {symbol} 的财务数据")
				return None
			
			# 缓存数据
			self.data_cache[symbol] = df
			self.fetched_symbols.add(symbol)
			
			print(f"成功获取 {symbol} 的财务数据，共 {len(df)} 行")
			return df
			
		except Exception as e:
			print(f"获取 {symbol} 财务数据时出错: {e}")
			return None

	def get_indicator_data(self, symbol: str, indicator: str) -> Optional[pd.DataFrame]:
		"""
		获取某个指标的完整数据（保留列名）
		
		Parameters:
		-----------
		symbol : str
		    股票代码
		indicator : str
			指标名称，如 '基本每股收益'
		
		Returns:
		--------
		pd.DataFrame
		单行数据的DataFrame，保留所有列名
		"""
		df = self.get_financial_data(symbol)
		if df is None:
			return None

		row = 0
		index_list = {}
		if '指标' in df.columns:
			for idx, value in df['指标'].items():
				if indicator == value:
					row = idx

		print(df.iloc[[row]])
		return df.iloc[[row]]



	def get_indicator_value(self, symbol: str, indicator: str, 
						  date: Optional[str] = None) -> Optional[float]:
		"""
		获取指定股票、指标和日期的数值
		
		Parameters:
		-----------
		symbol : str
			股票代码
		indicator : str
			指标名称，如 '基本每股收益'
		date : str, optional
			日期字符串，格式如 '2023-12-31'，如果为None则返回最新数据
			
		Returns:
		--------
		float or None
			指标数值，如果找不到返回None
		"""
		# 获取或加载数据
		df = self.get_financial_data(symbol)
		if df is None:
			return None

		#print(df)
		index_list = {}
		if '指标' in df.columns:
			for idx, value in df['指标'].items():
				index_list[idx] = value

		# 遍历DataFrame的列（日期）
		for column in df.columns:
			try:
				if isinstance(column, (int, str)) and len(str(column)) == 8:
					date_str = str(column)
					year = int(date_str[:4])
					month = int(date_str[5:6])

					input_year = int(date[:4])
					input_month = int(date[5:6])
					#print(f"year month:  {input_year}, {input_month}")

					
					# 筛选近几年的数据
					if year == input_year and month == input_month:
						period_data = df[column]
						for idx, value in period_data.items():
							if index_list[idx] == indicator:
								return value
						
			except Exception as e:
				print("获取indicator_value失败")
				continue

	def get_indicator_list(self, symbol: str, p : bool = False):
		'''
		return 指标列表
		'''
		df = self.get_financial_data(symbol)
		if df is None:
			return None

		if p:
			if '指标' in df.columns:
				for idx, value in df['指标'].items():
					print(value)
		return df['指标']

# 使用示例
if __name__ == "__main__":
	# 创建实例
	stock_data = FinancialData()
	
	# 示例1：获取单只股票的单个指标
	print("示例1：获取基本每股收益")
	eps = stock_data.get_indicator_value("000001", "净利润", "20250330")
	print(f"结果: {eps}\n")

	stock_data.get_indicator_data("000001", "基本每股收益")
	#stock_data.get_indicator_list("000001", True)