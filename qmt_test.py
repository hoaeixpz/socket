#coding:gbk
# -*- coding: utf-8 -*-
"""
超简版定时交易策略
"""
import time
from datetime import datetime
from typing import Dict
import math

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
	print('stock code: ', obj.m_strInstrumentID, '.', obj.m_strExchangeID)
	print('stock name: ', obj.m_strInstrumentName)
	print('持仓: ', obj.m_nVolume)
	print('最新价: ', obj.m_dSettlementPrice)
	print('市值: ', obj.m_dMarketValue)
	print('成本价: ', obj.m_dOpenPrice)
	print('盈亏: ', obj.m_dFloatProfit)
	print('')

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
	print('股票:', obj.m_strInstrumentID, ' ', obj.m_strInstrumentName)
	print('委托时间: ', obj.m_strInsertDate, ' ', obj.m_strInsertTime)
	print('委托类型: ', ('买卖' if obj.m_eEntrustType == 48 else '未知'))
	if obj.m_nDirection == 48:
		print('买入')
	elif obj.m_nDirection == 49:
		print('卖出')
	else:
		print('质押')
	print('委托价: ', obj.m_dLimitPrice)
	print('成交额: ', obj.m_dTradeAmount)
	print('成交均价: ', obj.m_dTradedPrice)
	print('成交量: ', obj.m_nVolumeTraded)
	print('委托状态: ', get_entrust_status_str(obj.m_nOrderStatus))
	print('委托剩余量: ', obj.m_nVolumeTotal)
	print('委托初始量: ', obj.m_nVolumeTotalOriginal)
	#print('合同编号:', obj.m_strOrderSysID)
	#print('任务号:', obj.m_nTaskId)
	print('')

def print_deal_info(obj):
	print('股票:', obj.m_strInstrumentID, ' ', obj.m_strInstrumentName)
	print('成交时间: ', obj.m_strTradeDate, ' ', obj.m_strTradeTime)
	print('委托类型: ', ('买卖' if obj.m_eEntrustType == 48 else '未知'))
	if obj.m_nDirection == 48:
		print('买入')
	elif obj.m_nDirection == 49:
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

def get_current_date(ContextInfo):
	current_time = ContextInfo.get_bar_timetag(ContextInfo.barpos)
	ctstr = timetag_to_datetime(current_time, "%Y-%m-%d %H%M%S")
	date = datetime.strptime(ctstr, "%Y-%m-%d %H%M%S")
	return date

class G():
	pass
g = G() #创建空的类的实例 用来保存委托状态

def init(ContextInfo):
	print("策略启动")
	period = ContextInfo.period
	print(period)
	ContextInfo.account = '8885388757'
	ContextInfo.set_account(ContextInfo.account)

	# 设置全局变量
	g.stock_pool = []
	g.selected_stocks = []
	g.stocks_to_buy = []
	g.stocks_to_sell = []
	g.stocks_fail_sell = []
	g.hold_list = []
	g.limitup_stocks = []
	g.yesterday_HL_list = []  #昨日涨停股票
	g.stock_prices = {} #记录持仓股票的市值和持仓数，反推股价，来计算个股涨跌幅度
	g.st_code = set()
	g.excepted_position = {}
	g.position_step = 0.00
	g.reason_to_sell = ''
	g.refresh_hold = False
	g.trade = True
	g.stock_num = 9  # 每月持有的股票数量 5
	g.weekday = 2  #每周二调仓
	g.trade_day = False
	g.each_cash = ContextInfo.capital / g.stock_num
	g.sell_done = False
	g.last_month = None
	g.run_stoploss = True
	g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
	g.stoploss_limit = 0.1  # 止损线
	g.stoploss_market = 0.05  # 市场趋势止损参数
	g.etf = '511880.SH'  # 空仓月份持有银华日利ETF


	# 每天执行调仓函数
	# 聚宽会自动将非交易日的触发顺延至下一个交易日
	#ContextInfo.run_time("sell_func", "1nDay", "2025-01-03 10:00:00","SH")
	#ContextInfo.run_time("buy_func", "1nDay", "2025-01-03 14:00:00","SH")
	#ContextInfo.run_time("myHandlebar","5nSecond","2025-01-03 13:20:00","SH")
	print(f'策略初始化完成：每月初调仓，持有市值最小的{g.stock_num}只股票, 初始资金{ContextInfo.capital}')

def judge_date(ContextInfo):
	current_date = get_current_date(ContextInfo)
	current_month = current_date.month
	if (current_month == 1 or current_month == 4):
		if g.trade == True:
			print('✅========== 一月和四月份清仓，日期：%s ==========' % current_date)
		g.trade = False
	else:
		g.trade = True

'''
def prepare_stock_list(ContextInfo):
	#获取已持有列表
	g.hold_list= []
	g.limitup_stocks = []
	g.trade_day = False
	objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
	for obj in objlist:
		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		g.hold_list.append(stock)
	#获取昨日涨停列表
	if g.hold_list != []:
		df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
		df = df[df['close'] == df['high_limit']]
		g.yesterday_HL_list = list(df.code)
		if g.yesterday_HL_list != []:
			print("")
			print(f"************昨日({context.previous_date})涨停 **************")
			print(list(df.code))
			print("")
	else:
		g.yesterday_HL_list = []
'''

def collect_sell_buy_stocks(ContextInfo):
	g.stocks_to_sell = []
	g.stocks_to_buy = []
	current_holdings = get_current_holding_stocks(ContextInfo)
	for stock in current_holdings:
		if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
			g.stocks_to_sell.append(stock)
			
	for stock in g.selected_stocks:
		if (stock not in current_holdings) and (stock not in g.yesterday_HL_list):
			g.stocks_to_buy.append(stock)

def trade_etf(ContextInfo):
	if g.trade is False:
		current_holdings = get_current_holding_stocks(ContextInfo)
		if current_holdings != [g.etf]:
			print('买入ETF')
			g.selected_stocks = [g.etf]
			collect_sell_buy_stocks(ContextInfo)
			sell_stocks(ContextInfo)
			buy_stocks(ContextInfo)

def rebalance_sell(ContextInfo):
	if g.trade is False:
		return
	g.trade_day = True
	
    current_date = get_current_date(ContextInfo)
	
    print(f'✅========== 执行周度调仓，日期：{current_date} ==========')

	info_position(context)
	no_st_codes = get_normal_stocks(ContextInfo, current_date.strftime('%Y%m%d'))
	g.stock_pool = no_st_codes
	g.selected_stocks = get_small_cap_stocks(ContextInfo, g.stock_pool, current_date, g.stock_num)

	collect_sell_buy_stocks(context)
	current_holdings = list(context.portfolio.positions.keys())
	if len(g.stocks_to_buy) > 0 or len(g.stocks_to_sell) > 0:
		log.info(f"✅当前持股 {len(current_holdings)}只")
		for stock in current_holdings:
			log.info(f"✅{get_security_info(stock).display_name}")
			
		log.info(f"✅需要买入股票 {len(g.stocks_to_buy)}只")
		log.info(f"✅需要卖出股票 {len(g.stocks_to_sell)}只")
		for stock in g.stocks_to_buy:
			log.info("✅待买入 ", get_security_info(stock).display_name)
		for stock in g.stocks_to_sell:
			log.info('✅待卖出: %s' % get_security_info(stock).display_name)
			
			
		log.info(f"✅今日({current_time})为卖出时间，执行卖出操作")
		log.info('✅------------------------------------------')
		# 执行卖出逻辑
		sell_stocks(ContextInfo)
		# 标记卖出已完成
		g.sell_done = True
		#log_selection_details(g.selected_stocks, prev_date)

	else:
		print('未选到符合条件的股票，本日不调仓')
			

def rebalance_buy(ContextInfo):
	if g.trade is False:
		return
	g.trade_day = True
	# 执行买入逻辑
	if len(g.stocks_to_buy):
		current_time = get_current_date(ContextInfo)
		print(f"✅今日({current_time})为买入时间，执行买入操作")
		print('✅+++++++++++++++++++++++++++++++++++++++++')
		print(f"✅需要买入股票 {len(g.stocks_to_buy)}只")
		for stock in g.stocks_to_buy:
			log.info(get_security_info(stock).display_name)
		
	buy_stocks(ContextInfo)
	# 重置卖出标记
	g.sell_done = False
	info_position(context)

def handlebar(ContextInfo):
	if not ContextInfo.is_last_bar():
		#return
		pass
	# 获取当前K线的时间戳
	# 将时间戳转换为可读的日期时间对象，这里需要根据QMT API具体函数来操作
	# 假设有一个函数 timetag_to_datetime 用于转换
	dt = get_current_date(ContextInfo)
	#print(dt)
		

	if dt.hour == 9 and dt.minute == 35:
		judge_date(ContextInfo)
		trade_etf(ContextInfo)

	if dt.hour == 10 and dt.minute == 0:
		rebalance_sell(ContextInfo)

	if dt.hour == 10 and dt.minute == 10:
		rebalance_buy(ContextInfo)	

	#print(ContextInfo.is_last_bar())
	if dt.hour == 15 and dt.minute == 0:
		after_trading_end(ContextInfo)
		#stocklist = get_normal_stocks(ContextInfo, dt.strftime('%Y%m%d'))
		#get_small_cap_stocks(ContextInfo, stocklist, dt, g.stock_num)

	# 同样，判断是否为上午10点
	if dt.hour == 19 and dt.minute == 0:
		return
		#这里是你的卖出逻辑
		print(dt)
		print("执行卖出511880")
		

		objlist = get_trade_detail_data(ContextInfo.account,'STOCK','TASK')
		print('task')
		for obj in objlist:
			if get_task_status_str(obj.m_eStatus) == '完成':
				continue
			print_task_info(obj)
		# passorder(...)
		pass

def get_current_price(ContextInfo, stock, query_date):
	dt_str = query_date.strftime('%Y%m%d%H%M%S')
	price_data=ContextInfo.get_market_data_ex(['close'], [stock], period='5m', start_time='', end_time=dt_str, count=1,dividend_type='none',fill_data=True,subscribe=False)
	for key, price in price_data.items():
		return price.iloc[0]['close']

def get_market(ContextInfo, stock_list, query_date):
	fieldList = ['CAPITALSTRUCTURE.total_capital']
	dt_str = query_date.strftime('%Y%m%d %H:%M:%S')
	result = ContextInfo.get_financial_data(fieldList, stock_list, dt_str, dt_str)
	#print("市值")
	#print(result)
	
	dt_str = query_date.strftime('%Y%m%d%H%M%S')
	price_data=ContextInfo.get_market_data_ex(['close'], stock_list, period='5m', start_time='', end_time=dt_str, count=1,dividend_type='none',fill_data=True,subscribe=False)
	#print(price_data)
	guben = result['total_capital']
	market = {}
	for key, price in price_data.items():
		gb = guben[key]
		value = price.iloc[0]['close']
		#print(gb, " ", value)
		if math.isnan(gb) or math.isnan(value):
			continue
		market[key] = gb * value

	return market

def get_small_cap_stocks(ContextInfo, stock_list, query_date, n=5):
	#获取市值最小的n只股票（修正版：全局排序）
	# 用于存储所有查询到的市值数据
	market = get_market(ContextInfo, stock_list, query_date)
	print('market')
	#print(market)
	sorted_market = dict(sorted(market.items(), key=lambda x:x[1], reverse=False))
	#print(sorted_market)
	#sorted_market = sorted_market[0:10]
	if n > 30:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[0:10]:
			stock_name = ContextInfo.get_stock_name(stock)
			cap_in_10k = round(cap/100000000.0, 2)
			rank = rank + 1
			marker = '  <== 选中' if rank <= n else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 流通市值: {cap_in_10k} 亿元{marker}')

	selected_stocks = list(sorted_market)[0:n]

	flag = False
	for stock_code in selected_stocks:
		if stock_code not in g.selected_stocks:
			flag = True
			break

	if flag:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[0:10]:
			stock_name = ContextInfo.get_stock_name(stock)
			cap_in_10k = round(cap/100000000.0, 2)
			rank = rank + 1
			marker = '  <== 选中' if rank <= n else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 流通市值: {cap_in_10k} 亿元{marker}')

	return selected_stocks

def is_date_in_range(input_date_str, start_date_str, end_date_str, date_format = '%Y%m%d'):
	input_date = datetime.strptime(input_date_str, date_format).date()
	start_date = datetime.strptime(start_date_str, date_format).date()
	end_date = datetime.strptime(end_date_str, date_format).date()

	return start_date <= input_date <= end_date

def get_normal_stocks(ContextInfo, current_time):
	stock_index = '中小综指'
	stocklist = ContextInfo.get_stock_list_in_sector('中小综指')
	print(f'{current_time} 中小综指共有 {len(stocklist)}只股票')

	non_st_stocks = []
	for stock in stocklist:
		ST = ContextInfo.get_his_st_data(stock)
		if ST:
			is_st = False
			for stkey, time_period in ST.items():
				for tp in time_period:
					if is_date_in_range(current_time, tp[0], tp[1]):
						is_st = True
						break
				if is_st:
					break
			if is_st:
				continue

		non_st_stocks.append(stock)

	print(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
	return non_st_stocks

def get_current_holding_stocks(ContextInfo):
	current_holdings = []
	objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
	for obj in objlist:
		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		current_holdings.append(stock)

	return current_holdings


def sell_stocks(ContextInfo):
	# 执行卖出
	for stock in g.stocks_to_sell:
		print('✅>>>>>>>>>>>>')
		print('✅卖出: ',ContextInfo.get_stock_name(stock))
		order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
		#if order_info != None and order_info.filled > 0:
		#    print(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')

def buy_stocks(ContextInfo):
	if len(g.stocks_to_buy) > 0:
		account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
		info = account_info[0]
		available_cash = info.m_dAvailable
		position_value = info.m_dInstrumentValue
		#total_cash = context.portfolio.cash
		total_value = info.m_dBalance
		g.each_cash = available_cash / len(g.stocks_to_buy)
		#if g.stocks_to_buy != [g.etf]:
		#    g.each_cash = min(g.each_cash, total_value * 1.5 / g.stock_num)
		print("====调整每股额度====\n当前可用资金 ", available_cash, "\n持仓市值 ", 
		position_value, "\n总资产: ", total_value, "\n每股额度 ", g.each_cash)
		# 计算每只股票的目标市值（等权重）
		# 获取当前总资产
		
		target_value_per_stock = g.each_cash
		#buy_num  = len(g.stocks_to_buy)
		for stock in g.stocks_to_buy:
			current_price = get_current_price(ContextInfo, stock, dt)
			if math.isnan(current_price):
				continue
			if stock == g.etf:
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				order_shares(stock, amount, ContextInfo, ContextInfo.account)
				print(f'买入: {ContextInfo.get_stock_name(stock)}, {stock} \n目标价值:{target_value_per_stock:.2f}'
						 f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
			else:
				order_target_value(stock, target_value_per_stock, ContextInfo, ContextInfo.account)
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				log.info(f'委托买入: {get_security_info(stock).display_name}, {stock} \n目标价值:{target_value_per_stock:.2f}'
					f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
				#if order_info != None and order_info.filled > 0:
				#    print(f'实际买入{order_info.filled}股，每股{order_info.price}元，合计:{order_info.filled * order_info.price:.2f}')
				#else:
				#    print(f'股票 {stock} 买入失败，跳过')

def order_callback(ContextInfo, orderInfo):
	print_order_info(orderInfo)
	#print('委托更新 id ', orderInfo.m_strOrderSysID)
	#print('股票:', orderInfo.m_strInstrumentID, ' ', orderInfo.m_strInstrumentName)
	#print(f"方向: {'买入' if orderInfo.m_nDirection == 48 else '卖出'}")

def get_positions(ContextInfo):
	positions = {}
	objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
	for obj in objlist:
		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		pos = {}
		pos['total_amount'] = obj.m_nVolume
		pos['value'] = obj.m_dMarketValue
		positions[stock] = pos

	return positions

def info_position(context):
	current_date = get_current_date(ContextInfo)
	positions = get_positions(ContextInfo)	
	
	if len(positions) > 0:
		print(f'******************当日({current_date})持仓市值: {position_value:.2f}元*******************')
		account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
		info = account_info[0]
		available_cash = info.m_dAvailable
		position_value = info.m_dInstrumentValue
		total_value = info.m_dBalance

		sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in sorted_pos.items():
			stock_name = ContextInfo.get_stock_name(stock)
			price = pos['value'] / pos['total_amount']
			#ratio = (price / (g.stock_prices[stock][0]/g.stock_prices[stock][1]) - 1) * 100
			#diff_price = price - g.stock_prices[stock][0]/g.stock_prices[stock][1]
			ratio = 0
			diff_price = 0
			print(f'✅持仓: {stock_name}({stock}), 占比 {pos['value'] / total_value * 100:.2f}%, 涨跌幅: {ratio:.2f}% ({diff_price*pos.total_amount:.2f}), 数量: {pos['total_amount']}, 市值: {pos['value']:.2f}元')

		print(f'✅*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')
def after_trading_end(ContextInfo):
	current_date = get_current_date(ContextInfo)
	#if not g.trade_day and g.refresh_hold == False:
	#    return
	g.refresh_hold = False
	#每日收盘后运行，记录当日持仓情况
	# 获取当前持仓
	positions = get_positions(ContextInfo)	

	if len(positions) > 0:
		account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
		info = account_info[0]
		available_cash = info.m_dAvailable
		position_value = info.m_dInstrumentValue
		total_value = info.m_dBalance

		print(f'✅*******************当日(周{current_date.weekday()+1})持仓市值: {position_value:.2f}元*******************')
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			price = pos['value'] / pos['total_amount']
			#ratio = (price / (g.stock_prices[stock][0]/g.stock_prices[stock][1]) - 1) * 100
			#diff_price = price - g.stock_prices[stock][0]/g.stock_prices[stock][1]
			ratio = 0
			diff_price = 0
			print(f'✅持仓: {stock_name}({stock}), 占比 {pos['value'] / total_value * 100:.2f}%, 涨跌幅: {ratio:.2f}% ({diff_price*pos.total_amount:.2f}), 数量: {pos['total_amount']}, 市值: {pos['value']:.2f}元')
			#g.stock_prices[stock] = [pos.value, pos.total_amount]
		print(f'✅*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')
