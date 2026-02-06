#coding:gbk
# -*- coding: utf-8 -*-
"""
超简版定时交易策略
"""
import time
from datetime import datetime, timedelta
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
	print('')

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
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	available_cash = account_info[0].m_dAvailable

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
	g.each_cash = available_cash / g.stock_num
	g.sell_done = False
	g.last_month = None
	g.run_stoploss = True
	g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
	g.stoploss_limit = 0.1  # 止损线
	g.stoploss_market = 0.05  # 市场趋势止损参数
	g.etf = '511880.SH'  # 空仓月份持有银华日利ETF

	g.count = 0
	# 每天执行调仓函数
	# 聚宽会自动将非交易日的触发顺延至下一个交易日
	#ContextInfo.run_time("sell_func", "1nDay", "2025-01-03 10:00:00","SH")
	#ContextInfo.run_time("buy_func", "1nDay", "2025-01-03 14:00:00","SH")
	#ContextInfo.run_time("myHandlebar","5nSecond","2025-01-03 13:20:00","SH")
	print(f'策略初始化完成：每月初调仓，持有市值最小的{g.stock_num}只股票, 初始资金{available_cash}')

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

	if dt.hour == 10 and dt.minute == 0 and is_weekday_job(ContextInfo):
		rebalance_sell(ContextInfo)

	if dt.hour == 10 and dt.minute == 2:
		stop_loss(ContextInfo)

	if dt.hour == 10 and dt.minute == 10 and is_weekday_job(ContextInfo):
		if g.sell_done:
			rebalance_buy(ContextInfo)
		else:
			print(f"今日({dt})非调仓日，不执行操作")


	if dt.hour == 14 and dt.minute == 0:
		trade_afternoon(ContextInfo)


	if dt.hour == 15 and dt.minute == 0:
		objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
		for obj in objlist:
			print_hold_stock_info(obj)
		after_trading_end(ContextInfo)

	'''
	#TEST
	if dt.hour == 15 and dt.minute == 0:
		check_limit_up(ContextInfo)
	'''


def judge_date(ContextInfo):
	current_date = get_current_date(ContextInfo)
	current_month = current_date.month
	g.count = 1
	if (current_month == 1 or current_month == 4):
		if g.trade == True:
			print('GGG========== 一月和四月份清仓，日期：%s ==========' % current_date)
		g.trade = False
	else:
		g.trade = True
	print('judge_date count ',g.count)

def prepare_stock_list(ContextInfo):
	#获取已持有列表
	g.count += 1
	g.hold_list= []
	g.limitup_stocks = []
	g.trade_day = False
	g.hold_list = get_current_holding_stocks(ContextInfo)
	
	#获取昨日涨停列表
	current_date = get_current_date(ContextInfo)
	yesterday = current_date - timedelta(days=1)
	g.yesterday_HL_list = []

	for stock in g.hold_list:
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = ContextInfo.get_trading_dates(stock, '', dt_str, 1, '1d')
		last_date = last_date[0]
		query_date = datetime.strptime(last_date+'150000', '%Y%m%d%H%M%S')

		if is_specified_date_limit_up(ContextInfo, stock, query_date):
			g.yesterday_HL_list.append(stock)

	if g.yesterday_HL_list != []:
		print("")
		print(f"************昨日({yesterday})涨停 **************")
		print(g.yesterday_HL_list)
		print("")


	g.stock_pool = get_normal_stocks(ContextInfo, current_date.strftime('%Y%m%d'))

	print('prepare_stock_list count ',g.count)

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
	print("trade_etf")
	if g.trade is False:
		current_holdings = get_current_holding_stocks(ContextInfo)
		if current_holdings != [g.etf]:
			print('买入ETF')
			g.selected_stocks = [g.etf]
			collect_sell_buy_stocks(ContextInfo)
			sell_stocks(ContextInfo)
			buy_stocks(ContextInfo)

		account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
		info = account_info[0]
		available_cash = info.m_dAvailable
		print(f"当前可买ETF现金为 {available_cash}")
		if available_cash > 10000:
			g.stocks_to_buy = [g.etf]
			buy_stocks(ContextInfo)

def rebalance_sell(ContextInfo):
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = get_current_date(ContextInfo)
	print(f'GGG========== 执行周度调仓，日期：{current_date} ==========')

	info_position(ContextInfo)
	#yesterday = current_date - timedelta(days=1)
	#query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
	query_date = current_date
	g.selected_stocks = get_small_cap_stocks(ContextInfo, g.stock_pool, query_date, g.stock_num)

	collect_sell_buy_stocks(ContextInfo)
	current_holdings = get_current_holding_stocks(ContextInfo)

	if len(g.stocks_to_buy) > 0 or len(g.stocks_to_sell) > 0:
		print(f"GGG当前持股 {len(current_holdings)}只")
		current_holdings.sort()
		for stock in current_holdings:
			print(f"GGG{ContextInfo.get_stock_name(stock)}")
			
		print(f"GGG需要买入股票 {len(g.stocks_to_buy)}只")
		print(f"GGG需要卖出股票 {len(g.stocks_to_sell)}只")
		for stock in g.stocks_to_buy:
			print("GGG待买入 ", ContextInfo.get_stock_name(stock))
		for stock in g.stocks_to_sell:
			print('GGG待卖出: %s' % ContextInfo.get_stock_name(stock))
			
			
		print(f"GGG今日({current_date})为卖出时间，执行卖出操作")
		print('GGG------------------------------------------')
		# 执行卖出逻辑
		sell_stocks(ContextInfo)
		# 标记卖出已完成
		g.sell_done = True
		#log_selection_details(g.selected_stocks, prev_date)

	else:
		print('未选到符合条件的股票，本日不调仓')

	print('rebalance_sell count ',g.count)

def rebalance_buy(ContextInfo):
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = get_current_date(ContextInfo)
	print(f'GGG========== 执行周度调仓，日期：{current_date} ==========')
	# 执行买入逻辑
	if len(g.stocks_to_buy):
		current_time = get_current_date(ContextInfo)
		print(f"GGG今日({current_time})为买入时间，执行买入操作")
		print('GGG+++++++++++++++++++++++++++++++++++++++++')
		print(f"GGG需要买入股票 {len(g.stocks_to_buy)}只")
		for stock in g.stocks_to_buy:
			print(ContextInfo.get_stock_name(stock))
		
	calc_position(ContextInfo)
	buy_stocks(ContextInfo)
	# 重置卖出标记
	g.sell_done = False
	info_position(ContextInfo)
	print('rebalance_buy count ',g.count)

def calc_position(ContextInfo):
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	total_value = account_info[0].m_dBalance
	current_holdings = get_current_holding_stocks(ContextInfo)
	holding_num = len(current_holdings) + len(g.stocks_to_buy)
	'''
	if holding_num != g.stock_num:
		fail_sell_stock_num = len(g.stocks_fail_sell) + len(g.yesterday_HL_list)
		print(f'⭕ ⭕  有{fail_sell_stock_num}只股票没能卖出，调整买入计划')
		print(f'等权买入股票')
		available_cash = context.portfolio.available_cash
		for stock in g.stocks_to_buy:
			g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / total_value
			print(f'期望持仓: {ContextInfo.get_stock_name(stock)}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')
		return
	'''
	if  holding_num != len(g.selected_stocks):
		print(f'⭕ ⭕ 股票数量异常，期望最终持仓{holding_num}只，实际选中{len(g.selected_stocks)}只')
		
	positions = get_positions(ContextInfo)
	fail_pos = 0
	for stock in g.stocks_fail_sell:
		fp = positions[stock]['value'] / total_value
		fail_pos += fp
		print(f'停牌股 {ContextInfo.get_stock_name(stock)} 占仓位比重为 {fp*100:.2f}%')
	HL_count = 0
	for stock in g.yesterday_HL_list:
		if stock in current_holdings:
			fp = positions[stock]['value'] / total_value
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
	for i in range(len(g.selected_stocks)):
		stock = g.selected_stocks[i]
		if stock in g.stocks_fail_sell or stock in g.yesterday_HL_list:
			continue
		g.excepted_position[stock] = p + ((holding_num - 1) / 2 - i) * g.position_step
		
	for stock, pos in g.excepted_position.items():
		stock_name = ContextInfo.get_stock_name(stock)
		print(' 期望持仓: %s(%s), 占比 %.2f%%' % (stock_name, stock, pos * 100))
		
	position_dict = {} #记录实际仓位比重
	position_sum = 0
	#计算已有持仓的股票占比
	for stock, pos in positions.items():
		current_price = get_last_price(ContextInfo, stock)
		if current_price is None or current_price == 0:
			continue
		position_sum += pos['value']
		position_dict[stock] = pos['value'] / total_value, current_price
	
	#计算待买入的股票的持仓占比
	for stock in g.stocks_to_buy:
		stock_name = ContextInfo.get_stock_name(stock)
		target_value = total_value * g.excepted_position[stock]
		current_price = get_last_price(ContextInfo, stock)
		if current_price is None or current_price == 0:
			g.excepted_position.pop(stock)
			continue
		amount = int(target_value / current_price / 100) * 100
		need_cash = amount * current_price
		print(f'预计买入{stock_name}({stock})  {amount} 股 * {current_price:.2f},总计 {need_cash:.2f}')
		position_sum += need_cash
		position_dict[stock] = [need_cash / total_value, current_price]
		
	avai_cash = total_value - position_sum
	print(f'预计持仓 {position_sum} 剩余金额 {avai_cash:.2f}')
	if abs(avai_cash) > 5000 or avai_cash < 0:
		print(f'❌❌剩余资金过大 {total_value - position_sum}')
		cash = 0
		for stock, exce_pos in g.excepted_position.items():
			if stock in g.stocks_fail_sell:
				continue
			pos, stock_price = position_dict[stock]
			diff_pos = exce_pos - pos
			#if abs(diff_pos) > 0.04:
			if abs(diff_pos) * total_value > 5000 or abs(diff_pos) > 0.04:
				stock_name = ContextInfo.get_stock_name(stock)
				print(f'{stock_name} 持仓与期望相差较大，持仓{pos*100:.2f}%,期望{exce_pos*100:.2f}%,金额相差{diff_pos*total_value:.2f}')
				if diff_pos > 0:
					g.stocks_to_buy.append(stock)
					cash -= diff_pos*total_value
				else:
					current_price = get_last_price(ContextInfo, stock)
					if current_price is None or current_price == 0:
						current_price = abs(avai_cash)
					amount = abs(avai_cash) / current_price
					is_paused = ContextInfo.is_suspended_stock(stock)
					is_dieting = is_limit_down(ContextInfo, stock)
					canuse_amount = positions[stock]['canuse_amount']
					if not is_paused and not is_dieting and not amount < 100 and not canuse_amount < 100:
						sell_target_value(ContextInfo, stock, exce_pos*total_value)
						cash -= diff_pos*total_value
						print(f'调整{stock_name}市值，卖出{abs(diff_pos) * total_value:.2f}元')
						#update_stock_price(stock, order_info.m_dPrice, -order_info.m_nVolume)
						
		
		avai_cash += cash
		if cash != 0:
			print(f'重新分配之后资金为{avai_cash:.2f}')
		
		if avai_cash > 5000:
			print(f'重新分配之后资金仍有剩余，追加买入')
			pos_dict = {}
			for stock, exce_pos in g.excepted_position.items():
				if stock in g.stocks_fail_sell or stock in g.stocks_to_buy:
					continue
				pos, stock_price = position_dict[stock]
				diff_pos = exce_pos - pos
				if diff_pos > 0:
					pos_dict[stock] = diff_pos
					
			sorted_pos = list(sorted(pos_dict.items(), key=lambda x: x[1], reverse=True))
			#print(sorted_pos)
			for stock, diff_pos in sorted_pos:
				stock_name = ContextInfo.get_stock_name(stock)
				cash = diff_pos*total_value
				avai_cash -= cash
				if avai_cash > 0:
					g.stocks_to_buy.append(stock)
					print(f'{stock_name} 持仓与期望相差{diff_pos*100:.2f}% {diff_pos*total_value:.2f}，补仓')
			
				
			'''
			each_cash = avai_cash / len(g.stocks_to_buy)
			for stock in g.stocks_to_buy:
				stock_name = ContextInfo.get_stock_name(stock)
				stock_data = current_data[stock]
				current_price = stock_data.last_price
				amount = int(each_cash / current_price / 100) * 100
				need_cash = amount * current_price
				target_value = total_value * g.excepted_position[stock]
				g.excepted_position[stock] = (target_value + need_cash) / total_value
				print(f'调整{stock_name}买入数量,增加{amount}股')
			'''
		elif avai_cash < 0 and cash == 0 and len(g.stocks_to_buy) > 0:
			print(f'未重新分配资金，调整买入仓位比重')
			account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
			available_cash = account_info[0].m_dAvailable
			for stock in g.stocks_to_buy:
				g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / total_value
				print(f'期望持仓: {ContextInfo.get_stock_name(stock)}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')
			
			
	position_dict = dict(sorted(position_dict.items(), key=lambda x: x[0]))
	for stock, pos in position_dict.items():
		stock_name = ContextInfo.get_stock_name(stock)
		print(f' 预估持仓: {stock_name}({stock}), 占比 {pos[0] * 100:.2f}% 单价 {pos[1]:.2f}')
		
	for stock, exce_pos in g.excepted_position.items():
		if stock in g.stocks_fail_sell:
			continue
		pos, stock_price = position_dict[stock]
		diff_value = (exce_pos - pos) * total_value
		
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
				excepted_value = exce_pos * total_value
				current_value = pos * total_value
				#num = 1
				num = int((excepted_value - current_value) / current_price / 100)
				print(f'调整{stock_name}买入数量，期望买入{excepted_value:.2f},当前{current_value:.2f},相差{diff_value:.2f}')
				while True:
					new_value = current_value + current_price * num * 100
					diff_v = excepted_value - new_value
					print(f'单价{current_price:.2f}，新市值{new_value:.2f}，差值{diff_v:.2f}')
					if abs(round(diff_v,2)) <= abs(round(diff_value,2)):
						diff_value = diff_v
						num += 1
					else:
						num -= 1
						break
				if num > 0:
					g.excepted_position[stock] = (current_value + current_price * num * 100) / total_value
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
	check_remain_amount(ContextInfo)
	
def check_limit_up(ContextInfo):
	g.count += 1
	now_time = get_current_date(ContextInfo)
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
				sell_target_value(ContextInfo, stock, 0)
				#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
				g.reason_to_sell = 'limitup'
				g.limitup_stocks.append(stock)
			else:
				print(f"{stock} {ContextInfo.get_stock_name(stock)}涨停，继续持有")

	print('check_limit_up count ',g.count)

#如果昨天有股票卖出或者买入失败，剩余的金额今天买入
def check_remain_amount(ContextInfo):
	g.count += 1
	account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
	available_cash = account_info[0].m_dAvailable
	if g.reason_to_sell is 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
		g.hold_list = get_current_holding_stocks(ContextInfo)
		flag = True
		if len(g.hold_list) < g.stock_num or flag:
			print(f'现有持仓:')
			for stock_code in g.hold_list:
				stock_name = ContextInfo.get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
			print('涨停卖出')
			for stock_code in g.limitup_stocks:
				stock_name = ContextInfo.get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
				
			# 计算需要买入的股票数量
			current_date = get_current_date(ContextInfo)
			prev_date = current_date - timedelta(days=1)
			g.selected_stocks = get_small_cap_stocks(ContextInfo, g.stock_pool, prev_date, g.stock_num)
			for stock_code in g.limitup_stocks:
				if stock_code in g.selected_stocks:
					g.selected_stocks.remove(stock_code)
			
			current_holdings = get_current_holding_stocks(ContextInfo)
			if len(current_holdings) > 3:
				g.selected_stocks = current_holdings
				
			collect_sell_buy_stocks(ContextInfo)
			if len(g.stocks_to_buy) > 0:
				print(f"需要买入股票 {len(g.stocks_to_buy)}只")
				for stock in g.stocks_to_buy:
					print("待买入 ", ContextInfo.get_stock_name(stock))
				
			#num_stocks_to_buy = min(len(g.limitup_stocks), g.stock_num - len(g.hold_list))
			#num_stocks_to_buy = g.stock_num - len(g.hold_list)
			#g.stocks_to_buy = [stock for stock in g.selected_stocks if stock not in g.hold_list and stock not in g.limitup_stocks][:num_stocks_to_buy]
			#sell_stocks(context)
			print('有余额可用'+str(round((available_cash),2))+'元。买入'+ str(g.stocks_to_buy))
			info_position(ContextInfo)
			calc_position(ContextInfo)
			buy_stocks(ContextInfo)
			#info_position(ContextInfo)
			g.refresh_hold = True
		g.reason_to_sell = ''
	elif g.reason_to_sell is 'stoploss':
		print('止盈止损后，有余额可用'+str(round((available_cash),2))+'元。买入'+ str(g.etf))
		g.stocks_to_buy = [g.etf]
		buy_stocks(ContextInfo)
		g.reason_to_sell = ''
		g.refresh_hold = True

	print('check_remain_amount count ',g.count)

#止盈止损
def stop_loss(ContextInfo):
	g.count += 1
	show_info = False
	if g.run_stoploss:
		current_positions = get_positions(ContextInfo)

		if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
			for stock in current_positions.keys():
				price = current_positions[stock]['price']
				avg_cost = current_positions[stock]['avg_cost']
				print(f"{stock} 股价{price:.2f} 成本{avg_cost:.2f}")
				# 个股盈利止盈
				if price >= avg_cost * 2:
					#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
					print("⭕ 收益100%止盈,卖出{}".format(stock))
				# 个股止损
				elif price < avg_cost * (1 - g.stoploss_limit):
					sell_target_value(ContextInfo, stock, 0)
					print(f"⭕ 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
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
			#stocklist = ContextInfo.get_stock_list_in_sector('中小综指')
			price_data = ContextInfo.get_market_data_ex(['open', 'close'], ['399101.SZ'], period='1d', start_time='', end_time=dt_str, count=1,dividend_type='none', fill_data=True,subscribe=True)
			#print(price_data)
			df = list(price_data.values())[0]
			#stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close','open'], count=1, panel=False)
			#print(stock_df)
			#pre_stock_df = get_price(security='399101.XSHE', end_date=context.previous_date - datetime.timedelta(days=1), frequency='daily', fields=['close'], count=1, panel=False)
			#down_ratio = abs(stock_df.close[0] / pre_stock_df.close[0] - 1)
			#print("⭕ 大盘降幅{:.2%}".format(stock_df.close[0] / pre_stock_df.close[0] - 1))
			down_ratio = (df.iloc[0]['close'] / df.iloc[0]['open'] - 1)
			#rise_ratio = (stock_df['close'] / pre_stock_df['close'] - 1).mean()
			#down_ratio = abs(down_ratio)
			print("大盘降幅{:.2%}".format(down_ratio))
			# 市场大跌止损
			if abs(down_ratio) >= g.stoploss_market:
				g.reason_to_sell = 'stoploss'
				g.refresh_hold = True
				if down_ratio < 0:
					print("⭕ 大盘惨跌,平均降幅{:.2%}".format(down_ratio))
					for stock in current_positions.keys():
						if stock == g.etf:
							continue
						print(f'⭕ 清仓{stock} {ContextInfo.get_stock_name(stock)}')
						sell_target_value(ContextInfo, stock, 0)
						#if order_info != None:
						#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
						show_info = True
						if stock in g.selected_stocks:
							g.selected_stocks.remove(stock)
				else:
					print("⭕ 大盘大涨,平均涨幅{:.2%}".format(down_ratio))
					for stock in current_positions.keys():
						if stock == g.etf:
							continue
						if stock in g.yesterday_HL_list:
							continue
						print(f'⭕ 清仓{stock} {ContextInfo.get_stock_name(stock)}')
						sell_target_value(ContextInfo, stock, 0)
						#if order_info != None:
						#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
						show_info = True
						if stock in g.selected_stocks:
							g.selected_stocks.remove(stock)
	
	if show_info == True:
		info_position(ContextInfo)

	print('stop_loss count ',g.count)

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

def is_limit_up(ContextInfo, stock):
	current_price = get_last_price(ContextInfo, stock)
	if current_price is None or current_price == 0:
		return False

	info = ContextInfo.get_instrumentdetail(stock)
	limit_up_price = info['UpStopPrice']
	if math.isnan(limit_up_price) or limit_up_price is None:
		return False

	if current_price >= limit_up_price:
		return True

	return False

def is_limit_down(ContextInfo, stock):
	current_price = get_last_price(ContextInfo, stock)
	if current_price is None or current_price == 0:
		return False

	info = ContextInfo.get_instrumentdetail(stock)
	limit_down_price = info['DownStopPrice']
	if math.isnan(limit_down_price) or limit_down_price is None:
		return False

	if current_price <= limit_down_price:
		return True

	return False

def get_specified_date_price(ContextInfo, stock, query_date, type='none'):
	dt_str = query_date.strftime('%Y%m%d%H%M%S')
	price_data=ContextInfo.get_market_data_ex(['close'], [stock], period='1m', start_time='', end_time=dt_str, count=1,dividend_type=type, fill_data=True,subscribe=True)
	for key, price in price_data.items():
		if not price.empty:
			return price.iloc[0]['close']
		else:
			return float('nan')

def get_last_price(ContextInfo, stock):
	price_data = ContextInfo.get_full_tick([stock])
	for key, price in price_data.items():
		if price['lastPrice'] == 0:
			print(stock, " 获取当前价格异常,股价为0")
		return price['lastPrice']

	print(stock, " 获取当前价格异常")
	return None

def get_market(ContextInfo, stock_list, query_date):
	dt_str = query_date.strftime('%Y%m%d %H:%M:%S')
	guben = {}
	for stock in stock_list:
		info = ContextInfo.get_instrumentdetail(stock)
		#print("市值 ", info['TotalVolumn'])
		guben[stock] = info['TotalVolumn']
	
	dt_str = query_date.strftime('%Y%m%d%H%M%S')
	price_data = ContextInfo.get_full_tick(stock_list)
	#print(price_data)
	market = {}
	for key, price in price_data.items():
		gb = guben[key]
		value = price['lastPrice']
		#print(gb, " ", value)
		if gb is None or math.isnan(gb) or math.isnan(value):
			continue
		market[key] = gb * value

	return market

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
		if ContextInfo.is_suspended_stock(stock):
			#print(f'停牌 {stock} {ContextInfo.get_stock_name(stock)}')
			continue
		info = ContextInfo.get_instrumentdetail(stock)
		if info['InstrumentID'] is None:
			print(f"可能退市 {stock} {ContextInfo.get_stock_name(stock)}")
			continue
		if stock not in current_holdings and is_limit_up(ContextInfo, stock):  # 涨停
			print(f'涨停 {stock} {ContextInfo.get_stock_name(stock)}')
			continue
		if stock not in current_holdings and is_limit_down(ContextInfo, stock):  # 跌停
			print(f'跌停 {stock} {ContextInfo.get_stock_name(stock)}')
			continue
		trading_stocks.append(stock)
	
	return trading_stocks

def get_current_holding_stocks(ContextInfo):
	current_holdings = []
	objlist = get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
	for obj in objlist:
		if obj.m_nVolume == 0:
			continue

		stock = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
		current_holdings.append(stock)

	return current_holdings

def sell_stocks(ContextInfo):
	# 执行卖出
	for stock in g.stocks_to_sell:
		print('GGG>>>>>>>>>>>>')
		print('GGG卖出: ',ContextInfo.get_stock_name(stock))
		sell_target_value(ContextInfo, stock, 0)
		#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
		#if order_info != None:
		#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')

def buy_stocks(ContextInfo):
	if len(g.stocks_to_buy) > 0:
		dt = get_current_date(ContextInfo)
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
			current_price = get_last_price(ContextInfo, stock)
			if current_price is None or current_price == 0:
				continue

			account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
			print(f'===可用资金 {account_info[0].m_dAvailable}===')

			if stock == g.etf:
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				#order_shares(stock, amount, ContextInfo, ContextInfo.account)
				buy_target_shares(ContextInfo, stock, amount)
				#if order_info != None:
				#	print(f'买入: {ContextInfo.get_stock_name(stock)}, {stock} \n目标价值:{target_value_per_stock:.2f}'
				#		 f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
			else:
				if g.excepted_position.get(stock) is not None:
					target_value_per_stock = g.excepted_position[stock] * total_value
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				print(f'委托买入: {ContextInfo.get_stock_name(stock)}, {stock} \n目标价值:{target_value_per_stock:.2f}'
					f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
				buy_target_value(ContextInfo, stock, target_value_per_stock, current_price)
				#if order_info != None:
				#	print(f'实际买入{order_info.m_nVolume}股，每股{order_info.m_dPrice}元，合计:{order_info.m_dTradeAmount:.2f}')
				#else:
				#	print(f'股票 {stock} 买入失败，跳过')

			positions = get_positions(ContextInfo)
			pos = positions.get(stock)
			if pos is not None:
				print(f"持仓 {pos['total_amount']}股, 市值:{pos['value']}")

def sell_target_value(ContextInfo, stock, target_value):
	# passorder(opType, orderType, accountid, orderCode, prType, modelprice, volume
	# opType    : 23 买入 ，24 卖出
	# orderType : 1102 按价格买卖
	# accountid : ContextInfo.account 账号
	# orderCode : stock 股票代码
	# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
	# modelprice: 如果prType是11，填指定价格，不是填任意值
	# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按目标价值买卖 、 为3，按百分比买卖
	# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整

	positions = get_positions(ContextInfo)
	pos = positions.get(stock)
	if pos is None:
		print(f'{stock} 没有持仓，无法卖出')
	else:
		if target_value == 0:
			passorder(24, 1101, ContextInfo.account, stock, 6, -1, pos['total_amount'], '', 2, 'qingkong', ContextInfo)
		else:
			volume = pos['value'] - target_value
			passorder(24, 1102, ContextInfo.account, stock, 6, -1, volume, 2, ContextInfo)
			print(f"sell passorder target value {target_value:.2f} current {pos['value']:.2f} volume {volume:.2f}")

	#order_target_value(stock, target_value, 'BUY1', ContextInfo, ContextInfo.account)

def buy_target_value(ContextInfo, stock, target_value, current_price):
	# passorder(opType, orderType, accountid, orderCode, prType, modelprice, volume
	# opType    : 23 买入 ，24 卖出
	# orderType : 1102 按价格买卖
	# accountid : ContextInfo.account 账号
	# orderCode : stock 股票代码
	# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
	# modelprice: 如果prType是11，填指定价格，不是填任意值
	# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按目标价值买卖 、 为3，按百分比买卖
	# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整

	current_value = 0
	positions = get_positions(ContextInfo)
	pos = positions.get(stock)
	if pos is not None:
		current_value = {pos['value']}

	volume = target_value - current_value + current_price * 5
	passorder(23, 1102, ContextInfo.account, stock, 4, -1, volume, 2, ContextInfo)
	print(f"buy passorder target value {target_value:.2f} current {current_value:.2f} volume {volume:.2f}")
	#order_target_value(stock, target_value + current_price * 10, 'SALE1', ContextInfo, ContextInfo.account)

def buy_target_shares(ContextInfo, stock, target_share):
	# passorder(opType, orderType, accountid, orderCode, prType, modelprice, volume
	# opType    : 23 买入 ，24 卖出
	# orderType : 1101 按股数买卖
	# accountid : ContextInfo.account 账号
	# orderCode : stock 股票代码
	# prType    : 0-4: 卖5~卖1 、 5:最新价 、 6-10: 买1~买5 、 11: 指定价格
	# modelprice: 如果prType是11，填指定价格，不是填任意值
	# volume    : 根据orderType最后一位判断 为1，按股数买卖 、 为2，按价值买卖 、 为3，按百分比买卖
	# quickTrade: 可选项， 为2 表明立刻下单，不用等待bar数据填充完整
	passorder(23, 1101, ContextInfo.account, stock, 6, -1, target_share, 2, ContextInfo)


def order_callback(ContextInfo, orderInfo):
	print("order_callback")
	print_order_info(orderInfo)
	#print('委托更新 id ', orderInfo.m_strOrderSysID)
	#print('股票:', orderInfo.m_strInstrumentID, ' ', orderInfo.m_strInstrumentName)
	#print(f"方向: {'买入' if orderInfo.m_nDirection == 48 else '卖出'}")

def deal_callback(ContextInfo, dealInfo):
	#print_deal_info(dealInfo)
	buy_sell_str = '买入' if dealInfo.m_nOffsetFlag == 48 else '卖出'
	#print(f"{buy_sell_str} {dealInfo.m_strInstrumentID} {dealInfo.m_nVolume} 股 * {dealInfo.m_dPrice:.2f} 元, 成交额 {dealInfo.m_dTradeAmount}, 手续费{dealInfo.m_dComssion}")

	if buy_sell_str == '买入':
		print(f'实际买入 {dealInfo.m_strInstrumentID} {dealInfo.m_nVolume}股，每股{dealInfo.m_dPrice}元，合计:{order_info.m_dTradeAmount:.2f}, 手续费{dealInfo.m_dComssion:.2f}')

	if buy_sell_str == '卖出':
		if dealinfo.m_strRemark == 'qingkong':
			print(f'卖出 {dealInfo.m_strInstrumentID} {dealInfo.m_nVolume}股 * {dealInfo.m_dPrice:.2f}元')

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

def info_position(ContextInfo):
	current_date = get_current_date(ContextInfo)
	positions = get_positions(ContextInfo)	
	
	if len(positions) > 0:
		account_info = get_trade_detail_data(ContextInfo.account, 'STOCK', 'ACCOUNT')
		info = account_info[0]
		available_cash = info.m_dAvailable
		position_value = info.m_dInstrumentValue
		total_value = info.m_dBalance
		print(f'******************当日({current_date})持仓市值: {position_value:.2f}元*******************')

		#sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				continue
			price = pos['value'] / pos['total_amount']
			#ratio = (price / (g.stock_prices[stock][0]/g.stock_prices[stock][1]) - 1) * 100
			#diff_price = price - g.stock_prices[stock][0]/g.stock_prices[stock][1]
			ratio = 0
			diff_price = 0
			print(f"GGG持仓: {stock_name}({stock}), 占比 {pos['value'] / total_value * 100:.1f}%, 涨跌幅: {ratio:.1f}% ({diff_price * pos['total_amount']:.1f}), 数量: {pos['total_amount']}, 市值: {pos['value']:.1f}元")
		
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				print(f"GGG持仓: {stock_name}({stock}) 0股")

		print(f'GGG*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')

# 可选：每日盘后记录函数（非必需）
def after_trading_end(ContextInfo):
	current_date = get_current_date(ContextInfo)
	if not g.trade_day and g.refresh_hold == False:
		return
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

		print(f'GGG*******************当日{current_date}(周{current_date.weekday()+1})持仓市值: {position_value:.2f}元*******************')
		#sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				continue
			price = pos['value'] / pos['total_amount']
			#ratio = (price / (g.stock_prices[stock][0]/g.stock_prices[stock][1]) - 1) * 100
			#diff_price = price - g.stock_prices[stock][0]/g.stock_prices[stock][1]
			ratio = 0
			diff_price = 0
			print(f"GGG持仓: {stock_name}({stock}), 占比 {pos['value'] / total_value * 100:.1f}%, 涨跌幅: {ratio:.1f}% ({diff_price * pos['total_amount']:.1f}), 数量: {pos['total_amount']}, 市值: {pos['value']:.1f}元")
			#g.stock_prices[stock] = [pos.value, pos.total_amount]
		
		for stock, pos in positions.items():
			stock_name = ContextInfo.get_stock_name(stock)
			if pos['total_amount'] == 0:
				print(f"GGG持仓: {stock_name}({stock}) 0股")

		print(f'GGG*******************总资产 {total_value:.2f}  剩余可用金额 {available_cash:.2f}元*******************\n\n')
