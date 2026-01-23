#coding:gbk
# -*- coding: utf-8 -*-
"""
超简版定时交易策略
"""
import time
from datetime import datetime
from typing import Dict

class G():
	pass
g = G() #创建空的类的实例 用来保存委托状态 

ORDER_TYPE_MAP: Dict[int, str] = {
	0: "常规",                              # OTP_ORDINARY
	1: "算法交易",                          # OTP_ALGORITHM
	2: "随机量交易",                        # OTP_RANDVOLUME
	3: "算法交易3",                         # OTP_ALGORITHM3
	4: "中信建投算法",                      # OTP_ZXJT
	5: "隔时交易",                          # OTP_ZSGS
	6: "普通交易的触价单笔委托方式",         # OTP_ORDINARY_BASKET_TRIGGER_SINGLE_ORDER
	7: "算法交易的触价单笔委托方式",         # OTP_ALGORITHM_BASKET_TRIGGER_SINGLE_ORDER
	8: "中信证券算法",                      # OTP_ZXZQ
	9: "金纳算法",                          # OTP_GENUS
	10: "爵士算法",                         # OTP_JAZZ
	11: "智能VWAP",                         # OTP_VWAP
	12: "智能TWAP",                         # OTP_TWAP
	13: "智能算法",                         # OTP_XTALGO
	14: "华创算法",                         # OTP_HUACHUANG
	15: "华润算法",                         # OTP_HUARUN
	16: "回转算法",                         # OTP_CUSTOM
	17: "主动算法",                         # OPT_EXTERN
	18: "广发算法"                          # OTP_GUANGFA
}

OPERATION_TYPE_MAP: Dict[int, str] = {
	0: "开多",
	1: "平昨多",           # 黄金用平多表示
	2: "平今多",
	3: "开空",
	4: "平昨空",           # 黄金用平空表示
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
	18: "买入",            # 您的例子
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

def init(ContextInfo):
	print("策略启动")
	period = ContextInfo.period
	print(period)
	ContextInfo.account = '8885388757'
	ContextInfo.set_account(ContextInfo.account)

	stock300 =ContextInfo.get_stock_list_in_sector('中小综指')
	print(stock300)
	
	#data=ContextInfo.get_market_data_ex([],['000001.SZ'],period='1d',start_time='20251111',end_time='20260122',count=-1,dividend_type='front')
	#print('data>>>>')
	#print(data)
	#print('data<<<<')

	# 设置定时器 - 最简单的调用方式
	#ContextInfo.run_time("sell_func", "1nDay", "2025-01-03 10:00:00","SH")
	#ContextInfo.run_time("buy_func", "1nDay", "2025-01-03 14:00:00","SH")
	#ContextInfo.run_time("myHandlebar","5nSecond","2025-01-03 13:20:00","SH")
'''
def myHandlebar(ContextInfo):
	print('hello world')


def sell_func(ContextInfo):
	"""10:00卖出函数"""
	print("执行卖出513500")
	# 这里添加您的卖出代码
	# 示例: passorder(操作类型, 账户, 股票代码, 交易类型, 价格, 数量)

def buy_func(ContextInfo):
	"""14:00买入函数"""  
	print("执行全仓买入513500")
	# 这里添加您的买入代码
'''

def print_hold_stock_info(obj):
	print('stock code: ', obj.m_strInstrumentID, '.', obj.m_strExchangeID)
	print('stock name: ', obj.m_strInstrumentName)
	print('持仓: ', obj.m_nVolume)
	print('最新价: ', obj.m_dSettlementPrice)	
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

def revert_timestamp(timestamp):
	dt = datetime.fromtimestamp(timestamp)
	return dt

def handlebar(ContextInfo):
	if not ContextInfo.is_last_bar():
		return
		#pass
	# 获取当前K线的时间戳
	current_time = ContextInfo.get_bar_timetag(ContextInfo.barpos)
	
	#print(current_time)
	# 将时间戳转换为可读的日期时间对象，这里需要根据QMT API具体函数来操作
	# 假设有一个函数 timetag_to_datetime 用于转换
	dt = timetag_to_datetime(current_time, "%Y-%m-%d %H%M%S")
	dt = datetime.strptime(dt, "%Y-%m-%d %H%M%S")
	
	print(dt)
	#print(dt.hour)
	#print(ContextInfo.is_last_bar())
	
	# 判断时间是否为下午2点（14:00）左右，并且确保是当前K线的最后一个Tick（避免在K线中间阶段交易）
	if dt.hour == 15 and dt.minute >= 0:
		# 这里是你的买入逻辑
		# 例如：全仓买入513500
		print(dt)
		print("执行全仓买入511880")
		#order_shares('000001.SZ', 100, 'BUY1', ContextInfo, ContextInfo.account)
		order_shares('511880.SH', 100, 'BUY1', ContextInfo, ContextInfo.account)
		objlist = get_trade_detail_data(ContextInfo.account,'STOCK','TASK')
		print('buy task')
		for obj in objlist:
			status = get_task_status_str(obj.m_eStatus)
			if  status == '完成' or '异常' in status:
				continue
			print_task_info(obj)
			
			
			if  status == '完成' or '异常' in status:
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
		print(account_info)
		for obj in account_info:
			print_account_info(obj)
			break
		
		#orderid = get_last_order_id(ContextInfo.account, 'stock', 'order')
		#print(orderid)
		#obj = get_value_by_order_id(orderid,ContextInfo.account, 'stock', 'order')
		#print(dir(obj))
		#can_cancel = can_cancel_order(orderid,ContextInfo.account,'stock')
		#print('是否可撤:', can_cancel)

		#resultlist=get_trade_detail_data('','STOCK',"POSITION")
		#print(resultlist)
		# passorder(...)
		pass
	
	# 同样，判断是否为上午10点
	if dt.hour == 14 and dt.minute == 0:
		#这里是你的卖出逻辑
		print(dt)
		print("执行卖出511880")
		resultlist=get_trade_detail_data(ContextInfo.account,'STOCK',"POSITION")
		print('holding')
		print(resultlist)
		for obj in resultlist:
			print_hold_stock_info(obj)
			
			# 查看有哪些属性字段
			#print(dir(obj))
			stock_name = obj.m_strInstrumentID + '.' + obj.m_strExchangeID
			print(stock_name)
			#order_shares(obj.m_strInstrumentID, -obj.m_nVolume, 100.114, ContextInfo, ContextInfo.account)
			#order_shares(stock_name, -obj.m_nVolume, 'fix', obj.m_dSettlementPrice, ContextInfo, ContextInfo.account)
			#order_lots(obj.m_strInstrumentID, -obj.m_nVolume/100, 'fix', 100.114, ContextInfo, ContextInfo.account)

		objlist = get_trade_detail_data(ContextInfo.account,'STOCK','TASK')
		print('task')
		for obj in objlist:
			if get_task_status_str(obj.m_eStatus) == '完成':
				continue
			print_task_info(obj)

		# passorder(...)
		pass
	
