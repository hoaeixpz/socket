#coding:gbk
# -*- coding: utf-8 -*-
"""
超简版定时交易策略
"""
import time
from datetime import datetime, timedelta
from typing import Dict
import math
import re
import os
import numpy as np

ETF_POOL = [
	"513100.SH", "513520.SH", "513030.SH",  # 境外: 纳指, 日经, 德国
	"518880.SH", "159980.SZ", "159985.SZ",  # 商品: 黄金, 有色, 豆粕
	"501018.SH", "511090.SH", "513130.SH",  # 原油, 30年国债, 恒生科技
	"515980.SH"                             # 人工智能
]
SAFE_ETF = '511220.SH'  # 城投债

print(f"当前工作目录: {os.getcwd()}")
import sys
print(sys.version_info)
print(sys.version)
print("===============================")

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class Tee:
	"""将输出同时写入终端和日志文件"""
	def __init__(self, log_file_path):
		#self.terminal = sys.__stdout__      # 保留原始控制台输出流
		self.log = open(log_file_path, 'a', encoding='utf-8')  # 追加模式

	def write(self, message):
		#self.terminal.write(message)                  # 打印到控制台
		clean_message = ansi_escape.sub('', message)  # 去除颜色代码
		self.log.write(clean_message)                 # 写入日志文件
		self.log.flush()                              # 实时写入磁盘

	def flush(self):
		try:
			#self.terminal.flush()
			self.log.flush()
		except ValueError:
			pass

	def close(self):
		self.log.close()
		
log_name = datetime.now().strftime('%Y%m%d-%H%M')

tee = Tee(f"D:\\stock\\test_stock\\socket\\QMT\\code\\logfiles\\{log_name}.log")
sys.stdout = tee


class G():
	pass
g = G() #创建空的类的实例 用来保存委托状态

# 动量策略索引 / 小市值策略索引
MOM_IDX = 0
SC_IDX = 1

# ================================================================
# 工具函数（共用）
# ================================================================

def sleep_sec(seconds):
	time.sleep(seconds)

def sleep_mins(minutes):
	m = minutes * 60 + 1
	print("sleep ", m)
	time.sleep(m)

def get_current_date(ContextInfo):
	current_time = ContextInfo.get_bar_timetag(ContextInfo.barpos)
	ctstr = timetag_to_datetime(current_time, "%Y-%m-%d %H%M%S")
	date = datetime.strptime(ctstr, "%Y-%m-%d %H%M%S")
	return date

def is_trading_day(ContextInfo):

	today = datetime.now().strftime('%Y%m%d')
    #dates = get_trading_dates('399101.SZ', today)
	current_date = get_current_date(ContextInfo)
	dt_str = current_date.strftime('%Y%m%d')
	last_date = ContextInfo.get_trading_dates('000300.SH', '', dt_str, 1, '1d')
	return today == last_date

def is_weekday_job(ContextInfo):
	current_date = get_current_date(ContextInfo)
	for day in range(1, g.weekday + 1):
		yesterday = current_date - timedelta(days=day)
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = ContextInfo.get_trading_dates('000300.SH', '', dt_str, 1, '1d')
		last_date = last_date[0]

		if day < g.weekday:
			if last_date != dt_str:
				return False
		else:
			if last_date != dt_str:
				if (current_date.weekday() + 1) != g.weekday:
					print(f'{current_date} 是周{current_date.weekday() + 1}')
				return True
	return False

def get_last_price(ContextInfo, stock):
	full_tick_dict = ContextInfo.get_full_tick([stock])
	for key, price in full_tick_dict.items():

		if price['lastPrice'] == 0:
			print(stock, " 获取当前价格异常,股价为0")
		return price['lastPrice']

	print(stock, " 获取当前价格异常")
	return None

def get_positions(ContextInfo):
	positions = {}
	objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
	for obj in objlist:
		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		pos = {}
		pos['total_amount'] = obj.m_nVolume
		pos['value'] = obj.m_dMarketValue
		pos['price'] = obj.m_dSettlementPrice
		pos['avg_cost'] = obj.m_dOpenPrice
		pos['canuse_amount'] = obj.m_nCanUseVolume
		positions[stock] = pos

	return positions

def get_current_holding_stocks(ContextInfo):
	current_holdings = []
	#print("get_current_holding_stocks")
	objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
	for obj in objlist:
		if obj.m_nVolume == 0:
			continue
		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		#print(stock)
		if stock in g.positions[MOM_IDX]:
			continue
		current_holdings.append(stock)

	return current_holdings

def get_specified_date_price(ContextInfo, stock, query_date, type='none'):
	dt_str = query_date.strftime('%Y%m%d%H%M%S')
	price_data=ContextInfo.get_market_data_ex(['close'], 
											[stock], 
											period='1m', 
											start_time='',
											end_time=dt_str, 
											count=1,
											dividend_type=type, 
											fill_data=True,
											subscribe=True)
	for key, price in price_data.items():
		if not price.empty:
			return price.iloc[0]['close']
		else:
			return float('nan')

def is_limit_up(ContextInfo, stock):
	#今日是否已经涨停
	current_price = get_last_price(ContextInfo, stock)
	if current_price is None or current_price == 0:
		return False

	detail = ContextInfo.get_instrumentdetail(stock)
	limit_up_price = detail["UpStopPrice"]
	if math.isnan(limit_up_price) or limit_up_price is None:
		return False

	if current_price >= limit_up_price:
		return True

	return False

def is_limit_down(ContextInfo, stock):
	#今日是否已经跌停
	current_price = get_last_price(ContextInfo, stock)
	if current_price is None or current_price == 0:
		return False

	detail = ContextInfo.get_instrumentdetail(stock)
	limit_down_price = detail['DownStopPrice']
	if math.isnan(limit_down_price) or limit_down_price is None:
		return False

	if current_price <= limit_down_price:
		return True

	return False

def is_specified_date_limit_up(ContextInfo, stock, query_date):
	current_price = get_specified_date_price(ContextInfo, stock, query_date, 'front')
	if math.isnan(current_price):
		return False

	yesterday = query_date - timedelta(days=1)
	query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
	prev_price = get_specified_date_price(ContextInfo, stock, query_date, 'front')
	if math.isnan(prev_price):
		return False

	limit_up_price = prev_price * 1.099
	if current_price >= limit_up_price:
		return True

	return False

def get_sw2_industry(ContextInfo):
	# 获取股票对应的申万二级行业
	positions = get_positions(ContextInfo)
	if len(positions) > 0:
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			clean_stock = stock[:6]
			print(clean_stock, " ", stock_name)

def get_market(ContextInfo, stock_list, query_date):
	"""获取股票总市值"""
	guben = {}
	#print("get_market")
	#print(stock_list)
	for stock in stock_list:
		info = ContextInfo.get_instrumentdetail(stock)
		#print(stock, " 市值 ", info['TotalVolumn'])
		guben[stock] = info['TotalVolumn']
	
	price_data = ContextInfo.get_full_tick(stock_list)
    #dt_str = query_date.strftime('%Y%m%d%H%M%S')
	#price_data=ContextInfo.get_market_data_ex(['close'], stock_list, period='5m', start_time='', end_time=dt_str, count=1,dividend_type='none',fill_data=True,subscribe=True)
	#print(price_data)
	market = {}
	for key, price in price_data.items():
		gb = guben[key]
		value = price['lastPrice']
		#value = price.iloc[0]['close']
		#print(gb, " ", value)
		if gb is None or math.isnan(gb) or math.isnan(value):
			continue
		market[key] = gb * value

	return market

def init(ContextInfo):
	print("init — 双策略合并版")
	period = ContextInfo.period
	print(period)
	ContextInfo.account = '8885388757'
	ContextInfo.set_account(ContextInfo.account)
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	available_cash = account_info[0].m_dAvailable

	# ===== 多策略配置 =====
	g.portfolio_value_proportion = [0.001, 0.999]
	# 每个策略的预留现金（买卖驱动），互相隔离
	g.cash_reserved = {MOM_IDX: g.portfolio_value_proportion[MOM_IDX] * available_cash,
					   SC_IDX: g.portfolio_value_proportion[SC_IDX] * available_cash}
	#记录上一交易日现金
	g.cash_record = g.cash_reserved.copy()
	# 各策略持仓股票集合，初始化时扫描已有持仓归入对应策略
	g.positions = {MOM_IDX: set(), SC_IDX: set()}
	objlist = get_trade_detail_data(ContextInfo.account, 'STOCK', 'POSITION')
	for obj in objlist:
		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		if stock in ETF_POOL:
			g.positions[MOM_IDX].add(stock)
		else:
			g.positions[SC_IDX].add(stock)

	# ===== 小市值全局变量 =====
	g.stock_pool = []
	g.selected_stocks = []
	g.stocks_to_buy = []
	g.stocks_to_sell = []
	g.stocks_fail_sell = []
	g.hold_list = []
	g.limitup_stocks = []
	g.yesterday_HL_list = []  #昨日涨停股票
	g.today_HL_list = []      #今日上午涨停股票
	g.excepted_position = {}
	g.position_step = 0.00
	g.reason_to_sell = ''
	g.refresh_hold = False
	g.trade = True
	g.is_trading_day = True
	g.stock_num = 9  # 每月持有的股票数量 9
	g.weekday = 2  #每周二调仓
	g.trade_day = False
	g.each_cash = available_cash / g.stock_num
	g.last_pos_value = account_info[0].m_dBalance
	g.sell_done = False
	g.run_stoploss = True
	g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
	g.stoploss_limit = 0.1  # 止损线
	g.stoploss_market = 0.05  # 市场趋势止损参数
	g.stoploss_map = {}    #记录止损股票，3日内该股票不再买入
	g.etf = '511880.SH'  # 空仓月份持有银华日利ETF
	g.all_weather_list = [  "518880.SH",  #黄金ETF
							"511220.SH",  #城投ETF
							"513100.SH",  #纳指ETF
							"512890.SH"]  #红利低波ETF

	g.count = 0

	# 初始化行业映射
    #print("初始化申万二级行业映射...")
    #g.industry_dict = get_sw2_industry()
    g.industry_dict = {'002065.SZ': 'IT服务', '002195.SZ': 'IT服务', '002229.SZ': 'IT服务', '002232.SZ': 'IT服务', '002331.SZ': 'IT服务', '002368.SZ': 'IT服务', '002373.SZ': 'IT服务', '002380.SZ': 'IT服务', '002401.SZ': 'IT服务', '002421.SZ': 'IT服务', '002474.SZ': 'IT服务', '002609.SZ': 'IT服务', '002642.SZ': 'IT服务', '002649.SZ': 'IT服务', '002657.SZ': 'IT服务', '002771.SZ': 'IT服务', '002777.SZ': 'IT服务', '002908.SZ': 'IT服务', '003005.SZ': 'IT服务', '002177.SZ': '一般零售', '002187.SZ': '一般零售', '002251.SZ': '一般零售', '002277.SZ': '一般零售', '002344.SZ': '一般零售', '002356.SZ': '一般零售', '002419.SZ': '一般零售', '002561.SZ': '一般零售', '002697.SZ': '一般零售', '002818.SZ': '一般零售', '002051.SZ': '专业工程', '002116.SZ': '专业工程', '002135.SZ': '专业工程', '002140.SZ': '专业工程', '002323.SZ': '专业工程', '002469.SZ': '专业工程', '002541.SZ': '专业工程', '002542.SZ': '专业工程', '002593.SZ': '专业工程', '002743.SZ': '专业工程', '003001.SZ': '专业工程', '002057.SZ': '专业服务', '002243.SZ': '专业服务', '002967.SZ': '专业服务', '003008.SZ': '专业服务', '002416.SZ': '专业连锁', '002006.SZ': '专用设备', '002009.SZ': '专用设备', '002021.SZ': '专用设备', '002031.SZ': '专用设备', '002073.SZ': '专用设备', '002204.SZ': '专用设备', '002209.SZ': '专用设备', '002278.SZ': '专用设备', '002337.SZ': '专用设备', '002353.SZ': '专用设备', '002367.SZ': '专用设备', '002483.SZ': '专用设备', '002490.SZ': '专用设备', '002523.SZ': '专用设备', '002526.SZ': '专用设备', '002527.SZ': '专用设备', '002529.SZ': '专用设备', '002530.SZ': '专用设备', '002535.SZ': '专用设备', '002564.SZ': '专用设备', '002595.SZ': '专用设备', '002611.SZ': '专用设备', '002667.SZ': '专用设备', '002689.SZ': '专用设备', '002690.SZ': '专用设备', '002691.SZ': '专用设备', '002722.SZ': '专用设备', '002730.SZ': '专用设备', '002757.SZ': '专用设备', '002774.SZ': '专用设备', '002779.SZ': '专用设备', '002786.SZ': '专用设备', '002816.SZ': '专用设备', '002833.SZ': '专用设备', '002837.SZ': '专用设备', '002890.SZ': '专用设备', '002960.SZ': '专用设备', '003036.SZ': '专用设备', '002511.SZ': '个护用品', '003006.SZ': '个护用品', '002082.SZ': '中药', '002107.SZ': '中药', '002198.SZ': '中药', '002275.SZ': '中药', '002287.SZ': '中药', '002317.SZ': '中药', '002349.SZ': '中药', '002390.SZ': '中药', '002412.SZ': '中药', '002424.SZ': '中药', '002566.SZ': '中药', '002603.SZ': '中药', '002644.SZ': '中药', '002728.SZ': '中药', '002737.SZ': '中药', '002864.SZ': '中药', '002873.SZ': '中药', '002907.SZ': '中药', '002594.SZ': '乘用车', '002024.SZ': '互联网电商', '002127.SZ': '互联网电商', '002315.SZ': '互联网电商', '002640.SZ': '互联网电商', '002803.SZ': '互联网电商', '003010.SZ': '互联网电商', '002557.SZ': '休闲食品', '002582.SZ': '休闲食品', '002695.SZ': '休闲食品', '002719.SZ': '休闲食品', '002820.SZ': '休闲食品', '002847.SZ': '休闲食品', '002956.SZ': '休闲食品', '002991.SZ': '休闲食品', '003000.SZ': '休闲食品', '002858.SZ': '体育', '002134.SZ': '元件', '002138.SZ': '元件', '002141.SZ': '元件', '002199.SZ': '元件', '002384.SZ': '元件', '002436.SZ': '元件', '002463.SZ': '元件', '002484.SZ': '元件', '002552.SZ': '元件', '002579.SZ': '元件', '002636.SZ': '元件', '002815.SZ': '元件', '002913.SZ': '元件', '002916.SZ': '元件', '002938.SZ': '元件', '002056.SZ': '光伏设备', '002079.SZ': '光伏设备', '002129.SZ': '光伏设备', '002150.SZ': '光伏设备', '002459.SZ': '光伏设备', '002506.SZ': '光伏设备', '002623.SZ': '光伏设备', '002865.SZ': '光伏设备', '003022.SZ': '光伏设备', '002036.SZ': '光学光电子', '002106.SZ': '光学光电子', '002137.SZ': '光学光电子', '002217.SZ': '光学光电子', '002222.SZ': '光学光电子', '002273.SZ': '光学光电子', '002289.SZ': '光学光电子', '002387.SZ': '光学光电子', '002449.SZ': '光学光电子', '002456.SZ': '光学光电子', '002587.SZ': '光学光电子', '002654.SZ': '光学光电子', '002745.SZ': '光学光电子', '002845.SZ': '光学光电子', '002876.SZ': '光学光电子', '002952.SZ': '光学光电子', '002955.SZ': '光学光电子', '002962.SZ': '光学光电子', '002983.SZ': '光学光电子', '002992.SZ': '光学光电子', '003015.SZ': '光学光电子', '003019.SZ': '光学光电子', '002614.SZ': '其他家电', '002130.SZ': '其他电子', '002161.SZ': '其他电子', '002388.SZ': '其他电子', '002729.SZ': '其他电子', '002782.SZ': '其他电子', '002859.SZ': '其他电子', '002885.SZ': '其他电子', '002922.SZ': '其他电子', '002052.SZ': '其他电源设备', '002227.SZ': '其他电源设备', '002255.SZ': '其他电源设备', '002335.SZ': '其他电源设备', '002364.SZ': '其他电源设备', '002366.SZ': '其他电源设备', '002518.SZ': '其他电源设备', '002534.SZ': '其他电源设备', '002630.SZ': '其他电源设备', '002851.SZ': '其他电源设备', '002951.SZ': '其他电源设备', '002124.SZ': '养殖业', '002157.SZ': '养殖业', '002234.SZ': '养殖业', '002299.SZ': '养殖业', '002321.SZ': '养殖业', '002458.SZ': '养殖业', '002714.SZ': '养殖业', '002746.SZ': '养殖业', '002982.SZ': '养殖业', '002025.SZ': '军工电子', '002151.SZ': '军工电子', '002179.SZ': '军工电子', '002189.SZ': '军工电子', '002214.SZ': '军工电子', '002338.SZ': '军工电子', '002383.SZ': '军工电子', '002413.SZ': '军工电子', '002414.SZ': '军工电子', '002446.SZ': '军工电子', '002465.SZ': '军工电子', '002935.SZ': '军工电子', '002977.SZ': '军工电子', '002556.SZ': '农业综合', '002086.SZ': '农产品加工', '002286.SZ': '农产品加工', '002481.SZ': '农产品加工', '002852.SZ': '农产品加工', '003030.SZ': '农产品加工', '002170.SZ': '农化制品', '002250.SZ': '农化制品', '002258.SZ': '农化制品', '002312.SZ': '农化制品', '002391.SZ': '农化制品', '002470.SZ': '农化制品', '002496.SZ': '农化制品', '002513.SZ': '农化制品', '002538.SZ': '农化制品', '002539.SZ': '农化制品', '002545.SZ': '农化制品', '002588.SZ': '农化制品', '002734.SZ': '农化制品', '002749.SZ': '农化制品', '002758.SZ': '农化制品', '002895.SZ': '农化制品', '002942.SZ': '农化制品', '002999.SZ': '农化制品', '002807.SZ': '农商行', '002839.SZ': '农商行', '002958.SZ': '农商行', '002181.SZ': '出版', '002688.SZ': '动物保健', '002868.SZ': '动物保健', '002014.SZ': '包装印刷', '002117.SZ': '包装印刷', '002191.SZ': '包装印刷', '002228.SZ': '包装印刷', '002303.SZ': '包装印刷', '002374.SZ': '包装印刷', '002565.SZ': '包装印刷', '002599.SZ': '包装印刷', '002701.SZ': '包装印刷', '002735.SZ': '包装印刷', '002752.SZ': '包装印刷', '002787.SZ': '包装印刷', '002799.SZ': '包装印刷', '002831.SZ': '包装印刷', '002836.SZ': '包装印刷', '002846.SZ': '包装印刷', '002969.SZ': '包装印刷', '003003.SZ': '包装印刷', '003018.SZ': '包装印刷', '002094.SZ': '化妆品', '002001.SZ': '化学制品', '002037.SZ': '化学制品', '002054.SZ': '化学制品', '002096.SZ': '化学制品', '002165.SZ': '化学制品', '002166.SZ': '化学制品', '002211.SZ': '化学制品', '002226.SZ': '化学制品', '002246.SZ': '化学制品', '002319.SZ': '化学制品', '002326.SZ': '化学制品', '002360.SZ': '化学制品', '002407.SZ': '化学制品', '002430.SZ': '化学制品', '002440.SZ': '化学制品', '002453.SZ': '化学制品', '002455.SZ': '化学制品', '002497.SZ': '化学制品', '002549.SZ': '化学制品', '002562.SZ': '化学制品', '002591.SZ': '化学制品', '002597.SZ': '化学制品', '002637.SZ': '化学制品', '002666.SZ': '化学制品', '002669.SZ': '化学制品', '002683.SZ': '化学制品', '002783.SZ': '化学制品', '002802.SZ': '化学制品', '002809.SZ': '化学制品', '002810.SZ': '化学制品', '002827.SZ': '化学制品', '002909.SZ': '化学制品', '002915.SZ': '化学制品', '002917.SZ': '化学制品', '002971.SZ': '化学制品', '003002.SZ': '化学制品', '002004.SZ': '化学制药', '002019.SZ': '化学制药', '002020.SZ': '化学制药', '002038.SZ': '化学制药', '002099.SZ': '化学制药', '002102.SZ': '化学制药', '002262.SZ': '化学制药', '002294.SZ': '化学制药', '002332.SZ': '化学制药', '002365.SZ': '化学制药', '002370.SZ': '化学制药', '002393.SZ': '化学制药', '002399.SZ': '化学制药', '002422.SZ': '化学制药', '002437.SZ': '化学制药', '002550.SZ': '化学制药', '002653.SZ': '化学制药', '002675.SZ': '化学制药', '002693.SZ': '化学制药', '002742.SZ': '化学制药', '002755.SZ': '化学制药', '002793.SZ': '化学制药', '002817.SZ': '化学制药', '002826.SZ': '化学制药', '002872.SZ': '化学制药', '002900.SZ': '化学制药', '002923.SZ': '化学制药', '002940.SZ': '化学制药', '003020.SZ': '化学制药', '002092.SZ': '化学原料', '002109.SZ': '化学原料', '002136.SZ': '化学原料', '002145.SZ': '化学原料', '002274.SZ': '化学原料', '002386.SZ': '化学原料', '002601.SZ': '化学原料', '002648.SZ': '化学原料', '002748.SZ': '化学原料', '003017.SZ': '化学原料', '002064.SZ': '化学纤维', '002206.SZ': '化学纤维', '002254.SZ': '化学纤维', '002427.SZ': '化学纤维', '002998.SZ': '化学纤维', '002022.SZ': '医疗器械', '002030.SZ': '医疗器械', '002223.SZ': '医疗器械', '002382.SZ': '医疗器械', '002432.SZ': '医疗器械', '002551.SZ': '医疗器械', '002901.SZ': '医疗器械', '002932.SZ': '医疗器械', '002950.SZ': '医疗器械', '002044.SZ': '医疗服务', '002172.SZ': '医疗服务', '002173.SZ': '医疗服务', '002219.SZ': '医疗服务', '002524.SZ': '医疗服务', '002622.SZ': '医疗服务', '002821.SZ': '医疗服务', '002462.SZ': '医药商业', '002589.SZ': '医药商业', '002727.SZ': '医药商业', '002788.SZ': '医药商业', '002049.SZ': '半导体', '002077.SZ': '半导体', '002119.SZ': '半导体', '002156.SZ': '半导体', '002185.SZ': '半导体', '002213.SZ': '半导体', '002371.SZ': '半导体', '002409.SZ': '半导体', '003026.SZ': '半导体', '002035.SZ': '厨卫电器', '002508.SZ': '厨卫电器', '002543.SZ': '厨卫电器', '002677.SZ': '厨卫电器', '002519.SZ': '地面兵装', '002142.SZ': '城商行', '002936.SZ': '城商行', '002948.SZ': '城商行', '002966.SZ': '城商行', '002060.SZ': '基础建设', '002061.SZ': '基础建设', '002062.SZ': '基础建设', '002200.SZ': '基础建设', '002307.SZ': '基础建设', '002431.SZ': '基础建设', '002586.SZ': '基础建设', '002628.SZ': '基础建设', '002663.SZ': '基础建设', '002717.SZ': '基础建设', '002775.SZ': '基础建设', '002941.SZ': '基础建设', '002108.SZ': '塑料', '002263.SZ': '塑料', '002324.SZ': '塑料', '002361.SZ': '塑料', '002395.SZ': '塑料', '002522.SZ': '塑料', '002585.SZ': '塑料', '002632.SZ': '塑料', '002768.SZ': '塑料', '002825.SZ': '塑料', '002838.SZ': '塑料', '002886.SZ': '塑料', '002423.SZ': '多元金融', '002647.SZ': '多元金融', '002961.SZ': '多元金融', '002084.SZ': '家居用品', '002162.SZ': '家居用品', '002489.SZ': '家居用品', '002571.SZ': '家居用品', '002572.SZ': '家居用品', '002615.SZ': '家居用品', '002631.SZ': '家居用品', '002790.SZ': '家居用品', '002798.SZ': '家居用品', '002853.SZ': '家居用品', '002918.SZ': '家居用品', '003011.SZ': '家居用品', '003012.SZ': '家居用品', '002011.SZ': '家电零部件', '002050.SZ': '家电零部件', '002290.SZ': '家电零部件', '002418.SZ': '家电零部件', '002676.SZ': '家电零部件', '002860.SZ': '家电零部件', '003028.SZ': '家电零部件', '002005.SZ': '小家电', '002032.SZ': '小家电', '002242.SZ': '小家电', '002403.SZ': '小家电', '002705.SZ': '小家电', '002959.SZ': '小家电', '003023.SZ': '小家电', '002149.SZ': '小金属', '002167.SZ': '小金属', '002182.SZ': '小金属', '002378.SZ': '小金属', '002428.SZ': '小金属', '002738.SZ': '小金属', '002842.SZ': '小金属', '002978.SZ': '小金属', '002114.SZ': '工业金属', '002160.SZ': '工业金属', '002171.SZ': '工业金属', '002203.SZ': '工业金属', '002295.SZ': '工业金属', '002379.SZ': '工业金属', '002501.SZ': '工业金属', '002532.SZ': '工业金属', '002540.SZ': '工业金属', '002578.SZ': '工业金属', '002824.SZ': '工业金属', '002988.SZ': '工业金属', '002996.SZ': '工业金属', '003038.SZ': '工业金属', '002883.SZ': '工程咨询服务', '002949.SZ': '工程咨询服务', '003013.SZ': '工程咨询服务', '002097.SZ': '工程机械', '002685.SZ': '工程机械', '002027.SZ': '广告营销', '002264.SZ': '广告营销', '002291.SZ': '广告营销', '002354.SZ': '广告营销', '002400.SZ': '广告营销', '002712.SZ': '广告营销', '002878.SZ': '广告营销', '002995.SZ': '广告营销', '002292.SZ': '影视院线', '002343.SZ': '影视院线', '002739.SZ': '影视院线', '002905.SZ': '影视院线', '002016.SZ': '房地产开发', '002133.SZ': '房地产开发', '002146.SZ': '房地产开发', '002208.SZ': '房地产开发', '002244.SZ': '房地产开发', '002305.SZ': '房地产开发', '002314.SZ': '房地产开发', '002188.SZ': '房地产服务', '002285.SZ': '房地产服务', '002968.SZ': '房地产服务', '002761.SZ': '房屋建设', '002105.SZ': '摩托车及其他', '003033.SZ': '摩托车及其他', '002093.SZ': '教育', '002607.SZ': '教育', '002659.SZ': '教育', '003032.SZ': '教育', '002095.SZ': '数字媒体', '002103.SZ': '文娱用品', '002301.SZ': '文娱用品', '002348.SZ': '文娱用品', '002678.SZ': '文娱用品', '002862.SZ': '文娱用品', '002899.SZ': '文娱用品', '002033.SZ': '旅游及景区', '002059.SZ': '旅游及景区', '002159.SZ': '旅游及景区', '002627.SZ': '旅游及景区', '002707.SZ': '旅游及景区', '002110.SZ': '普钢', '002029.SZ': '服装家纺', '002154.SZ': '服装家纺', '002193.SZ': '服装家纺', '002269.SZ': '服装家纺', '002293.SZ': '服装家纺', '002327.SZ': '服装家纺', '002397.SZ': '服装家纺', '002404.SZ': '服装家纺', '002486.SZ': '服装家纺', '002494.SZ': '服装家纺', '002563.SZ': '服装家纺', '002569.SZ': '服装家纺', '002612.SZ': '服装家纺', '002634.SZ': '服装家纺', '002656.SZ': '服装家纺', '002687.SZ': '服装家纺', '002762.SZ': '服装家纺', '002763.SZ': '服装家纺', '002780.SZ': '服装家纺', '002832.SZ': '服装家纺', '002875.SZ': '服装家纺', '003016.SZ': '服装家纺', '002679.SZ': '林业', '002068.SZ': '橡胶', '002224.SZ': '橡胶', '002381.SZ': '橡胶', '002442.SZ': '橡胶', '002753.SZ': '橡胶', '002205.SZ': '水泥', '002233.SZ': '水泥', '002302.SZ': '水泥', '002596.SZ': '水泥', '002671.SZ': '水泥', '003037.SZ': '水泥', '002048.SZ': '汽车零部件', '002085.SZ': '汽车零部件', '002101.SZ': '汽车零部件', '002126.SZ': '汽车零部件', '002190.SZ': '汽车零部件', '002239.SZ': '汽车零部件', '002265.SZ': '汽车零部件', '002283.SZ': '汽车零部件', '002284.SZ': '汽车零部件', '002328.SZ': '汽车零部件', '002355.SZ': '汽车零部件', '002363.SZ': '汽车零部件', '002406.SZ': '汽车零部件', '002434.SZ': '汽车零部件', '002448.SZ': '汽车零部件', '002454.SZ': '汽车零部件', '002472.SZ': '汽车零部件', '002488.SZ': '汽车零部件', '002510.SZ': '汽车零部件', '002516.SZ': '汽车零部件', '002536.SZ': '汽车零部件', '002537.SZ': '汽车零部件', '002547.SZ': '汽车零部件', '002553.SZ': '汽车零部件', '002590.SZ': '汽车零部件', '002592.SZ': '汽车零部件', '002662.SZ': '汽车零部件', '002664.SZ': '汽车零部件', '002703.SZ': '汽车零部件', '002708.SZ': '汽车零部件', '002715.SZ': '汽车零部件', '002725.SZ': '汽车零部件', '002765.SZ': '汽车零部件', '002766.SZ': '汽车零部件', '002806.SZ': '汽车零部件', '002813.SZ': '汽车零部件', '002863.SZ': '汽车零部件', '002870.SZ': '汽车零部件', '002906.SZ': '汽车零部件', '002921.SZ': '汽车零部件', '002937.SZ': '汽车零部件', '002965.SZ': '汽车零部件', '002976.SZ': '汽车零部件', '002984.SZ': '汽车零部件', '002997.SZ': '汽车零部件', '002207.SZ': '油服工程', '002554.SZ': '油服工程', '002629.SZ': '油服工程', '002828.SZ': '油服工程', '002045.SZ': '消费电子', '002055.SZ': '消费电子', '002139.SZ': '消费电子', '002241.SZ': '消费电子', '002351.SZ': '消费电子', '002369.SZ': '消费电子', '002402.SZ': '消费电子', '002426.SZ': '消费电子', '002475.SZ': '消费电子', '002600.SZ': '消费电子', '002635.SZ': '消费电子', '002655.SZ': '消费电子', '002660.SZ': '消费电子', '002681.SZ': '消费电子', '002841.SZ': '消费电子', '002855.SZ': '消费电子', '002861.SZ': '消费电子', '002866.SZ': '消费电子', '002888.SZ': '消费电子', '002925.SZ': '消费电子', '002947.SZ': '消费电子', '002981.SZ': '消费电子', '002993.SZ': '消费电子', '002069.SZ': '渔业', '002174.SZ': '游戏', '002425.SZ': '游戏', '002517.SZ': '游戏', '002555.SZ': '游戏', '002558.SZ': '游戏', '002602.SZ': '游戏', '002605.SZ': '游戏', '002624.SZ': '游戏', '002919.SZ': '游戏', '002221.SZ': '炼化及贸易', '002377.SZ': '炼化及贸易', '002408.SZ': '炼化及贸易', '002476.SZ': '炼化及贸易', '002493.SZ': '炼化及贸易', '002986.SZ': '炼化及贸易', '002128.SZ': '煤炭开采', '002076.SZ': '照明设备', '002638.SZ': '照明设备', '002723.SZ': '照明设备', '002724.SZ': '照明设备', '002259.SZ': '燃气', '002267.SZ': '燃气', '002700.SZ': '燃气', '002911.SZ': '燃气', '002010.SZ': '物流', '002120.SZ': '物流', '002352.SZ': '物流', '002468.SZ': '物流', '002485.SZ': '物流', '002492.SZ': '物流', '002682.SZ': '物流', '002769.SZ': '物流', '002800.SZ': '物流', '002889.SZ': '物流', '002930.SZ': '物流', '002075.SZ': '特钢', '002318.SZ': '特钢', '002443.SZ': '特钢', '002478.SZ': '特钢', '002645.SZ': '环保设备', '002658.SZ': '环保设备', '002034.SZ': '环境治理', '002210.SZ': '环境治理', '002266.SZ': '环境治理', '002573.SZ': '环境治理', '002672.SZ': '环境治理', '002778.SZ': '环境治理', '002887.SZ': '环境治理', '002973.SZ': '环境治理', '003027.SZ': '环境治理', '003039.SZ': '环境治理', '002080.SZ': '玻璃玻纤', '002201.SZ': '玻璃玻纤', '002613.SZ': '玻璃玻纤', '002007.SZ': '生物制品', '002252.SZ': '生物制品', '002581.SZ': '生物制品', '002773.SZ': '生物制品', '002880.SZ': '生物制品', '002015.SZ': '电力', '002039.SZ': '电力', '002053.SZ': '电力', '002218.SZ': '电力', '002256.SZ': '电力', '002310.SZ': '电力', '002479.SZ': '电力', '002480.SZ': '电力', '002608.SZ': '电力', '002616.SZ': '电力', '002617.SZ': '电力', '002893.SZ': '电力', '003035.SZ': '电力', '003816.SZ': '电力', '002584.SZ': '电子化学品', '002643.SZ': '电子化学品', '002741.SZ': '电子化学品', '002176.SZ': '电机', '002196.SZ': '电机', '002249.SZ': '电机', '002576.SZ': '电机', '002801.SZ': '电机', '002823.SZ': '电机', '002892.SZ': '电机', '003021.SZ': '电机', '002058.SZ': '电池', '002074.SZ': '电池', '002125.SZ': '电池', '002245.SZ': '电池', '002340.SZ': '电池', '002580.SZ': '电池', '002709.SZ': '电池', '002733.SZ': '电池', '002759.SZ': '电池', '002805.SZ': '电池', '002812.SZ': '电池', '002850.SZ': '电池', '002028.SZ': '电网设备', '002090.SZ': '电网设备', '002112.SZ': '电网设备', '002121.SZ': '电网设备', '002168.SZ': '电网设备', '002169.SZ': '电网设备', '002270.SZ': '电网设备', '002276.SZ': '电网设备', '002300.SZ': '电网设备', '002309.SZ': '电网设备', '002339.SZ': '电网设备', '002346.SZ': '电网设备', '002350.SZ': '电网设备', '002358.SZ': '电网设备', '002441.SZ': '电网设备', '002451.SZ': '电网设备', '002452.SZ': '电网设备', '002471.SZ': '电网设备', '002498.SZ': '电网设备', '002533.SZ': '电网设备', '002546.SZ': '电网设备', '002560.SZ': '电网设备', '002606.SZ': '电网设备', '002692.SZ': '电网设备', '002706.SZ': '电网设备', '002857.SZ': '电网设备', '002879.SZ': '电网设备', '002882.SZ': '电网设备', '002927.SZ': '电网设备', '002953.SZ': '电网设备', '002980.SZ': '电网设备', '002238.SZ': '电视广播', '002668.SZ': '白色家电', '002304.SZ': '白酒', '002646.SZ': '白酒', '002041.SZ': '种植业', '002215.SZ': '种植业', '002772.SZ': '种植业', '002003.SZ': '纺织制造', '002042.SZ': '纺织制造', '002083.SZ': '纺织制造', '002098.SZ': '纺织制造', '002144.SZ': '纺织制造', '002394.SZ': '纺织制造', '002674.SZ': '纺织制造', '002316.SZ': '综合', '002420.SZ': '综合', '002575.SZ': '综合', '002192.SZ': '能源金属', '002240.SZ': '能源金属', '002460.SZ': '能源金属', '002466.SZ': '能源金属', '002756.SZ': '能源金属', '002008.SZ': '自动化设备', '002184.SZ': '自动化设备', '002334.SZ': '自动化设备', '002698.SZ': '自动化设备', '002747.SZ': '自动化设备', '002957.SZ': '自动化设备', '002975.SZ': '自动化设备', '002979.SZ': '自动化设备', '002829.SZ': '航天装备', '003009.SZ': '航天装备', '002928.SZ': '航空机场', '002023.SZ': '航空装备', '002111.SZ': '航空装备', '002297.SZ': '航空装备', '002389.SZ': '航空装备', '002625.SZ': '航空装备', '002651.SZ': '航空装备', '002933.SZ': '航空装备', '002985.SZ': '航空装备', '002040.SZ': '航运港口', '002320.SZ': '航运港口', '002043.SZ': '装修建材', '002066.SZ': '装修建材', '002088.SZ': '装修建材', '002225.SZ': '装修建材', '002247.SZ': '装修建材', '002271.SZ': '装修建材', '002333.SZ': '装修建材', '002372.SZ': '装修建材', '002392.SZ': '装修建材', '002398.SZ': '装修建材', '002457.SZ': '装修建材', '002641.SZ': '装修建材', '002652.SZ': '装修建材', '002694.SZ': '装修建材', '002718.SZ': '装修建材', '002785.SZ': '装修建材', '002791.SZ': '装修建材', '002047.SZ': '装修装饰', '002081.SZ': '装修装饰', '002163.SZ': '装修装饰', '002375.SZ': '装修装饰', '002482.SZ': '装修装饰', '002620.SZ': '装修装饰', '002713.SZ': '装修装饰', '002789.SZ': '装修装饰', '002811.SZ': '装修装饰', '002822.SZ': '装修装饰', '002830.SZ': '装修装饰', '002856.SZ': '装修装饰', '002963.SZ': '装修装饰', '002989.SZ': '装修装饰', '002152.SZ': '计算机设备', '002180.SZ': '计算机设备', '002197.SZ': '计算机设备', '002236.SZ': '计算机设备', '002268.SZ': '计算机设备', '002376.SZ': '计算机设备', '002415.SZ': '计算机设备', '002512.SZ': '计算机设备', '002528.SZ': '计算机设备', '002577.SZ': '计算机设备', '002835.SZ': '计算机设备', '002869.SZ': '计算机设备', '002912.SZ': '计算机设备', '002970.SZ': '计算机设备', '002990.SZ': '计算机设备', '003004.SZ': '计算机设备', '002500.SZ': '证券', '002670.SZ': '证券', '002673.SZ': '证券', '002736.SZ': '证券', '002797.SZ': '证券', '002926.SZ': '证券', '002939.SZ': '证券', '002945.SZ': '证券', '002495.SZ': '调味发酵品', '002507.SZ': '调味发酵品', '002650.SZ': '调味发酵品', '002155.SZ': '贵金属', '002237.SZ': '贵金属', '002716.SZ': '贵金属', '002072.SZ': '贸易', '002091.SZ': '贸易', '002183.SZ': '贸易', '002972.SZ': '轨交设备', '002063.SZ': '软件开发', '002153.SZ': '软件开发', '002178.SZ': '软件开发', '002212.SZ': '软件开发', '002230.SZ': '软件开发', '002253.SZ': '软件开发', '002261.SZ': '软件开发', '002279.SZ': '软件开发', '002298.SZ': '软件开发', '002322.SZ': '软件开发', '002362.SZ': '软件开发', '002405.SZ': '软件开发', '002410.SZ': '软件开发', '002439.SZ': '软件开发', '002920.SZ': '软件开发', '002987.SZ': '软件开发', '003007.SZ': '软件开发', '003029.SZ': '软件开发', '002115.SZ': '通信服务', '002123.SZ': '通信服务', '002148.SZ': '通信服务', '002467.SZ': '通信服务', '002544.SZ': '通信服务', '002929.SZ': '通信服务', '002017.SZ': '通信设备', '002104.SZ': '通信设备', '002194.SZ': '通信设备', '002281.SZ': '通信设备', '002296.SZ': '通信设备', '002313.SZ': '通信设备', '002396.SZ': '通信设备', '002491.SZ': '通信设备', '002583.SZ': '通信设备', '002792.SZ': '通信设备', '002796.SZ': '通信设备', '002881.SZ': '通信设备', '002897.SZ': '通信设备', '002902.SZ': '通信设备', '003031.SZ': '通信设备', '003040.SZ': '通信设备', '002026.SZ': '通用设备', '002046.SZ': '通用设备', '002122.SZ': '通用设备', '002131.SZ': '通用设备', '002132.SZ': '通用设备', '002158.SZ': '通用设备', '002164.SZ': '通用设备', '002175.SZ': '通用设备', '002248.SZ': '通用设备', '002272.SZ': '通用设备', '002282.SZ': '通用设备', '002342.SZ': '通用设备', '002347.SZ': '通用设备', '002438.SZ': '通用设备', '002444.SZ': '通用设备', '002445.SZ': '通用设备', '002514.SZ': '通用设备', '002520.SZ': '通用设备', '002559.SZ': '通用设备', '002598.SZ': '通用设备', '002633.SZ': '通用设备', '002639.SZ': '通用设备', '002686.SZ': '通用设备', '002760.SZ': '通用设备', '002767.SZ': '通用设备', '002795.SZ': '通用设备', '002819.SZ': '通用设备', '002843.SZ': '通用设备', '002849.SZ': '通用设备', '002871.SZ': '通用设备', '002877.SZ': '通用设备', '002884.SZ': '通用设备', '002896.SZ': '通用设备', '002903.SZ': '通用设备', '002931.SZ': '通用设备', '002943.SZ': '通用设备', '003025.SZ': '通用设备', '002012.SZ': '造纸', '002067.SZ': '造纸', '002078.SZ': '造纸', '002235.SZ': '造纸', '002521.SZ': '造纸', '002186.SZ': '酒店餐饮', '002306.SZ': '酒店餐饮', '002357.SZ': '铁路公路', '002461.SZ': '非白酒', '002568.SZ': '非白酒', '002202.SZ': '风电设备', '002487.SZ': '风电设备', '002531.SZ': '风电设备', '002216.SZ': '食品加工', '002330.SZ': '食品加工', '002515.SZ': '食品加工', '002626.SZ': '食品加工', '002661.SZ': '食品加工', '002702.SZ': '食品加工', '002726.SZ': '食品加工', '002840.SZ': '食品加工', '002329.SZ': '饮料乳品', '002570.SZ': '饮料乳品', '002732.SZ': '饮料乳品', '002910.SZ': '饮料乳品', '002946.SZ': '饮料乳品', '002345.SZ': '饰品', '002574.SZ': '饰品', '002721.SZ': '饰品', '002731.SZ': '饰品', '002867.SZ': '饰品', '002100.SZ': '饲料', '002311.SZ': '饲料', '002385.SZ': '饲料', '002548.SZ': '饲料', '002567.SZ': '饲料', '002696.SZ': '饲料', '002891.SZ': '饲料', '002429.SZ': '黑色家电', '002848.SZ': '黑色家电'}
    #print(f"行业映射完成，共 {len(g.industry_dict)} 只股票")

	m_ratio = g.portfolio_value_proportion[MOM_IDX] * 100
	s_ratio = g.portfolio_value_proportion[SC_IDX] * 100
	print(f"双策略初始化完成: 动量{m_ratio}% + 小市值{s_ratio}%\033[0m")
	print(f"  初始资产 {g.last_pos_value:.2f}, 可用资金 {available_cash:.2f}")

	info_position(ContextInfo)

def handlebar(ContextInfo):
	if not ContextInfo.is_last_bar():
		return
		#pass

	if not ContextInfo.is_new_bar():
		return
		
	# 获取当前K线的时间戳
	# 将时间戳转换为可读的日期时间对象，这里需要根据QMT API具体函数来操作
	# 假设有一个函数 timetag_to_datetime 用于转换
	dt = get_current_date(ContextInfo)
	#print(dt)

	if dt.hour == 9 and dt.minute == 31:
		judge_date(ContextInfo)
		prepare_stock_list(ContextInfo)

	if dt.hour == 9 and dt.minute == 35:
		trade_etf(ContextInfo)

	if dt.hour == 9 and dt.minute == 55 and is_weekday_job(ContextInfo):
		rebalance_sell(ContextInfo)

	if dt.hour == 10 and dt.minute == 15:
		stop_loss(ContextInfo)

	if dt.hour == 10 and dt.minute == 30 and is_weekday_job(ContextInfo):
		if g.sell_done:
			rebalance_buy(ContextInfo)
		else:
			print(f"今日({dt})非调仓日，不执行操作")

	if dt.hour == 11 and dt.minute == 0:
		mom_rebalance(ContextInfo)


	if dt.hour == 14 and dt.minute == 10:
		trade_afternoon(ContextInfo)


	if dt.hour == 15 and dt.minute == 0:
		#objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
		#for obj in objlist:
		#	print_hold_stock_info(obj)
		after_trading_end(ContextInfo)

	'''
	#TEST
	if dt.hour == 15 and dt.minute == 0:
		judge_date(ContextInfo)
		trade_etf(ContextInfo)
	'''

# ================================================================
# 下单函数
# ================================================================
# passorder(opType, orderType, accountid, orderCode, prType, modelprice, volume
# opType    : 23 买入 ，24 卖出
# orderType : 1102 按价格买卖
# accountid : ContextInfo.account 账号
# orderCode : stock 股票代码
# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
# modelprice: 如果prType是11，填指定价格，不是填任意值
# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按目标价值买卖 、 为3，按百分比买卖
# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整


def calc_commission(value):
	#手续费，按万二算，不满5元按5元算
	commission = value * 2 / 10000
	if commission < 5:
		return 5
	return commission

def calc_sell_tax(value, stock):
	#卖出印花税，按万五算
	if stock in ETF_POOL:
		#ETF 卖出不收印花税
		return 0

	tax = value * 5 / 10000
	return tax

def sell_target_value(ContextInfo, stock, target_value, strat_idx=None):
	positions = get_positions(ContextInfo)
	for stock_code, pos in positions:
		if stock_code != stock:
			continue

		if pos is None or pos['total_amount'] == 0:
			print(f'{stock} 没有持仓，无法卖出')
			break

		if target_value == 0 and not is_limit_down(ContextInfo, stock):
			passorder(24,					# opType    : 23 买入 ，24 卖出
					1101,					# orderType : 1101 按股数买卖
					ContextInfo.account,	# accountid : ContextInfo.account 账号
					stock,					# orderCode : stock 股票代码
					6,						# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
					-1,						# modelprice: 如果prType是11，填指定价格，不是填任意值
					pos['total_amount'],	# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按目标价值买卖 、 为3，按百分比买卖
					'',
					2,						# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整
					f'清仓{stock}',
					ContextInfo
			)
		else:
			volume = pos['value'] - target_value
			if volume > 0:
				current_price = get_last_price(ContextInfo, stock)
				amount = int(volume / current_price / 100) * 100
				if amount < 100:
					print(f"{stock} {ContextInfo.get_stock_name(stock)} 现价{current_price:.2f} 期望持仓 {target_value:.2f}元,")
					print(f"现有持仓 {pos['value']:.2f}元，相差 {volume:.2f}元，需要卖出股数 {volume / current_price:.2f}不足100股，放弃交易")
				else:
					passorder(24,				# opType    : 23 买入 ，24 卖出
						1102,					# orderType : 1102 按价格买卖
						ContextInfo.account,	# accountid : ContextInfo.account 账号
						stock, 					# orderCode : stock 股票代码
						6, 						# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
						-1, 					# modelprice: 如果prType是11，填指定价格，不是填任意值
						volume, 				# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按目标价值买卖 、 为3，按百分比买卖
						2, 						# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整
						ContextInfo
					)

					print(f"sell {stock} passorder target value {target_value:.2f} current {pos['value']:.2f} volume {volume:.2f} @{current_price:.2f}")
		break

	if strat_idx is not None and not is_limit_down(ContextInfo, stock):
		# 卖出成功，现金回血
		commission = calc_commission(pos['value'] - target_value)
		tax = calc_sell_tax(pos['value'] - target_value, stock)
		cash_incr = pos['value'] - target_value - commission - tax
		g.cash_reserved[strat_idx] += cash_incr
		print(f"卖出 {stock} 手续费 {commission}，印花税 {tax}")
		if target_value == 0:
			g.positions[strat_idx].discard(stock)
			print(f"成功清仓 {stock} 后，策略{strat_idx} 增加资金{cash_incr:.2f}, 现有资金为 {g.cash_reserved[strat_idx]:.2f}")
		else:
			print(f"成功卖出 {stock} 后，策略{strat_idx} 增加资金{cash_incr:.2f}, 现有资金为 {g.cash_reserved[strat_idx]:.2f}")

	#order_target_value(stock, target_value, 'BUY1', ContextInfo, ContextInfo.account)

def buy_target_value(ContextInfo, stock, target_value, strat_idx=None):
	current_value = 0
	positions = get_positions(ContextInfo)
	pos = positions.get(stock)
	if pos is not None:
		current_value = pos['value']

	volume = target_value - current_value
	# 策略账面资金限额
	if strat_idx is not None:
		volume = min(volume, get_strategy_available_cash(strat_idx))

	if volume > 0:
		passorder(23,					# opType    : 23 买入 ，24 卖出
				1102,					# orderType : 1102 按价格买卖
				ContextInfo.account, 	# accountid : ContextInfo.account 账号
				stock, 					# orderCode : stock 股票代码
				4, 						# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
				-1, 					# modelprice: 如果prType是11，填指定价格，不是填任意值
				volume, 				# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按目标价值买卖 、 为3，按百分比买卖
				2, 						# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整
				ContextInfo
		)

		print(f"buy {stock} passorder target value {target_value:.2f} current {current_value:.2f} volume {volume:.2f}")

	if strat_idx is not None and volume > 0:
		commission = calc_commission(volume)
		g.cash_reserved[strat_idx] -= (volume + commission)
		g.positions[strat_idx].add(stock)
		print(f"成功买入 {stock} 后，策略{strat_idx} 现有资金 {g.cash_reserved[strat_idx]:.2f}")
	#order_target_value(stock, target_value + current_price * 10, 'SALE1', ContextInfo, ContextInfo.account)

def buy_target_shares(ContextInfo, stock, target_share, strat_idx=None):
	current_price = get_last_price(ContextInfo, stock)
	if not current_price:
		return
	
	
	passorder(23,						# opType    : 23 买入 ，24 卖出
			1101, 						# orderType : 1101 按股数买卖
			ContextInfo.account, 		# accountid : ContextInfo.account 账号
			stock, 						# orderCode : stock 股票代码
			6, 							# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
			-1, 						# modelprice: 如果prType是11，填指定价格，不是填任意值
			target_share, 				# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按价值买卖 、 为3，按百分比买卖
			2, 							# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整
			ContextInfo)
	print(f"buy {stock} {amount}股 @ {current_price:.2f}")
	
	if strat_idx is not None:
		if current_price:
			estimate_cash = target_share * current_price
			commission = calc_commission(estimate_cash)
			g.cash_reserved[strat_idx] -= (estimate_cash + commission)
			g.positions[strat_idx].add(stock)
			print(f"成功买入 {stock}，策略{strat_idx} 现有资金 {g.cash_reserved[strat_idx]:.2f}")


def order_callback(ContextInfo, orderInfo):
	print("order_callback")
	print_order_info(orderInfo)
	'''
	if get_entrust_status_str(orderInfo.m_nOrderStatus) == '废单':
		if orderInfo.m_nOffsetFlag == 49:
			stock = obj.m_strInstrumentID + '.' + obj.m_strInstrumentName
			g.stocks_fail_sell.append(stock)
	'''
	#print('委托更新 id ', orderInfo.m_strOrderSysID)
	#print('股票:', orderInfo.m_strInstrumentID, ' ', orderInfo.m_strInstrumentName)
	#print(f"方向: {'买入' if orderInfo.m_nDirection == 48 else '卖出'}")

def deal_callback(ContextInfo, dealInfo):
	print("deal_callback")
	buy_sell_str = '买入' if dealInfo.m_nOffsetFlag == 48 else '卖出'
	#print(f"{buy_sell_str} {dealInfo.m_strInstrumentID} {dealInfo.m_nVolume} 股 * {dealInfo.m_dPrice:.2f} 元, 成交额 {dealInfo.m_dTradeAmount}, 手续费{dealInfo.m_dComssion}")

	if buy_sell_str == '买入':
		print(f'实际买入 {dealInfo.m_strInstrumentID} {dealInfo.m_nVolume}股，每股{dealInfo.m_dPrice}元，合计:{dealInfo.m_dTradeAmount:.2f}, 手续费{dealInfo.m_dComssion:.2f}')

	if buy_sell_str == '卖出':
		if dealInfo.m_strRemark == 'qingkong':
			print(f'卖出 {dealInfo.m_strInstrumentID} {dealInfo.m_nVolume}股 * {dealInfo.m_dPrice:.2f}元')

# ================================================================
# 动量策略
# ================================================================

# 每只ETF的得分上限（基于2020-2026历史数据的P97分位，避免动量过热）
ETF_SHORT_MAX = {  # 短期(25天)上限
	"513100.SH": 3,  # 纳指ETF
	"513520.SH": 3,  # 日经ETF
	"513030.SH": 2,  # 德国ETF
	"518880.SH": 2,  # 黄金ETF
	"159980.SZ": 2,  # 有色ETF
	"159985.SZ": 3,  # 豆粕ETF
	"501018.SH": 9,  # 南方原油
	"511090.SH": 1,  # 30年国债ETF
	"513130.SH": 8,  # 恒生科技
	"515980.SH": 10,  # 人工智能
}
ETF_LONG_MAX = {  # 长期(250天)上限
	"513100.SH": 0.45,  # 纳指ETF
	"513520.SH": 0.45,  # 日经ETF
	"513030.SH": 0.45,  # 德国ETF
	"518880.SH": 0.5,  # 黄金ETF
	"159980.SZ": 0.45,  # 有色ETF
	"159985.SZ": 0.4,  # 豆粕ETF
	"501018.SH": 0.6,  # 南方原油
	"511090.SH": 0.2,  # 30年国债ETF
	"513130.SH": 0.5,  # 恒生科技
	"515980.SH": 0.8,  # 人工智能
}
ETF_DIP_MIN = {  # 近3日单日急跌过滤阈值（ratio = 1 - 跌幅%）
	"513100.SH": 0.95,  # 纳指ETF — 5%
	"513520.SH": 0.95,  # 日经ETF — 5%
	"513030.SH": 0.95,  # 德国ETF — 5%
	"518880.SH": 0.96,  # 黄金ETF — 4%
	"159980.SZ": 0.95,  # 有色ETF — 5%
	"159985.SZ": 0.97,  # 豆粕ETF — 3%
	"511090.SH": 0.98,  # 30年国债 — 2%
	"501018.SH": 0.94,  # 南方原油 — 6%
	"513130.SH": 0.94,  # 恒生科技 — 6%
	"515980.SH": 0.94,  # 人工智能 — 6%
}

def get_strategy_available_cash(strat_idx):
	"""策略剩余可用现金（直接返回预留现金）"""
	return max(0, g.cash_reserved[strat_idx])

def get_strategy_total(ContextInfo, strat_idx):
	"""策略当前实际总资产 = 预留现金 + 持仓市值（随市价波动）"""
	positions = get_positions(ContextInfo)
	holdings_value = 0
	for stock in g.positions[strat_idx]:
		if stock in positions:
			holdings_value += positions[stock]['value']
	return g.cash_reserved[strat_idx] + holdings_value

def calc_momentum_score(ContextInfo, etf, days):
	"""计算单只ETF的动量得分。返回 (annualized_return, r2, score, min_recent_ratio)"""

	# 获取历史数据
	dt_str = get_current_date(ContextInfo).strftime('%Y%m%d')
	down_history_data(etf, '1d', dt_str, "")
	history_data = ContextInfo.get_market_data_ex(['close'],
												[etf],
												period='1d',
												start_time='',
												end_time=dt_str,
												dividend_type='front',
												count=days+1)
	if etf not in history_data or history_data[etf].empty:
		return 0, 0, 0, 0

	df = history_data[etf]
	close_prices = df['close'].values
	prices = close_prices
	print(prices)

	# 对数价格加权线性回归
	y = np.log(prices)
	x = np.arange(len(y))
	weights = np.linspace(1, 2, len(y))

	slope, intercept = np.polyfit(x, y, 1, w=weights)

	# 年化收益率
	annualized_return = math.exp(slope * 250) - 1

	# 加权R²
	weighted_mean_y = np.average(y, weights=weights)
	ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
	ss_tot = np.sum(weights * (y - weighted_mean_y) ** 2)
	r2 = 1 - ss_res / ss_tot if ss_tot else 0

	# 得分
	score = annualized_return * abs(r2)

	recent_ratio = 10
	# 近3日急跌
	if len(prices) >= 4:
		recent_ratio = min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4])

	return annualized_return, r2, score, recent_ratio

def select_etf(ContextInfo):
	"""双动量选股：短期(25天) + 长期(250天)。

	返回: ETF代码列表（1只或2只）
	"""
	def filter_etf(max_score_map, days, label):
		print(f"\n========== [{label}] 开始 (窗口={days}天) ==========")
		results = {}
		for etf in ETF_POOL:
			ann_ret, r2, score, recent_ratio = calc_momentum_score(ContextInfo, etf, days)
			name = ContextInfo.get_stock_name(etf) or etf
			max_score = max_score_map.get(etf)
			dip_min = ETF_DIP_MIN.get(etf, 0.95)
			bad = (score <= 0 or score >= max_score) or recent_ratio < dip_min
			down_ratio = (1 - recent_ratio) * 100
			reason = ''
			if bad:
				reason += ' -> [淘汰]'
				if score >= max_score:
					reason += (f" 分数超出阈值{max_score}")
				if recent_ratio < dip_min:
					reason += (f" 跌幅超出阈值 {(1 - dip_min) * 100:.0f}%")

			print(f"  {name}({etf}): 年化={ann_ret:.4%} R²={r2:.4f} 近3日最大跌幅 {down_ratio:.2f}% 得分={score:.4f}{reason}")
			if not bad: results[etf] = score
		if not results:
			print(f"  无符合条件的ETF → 选用{ContextInfo.get_stock_name(SAFE_ETF)}({SAFE_ETF})")
			return SAFE_ETF
		selected = max(results, key=results.get)
		print(f"  >>> {label}最终选出: {ContextInfo.get_stock_name(selected)}({selected})")
		return selected

	etf1 = filter_etf(ETF_SHORT_MAX, 25, "短期动量")
	etf2 = filter_etf(ETF_LONG_MAX, 250, "长期动量")

	print(f"\n========== 选股汇总 ==========")
	print(f"  短期动量选出: {ContextInfo.get_stock_name(etf1)}({etf1})")
	print(f"  长期动量选出: {ContextInfo.get_stock_name(etf2)}({etf2})")

	print("-----------")
	print("  只买短期")
	print("-----------")
	return [etf1]

def mom_rebalance(ContextInfo):
	if not is_trading_day(ContextInfo):
		return

	print(f'\n========== [动量策略] 每日调仓 {get_current_date(ContextInfo)} ==========')

	# 选股
	targets = select_etf(ContextInfo)
	weights = {etf: 1.0 / len(targets) for etf in targets}

	# 获取总资产
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	info = account_info[0]
	total_value = info.m_dBalance
	strategy_budget = get_strategy_total(ContextInfo, MOM_IDX)
	print(f"  总资产： {total_value:,.2f}, 动量总资产: {strategy_budget:,.2f}")

	all_positions = get_positions(ContextInfo)
	# 只清仓策略持仓中不在目标里的ETF
	for stock in list(g.positions[MOM_IDX]):
		if stock not in weights:
			print(f"  [调出] {ContextInfo.get_stock_name(stock)}({stock}) → 清仓")
			if is_limit_up(ContextInfo, stock):
				print(f"  {ContextInfo.get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(ContextInfo, stock):
				print(f"  {ContextInfo.get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			sell_target_value(ContextInfo, stock, 0, MOM_IDX)
			print("sleep 30s")
			sleep_sec(30)
			strategy_budget = get_strategy_total(ContextInfo, MOM_IDX)
			print(f"  动量总资产更新: {strategy_budget:,.2f}")

	# 卖出超配
	for stock, weight in weights.items():
		target = strategy_budget * weight
		current_val = all_positions[stock]['value'] if stock in all_positions else 0
		price = get_last_price(ContextInfo, stock)
		if current_val - target > max(3000, price * 100 if price else 10000):
			print(f"  [减仓] {ContextInfo.get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			if is_limit_up(ContextInfo, stock):
				print(f"  {ContextInfo.get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(ContextInfo, stock):
				print(f"  {ContextInfo.get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			sell_target_value(ContextInfo, stock, target, MOM_IDX)
			print("sleep 30s")
			sleep_sec(30)
			strategy_budget = get_strategy_total(ContextInfo, MOM_IDX)
			print(f"  动量总资产更新: {strategy_budget:,.2f}")
		else:
			print(f"  [与目标差异太小，不减仓] {ContextInfo.get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")

	# 买入低配
	for stock, weight in weights.items():
		target = strategy_budget * weight
		current_val = all_positions[stock]['value'] if stock in all_positions else 0
		price = get_last_price(ContextInfo, stock)
		stra_avi_cash = get_strategy_available_cash(MOM_IDX)
		if min(target - current_val, stra_avi_cash) > max(3000, price * 100 if price else 10000):
			print(f"  [加仓] {ContextInfo.get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			if is_limit_up(ContextInfo, stock):
				print(f"  {ContextInfo.get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(ContextInfo, stock):
				print(f"  {ContextInfo.get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			buy_target_value(ContextInfo, stock, target, MOM_IDX)
		else:
			print(f"  [与目标差异太小，不加仓] {ContextInfo.get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f} 策略资金{stra_avi_cash:,.2f}")

	print(f'√========== [动量策略] 调仓结束 ==========\n')


# ================================================================
# 小市值策略（核心函数直接从 miniqmt_small_cap_0_1.py 移植）
# ================================================================

def small_cap_get_stock_industry(stock_list, num):
    #return stock_list[:num]
	"""行业分散选股"""
	try:
		selected_stocks = []
		industry_list = []

		for stock_code in stock_list:
			industry_name = get_industry_name_of_stock('SW', stock_code)
			print(stock_code, " ", industry_name)
			if industry_name != '':
				if industry_name not in industry_list:
					industry_list.append(industry_name)
					selected_stocks.append(stock_code)
					if len(industry_list) >= num:
						break
		return selected_stocks
	except Exception as e:
		print(f"行业筛选错误: {e}")
		return stock_list[:num]

def get_small_cap_stocks(ContextInfo, stock_list, query_date, n=5):
	#获取市值最小的n只股票（修正版：全局排序）
	# 用于存储所有查询到的市值数据
	market = get_market(ContextInfo, stock_list, query_date)
	#print('market')
	#print(market)
	sorted_market = dict(sorted(market.items(), key=lambda x:x[1], reverse=False))
	#print(sorted_market)
	#sorted_market = sorted_market[0:10]
	if n > 30:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[0:20]:
			stock_name = ContextInfo.get_stock_name(stock)
			cap_in_10k = round(cap/100000000.0, 2)
			rank = rank + 1
			marker = '  <== 选中' if rank <= n else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 市值: {cap_in_10k} 亿元{marker}')

	#selected_stocks = list(sorted_market)[0:n]
	# 取全局最小的N只股票
	selected_stocks = small_cap_get_stock_industry(list(sorted_market)[:100], n)

	flag = False
	for stock_code in selected_stocks:
		if stock_code not in g.selected_stocks:
			flag = True
			break

	if flag:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		str = ''
		for stock, cap in list(sorted_market.items())[:20]:
			stock_name = ContextInfo.get_stock_name(stock)
			cap_in_10k = round(cap/100000000.0, 2)
			industry_name = get_industry_name_of_stock('SW', stock)
			rank = rank + 1
			marker = '  <== 选中' if stock in selected_stocks else ''
			str += f'    第{rank:>2}名: {stock_name}({stock}), 市值: {cap_in_10k} 亿元 {industry_name} {marker}\n'
		print(str)

	return selected_stocks

def is_date_in_range(input_date_str, start_date_str, end_date_str, date_format = '%Y%m%d'):
	input_date = datetime.strptime(input_date_str, date_format).date()
	start_date = datetime.strptime(start_date_str, date_format).date()
	end_date = datetime.strptime(end_date_str, date_format).date()

	return start_date <= input_date <= end_date

def get_normal_stocks(ContextInfo, current_time):
	"""获取正常交易股票（过滤ST、停牌、涨跌停、退市）"""
	stock_index = '中小综指'
	stocklist = ContextInfo.get_stock_list_in_sector('中小综指')
	print(f"{current_time}")
	print(f"中小综指成分股数量：{len(stocklist)}")
	print(stocklist[:10])  # 打印前10只成分股

	non_st_stocks = []
	for stock in stocklist:
		ST = ContextInfo.get_his_st_data(stock)
		if ST:
			is_st = False
			for stkey, time_period in ST.items():
				for tp in time_period:
					if is_date_in_range(current_time, tp[0], tp[1]):
						#print(f"ST {stock}")
						is_st = True
						break
				if is_st:
					break
			if is_st:
				continue
		else:
			stock_name = ContextInfo.get_stock_name(stock)
			if "ST" in stock_name:
				#print(f"ST {stock}")
				continue

		non_st_stocks.append(stock)

	print(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
	print(f'去除科创版，北交所等，共有 {len(non_st_stocks)} 只股票')

	non_paused_stocks = filter_paused_stocks(ContextInfo, non_st_stocks)
	print(f'过滤停牌，涨跌停股票后，剩余 {len(non_paused_stocks)} 只')
	return non_paused_stocks
	
def filter_paused_stocks(ContextInfo, stock_list):
	trading_stocks = []
	
	if len(stock_list) == 0:
		return trading_stocks

	current_holdings = get_current_holding_stocks(ContextInfo)
	for stock in stock_list:
		info = ContextInfo.get_instrumentdetail(stock)
		if info['InstrumentID'] is None:
			print(f"{stock} 可能退市 {ContextInfo.get_stock_name(stock)}")
			continue
		if ContextInfo.is_suspended_stock(stock):
			print(f'{stock} 可能停牌 {ContextInfo.get_stock_name(stock)}')
			continue
		if stock not in current_holdings and is_limit_up(ContextInfo, stock):  # 涨停
			print(f'涨停 {stock} {ContextInfo.get_stock_name(stock)}')
			continue
		if stock not in current_holdings and is_limit_down(ContextInfo, stock):  # 跌停
			print(f'跌停 {stock} {ContextInfo.get_stock_name(stock)}')
			continue
		trading_stocks.append(stock)
	
	return trading_stocks




# ================================================================
# 小市值策略调度函数
# ================================================================

def judge_date(ContextInfo):
	g.is_trading_day = is_trading_day(ContextInfo)
	print(f'今天是交易日吗 {g.is_trading_day}')
	
	current_date = get_current_date(ContextInfo)
	current_month = current_date.month
	g.count = 1
	if current_month == 1 or current_month == 4:
		if g.trade:
			print(f'√========== 一月和四月份清仓，日期：{current_date} ==========')
		g.trade = False
	else:
		g.trade = True
	print('judge_date count ', g.count)

def prepare_stock_list(ContextInfo):
	if not g.is_trading_day:
		return
	#获取已持有列表
	g.count += 1
	g.hold_list = []
	g.limitup_stocks = []
	g.trade_day = False
	#获取已持有列表
	g.hold_list = get_current_holding_stocks(ContextInfo)

	# 获取昨日涨停列表
	current_date = get_current_date(ContextInfo)
	yesterday = current_date - timedelta(days=1)
	g.yesterday_HL_list = []
	g.today_HL_list = []

	for stock in g.hold_list:
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = ContextInfo.get_trading_dates(stock, '', dt_str, 1, '1d')
		last_date = last_date[0]
		query_date = datetime.strptime(last_date + '150000', '%Y%m%d%H%M%S')

		if is_specified_date_limit_up(ContextInfo, stock, query_date):
			g.yesterday_HL_list.append(stock)

	if g.yesterday_HL_list:
		print("")
		print(f"************昨日({yesterday})涨停 **************")
		print(g.yesterday_HL_list)
		print("")


	g.stock_pool = get_normal_stocks(ContextInfo, current_date.strftime('%Y%m%d'))
	g.stoploss_map = {k: v-1 for k, v in g.stoploss_map.items() if v-1 > 0}

	print('prepare_stock_list count ',g.count)

def collect_sell_buy_stocks(ContextInfo):
	"""对比选定股票与当前持仓，确定买卖清单"""
	g.stocks_to_sell = []
	g.stocks_to_buy = []
	current_holdings = get_current_holding_stocks(ContextInfo)
	for stock in current_holdings:
		if not is_limit_up(ContextInfo, stock):
			if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
				g.stocks_to_sell.append(stock)
		else:
			print(f"○ {stock} {ContextInfo.get_stock_name(stock)} 转为涨停股，今日不卖出。")
			g.today_HL_list.append(stock)

	for stock in g.selected_stocks:
		if (stock not in current_holdings) and (stock not in g.yesterday_HL_list):
			g.stocks_to_buy.append(stock)

def trade_etf(ContextInfo):
	if not g.is_trading_day:
		return
	if g.trade is False:
		print("trade_etf")
		current_holdings = get_current_holding_stocks(ContextInfo)
		all_weather = False
		for stock in current_holdings:
			if stock not in g.all_weather_list:
				all_weather = True
				break
		if len(current_holdings) == 0:
			all_weather = True

		if all_weather:
			print('使用全天候策略')
			g.selected_stocks = g.all_weather_list.copy()
			collect_sell_buy_stocks(ContextInfo)
			sell_stocks(ContextInfo)
			print("sleep 30s")
			sleep_sec(30)
			exec_all_weather(ContextInfo)

def exec_all_weather(ContextInfo):
	"""全天候ETF：-1/ES风险平价"""
	query_date = get_current_date(ContextInfo)
	yesterday = query_date - timedelta(days=200)
	dt_str = yesterday.strftime('%Y%m%d')
	#print(dt_str)
	for stock in g.all_weather_list:
		down_history_data(stock, '1d', dt_str, "")

	price_data = ContextInfo.get_market_data_ex(['close'], g.all_weather_list, start_time='', end_time=query_date.strftime('%Y%m%d'), period='1d', dividend_type='none', count=120)
	weights = {}
	
	for code, prices in price_data.items():
		print(code)
		if len(prices) < 120:
			weight = 0
		else:
			prices['daily_return'] = prices['close'].pct_change() * 100
			sorted_group = prices.sort_values(by='daily_return')
			ES = sorted_group['daily_return'].head(6).mean()
			print("ES ", ES)
			weight = -1 / ES
			
		weights[code] = weight
	print(f'权重:{weights}')
	
	# 标准化weight
	total_weight = sum([w for w in weights.values()])
	
	fin_weights = {key: value / total_weight for key, value in weights.items()}

	for stock, w in fin_weights.items():
		print(f'{stock} {ContextInfo.get_stock_name(stock)} 权重{100*w:.2f}%')

	available_cash = get_strategy_available_cash(SC_IDX)
	print('available_cash: ', available_cash)
	for stock in g.all_weather_list:
		current_price = get_last_price(ContextInfo, stock)
		if current_price is None or current_price == 0:
			continue
		print(stock, " ", current_price)
		target_value = available_cash * fin_weights[stock]
		amount = int(target_value / current_price / 100) * 100
		if amount > 0:
			print('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
			print(f'{stock} {ContextInfo.get_stock_name(stock)} 目标市值{target_value:.2f}, 买入{amount}股 * {current_price}元')
			buy_target_shares(ContextInfo, stock, amount, SC_IDX)
			g.refresh_hold = True

def rebalance_sell(ContextInfo):
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = get_current_date(ContextInfo)
	print(f'√========== [小市值策略] 周度调仓(卖出) {current_date} ==========')

	info_position(ContextInfo)
	#yesterday = current_date - timedelta(days=1)
	#query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
	query_date = current_date
	g.selected_stocks = get_small_cap_stocks(ContextInfo, g.stock_pool, query_date, g.stock_num)
	for stock in list(g.stoploss_map.keys()):
		if stock in g.selected_stocks:
			g.selected_stocks.remove(stock)
			print(f"{stock} {ContextInfo.get_stock_name(stock)} 前{3 - g.stoploss_map[stock]}日止损卖出，3日内不再买入")

	collect_sell_buy_stocks(ContextInfo)
	current_holdings = get_current_holding_stocks(ContextInfo)

	if g.stocks_to_buy or g.stocks_to_sell:
		print(f"√当前持股 {len(current_holdings)}只")
		current_holdings.sort()
		for stock in current_holdings:
			print(f"√{ContextInfo.get_stock_name(stock)}")
			
		print(f"√需要买入股票 {len(g.stocks_to_buy)}只")
		print(f"√需要卖出股票 {len(g.stocks_to_sell)}只")
		for stock in g.stocks_to_buy:
			print("√待买入 ", ContextInfo.get_stock_name(stock))
		for stock in g.stocks_to_sell:
			print('√待卖出: %s' % ContextInfo.get_stock_name(stock))
			
			
		print(f"√今日({current_date})为卖出时间，执行卖出操作")
		print('√------------------------------------------')
		# 执行卖出逻辑
		sell_stocks(ContextInfo)
		# 标记卖出已完成
		g.sell_done = True
		#log_selection_details(g.selected_stocks, prev_date)

	else:
		print('未选到符合条件的股票，本日不调仓')

	print('rebalance_sell count ',g.count)

def rebalance_buy(ContextInfo):
	if not g.sell_done:                     #卖出股票后才有钱买入
		return
	#止盈之后不再买入
	if g.reason_to_sell == 'takeprofit':
		return
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = get_current_date(ContextInfo)
	print(f'√========== 执行周度调仓，日期：{current_date} ==========')
	# 执行买入逻辑
	if g.stocks_to_buy:
		print(f"√今日({current_date})为买入时间，执行买入操作")
		print('√+++++++++++++++++++++++++++++++++++++++++')
		print(f"√需要买入股票 {len(g.stocks_to_buy)}只")
		for stock in g.stocks_to_buy:
			print(ContextInfo.get_stock_name(stock))

	calc_position(ContextInfo)
	buy_stocks(ContextInfo)
	# 重置卖出标记
	g.sell_done = False
	print("sleep 30s")
	sleep_sec(30)
	info_position(ContextInfo)
	print('rebalance_buy count ', g.count)

def calc_position(ContextInfo):
	CASH_YU = 5000

	strategy_total = get_strategy_total(ContextInfo, SC_IDX)
	current_holdings = get_current_holding_stocks(ContextInfo)
	holding_num = len(current_holdings) + len(g.stocks_to_buy)

	if  holding_num != len(g.selected_stocks):
		print(f'× × 股票数量异常，可能最终持仓{holding_num}只，实际选中{len(g.selected_stocks)}只')
		
	positions = get_positions(ContextInfo)
	fail_pos = 0
	for stock in g.stocks_fail_sell:
		fp = positions[stock]['value'] / strategy_total
		fail_pos += fp
		print(f'停牌股 {ContextInfo.get_stock_name(stock)} 占仓位比重为 {fp*100:.2f}%')
	HL_count = 0
	for stock in current_holdings:
		if (stock in g.yesterday_HL_list) or (stock in g.today_HL_list):
			fp = positions[stock]['value'] / strategy_total
			fail_pos += fp
			HL_count += 1
			print(f'涨停股 {ContextInfo.get_stock_name(stock)} 占仓位比重为 {fp*100:.2f}%')

	g.excepted_position = {}
	if holding_num - len(g.stocks_fail_sell) - HL_count <= 1:
		print("涨停股个数 ", HL_count)
		print("异常股个数 ", len(g.stocks_fail_sell))
		print("可调整股票个数 ", holding_num - len(g.stocks_fail_sell) - HL_count)
		print("无需调整")
		return
	p = (1 - fail_pos) / (holding_num - len(g.stocks_fail_sell) - HL_count)
	
	#计算买入之后期望每只股票的持仓占比
	print('selected_stocks')
	print(g.selected_stocks)
	for stock in g.selected_stocks:
		if stock in g.stocks_fail_sell or stock in g.yesterday_HL_list or stock in g.today_HL_list:
			continue
		g.excepted_position[stock] = p
		
	for stock, pos in g.excepted_position.items():
		stock_name = ContextInfo.get_stock_name(stock)
		print(' 期望持仓: %s(%s), 占比 %.2f%%' % (stock_name, stock, pos * 100))

	position_dict = {} #记录实际仓位比重
	position_sum = 0
	#计算已有持仓的股票占比
	for stock, pos in positions.items():
		if stock in g.positions[MOM_IDX]:
			continue  # 跳过动量策略的ETF持仓
		current_price = get_last_price(ContextInfo, stock)
		if current_price is None or current_price == 0:
			continue
		position_sum += pos['value']
		position_dict[stock] = pos['value'] / strategy_total, current_price
	
	#计算待买入的股票的持仓占比
	for stock in g.stocks_to_buy:
		current_price = get_last_price(ContextInfo, stock)
		if current_price is None or current_price == 0:
			g.excepted_position.pop(stock)
			continue
		stock_name = ContextInfo.get_stock_name(stock)
		target_value = strategy_total * g.excepted_position[stock]
		amount = int(target_value / current_price / 100) * 100
		need_cash = amount * current_price
		print(f'预计买入{stock_name}({stock})  {amount} 股 * {current_price:.2f},总计 {need_cash:.2f}')
		position_sum += need_cash
		position_dict[stock] = [need_cash / strategy_total, current_price]
		
	avai_cash = strategy_total - position_sum
	print(f'预计持仓 {position_sum} 剩余金额 {avai_cash:.2f}')
	if abs(avai_cash) > CASH_YU or avai_cash < 0:
		print(f'○ ○ 剩余资金过大 {strategy_total - position_sum:.2f}')
		cash = 0
		for stock, exce_pos in g.excepted_position.items():
			if stock in g.stocks_fail_sell:
				continue
			pos_frac, stock_price = position_dict[stock]
			diff_pos = exce_pos - pos_frac
			#if abs(diff_pos) > 0.04:
			if abs(diff_pos) * strategy_total > CASH_YU or abs(diff_pos) > 0.04:
				stock_name = ContextInfo.get_stock_name(stock)
				print(f'{stock_name} 持仓与期望相差较大，持仓{pos_frac*100:.2f}%, 期望{exce_pos*100:.2f}%, 金额差额{diff_pos * strategy_total:.2f}')
				if diff_pos > 0:
					g.stocks_to_buy.append(stock)
					cash -= diff_pos * strategy_total
				else:
					current_price = get_last_price(ContextInfo, stock)
					if current_price is None or current_price == 0:
						continue
					amount = abs(avai_cash) / current_price
					if amount < 100:
						continue
					if ContextInfo.is_suspended_stock(stock):
						continue
					if is_limit_down(ContextInfo, stock):
						continue
					if positions[stock]['canuse_amount'] < 100:
						continue

					sell_target_value(ContextInfo, stock, exce_pos*strategy_total, SC_IDX)
					cash -= diff_pos * strategy_total
					print(f'调整{stock_name}市值，卖出{abs(diff_pos) * strategy_total:.2f}元')

		if cash > 0:
			print("sleep 30s")
			sleep_sec(30)
			print(f"卖出部分股票后，多出现金 {cash:.2f}")

		avai_cash += cash
		if cash != 0:
			print(f'重新分配之后资金{avai_cash:.2f}')

		if avai_cash > CASH_YU:
			print('重新分配之后资金仍有剩余，追加买入')
			pos_dict = {}
			for stock, exce_pos in g.excepted_position.items():
				if stock in g.stocks_fail_sell or stock in g.stocks_to_buy:
					continue
				pos_frac, _ = position_dict[stock]
				diff_pos = exce_pos - pos_frac
				if diff_pos > 0:
					pos_dict[stock] = diff_pos
					
			sorted_pos = list(sorted(pos_dict.items(), key=lambda x: x[1], reverse=True))
			#print(sorted_pos)
			for stock, diff_pos in sorted_pos:
				stock_name = ContextInfo.get_stock_name(stock)
				c = diff_pos * strategy_total
				avai_cash -= c
				if avai_cash > 0:
					g.stocks_to_buy.append(stock)
					print(f'{stock_name} 持仓与期望相差{diff_pos*100:.2f}% {diff_pos*strategy_total:.2f}，补仓')
		elif avai_cash < 0 and cash == 0 and len(g.stocks_to_buy) > 0:
			print(f'未重新分配资金，调整买入仓位比重')
			available_cash = get_strategy_available_cash(SC_IDX)
			for stock in g.stocks_to_buy:
				g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / strategy_total
				print(f'期望持仓: {ContextInfo.get_stock_name(stock)}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')

	# 排序并打印预估持仓
	position_dict_sorted = dict(sorted(position_dict.items(), key=lambda x: x[0]))
	for stock, pos_data in position_dict_sorted.items():
		stock_name = ContextInfo.get_stock_name(stock)
		print(f' 预估持仓: {stock_name}({stock}), 占比 {pos_data[0]*100:.2f}% 单价 {pos_data[1]:.2f}')
		

	# 调整买入数量（微调手数）
	for stock, exce_pos in g.excepted_position.items():
		if stock in g.stocks_fail_sell:
			continue
		pos, stock_price = position_dict[stock]
		diff_value = (exce_pos - pos) * strategy_total
		
		stock_name = ContextInfo.get_stock_name(stock)
		current_price = get_last_price(ContextInfo, stock)
		if current_price is None or current_price == 0:
			continue
		'''
		如果这个股票是在买入清单中，那么调整买入数量
		如果这只股票已经持有，那么看与预期的占比份额是不是差别很大，差别很大则调仓
		'''
		if stock in g.stocks_to_buy:
			'''
			exce_pos 11.11%
			pos 10.01%
			'''
			if diff_value > 0:
				excepted_value = exce_pos * strategy_total
				current_value = pos * strategy_total
				#num = 1
				num = int((excepted_value - current_value) / current_price / 100)
				print(f'调整{stock_name}买入数量，期望买入{excepted_value:.2f},当前{current_value:.2f},相差{diff_value:.2f}')
				while True:
					new_value = current_value + current_price * num * 100
					diff_v = excepted_value - new_value
					print(f'单价{current_price:.2f}，新市值{new_value:.2f}，差值{diff_v:.2f}')
					if abs(round(diff_v,1)) <= abs(round(diff_value,1)):
						diff_value = diff_v
						num += 1
					else:
						num -= 1
						break
				if num > 0:
					g.excepted_position[stock] = (current_value + current_price * num * 100) / strategy_total
					print(f'调整买入数量，追加{num}手,仓位占比调整为{g.excepted_position[stock] * 100:.2f}%')
					
		'''
		amount = int(diff_value / current_price / 100) * 100
		if amount > 0:
			if stock not in g.stocks_to_buy:
				g.stocks_to_buy.append(stock)
			print(f'{stock_name}({stock}) 可以再买入{amount}')
		'''

def trade_afternoon(ContextInfo):
	check_limit_up(ContextInfo)
	time.sleep(20)
	check_remain_amount(ContextInfo)
	
def check_limit_up(ContextInfo):
	if not g.is_trading_day:
		return
	g.count += 1
	if g.yesterday_HL_list != []:
		#对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
		for stock in g.yesterday_HL_list:
			info = ContextInfo.get_instrumentdetail(stock)
			current_price = get_last_price(ContextInfo, stock)
			prev_price = info['PreClose']
			rise_ratio = (current_price - prev_price) / prev_price * 100
			print(f'{stock} {ContextInfo.get_stock_name(stock)} 股价{current_price} 涨幅{rise_ratio:.2f}%')

			limit_up_price = info['UpStopPrice']
			if current_price < limit_up_price:
				print(f"{stock} {ContextInfo.get_stock_name(stock)}涨停打开，卖出")
				sell_target_value(ContextInfo, stock, 0, SC_IDX)
				#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
				g.reason_to_sell = 'limitup'
				g.limitup_stocks.append(stock)
			else:
				print(f"{stock} {ContextInfo.get_stock_name(stock)}涨停，继续持有")

	print('check_limit_up count ', g.count)

def check_remain_amount(ContextInfo):
	#如果昨天有股票卖出或者买入失败，剩余的金额今天买入
	if not g.is_trading_day:
		return
	g.count += 1
	#判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
	if g.reason_to_sell == 'limitup':
		g.hold_list = get_current_holding_stocks(ContextInfo)
		if True:
			print(f'现有持仓:')
			for stock_code in g.hold_list:
				stock_name = ContextInfo.get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
			print('涨停卖出')
			for stock_code in g.limitup_stocks:
				stock_name = ContextInfo.get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
				
			# 计算需要买入的股票数量
			prev_date = get_current_date(ContextInfo) - timedelta(days=1)
			g.selected_stocks = get_small_cap_stocks(ContextInfo, g.stock_pool, prev_date, g.stock_num)
			for stock_code in g.limitup_stocks:
				if stock_code in g.selected_stocks:
					g.selected_stocks.remove(stock_code)

			for stock in list(g.stoploss_map.keys()):
				if stock in g.selected_stocks:
					g.selected_stocks.remove(stock)
					print(f"{stock} {ContextInfo.get_stock_name(stock)} 前{3 - g.stoploss_map[stock]}日止损卖出，3日内不再买入")
			current_holdings = get_current_holding_stocks(ContextInfo)
			if len(current_holdings) > 3:
				print("已有持仓数量大于3，不再买入其他较小市值股票。")
				g.selected_stocks = current_holdings
				
			collect_sell_buy_stocks(ContextInfo)
			if len(g.stocks_to_buy) > 0:
				print(f"需要买入股票 {len(g.stocks_to_buy)}只")
				for stock in g.stocks_to_buy:
					print("待买入 ", ContextInfo.get_stock_name(stock))

			avi_cash = get_strategy_available_cash(SC_IDX)
			print('有余额可用'+str(round((avi_cash),2))+'元。买入'+ str(g.stocks_to_buy))
			info_position(ContextInfo)
			calc_position(ContextInfo)
			buy_stocks(ContextInfo)
			g.refresh_hold = True
		g.reason_to_sell = ''
	elif g.reason_to_sell in ('stoploss', 'takeprofit'):
		avi_cash = get_strategy_available_cash(SC_IDX)
		print(f'止盈止损后余额{avi_cash:.2f}元，买入{g.etf}')
		g.stocks_to_buy = [g.etf]
		buy_stocks(ContextInfo)
		g.reason_to_sell = ''
		g.refresh_hold = True

	print("sleep 20s")
	sleep_sec(20)
	info_position(ContextInfo)
	print('check_remain_amount count ', g.count)

#止盈止损
def stop_loss(ContextInfo):
	if not g.is_trading_day:
		return
	g.count += 1
	show_info = False
	if g.run_stoploss:
		current_positions = get_positions(ContextInfo)
		# 过滤掉动量策略的持仓，只保留小市值策略的股票
		current_positions = {k: v for k, v in current_positions.items() if k not in g.positions[MOM_IDX]}

		if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
			for stock in current_positions.keys():
				if current_positions[stock]['total_amount'] == 0:
					continue
				if stock in g.all_weather_list or stock == g.etf:
					continue

				price = current_positions[stock]['price']
				avg_cost = current_positions[stock]['avg_cost']
				if avg_cost <= 0:
					continue
				# 个股盈利止盈
				if price >= avg_cost * 2:
					#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
					print(f"○ 收益100%止盈,卖出{stock}")
				# 个股止损
				elif price < avg_cost * (1 - g.stoploss_limit):
					sell_target_value(ContextInfo, stock, 0, SC_IDX)
					g.stoploss_map[stock] = g.stoploss_map.setdefault(stock, 3)
					print(f"{stock} 股价{price:.2f} 成本{avg_cost:.2f}")
					print(f"× 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
					#if order_info != None:
					#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
					show_info = True
					
					g.reason_to_sell = 'stoploss'
					if stock in g.selected_stocks:
						g.selected_stocks.remove(stock)

		if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
			query_date = get_current_date(ContextInfo)
			yesterday = query_date - timedelta(days=1)
			query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
			dt_str = query_date.strftime('%Y%m%d%H%M%S')
			price_data = ContextInfo.get_market_data_ex(['open', 'close'],
														['399101.SZ'], 
														period='1d', 
														start_time='', 
														end_time=dt_str, 
														count=1,
														dividend_type='none', 
														fill_data=True,
														subscribe=True)
			#print(price_data)
			df = list(price_data.values())[0]
			down_ratio = (df.iloc[0]['close'] / df.iloc[0]['open'] - 1)
			print("大盘涨幅 {:.2%}".format(down_ratio))
			# 市场大涨大跌止盈止损
			if abs(down_ratio) >= g.stoploss_market:
				g.refresh_hold = True
				if down_ratio < 0:
					g.reason_to_sell = 'stoploss'
					print(f"× 大盘惨跌,平均降幅{down_ratio:.2%}")
				else:
					g.reason_to_sell = 'takeprofit'
					print(f"○ 大盘大涨,平均涨幅{down_ratio:.2%}")
				for stock in current_positions.keys():
					if stock in g.all_weather_list or stock == g.etf:
						continue
					if stock in g.yesterday_HL_list or is_limit_up(ContextInfo, stock):
						continue
					print(f'○ 清仓{stock} {ContextInfo.get_stock_name(stock)}')
					sell_target_value(ContextInfo, stock, 0, SC_IDX)
					#if order_info != None:
					#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
					show_info = True
					if stock in g.selected_stocks:
						g.selected_stocks.remove(stock)

	if show_info:
		print("sleep 30s")
		sleep_sec(30)
		info_position(ContextInfo)

	print('stop_loss count ', g.count)

def sell_stocks(ContextInfo):
	"""执行卖出"""
	g.stocks_fail_sell = []
	for stock in g.stocks_to_sell:
		print('√>>>>>>>>>>>>')
		print('√卖出: ',ContextInfo.get_stock_name(stock))
		sell_target_value(ContextInfo, stock, 0, SC_IDX)
		is_paused = ContextInfo.is_suspended_stock(stock)
		is_dieting = is_limit_down(ContextInfo, stock)
		if is_paused or is_dieting:
			g.stocks_fail_sell.append(stock)
			print(f'{ContextInfo.get_stock_name(stock)} 停牌或跌停，卖出失败')
		#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
		#if order_info != None:
		#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')

def buy_stocks(ContextInfo):
	"""执行买入"""
	if g.stocks_to_buy:
		available_cash = get_strategy_available_cash(SC_IDX)
		position_value = 0
		positions = get_positions(ContextInfo)
		for stock, pos in positions.items():
			if stock not in g.positions[MOM_IDX]:
				position_value += pos['value']

		strategy_total = get_strategy_total(ContextInfo, SC_IDX)
		g.each_cash = available_cash / len(g.stocks_to_buy)
		print("====调整每股额度====\n当前可用资金 ", available_cash, "\n持仓市值 ",
		position_value, "\n总资产: ", strategy_total, "\n每股额度 ", g.each_cash)
		# 计算每只股票的目标市值（等权重）
		# 获取当前总资产
		
		target_value_per_stock = g.each_cash
		for stock in g.stocks_to_buy:
			current_price = get_last_price(ContextInfo, stock)
			if current_price is None or current_price == 0:
				continue

			print("")
			available_cash = get_strategy_available_cash(SC_IDX)
			print(f'===可用资金 {available_cash}===')

			if stock == g.etf:
				target_value_per_stock = min(available_cash, target_value_per_stock)
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				if amount > 0:
					print(f'买入ETF {stock} {ContextInfo.get_stock_name(stock)} 目标市值{target_value_per_stock:.2f}, {amount}股 * {current_price}元')
					buy_target_shares(ContextInfo, stock, amount, SC_IDX)
					#order_shares(stock, amount, ContextInfo, ContextInfo.account)
			else:
				if g.excepted_position.get(stock) is not None:
					target_value_per_stock = g.excepted_position[stock] * strategy_total
					current_value = 0
					positions = get_positions(ContextInfo)
					if stock in positions:
						current_value = positions[stock]['value']
					target_value_per_stock = min(available_cash + current_value, target_value_per_stock)
				
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				print(f'委托买入: {ContextInfo.get_stock_name(stock)}, {stock} \n目标价值:{target_value_per_stock:.2f}'
					f'\n预计最终持股{amount}股，每股{current_price:.2f}元，合计:{amount * current_price:.2f}')
				buy_target_value(ContextInfo, stock, target_value_per_stock, SC_IDX)
			sleep_sec(10)

def get_blank(ratio):
	blank_num = 2
	if ratio < 0:
		blank_num = blank_num - 1
	if abs(ratio) >= 10:
		blank_num = blank_num - 1
	
	blank = ''
	for i in range(blank_num):
		blank = blank + ' '

	return blank

def info_position(ContextInfo):
	current_date = get_current_date(ContextInfo)
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	positions = get_positions(ContextInfo)
	
	if len(positions) > 0:
		info = account_info[0]
		available_cash = info.m_dAvailable
		position_value = info.m_dInstrumentValue
		total_value = info.m_dBalance
		print(f'******************当日({current_date}) (周{current_date.weekday()+1}) 持仓市值: {position_value:.2f}元*******************')

		#sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				continue
			if pos['avg_cost'] <= 0:
				continue
			price = pos['value'] / pos['total_amount']
			ratio = (price / pos['avg_cost'] - 1) * 100
			blank = get_blank(ratio)
			diff_price = price - pos['avg_cost']
			industry = g.industry_dict.get(stock,None)
			print(f"√{stock_name}({stock}) 占比 {pos['value'] / total_value * 100:.2f}%, 涨幅: {blank}{ratio:.2f}% ({diff_price * pos['total_amount']:.2f}) x {pos['total_amount']} = {pos['value']:.1f}元")
		
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				print(f"√持仓: {stock_name}({stock}) 0股")

		print(f'√*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')

		# 打印各策略资金隔离状况
		for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
			cash = g.cash_reserved[idx]
			stock_set = g.positions[idx]
			holdings_val = 0
			stock_names = []
			for stock, pos in positions.items():
				if stock in stock_set:
					holdings_val += pos['value']
					stock_names.append(ContextInfo.get_stock_name(stock))

			total = cash + holdings_val
			print(f'  [{name}策略] 预留现金: {cash:,.2f} | 持仓市值: {holdings_val:,.2f} | 总资产: {total:,.2f}')
			if stock_names:
				print(f'    持仓: {", ".join(stock_names)}')
			else:
				print(f'    持仓: (空)')
		print()

def after_trading_end(ContextInfo):
	current_date = get_current_date(ContextInfo)
	positions = get_positions(ContextInfo)

	# 收盘后资金对账（每日执行，校正 cash_reserved 漂移）
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	info = account_info[0]
	available_cash = info.m_dAvailable
	position_value = info.m_dInstrumentValue
	total_value = info.m_dBalance

	if len(positions) > 0:
		print(f'√*******************当日{current_date}(周{current_date.weekday()+1})持仓市值: {position_value:.2f}元*******************')
		#sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				continue
			if pos['avg_cost'] <= 0:
				continue
			price = pos['value'] / pos['total_amount']
			ratio = (price / pos['avg_cost'] - 1) * 100
			diff_price = price - pos['avg_cost']
			print(f"√持仓: {stock_name}({stock}), 占比 {pos['value'] / total_value * 100:.1f}%, 涨跌幅: {ratio:.1f}% ({diff_price * pos['total_amount']:.1f}), 数量: {pos['total_amount']}, 市值: {pos['value']:.1f}元")

		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				print(f"√持仓: {stock_name}({stock}) 0股")

		print(f'√*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')


	cash = 0
	for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
		cash += g.cash_reserved[idx]

	if abs(available_cash - cash) < 0.001:
		print("  各策略的资金总和与账面资金吻合\n")
		g.cash_record[SC_IDX] = g.cash_reserved[SC_IDX]
		g.cash_record[MOM_IDX] = g.cash_reserved[MOM_IDX]
	else:
		print(f"  策略资金总和为{cash:.2f}，账面资金为{available_cash:.2f}\n")
		cash_diff = available_cash - cash
		print(f"资金差额为{cash_diff:.2f}")
		for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
			print(f'  [{name}策略] 上一交易日现金记录{g.cash_record[idx]:,.2f}')

		if available_cash > 0 and abs(cash_diff / available_cash) > 0.3:
			print("资金差额较大，可能代码有问题，请调试")
		else:
			if abs(g.cash_reserved[MOM_IDX] - g.cash_record[MOM_IDX]) < 0.001:
				print("动量策略资金与上一交易日持平，更新小市值策略资金")
				g.cash_reserved[SC_IDX] = abs(available_cash - g.cash_record[MOM_IDX])
				g.cash_record[SC_IDX] = g.cash_reserved[SC_IDX]
			elif abs(g.cash_reserved[SC_IDX] - g.cash_record[SC_IDX]) < 0.001:
				print("小市值策略资金与上一交易日持平，更新动量策略资金")
				g.cash_reserved[MOM_IDX] = abs(available_cash - g.cash_record[SC_IDX])
				g.cash_record[MOM_IDX] = g.cash_reserved[MOM_IDX]
			else:
				print("资金差额较小，可能是手续费或者分红导致。现决定2个策略各分走一半差额资金")
				for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
					g.cash_reserved[idx] += cash_diff / 2
					g.cash_record[idx] = g.cash_reserved[idx]

			for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
				print(f'  [{name}策略] 预留现金: {g.cash_reserved[idx]:,.2f}, 现金记录更新{g.cash_record[idx]:,.2f}')

	daily_return = total_value - g.last_pos_value
	if g.last_pos_value != 0:
		rate_of_return = daily_return / g.last_pos_value * 100
	else:
		rate_of_return = 0
	print('==============================')
	print(f'今日股票收益: {daily_return:.2f} 元')
	print(f'收益率:       {rate_of_return:.2f} %')
	print('==============================\n\n')
	g.last_pos_value = total_value

	# 每日收盘后记录当日持仓情况（仅在当日有交易时打印明细）
	if not g.trade_day and g.refresh_hold == False:
		return
	g.refresh_hold = False


ORDER_TYPE_MAP: Dict[int, str] = {
	0: "常规", # OTP_ORDINARY
	1: "算法交易", # OTP_ALGORITHM
	2: "随机量交易", # OTP_RANDVOLUME
	3: "算法交易3", # OTP_ALGORITHM3
	4: "中信建投算法", # OTP_ZXJT
	5: "隔时交易", # OTP_ZSGS
	6: "普通交易的触价单笔委托方式", # OTP_ORDINARY_BASKET_TRIGGER_SINGLE_ORDER
	7: "算法交易的触价单笔委托方式", # OTP_ALGORITHM_BASKET_TRIGGER_SINGLE_ORDER
	8: "中信证券算法", # OTP_ZXZQ
	9: "金纳算法", # OTP_GENUS
	10: "爵士算法", # OTP_JAZZ
	11: "智能VWAP", # OTP_VWAP
	12: "智能TWAP", # OTP_TWAP
	13: "智能算法", # OTP_XTALGO
	14: "华创算法", # OTP_HUACHUANG
	15: "华润算法", # OTP_HUARUN
	16: "回转算法", # OTP_CUSTOM
	17: "主动算法", # OPT_EXTERN
	18: "广发算法" # OTP_GUANGFA
}

OPERATION_TYPE_MAP: Dict[int, str] = {
	0: "开多",
	1: "平昨多", # 黄金用平多表示
	2: "平今多",
	3: "开空",
	4: "平昨空", # 黄金用平空表示
	5: "平今空",
	6: "平多优先平今",
	7: "平多优先平昨",
	8: "平空优先平今",
	9: "平空优先平昨",
	10: "卖出优先平今",
	11: "卖出优先平昨",
	12: "买入优先平今",
	13: "买入优先平昨",
	14: "平多",
	15: "平空",
	16: "开仓",
	17: "平仓",
	18: "买入", # 您的例子
	19: "卖出",
	20: "融资买入",
	21: "融券卖出",
	22: "买券还券",
	23: "直接还券",
	24: "卖券还款",
	25: "直接还款"
}

# 价格类型映射字典
PRICE_TYPE_MAP: Dict[int, str] = {
	0: "卖5价",
	1: "卖4价",
	2: "卖3价",
	3: "卖2价",
	4: "卖1价",
	5: "最新价",
	6: "买1价",
	7: "买2价",
	8: "买3价",
	9: "买4价",
	10: "买5价",
	11: "指定价",
	12: "市价_涨跌停价",
	13: "挂单价",
	14: "对手价",
	15: "自动盘口",
	16: "昨收价",
	17: "大宗加权平均价",
	18: "市价_最优价",
	19: "市价_即成剩撤",
	20: "市价_全额成交或撤",
	21: "市价_最优1档即成剩撤",
	22: "市价_最优5档即成剩撤",
	23: "市价_最优1档即成剩转",
	24: "市价_最优5档即成剩转",
	25: "询价",
	26: "限价即时全部成交否则撤单",
	27: "市价即时成交剩余撤单",
	28: "市价即时全部成交否则撤单",
	29: "市价剩余转限价",
	30: "卖6价",
	31: "卖7价",
	32: "卖8价",
	33: "卖9价",
	34: "卖10价",
	35: "买6价",
	36: "买7价",
	37: "买8价",
	38: "买9价",
	39: "买10价",
	40: "涨停价",
	41: "跌停价",
	42: "最优五档即时成交剩余撤销",
	43: "最优五档即时成交剩转限价",
	44: "对手方最优价格委托",
	45: "本方最优价格委托",
	46: "即时成交剩余撤销委托",
	47: "最优五档即时成交剩余撤销委托",
	48: "全额成交或撤销委托",
	49: "盘后定价申报"
}

TASK_STATUS_MAP: Dict[int, str] = {
	0: "未知",
	1: "等待",
	2: "提交中",
	3: "执行中",
	4: "暂停",
	5: "撤销中",
	6: "异常撤销中",
	7: "完成",
	8: "已撤",
	9: "打回",
	10: "异常终止",
	11: "放弃",
	12: "强制终止"
}

ENTRUST_STATUS_MAP: Dict[int, str] = {
	0: "等待完成",
	48: "未报",
	49: "待报",
	50: "已报",
	51: "已报待撤",
	52: "部成待撤",
	53: "部撤",
	54: "已撤",
	55: "部成",
	56: "已成",
	57: "废单",
	86: "已确认",
	255: "未知"
}

def get_entrust_status_str(status_code):
	"""根据状态码获取委托状态描述"""
	return ENTRUST_STATUS_MAP.get(status_code, f"未知状态({status_code})")
def get_task_status_str(status_code):
	"""根据状态码获取状态描述"""
	return TASK_STATUS_MAP.get(status_code, f"未知状态({status_code})")
def get_price_type_name(code):
	"""根据代码获取价格类型名称"""
	return PRICE_TYPE_MAP.get(code, f"未知价格类型({code})")
def get_operation_type_str(operation_code: int) -> str:
	if operation_code in OPERATION_TYPE_MAP:
		return OPERATION_TYPE_MAP[operation_code]
	else:
		raise ValueError(f"无效的操作代码: {operation_code}")
def get_order_type_str(operation_code: int) -> str:
	if operation_code in ORDER_TYPE_MAP:
		return ORDER_TYPE_MAP[operation_code]
	else:
		raise ValueError(f"无效的操作代码: {operation_code}")

def print_hold_stock_info(obj):
	info_str = 'stock code: '+ obj.m_strInstrumentID + '.' + obj.m_strExchangeID + "\t" \
			+ '持仓: '+ str(obj.m_nVolume) + "\t" \
			+ '可用持仓: '+ str(obj.m_nCanUseVolume) + "\t" \
			+ '最新价: '+ str(round(obj.m_dSettlementPrice,2)) + "\t" \
			+ '市值: '+ str(round(obj.m_dMarketValue, 1)) + "\t" \
			+ '成本价: '+ str(round(obj.m_dOpenPrice,2)) + "\t" \
			+ '盈亏: ' + str(round(obj.m_dFloatProfit,1)) + "\t" \
			+ 'stock name: '+ obj.m_strInstrumentName
	print(info_str)

def print_task_info(obj):
	print('task id: ', obj.m_nTaskId)
	print(obj.m_stockCode)
	print('委托', get_operation_type_str(obj.m_eOperationType))
	print('委托价:', obj.m_dFixPrice)
	print(get_price_type_name(obj.m_ePriceType))
	print('委托量: ', obj.m_nNum)
	print('已成交量: ', obj.m_nBusinessNum)
	print('算法: ', get_order_type_str(obj.m_eOrderType))
	print('状态: ', get_task_status_str(obj.m_eStatus))
	print('开始时间: ',revert_timestamp(obj.m_startTime))
	print('结束时间: ', revert_timestamp(obj.m_endTime))
	print(obj.m_strAccountID)
	print(obj.m_strMsg)
	print('取消时间: ', revert_timestamp(obj.m_cancelTime))
	print('')

def print_order_info(obj):
	'''
	print('股票:', obj.m_strInstrumentID, ' ', obj.m_strInstrumentName)
	print('委托时间: ', obj.m_strInsertDate, ' ', obj.m_strInsertTime)
	print('委托类型: ', ('买卖' if obj.m_eEntrustType == 48 else '未知'))
	if obj.m_nOffsetFlag == 48:
		print('买入')
	elif obj.m_nOffsetFlag == 49:
		print('卖出')
	print('委托价: ', obj.m_dLimitPrice)
	print('成交额: ', obj.m_dTradeAmount)
	print('成交量: ', obj.m_nVolumeTraded)
	print('委托状态: ', get_entrust_status_str(obj.m_nOrderStatus))
	print('委托剩余量: ', obj.m_nVolumeTotal)
	print('委托初始量: ', obj.m_nVolumeTotalOriginal)
	#print('合同编号:', obj.m_strOrderSysID)
	#print('任务号:', obj.m_nTaskId)
	'''
	buy_or_sell_str = ''
	if obj.m_nOffsetFlag == 48:
		buy_or_sell_str = '买入'
	elif obj.m_nOffsetFlag == 49:
		buy_or_sell_str = '卖出'

	info_str = 'code: '+ obj.m_strInstrumentID + '.' + obj.m_strExchangeID + " " + obj.m_strInstrumentName + "    \t" \
			+ '委托时间: ' + obj.m_strInsertDate + ' ' + obj.m_strInsertTime + "    \t" \
			+ '委托类型: '+ buy_or_sell_str + "    \t" \
			+ '委托价: ' + str(round(obj.m_dLimitPrice,2)) + "    \t" \
			+ '委托初始量: ' + str(obj.m_nVolumeTotalOriginal) + "    \t" \
			+ '委托剩余量: ' + str(obj.m_nVolumeTotal) + "    \t" \
			+ '成交量: ' + str(obj.m_nVolumeTraded) + "    \t" \
			+ '成交额: ' + str(round(obj.m_dTradeAmount,2)) + "    \t" \
			+ '委托状态: ' + get_entrust_status_str(obj.m_nOrderStatus)
	print(info_str)

def print_deal_info(obj):
	print('委托号: ', obj.m_strOrderSysID)
	print('股票:', obj.m_strInstrumentID, ' ', obj.m_strInstrumentName)
	print('成交时间: ', obj.m_strTradeDate, ' ', obj.m_strTradeTime)
	print('委托类型: ', ('买卖' if obj.m_eEntrustType == 48 else '未知'))
	if obj.m_nOffsetFlag == 48:
		print('买入')
	elif obj.m_nOffsetFlag == 49:
		print('卖出')
	else:
		print('质押')
	print('成交额: ', obj.m_dTradeAmount)
	print('成交均价: ', obj.m_dPrice)
	print('成交量: ', obj.m_nVolume)
	print('手续费: ', obj.m_dComssion)
	print('')

def print_account_info(obj):
	#print('净资产: ', obj.m_dAssureAsset)
	print('可用余额: ',obj.m_dAvailable)
	print('总资产: ',obj.m_dBalance)
	print('已付手续费: ', obj.m_dCommission)
	print('可取金额: ', obj.m_dFetchBalance)
	print('冻结', obj.m_dFrozenCash)
	print('基金总市值: ', obj.m_dFundValue)
	print('初始平仓盈亏: ', obj.m_dInitCloseMoney)
	print('总市值 :', obj.m_dInstrumentValue)
	print('持仓盈亏: ', obj.m_dPositionProfit)
	print('')
	
def fun_list():
	if True:
		objlist = get_trade_detail_data(ContextInfo.account,'STOCK','TASK')
		print('buy task')
		for obj in objlist:
			status = get_task_status_str(obj.m_eStatus)
			if status == '完成' or '异常' in status:
				continue
			print_task_info(obj)
			if status == '完成' or '异常' in status:
				send = cancel_task(obj.m_nTaskId, ContextInfo.account,'stock',ContextInfo)
				print('是否发送撤销命令', send)

		objlist = get_trade_detail_data(ContextInfo.account,'STOCK','ORDER')
		print('order')
		for obj in objlist:
			print_order_info(obj)

		objlist = get_trade_detail_data(ContextInfo.account,'STOCK','DEAL')
		print('deal')
		for obj in objlist:
			print_deal_info(obj)

		account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
		print('account')
		print(account_info)
		for obj in account_info:
			print_account_info(obj)

		objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
		print('holding')
		print(objlist)
		for obj in objlist:
			print_hold_stock_info(obj)

def revert_timestamp(timestamp):
	dt = datetime.fromtimestamp(timestamp)
	return dt
