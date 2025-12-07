import akshare as ak
import datetime
from financial_data import FinancialData
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 创建全局实例
stock_data = FinancialData()


def check_profit(profits):
	#检查季度数据是否连续，有无断档
	#并返回每个季度的净利润增量
	today, last_p = profits[0]
	last_month = int(today[4:6])
	last_year = int(today[0:4])

	result = True
	profit_list = []
	profit_list.append(last_p)
	year_profits = []
	year_profits.append(profit_list)
	for date, p in profits[1:]:
		year = int(date[0:4])
		if year != last_year:
			year_profits.append([])
			year_profits[-1].append(p)
		else:
			year_profits[-1].append(p)
		last_year = year

		month = int(date[4:6])
		#print(last_month, month)
		if not (last_month == 3 and month == 12):
			if last_month - month != 3:
				result = False
				break

		last_month = month

	profits_diff = []
	for profit_list in  year_profits:
		if len(profit_list) > 1:
			last_profit = profit_list[0]
			for profit in profit_list[1:]:
				profits_diff.append(last_profit - profit)
				last_profit = profit
			profits_diff.append(profit_list[-1])

	profits_diff = profits_diff[0:-1]
	'''
	print(profits_diff)
	
	X = list(range(len(profits_diff),0,-1))
	plt.scatter(X, profits_diff, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
	plt.show()
	'''
	return result, profits_diff


def get_last_12_quater_indiator(stock_code, target_date, indiator = "净利润"):
	df = stock_data.get_indicator_data(stock_code, indiator)
	date_columns = []
	for col in df.columns:
		# 检查列名是否为日期格式（YYYYMMDD）
		if isinstance(col, str) and col.isdigit() and len(col) == 8:
			date_columns.append(col)

	recent_date_columns = []
	target_dt = pd.to_datetime(target_date, format='%Y%m%d')
	for date_col in date_columns:
		date = pd.to_datetime(date_col, format='%Y%m%d')
		if (date < target_dt):
			recent_date_columns.append(date_col)	
			if len(recent_date_columns) == 14:
				break

	if len(recent_date_columns) < 14:
		print(f"警告：{stock_code} 不满14个季度数据")
		return None
	
	values = []
	for date_col in recent_date_columns:
		if date_col in df.columns:
			value = df[date_col].iloc[0] / 1000000  # 取第一行的数据
			values.append((date_col, value))

	return values

def cal_SUE(stock_code, target_date):
	#获取前12个季度的净利润数据，
	#来估算下当前季度的差额收益因子SUE

	last_profit = get_last_12_quater_indiator(stock_code, target_date)
	if last_profit is None:
		return None
	valid, quater_profit = check_profit(last_profit)
	if valid is False:
		print(f"{stock_code} 近12个季度数据出现断档")
		print(last_profit)
		return None

	#print(last_profit)
	current_profit = quater_profit[0]
	profit_Y2Y = []
	for i in range(1,9):
		profit_Y2Y.append(quater_profit[i] - quater_profit[i+4])

	mean_Y2Y = np.mean(profit_Y2Y)
	se = np.std(profit_Y2Y, ddof=1)
	estimate_profit = quater_profit[4] + mean_Y2Y
	#print(f"estimate_profit {estimate_profit} {quater_profit[4]}")

	SUE = (current_profit - estimate_profit) / se
	#print(f"SUE {SUE}")

	'''
	X = list(range(0, len(profit_Y2Y)))
	plt.scatter(X, profit_Y2Y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
	plt.show()
	'''
	return SUE

def test():
	cal_SUE("000001", "20241122")

#test()