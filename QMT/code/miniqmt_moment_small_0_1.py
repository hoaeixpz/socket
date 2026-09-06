# MiniQMT 双策略合并版 — ETF动量轮动(50%) + 小市值轮动(50%)
# 动量策略：克隆自聚宽 https://www.joinquant.com/post/58963
# 小市值策略：移植自 miniqmt_small_cap_0_1.py

from xtquant import xtdata
from xtquant.xttype import StockAccount
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant import xtconstant
import time
from datetime import datetime, timedelta
import math
import sys
import subprocess
import re
import numpy as np
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import os
import signal

ETF_POOL = [
	"513100.SH", "513520.SH", "513030.SH",  # 境外: 纳指, 日经, 德国
	"518880.SH", "159980.SZ", "159985.SZ",  # 商品: 黄金, 有色, 豆粕
	"501018.SH", "511090.SH", "513130.SH",  # 原油, 30年国债, 恒生科技
	"515980.SH"                             # 人工智能
]
SAFE_ETF = '511220.SH'  # 城投债


DEBUG_DAILY_MODE = False
#DEBUG_DAILY_MODE = True

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class Tee:
	"""将输出同时写入终端和日志文件"""
	def __init__(self, log_file_path):
		self.terminal = sys.__stdout__      # 保留原始控制台输出流
		self.log = open(log_file_path, 'a', encoding='utf-8')  # 追加模式

	def write(self, message):
		self.terminal.write(message)                  # 打印到控制台
		clean_message = ansi_escape.sub('', message)  # 去除颜色代码
		self.log.write(clean_message)                 # 写入日志文件
		self.log.flush()                              # 实时写入磁盘

	def flush(self):
		try:
			self.terminal.flush()
			self.log.flush()
		except ValueError:
			pass

	def close(self):
		self.log.close()

# 重定向 stdout，所有 print 都会经过 Tee 对象
if not DEBUG_DAILY_MODE:
	log_name = datetime.now().strftime('%Y%m%d')
	tee = Tee(f"logfiles/{log_name}.log")
	sys.stdout = tee

red_c = '\033[31m'
green_c = '\033[32m'

scheduler = BackgroundScheduler()

class G():
	pass
g = G() #创建空的类的实例 用来保存委托状态

class MyXtQuantTraderCallback(XtQuantTraderCallback):
	def on_disconnected(self):
		"""
		连接断开
		:return:
		"""
		print(datetime.datetime.now(), '连接断开回调')

	def on_stock_order(self, order):
		"""
		委托回报推送
		:param order: XtOrder对象
		:return:
		"""
		print(datetime.datetime.now(), '委托回调 投资备注', order.order_remark)

	def on_stock_trade(self, trade):
		"""
		成交变动推送
		:param trade: XtTrade对象
		:return:
		"""
		print(datetime.datetime.now(), '成交回调', trade.order_remark, f"委托方向(48买 49卖) {trade.offset_flag} 成交价格 {trade.traded_price} 成交数量 {trade.traded_volume}")

	def on_order_error(self, order_error):
		"""
		委托失败推送
		:param order_error:XtOrderError 对象
		:return:
		"""
		# print("on order_error callback")
		# print(order_error.order_id, order_error.error_id, order_error.error_msg)
		print(f"委托报错回调 {order_error.order_remark} {order_error.error_msg}")

	def on_cancel_error(self, cancel_error):
		"""
		撤单失败推送
		:param cancel_error: XtCancelError 对象
		:return:
		"""
		print(datetime.datetime.now(), sys._getframe().f_code.co_name)

	def on_order_stock_async_response(self, response):
		"""
		异步下单回报推送
		:param response: XtOrderResponse 对象
		:return:
		"""
		print(f"异步委托回调 投资备注: {response.order_remark}")

	def on_cancel_order_stock_async_response(self, response):
		"""
		:param response: XtCancelOrderResponse 对象
		:return:
		"""
		print(datetime.datetime.now(), sys._getframe().f_code.co_name)

	def on_account_status(self, status):
		"""
		:param response: XtAccountStatus 对象
		:return:
		"""
		print(datetime.datetime.now(), sys._getframe().f_code.co_name)



# ================================================================
# 工具函数（共用）
# ================================================================

def sleep_sec(seconds):
	time.sleep(seconds)

def sleep_mins(minutes):
	m = minutes * 60 + 1
	print("sleep ", m)
	time.sleep(m)

def sleep_hours(hours):
	time.sleep(3600 * hours)

def get_stock_name(stock):
	detail = xtdata.get_instrument_detail(stock)
	if detail:
		return detail['InstrumentName']
	else:
		return None

def get_trading_dates(stock, dt_str, days = 7):
	xtdata.download_history_data(stock,period='1d',incrementally=True)
	history_data = xtdata.get_market_data_ex(['close'],
											 [stock],
											 period='1d',
											 start_time='',
											 end_time=dt_str,
											 count=days)
	#print(history_data)
	dates = history_data[stock].index.tolist()
	return dates

def is_trading_day():
	if DEBUG_DAILY_MODE:
		return True

	today = datetime.now().strftime('%Y%m%d')
	dates = get_trading_dates('399101.SZ', today)
	return today == dates[-1]

def is_weekday_job(target_weekday):
	if DEBUG_DAILY_MODE:
		return True

	current_date = datetime.now()
	dt_str = current_date.strftime('%Y%m%d')
	date = get_trading_dates('399101.SZ', dt_str)
	#print(f"last 7 days:\n{date}")
	for day in range(1, target_weekday + 1):
		yesterday = current_date - timedelta(days=day)
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = date[-(day+1)]
		#print(f"last_date {last_date}   yesterday {dt_str}")
		if day < target_weekday:
			if last_date != dt_str:
				return False
		else:
			if last_date != dt_str:
				if (current_date.weekday() + 1) != target_weekday:
					print(f'{current_date} 是周{current_date.weekday() + 1}')
				#print("return True")
				return True
	return False

def get_last_price(stock):
	full_tick_dict = xtdata.get_full_tick([stock])
	for key, price in full_tick_dict.items():
		if key == stock and price:
			if price['lastPrice'] == 0:
				print(stock, " 获取当前价格异常,股价为0")
			return price['lastPrice']
	print(stock, " 获取当前价格异常")
	return None

def get_positions():
	positions = {}
	objlist = g.xt_trader.query_stock_positions(g.account)
	for obj in objlist:
		stock = obj.stock_code
		positions[stock] = obj

	return positions

def get_current_holding_stocks():
	xt_trader = g.xt_trader
	acc = g.account
	current_holdings = []
	#print("get_current_holding_stocks")
	positions = xt_trader.query_stock_positions(acc)
	for pos in positions:
		if pos.volume == 0:
			continue
		#print(pos.stock_code)
		if pos.stock_code in g.positions[MOM_IDX]:
			continue
		current_holdings.append(pos.stock_code)

	return current_holdings

def get_specified_date_price(stock, query_date, type='none'):
	dt_str = query_date.strftime('%Y%m%d%H%M%S')
	xtdata.download_history_data(stock,period='1d',incrementally=True)
	#xtdata.subscribe_quote(stock, period = '1d')
	history_data = xtdata.get_market_data_ex(['close'],
											 [stock],
											 period='1d',
											 start_time='',
											 end_time=dt_str,
											 count=1,
											 dividend_type=type)
	for key, price in history_data.items():
		if key == stock and not price.empty:
			price = history_data[stock].iloc[0]['close']
			return price
		else:
			return float('nan')

def is_limit_up(stock):
	#今日是否已经涨停
	current_price = get_last_price(stock)
	if current_price is None or current_price == 0:
		return False

	detail = xtdata.get_instrument_detail(stock)
	limit_up_price = detail["UpStopPrice"]
	if math.isnan(limit_up_price) or limit_up_price is None:
		return False

	if current_price >= limit_up_price:
		return True

	return False

def is_limit_down(stock):
	#今日是否已经跌停
	current_price = get_last_price(stock)
	if current_price is None or current_price == 0:
		return False

	detail = xtdata.get_instrument_detail(stock)
	limit_down_price = detail['DownStopPrice']
	if math.isnan(limit_down_price) or limit_down_price is None:
		return False

	if current_price <= limit_down_price:
		return True

	return False

def is_specified_date_limit_up(stock, query_date):
	current_price = get_specified_date_price(stock, query_date, 'front')
	if math.isnan(current_price):
		return False

	yesterday = query_date - timedelta(days=1)
	query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
	prev_price = get_specified_date_price(stock, query_date, 'front')
	if math.isnan(prev_price):
		return False

	limit_up_price = prev_price * 1.099
	if current_price >= limit_up_price:
		return True

	return False

def get_sw2_industry():
	"""获取申万二级行业映射"""
	sector_list = xtdata.get_sector_list()
	sw2_list = [s for s in sector_list if s[:3].lower() == 'sw2' and '加权' not in s]
	stocks = xtdata.get_stock_list_in_sector('399101.SZ')
	ret = {}
	for sw2 in sw2_list:
		s_list = xtdata.get_stock_list_in_sector(sw2)
		for stock in stocks:
			if stock in s_list:
				ret[stock] = sw2[3:]
	return ret

def get_market(stock_list):
	"""获取股票总市值"""
	guben = {}
	for stock in stock_list:
		#xtdata.download_history_data(stock,period='1d',incrementally=True)
		TotalVolume = xtdata.get_instrument_detail(stock)['TotalVolume'] # 总股本
		#print(stock, " 市值 ", TotalVolume)
		guben[stock] = TotalVolume

	price_data = xtdata.get_full_tick(stock_list)
	#print(price_data)
	market = {}
	for key, price in price_data.items():
		gb = guben.get(key)
		value = price['lastPrice']
		if gb is None or math.isnan(gb) or math.isnan(value):
			continue
		market[key] = gb * value

	return market

def get_userdata_mini_path():
	"""检查多个可能的userdata_mini路径，返回第一个存在的"""
	candidates = [
		'C:\\QMT\\国金证券QMT交易端\\userdata_mini',
		'D:\\国金证券QMT交易端\\userdata_mini',
		'C:\\QMT\\userdata_mini',
	]
	for p in candidates:
		if os.path.exists(p):
			print(f'QMT路径: {p}')
			return p
	print('未找到userdata_mini路径，使用默认路径')
	return candidates[0]

def init():
	print("init — 双策略合并版")
	path = get_userdata_mini_path()
	session_id = int(time.time())
	g.xt_trader = XtQuantTrader(path, session_id)
	g.callback = MyXtQuantTraderCallback()
	g.xt_trader.register_callback(g.callback)
	g.xt_trader.start()
	connect_result = g.xt_trader.connect()
	print('建立交易连接，返回0表示连接成功', connect_result)

	g.account = StockAccount('8885388757')

	info = g.xt_trader.query_stock_asset(g.account)

	# 多策略配置
	g.portfolio_value_proportion = [0.05, 0.95]
	# 每个策略的预留现金（买卖驱动），互相隔离
	g.cash_reserved = {MOM_IDX: g.portfolio_value_proportion[MOM_IDX] * info.cash,
					   SC_IDX: g.portfolio_value_proportion[SC_IDX] * info.cash}
	#记录上一交易日现金
	g.cash_record = g.cash_reserved.copy()
	# 各策略持仓股票集合，初始化时扫描已有持仓归入对应策略
	g.positions = {MOM_IDX: set(), SC_IDX: set()}
	positions = g.xt_trader.query_stock_positions(g.account)
	for pos in positions:
		if pos.volume == 0:
			continue
		if pos.stock_code in ETF_POOL:
			g.positions[MOM_IDX].add(pos.stock_code)
		else:
			g.positions[SC_IDX].add(pos.stock_code)

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
	g.each_cash = info.cash / g.stock_num
	g.last_pos_value = info.total_asset
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
	print("初始化申万二级行业映射...")
	g.industry_dict = get_sw2_industry()
	print(f"行业映射完成，共 {len(g.industry_dict)} 只股票")

	m_ratio = g.portfolio_value_proportion[MOM_IDX] * 100
	s_ratio = g.portfolio_value_proportion[SC_IDX] * 100
	print(f"{green_c}双策略初始化完成: 动量{m_ratio}% + 小市值{s_ratio}%\033[0m")
	print(f"  初始资产 {info.total_asset:.2f}, 可用资金 {info.cash:.2f}")

	sc_info_position()

def closeQMT():
	current_date = datetime.now()
	if current_date.weekday() != 4:
		return
	kill_process_by_name("XtMiniQmt.exe")

def reopenQMT():
	current_date = datetime.now()
	if current_date.weekday() != 4:
		return
	open_QMT()

def reconnect():
	current_date = datetime.now()
	if current_date.weekday() != 4:
		return
	print("reconnect")
	# path为mini qmt客户端安装目录下userdata_mini路径
	path = get_userdata_mini_path()
	session_id = int(time.time())
	g.xt_trader = XtQuantTrader(path, session_id)
	print("new g.xt_trader")
	g.xt_trader.register_callback(g.callback)
	g.xt_trader.start()
	print("start")
	connect_result = g.xt_trader.connect()
	print('建立交易连接，返回0表示连接成功', connect_result)


def kill_process_by_name(name):
	"""终止所有名称包含 name 的进程"""
	try:
		subprocess.run(['taskkill', '/f', '/im', name], capture_output=True,text=True,check=True)
		print(f"close {name} success")
	except subprocess.CalledProcessError as e:
		print(f"close {name} failed {e.stderr}")

def open_QMT():
	try:
		subprocess.run(['py', 'login.py'], capture_output=False,text=True,check=True)
		print(f"open QMT success")
	except subprocess.CalledProcessError as e:
		print(f"open QMT failed {e.stderr}")

def shutdown_scheduler(signum, frame):
	"""信号处理函数"""
	print(f"\n收到信号 {signum}，关闭调度器...")
	scheduler.shutdown(wait=False)
	print("调度器已关闭")
	tee.close()
	sys.exit(0)


def run_strategy():
	signal.signal(signal.SIGINT, shutdown_scheduler)
	signal.signal(signal.SIGTERM, shutdown_scheduler)

	# ===== 小市值策略 =====
	if g.portfolio_value_proportion[SC_IDX] > 0:
		scheduler.add_job(sc_judge_date,         'cron', hour=9,  minute=30)
		scheduler.add_job(sc_prepare_stock_list, 'cron', hour=9,  minute=31)
		scheduler.add_job(sc_trade_etf,          'cron', hour=9,  minute=35)
		scheduler.add_job(sc_rebalance_sell,     'cron', hour=9,  minute=55)
		scheduler.add_job(sc_stop_loss,          'cron', hour=10, minute=15)
		scheduler.add_job(sc_rebalance_buy,      'cron', hour=10, minute=30)
		scheduler.add_job(sc_check_limit_up,     'cron', hour=14, minute=10)
		scheduler.add_job(sc_check_remain_amount,'cron', hour=14, minute=12)
		scheduler.add_job(sc_info_position,      'cron', hour=15, minute=2)

	# ===== 动量策略（每天 11:00） =====
	if g.portfolio_value_proportion[MOM_IDX] > 0:
		scheduler.add_job(mom_rebalance, 'cron', hour=11, minute=0)

	#scheduler.add_job(closeQMT,              'cron', hour=15, minute=10)
	#scheduler.add_job(reopenQMT,             'cron', hour=18, minute=0)
	#scheduler.add_job(reconnect,             'cron', hour=18, minute=10)

	try:
		print("start")
		scheduler.start()
		print(f"{green_c}调度器已启动 — 动量(每天11:00) + 小市值(周二) \033[0m")
	except (KeyboardInterrupt, SystemExit):
		print("服务已手动停止")

	while True:
		print("sleep a day")
		sleep_hours(24)


# ================================================================
# 下单函数（策略感知版）
# ================================================================

MOM_IDX = 0   # 动量策略索引
SC_IDX = 1    # 小市值策略索引

def get_tick_size(stock):
	#获取5挡盘口
	tick_data = xtdata.get_full_tick([stock])
	size = 0
	if stock in tick_data:
		sell_price = tick_data[stock]['askPrice']
		if sell_price[0] > 0:
			size = abs(sell_price[1] - sell_price[0])
		else:
			buy_price = tick_data[stock]['bidPrice']
			if buy_price[0] > 0:
				size = abs(buy_price[0] - buy_price[1])
			
		if size:
			if size < 0.009:
				return 0.001
			else:
				return 0.01
	else:
		print(f"{stock} 获取五档价格失败，返回默认值0.01")

	return 0.01

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

def sell_target_value(stock, target_value, strat_idx=None):
	if DEBUG_DAILY_MODE:
		return
	positions = g.xt_trader.query_stock_positions(g.account)
	async_seq = None
	for pos in positions:
		if stock != pos.stock_code:
			continue

		if pos.volume == 0:
			print(f'{stock} 没有持仓，无法卖出')
			break

		if target_value == 0 and not is_limit_down(stock):
			async_seq = g.xt_trader.order_stock_async(g.account, 
													stock,                                #stock_code
													xtconstant.STOCK_SELL,                #order_type
													pos.volume,                           #order_volume
													xtconstant.MARKET_PEER_PRICE_FIRST,   #price_type: 以对手最优价卖出，既买一价
													0,                                    #price: 当price_type是FIXED时，需要填确切价格
													'',                                   #strategy_name
													f'清仓{stock} '                       #order_remark
			)
		else:
			volume = pos.market_value - target_value
			if volume > 0:
				current_price = get_last_price(stock)
				amount = int(volume / current_price / 100) * 100
				if amount < 100:
					print(f"{stock} {get_stock_name(stock)} 现价{current_price:.2f} 期望持仓 {target_value:.2f}元,")
					print(f"现有持仓 {pos.market_value:.2f}元，相差 {volume:.2f}元，需要卖出股数 {volume / current_price:.2f}不足100股，放弃交易")
				else:
					tick_size = get_tick_size(stock)
					detail = xtdata.get_instrument_detail(stock)
					limit_down_price = detail['DownStopPrice']
					sell_price = max(current_price - tick_size * 10, limit_down_price)
					async_seq = g.xt_trader.order_stock_async(g.account, 
															stock,							#stock_code
															xtconstant.STOCK_SELL,			#order_type
															amount,							#order_volume
															xtconstant.FIX_PRICE,			#price_type: 以固定价格卖出
															sell_price,						#price: 当price_type是FIXED时，需要填确切价格
															'',								#strategy_name
															f'Sell {stock} {target_value}元 '   #order_remark
					)

					print(f"sell {stock} passorder target value {target_value:.2f} current {pos.market_value:.2f} amount {amount} @{sell_price:.2f}")
		break
	print("async_seq ", async_seq)
	if async_seq == -1 or async_seq is None:
		print(f"sell_target_value failed {stock} {get_stock_name(stock)}")

	if async_seq != -1 and async_seq is not None and strat_idx is not None and not is_limit_down(stock):
		# 卖出成功，现金回血
		commission = calc_commission(pos.market_value - target_value)
		tax = calc_sell_tax(pos.market_value - target_value, stock)
		cash_incr = pos.market_value - target_value - commission - tax
		g.cash_reserved[strat_idx] += cash_incr
		print(f"卖出 {stock} 手续费 {commission}，印花税 {tax}")
		if target_value == 0:
			g.positions[strat_idx].discard(stock)
			print(f"成功清仓 {stock} 后，策略{strat_idx} 增加资金{cash_incr:.2f}, 现有资金为 {g.cash_reserved[strat_idx]:.2f}")
		else:
			print(f"成功卖出 {stock} 后，策略{strat_idx} 增加资金{cash_incr:.2f}, 现有资金为 {g.cash_reserved[strat_idx]:.2f}")

def buy_target_value(stock, target_value, strat_idx=None):
	if DEBUG_DAILY_MODE:
		return
	positions = get_positions()
	async_seq = None
	current_value = positions[stock].market_value if stock in positions else 0

	volume = target_value - current_value
	# 策略账面资金限额
	if strat_idx is not None:
		volume = min(volume, get_strategy_available_cash(strat_idx))

	if volume > 0:
		current_price = get_last_price(stock)
		amount = int(volume / current_price / 100) * 100
		if amount < 100:
			print(f"{stock} {get_stock_name(stock)} 现价{current_price:.2f} 期望持仓 {target_value:.2f}元,")
			print(f"现有持仓 {current_value:.2f}元，相差 {volume:.2f}元，需要买入股数 {volume / current_price:.2f}不足100股，放弃交易")
		else:
			tick_size = get_tick_size(stock)
			buy_price = current_price + tick_size * 10
			async_seq = g.xt_trader.order_stock_async(g.account, 
													stock,								#stock_code
													xtconstant.STOCK_BUY,				#order_type
													amount,								#order_volume
													xtconstant.FIX_PRICE,				#price_type: 以对手最优价买入，既卖一价
													buy_price,							#price: 当price_type是FIXED时，需要填确切价格
													'',                                 #strategy_name
													f'Buy {stock} Tgt {target_value}元 '	#order_remark
			)

			print(f"buy {stock} passorder target value {target_value:.2f} current {current_value:.2f} amount {amount} @{buy_price:.2f}")
			if async_seq != -1 and async_seq is not None and strat_idx is not None:
				estimate_cash = amount * (current_price + tick_size)
				commission = calc_commission(estimate_cash)
				g.cash_reserved[strat_idx] -= (estimate_cash + commission)
				g.positions[strat_idx].add(stock)
				print(f"成功买入 {stock} 后，策略{strat_idx} 减少资金{estimate_cash:.2f}, 再扣除佣金{commission:.1f}, 现有资金为 {g.cash_reserved[strat_idx]:.2f}")

	print("async_seq ", async_seq)
	if async_seq == -1 or async_seq is None:
		print(f"buy_target_value failed {stock} {get_stock_name(stock)}")

def buy_target_shares(stock, amount, strat_idx=None):
	if DEBUG_DAILY_MODE:
		return

	current_price = get_last_price(stock)
	if not current_price:
		return

	tick_size = get_tick_size(stock)
	buy_price = current_price + tick_size * 10
	async_seq = g.xt_trader.order_stock_async(g.account, 
											stock,								#stock_code
											xtconstant.STOCK_BUY,               #order_type
											amount,                               #order_volume
											xtconstant.FIX_PRICE,               #price_type: 以对手最优价买入，既卖一价
											buy_price,							#price: 当price_type是FIXED时，需要填确切价格
											'',                                 #strategy_name
											f'Buy {stock} {amount}股'     #order_remark
											)  
	print(f"buy {stock} {amount}股 @ {current_price:.2f}")
	print(f"async_seq {async_seq}")
	if async_seq == -1:
		print(f"buy_target_shares failed {stock} {get_stock_name(stock)}")
	if async_seq != -1 and async_seq is not None and strat_idx is not None:
		estimate_cash = amount * (current_price + tick_size)
		commission = calc_commission(estimate_cash)
		g.cash_reserved[strat_idx] -= (estimate_cash + commission)
		g.positions[strat_idx].add(stock)
		print(f"成功买入 {stock} 后，策略{strat_idx} 减少资金{estimate_cash:.2f}, 再扣除佣金{commission:.1f}, 现有资金为 {g.cash_reserved[strat_idx]:.2f}")


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
ETF_DIP_MIN = {  # 近3日单日急跌过滤阈值（ratio = 1 - 跌幅%），按各ETF历史波动特征设定
    "513100.SH": 0.95,  # 纳指ETF — 5%
    "513520.SH": 0.95,  # 日经ETF — 5%
    "513030.SH": 0.95,  # 德国ETF — 5%
    "518880.SH": 0.96,  # 黄金ETF — 4%
    "159980.SZ": 0.95,  # 有色ETF — 5%
    "159985.SZ": 0.97,  # 豆粕ETF — 3%（历史最大跌仅5.9%，5%太松）
    "511090.SH": 0.98,  # 30年国债 — 2%（历史从未跌超3%，5%永不触发）
    "501018.SH": 0.94,  # 南方原油 — 6%（波动大，5%触发太频繁）
    "513130.SH": 0.94,  # 恒生科技 — 6%
    "515980.SH": 0.94,  # 人工智能 — 6%
}

def get_strategy_available_cash(strat_idx):
	"""策略剩余可用现金（直接返回预留现金）"""
	return max(0, g.cash_reserved[strat_idx])

def get_strategy_total(strat_idx):
	"""策略当前实际总资产 = 预留现金 + 持仓市值（随市价波动）"""
	positions = get_positions()
	holdings_value = 0
	for stock in g.positions[strat_idx]:
		if stock in positions:
			holdings_value += positions[stock].market_value
	return g.cash_reserved[strat_idx] + holdings_value

def calc_momentum_scores(etf, days):
	"""计算单只ETF当日以及上一日的动量得分。返回 (annualized_return, r2, min_recent_ratio, score, score_last)"""
	# 获取历史数据
	xtdata.download_history_data(etf, period='1d', incrementally=True)
	history_data = xtdata.get_market_data_ex(['close'],
											 [etf],
											 period='1d',
											 start_time='',
											 fill_data=False,
											 dividend_type='front',
											 count=days+2)
	if etf not in history_data or history_data[etf].empty:
		return 0, 0, 0, 0, 0

	close_prices = history_data[etf]['close'].values
	prices = close_prices[1:]
	print(prices)

	annualized_return, r2, score, min_recent_ratio = calc_momentum_score(prices)

	prices_last = close_prices[:-1]
	_, _, score_last, _ = calc_momentum_score(prices_last)

	return annualized_return, r2, min_recent_ratio, score, score_last

def calc_momentum_score(prices):
	"""计算单只ETF的动量得分。返回 (annualized_return, r2, score, min_recent_ratio)。"""

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

	# 近3日急跌
	if len(prices) >= 4:
		recent_ratios = [prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]]

	return annualized_return, r2, score, min(recent_ratios)

def select_etf():
	"""双动量选股：短期(25天) + 长期(250天)。

	返回: ETF代码列表（1只或2只）
	"""
	def filter_etf(max_score_map, days, label):
		print(f"\n========== [{label}] 开始 (窗口={days}天) ==========")
		results = {}
		for etf in ETF_POOL:
			ann_ret, r2, recent_ratio, score, score_last = calc_momentum_scores(etf, days)
			name = get_stock_name(etf) or etf
			max_score = max_score_map.get(etf)
			dip_min = ETF_DIP_MIN.get(etf, 0.95)
			bad = (score <= 0 or score >= max_score or score_last >= max_score) or recent_ratio < dip_min
			down_ratio = (1 - recent_ratio) * 100
			reason = ''
			if bad:
				reason += ' -> [淘汰]'
				if score >= max_score:
					reason += (f" 分数超出阈值{max_score}")
				elif score_last >= max_score:
					reason += (f" 近2日分数超出阈值{score_last:.2f} > {max_score}")

				if recent_ratio < dip_min:
					reason += (f" 跌幅超出阈值 {(1 - dip_min) * 100:.0f}%")

			print(f"  {name}({etf}): 年化={ann_ret:.4%} R²={r2:.4f} 近3日最大跌幅 {down_ratio:.2f}% 得分={score:.4f}{reason}")
			if not bad: results[etf] = score
		if not results:
			print(f"  无符合条件的ETF → 选用{get_stock_name(SAFE_ETF)}({SAFE_ETF})")
			return SAFE_ETF

		selected = max(results, key=results.get)
		print(f"  >>> {label}最终选出: {get_stock_name(selected)}({selected})")
		return selected

	etf1 = filter_etf(ETF_SHORT_MAX, 25, "短期动量")
	etf2 = filter_etf(ETF_LONG_MAX, 250, "长期动量")

	print(f"\n========== 选股汇总 ==========")
	print(f"  短期动量选出: {get_stock_name(etf1)}({etf1})")
	print(f"  长期动量选出: {get_stock_name(etf2)}({etf2})")

	print("-----------")
	print("  只买短期")
	print("-----------")
	return [etf1]

	if etf1 != etf2:
		print(f"  两者不同 → 各配50%")
		return [etf1, etf2]
	print(f"  两者相同 → 全仓")
	return [etf1]

def mom_rebalance():
	if not is_trading_day():
		return

	print(f'\n{green_c}✅========== [动量策略] 每日调仓 {datetime.now().strftime("%Y-%m-%d")} ==========\033[0m')

	# 选股
	targets = select_etf()
	weights = {etf: 1.0 / len(targets) for etf in targets}

	# 获取总资产
	asset = g.xt_trader.query_stock_asset(g.account)
	strategy_budget = get_strategy_total(MOM_IDX)
	print(f"  总资产: {asset.total_asset:,.2f}, 动量总资产: {strategy_budget:,.2f}")

	all_positions = get_positions()
	# 只清仓策略持仓中不在目标里的ETF
	for stock in list(g.positions[MOM_IDX]):
		if stock not in weights:
			print(f"  [调出] {get_stock_name(stock)}({stock}) → 清仓")
			if is_limit_up(stock):
				print(f"  {get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(stock):
				print(f"  {get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			sell_target_value(stock, 0, MOM_IDX)
			print("sleep 30s")
			sleep_sec(30)
			strategy_budget = get_strategy_total(MOM_IDX)
			print(f"  动量总资产更新: {strategy_budget:,.2f}")

	# 卖出超配
	for stock, weight in weights.items():
		target = strategy_budget * weight
		current_val = all_positions[stock].market_value if stock in all_positions else 0
		price = get_last_price(stock)
		if current_val - target > max(3000, price * 100 if price else 10000):
			print(f"  [减仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			if is_limit_up(stock):
				print(f"  {get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(stock):
				print(f"  {get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			sell_target_value(stock, target, MOM_IDX)
			print("sleep 30s")
			sleep_sec(30)
			strategy_budget = get_strategy_total(MOM_IDX)
			print(f"  动量总资产更新: {strategy_budget:,.2f}")
		else:
			print(f"  [与目标差异太小，不减仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")

	# 买入低配
	for stock, weight in weights.items():
		target = strategy_budget * weight
		current_val = all_positions[stock].market_value if stock in all_positions else 0
		price = get_last_price(stock)
		stra_avi_cash = get_strategy_available_cash(MOM_IDX)
		if min(target - current_val, stra_avi_cash) > max(3000, price * 100 if price else 10000):
			print(f"  [加仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			if is_limit_up(stock):
				print(f"  {get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(stock):
				print(f"  {get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			buy_target_value(stock, target, MOM_IDX)
		else:
			print(f"  [与目标差异太小，不加仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f} 策略资金{stra_avi_cash:,.2f}")

	print(f'{green_c}✅========== [动量策略] 调仓结束 ==========\033[0m\n')


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
			if stock_code in g.industry_dict:
				industry_name = g.industry_dict[stock_code]
				if industry_name not in industry_list:
					industry_list.append(industry_name)
					selected_stocks.append(stock_code)
					if len(industry_list) >= num:
						break
		return selected_stocks
	except Exception as e:
		print(f"行业筛选错误: {e}")
		return stock_list[:num]
	
def get_small_cap_stocks(stock_list, query_date, n=5):
	#获取市值最小的n只股票（修正版：全局排序）
	# 用于存储所有查询到的市值数据
	market = get_market(stock_list)
	#print('market')
	#print(market)
	sorted_market = dict(sorted(market.items(), key=lambda x: x[1], reverse=False))
	#print(sorted_market)

	if n > 30:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[:10]:
			stock_name = get_stock_name(stock)
			cap_in_10k = round(cap / 1e8, 2)
			rank += 1
			marker = '  <== 选中' if rank <= n else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 流通市值: {cap_in_10k} 亿元{marker}')

	#selected_stocks = list(sorted_market)[0:n]
	selected_stocks = small_cap_get_stock_industry(list(sorted_market)[:100], n)

	# 打印选股详情
	flag = any(s not in g.selected_stocks for s in selected_stocks)
	if flag:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[:20]:
			stock_name = get_stock_name(stock)
			cap_in_10k = round(cap / 1e8, 2)
			industry = g.industry_dict.get(stock, '未知')
			rank += 1
			marker = '  <== 选中' if stock in selected_stocks else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 流通市值: {cap_in_10k} 亿元 {industry} {marker}')

	return selected_stocks

def get_normal_stocks():
	"""获取正常交易股票（过滤ST、停牌、涨跌停、退市）"""
	xtdata.download_sector_data()
	stocklist = xtdata.get_stock_list_in_sector('399101.SZ')
	print(f"中小综指成分股数量：{len(stocklist)}")
	print(stocklist[:10])  # 打印前10只成分股

	non_st_stocks = []
	current_holdings = get_current_holding_stocks()
	for stock in stocklist:
		detail = xtdata.get_instrument_detail(stock)
		if not detail:
			print(f'{stock} cannot get instrument detail !!!')
			continue
		stock_name = detail['InstrumentName']
		if 'ST' in stock_name or 'st' in stock_name:
			#print(stock, " ", stock_name)
			continue

		if detail['ExpireDate'] != '99999999':
			print(stock, " 可能退市 ", detail['ExpireDate'])
			continue

		if detail['InstrumentStatus'] < 0:
			print(stock, " 可能停牌 ", detail['InstrumentStatus'])
			continue

		if stock not in current_holdings and is_limit_up(stock):
			print(f'涨停 {stock} {stock_name}')
			continue

		if stock not in current_holdings and is_limit_down(stock):
			print(f'跌停 {stock} {stock_name}')
			continue

		non_st_stocks.append(stock)

	print(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
	return non_st_stocks


# ================================================================
# 小市值策略调度函数
# ================================================================

def sc_judge_date():
	g.is_trading_day = is_trading_day()
	print(f'今天是交易日吗 {g.is_trading_day}')
	
	current_date = datetime.now()
	current_month = current_date.month
	g.count = 1
	if current_month == 1 or current_month == 4:
		if g.trade:
			print(f'{green_c}✅\033[0m========== 一月和四月份清仓，日期：{current_date} ==========')
		g.trade = False
	else:
		g.trade = True
	print('judge_date count ', g.count)

def sc_prepare_stock_list():
	if not g.is_trading_day:
		return
	g.count += 1
	g.hold_list = []
	g.limitup_stocks = []
	g.trade_day = False
	#获取已持有列表
	g.hold_list = get_current_holding_stocks()

	# 获取昨日涨停列表
	current_date = datetime.now()
	yesterday = current_date - timedelta(days=1)
	g.yesterday_HL_list = []
	g.today_HL_list = []

	for stock in g.hold_list:
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = get_trading_dates(stock, dt_str, 1)
		last_date = last_date[0]
		query_date = datetime.strptime(last_date + '150000', '%Y%m%d%H%M%S')

		if is_specified_date_limit_up(stock, query_date):
			g.yesterday_HL_list.append(stock)

	if g.yesterday_HL_list:
		print("")
		print(f"************昨日({yesterday})涨停 **************")
		print(g.yesterday_HL_list)
		print("")


	g.stock_pool = get_normal_stocks()
	g.stoploss_map = {k: v-1 for k, v in g.stoploss_map.items() if v-1 > 0}

	print('prepare_stock_list count ',g.count)

def collect_sell_buy_stocks():
	"""对比选定股票与当前持仓，确定买卖清单"""
	g.stocks_to_sell = []
	g.stocks_to_buy = []
	current_holdings = get_current_holding_stocks()
	for stock in current_holdings:
		if not is_limit_up(stock):
			if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
				g.stocks_to_sell.append(stock)
		else:
			print(f"{red_c}⭕\033[0m {stock} {get_stock_name(stock)} 转为涨停股，今日不卖出。")
			g.today_HL_list.append(stock)
			
	for stock in g.selected_stocks:
		if (stock not in current_holdings) and (stock not in g.yesterday_HL_list):
			g.stocks_to_buy.append(stock)

def sc_trade_etf():
	if not g.is_trading_day:
		return
	if g.trade is False:
		print("trade_etf")
		current_holdings = get_current_holding_stocks()
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
			collect_sell_buy_stocks()
			sell_stocks()
			print("sleep 30s")
			sleep_sec(30)
			exec_all_weather()

def exec_all_weather():
	"""全天候ETF：-1/ES风险平价"""
	query_date = datetime.now()
	for stock in g.all_weather_list:
		xtdata.download_history_data(stock, period='1d', incrementally=True)

	price_data = xtdata.get_market_data_ex(['close'],
											g.all_weather_list,
											period='1d',
											start_time='',
											end_time=query_date.strftime('%Y%m%d'),
											count=120)
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
	total_weight = sum(weights.values())
	
	fin_weights = {key: value / total_weight for key, value in weights.items()}

	for stock, w in fin_weights.items():
		print(f'{stock} {get_stock_name(stock)} 权重{100*w:.2f}%')

	available_cash = get_strategy_available_cash(SC_IDX)
	print('available_cash: ', available_cash)
	for stock in g.all_weather_list:
		current_price = get_last_price(stock)
		if current_price is None or current_price == 0:
			continue
		target_value = available_cash * fin_weights[stock]
		amount = int(target_value / current_price / 100) * 100
		if amount > 0:
			print('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
			print(f'{stock} {get_stock_name(stock)} 目标市值{target_value:.2f}, 买入{amount}股 * {current_price}元')
			buy_target_shares(stock, amount, SC_IDX)
			sleep_sec(1)
			g.refresh_hold = True
		else:
			print('=====================================')
			print(f"{stock} {get_stock_name(stock)} 未买入, 目标市值{target_value:.2f}, 股价 {current_price}元, amount {target_value / current_price:.2f}")

def sc_rebalance_sell():
	if not is_weekday_job(g.weekday):
		return
	if not g.is_trading_day:
		return
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = datetime.now()
	print(f'{green_c}✅\033[0m========== [小市值策略] 周度调仓(卖出) {current_date} ==========')

	sc_info_position()
	query_date = current_date
	g.selected_stocks = get_small_cap_stocks(g.stock_pool, query_date, g.stock_num)
	for stock in list(g.stoploss_map.keys()):
		if stock in g.selected_stocks:
			g.selected_stocks.remove(stock)
			print(f"{stock} {get_stock_name(stock)} 前{3 - g.stoploss_map[stock]}日止损卖出，3日内不再买入")
		

	collect_sell_buy_stocks()
	current_holdings = get_current_holding_stocks()

	if g.stocks_to_buy or g.stocks_to_sell:
		print(f"{green_c}✅\033[0m当前持股 {len(current_holdings)}只")
		current_holdings.sort()
		for stock in current_holdings:
			print(get_stock_name(stock))
			
		print(f"{green_c}✅\033[0m需要买入股票 {len(g.stocks_to_buy)}只")
		print(f"{green_c}✅\033[0m需要卖出股票 {len(g.stocks_to_sell)}只")
		for stock in g.stocks_to_buy:
			print(f"{green_c}✅\033[0m待买入 ", get_stock_name(stock))
		for stock in g.stocks_to_sell:
			print(f'{green_c}✅\033[0m待卖出: {get_stock_name(stock)}')
			
			
		print(f"{green_c}✅\033[0m今日({current_date})为卖出时间，执行卖出操作")
		print(f'{green_c}✅\033[0m------------------------------------------')
		# 执行卖出逻辑
		sell_stocks()
		# 标记卖出已完成
		g.sell_done = True
		

	else:
		print('未选到符合条件的股票，本日不调仓')

	print('rebalance_sell count ',g.count)

def sc_rebalance_buy():
	#卖出股票后才有钱买入
	if not is_weekday_job(g.weekday):
		return
	if not g.is_trading_day:
		return
	if not g.sell_done:                     #卖出股票后才有钱买入
		return
	#止盈之后不再买入
	if g.reason_to_sell == 'takeprofit':
		return
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = datetime.now()
	print(f'{green_c}✅\033[0m========== [小市值策略] 周度调仓(买入) {current_date} ==========')
	# 执行买入逻辑
	if g.stocks_to_buy:
		print(f"{green_c}✅\033[0m今日({current_date})为买入时间，执行买入操作")
		print(f'{green_c}✅\033[0m+++++++++++++++++++++++++++++++++++++++++')
		print(f"{green_c}✅\033[0m需买入 {len(g.stocks_to_buy)}只")
		for stock in g.stocks_to_buy:
			print(get_stock_name(stock))

	sc_calc_position()
	buy_stocks()
	# 重置卖出标记
	g.sell_done = False
	print("sleep 30s")
	sleep_sec(30)
	sc_info_position()
	print('rebalance_buy count ', g.count)

def sc_calc_position():
	CASH_YU = 5000
	"""等权仓位计算 + 偏差修正"""
	strategy_total = get_strategy_total(SC_IDX)
	current_holdings = get_current_holding_stocks()
	holding_num = len(current_holdings) + len(g.stocks_to_buy)

	if  holding_num != len(g.selected_stocks):
		print(f'{red_c}❌❌\033[0m 股票数量异常，可能最终持仓{holding_num}只，实际选中{len(g.selected_stocks)}只')
		
	positions = get_positions()
	fail_pos = 0
	for stock in g.stocks_fail_sell:
		fp = positions[stock].market_value / strategy_total
		fail_pos += fp
		print(f'停牌股 {get_stock_name(stock)} 占仓位 {fp*100:.2f}%')
	HL_count = 0
	for stock in current_holdings:
		if (stock in g.yesterday_HL_list) or (stock in g.today_HL_list):
			fp = positions[stock].market_value / strategy_total
			fail_pos += fp
			HL_count += 1
			print(f'涨停股 {get_stock_name(stock)} 占仓位 {fp*100:.2f}%')

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
	for i, stock in enumerate(g.selected_stocks):

		if stock in g.stocks_fail_sell or stock in g.yesterday_HL_list or stock in g.today_HL_list:
			continue
		g.excepted_position[stock] = p
		
	for stock, pos in g.excepted_position.items():
		print(f'  期望持仓: {get_stock_name(stock)}({stock}), {pos*100:.2f}%')

	# 预估持仓
	position_dict = {} #记录实际仓位比重
	position_sum = 0
	#计算已有持仓的股票占比
	for stock, pos in positions.items():
		if stock in g.positions[MOM_IDX]:
			continue  # 跳过动量策略的ETF持仓
		current_price = get_last_price(stock)
		if current_price is None or current_price == 0:
			continue
		position_sum += pos.market_value
		position_dict[stock] = pos.market_value / strategy_total, current_price
	
	#计算待买入的股票的持仓占比
	for stock in g.stocks_to_buy:
		current_price = get_last_price(stock)
		if current_price is None or current_price == 0:
			g.excepted_position.pop(stock)
			continue
		stock_name = get_stock_name(stock)
		target_value = strategy_total * g.excepted_position[stock]
		amount = int(target_value / current_price / 100) * 100
		need_cash = amount * current_price
		print(f'预计买入{stock_name}({stock})  {amount} 股 * {current_price:.2f},总计 {need_cash:.2f}')
		position_sum += need_cash
		position_dict[stock] = [need_cash / strategy_total, current_price]
		
	avai_cash = strategy_total - position_sum
	print(f'预计持仓 {position_sum} 剩余金额 {avai_cash:.2f}')
	if abs(avai_cash) > CASH_YU or avai_cash < 0:
		print(f'{red_c}⭕⭕\033[0m剩余资金过大 {strategy_total - position_sum:.2f}')
		cash = 0
		for stock, exce_pos in g.excepted_position.items():
			if stock in g.stocks_fail_sell:
				continue
			pos_frac, stock_price = position_dict[stock]
			diff_pos = exce_pos - pos_frac

			if abs(diff_pos) * strategy_total > CASH_YU or abs(diff_pos) > 0.04:
				stock_name = get_stock_name(stock)
				print(f'{green_c}✅\033[0m{stock_name} 持仓与期望相差较大，持仓{pos_frac*100:.2f}%, 期望{exce_pos*100:.2f}%, 金额差额{diff_pos * strategy_total:.2f}')
				if diff_pos > 0:
					g.stocks_to_buy.append(stock)
					cash -= diff_pos * strategy_total
				else:
					current_price = get_last_price(stock)
					if current_price is None or current_price == 0:
						continue
					amount = abs(avai_cash) / current_price
					if amount < 100:
						continue
					detail = xtdata.get_instrument_detail(stock)
					is_paused = detail['InstrumentStatus'] < 0
					if is_paused:
						continue
					if is_limit_down(stock):
						continue
					if positions[stock].can_use_volume < 100:
						continue

					sell_target_value(stock, exce_pos * strategy_total, SC_IDX)
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
			print('资金仍有剩余，追加买入')
			pos_dict = {}
			for stock, exce_pos in g.excepted_position.items():
				if stock in g.stocks_fail_sell or stock in g.stocks_to_buy:
					continue
				pos_frac, _ = position_dict[stock]
				diff_pos = exce_pos - pos_frac
				if diff_pos > 0:
					pos_dict[stock] = diff_pos
					
			sorted_pos = list(sorted(pos_dict.items(), key=lambda x: x[1], reverse=True))
			for stock, diff_pos in sorted_pos:
				stock_name = get_stock_name(stock)
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
				print(f'期望持仓: {get_stock_name(stock)}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')

	# 排序并打印预估持仓
	position_dict_sorted = dict(sorted(position_dict.items(), key=lambda x: x[0]))
	for stock, pos_data in position_dict_sorted.items():
		stock_name = get_stock_name(stock)
		print(f' 预估持仓: {stock_name}({stock}), 占比 {pos_data[0]*100:.2f}% 单价 {pos_data[1]:.2f}')
		

	# 调整买入数量（微调手数）
	for stock, exce_pos in g.excepted_position.items():
		if stock in g.stocks_fail_sell:
			continue
		pos, stock_price = position_dict[stock]
		diff_value = (exce_pos - pos) * strategy_total
		
		stock_name = get_stock_name(stock)
		current_price = get_last_price(stock)
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
					print(f'{green_c}✅\033[0m调整买入数量，追加{num}手,仓位占比调整为{g.excepted_position[stock] * 100:.2f}%')
					
		'''
		amount = int(diff_value / current_price / 100) * 100
		if amount > 0:
			if stock not in g.stocks_to_buy:
				g.stocks_to_buy.append(stock)
			print(f'{stock_name}({stock}) 可以再买入{amount}')
		'''
	
def sc_check_limit_up():
	if not g.is_trading_day:
		return
	g.count += 1
	if g.yesterday_HL_list != []:
		#对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
		for stock in g.yesterday_HL_list:
			info = xtdata.get_instrument_detail(stock)
			current_price = get_last_price(stock)
			prev_price = info['PreClose']
			rise_ratio = (current_price - prev_price) / prev_price * 100
			print(f'{stock} {get_stock_name(stock)} 股价{current_price} 涨幅{rise_ratio:.2f}%')

			limit_up_price = info['UpStopPrice']
			if current_price < limit_up_price:
				print(f"{stock} {get_stock_name(stock)}涨停打开，卖出")
				sell_target_value(stock, 0, SC_IDX)
				g.reason_to_sell = 'limitup'
				g.limitup_stocks.append(stock)
			else:
				print(f"{stock} {get_stock_name(stock)}涨停，继续持有")

	print('check_limit_up count ', g.count)

def sc_check_remain_amount():
	#如果昨天有股票卖出或者买入失败，剩余的金额今天买入
	if not g.is_trading_day:
		return
	g.count += 1
	#判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
	if g.reason_to_sell == 'limitup':
		g.hold_list = get_current_holding_stocks()
		if True:
			print(f'现有持仓:')
			for stock_code in g.hold_list:
				stock_name = get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
			print('涨停卖出')
			for stock_code in g.limitup_stocks:
				stock_name = get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
				
			# 计算需要买入的股票数量
			prev_date = datetime.now() - timedelta(days=1)
			g.selected_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
			for stock in g.limitup_stocks:
				if stock in g.selected_stocks:
					g.selected_stocks.remove(stock)

			for stock in list(g.stoploss_map.keys()):
				if stock in g.selected_stocks:
					g.selected_stocks.remove(stock)
					print(f"{stock} {get_stock_name(stock)} 前{3 - g.stoploss_map[stock]}日止损卖出，3日内不再买入")
			current_holdings = get_current_holding_stocks()
			if len(current_holdings) > 3:
				print("已有持仓数量大于3，不再买入其他较小市值股票。")
				g.selected_stocks = current_holdings
				
			collect_sell_buy_stocks()
			if len(g.stocks_to_buy) > 0:
				print(f"需要买入股票 {len(g.stocks_to_buy)}只")
				for stock in g.stocks_to_buy:
					print("待买入 ", get_stock_name(stock))

			avi_cash = get_strategy_available_cash(SC_IDX)
			print('有余额可用'+str(round((avi_cash),2))+'元。买入'+ str(g.stocks_to_buy))
			sc_info_position()
			sc_calc_position()
			buy_stocks()
			g.refresh_hold = True
		g.reason_to_sell = ''
	elif g.reason_to_sell in ('stoploss', 'takeprofit'):
		avi_cash = get_strategy_available_cash(SC_IDX)
		print(f'止盈止损后余额{avi_cash:.2f}元，买入{g.etf}')
		g.stocks_to_buy = [g.etf]
		buy_stocks()
		g.reason_to_sell = ''
		g.refresh_hold = True

	print("sleep 20s")
	sleep_sec(20)
	sc_info_position()
	print('check_remain_amount count ', g.count)

#止盈止损
def sc_stop_loss():
	if not g.is_trading_day:
		return
	g.count += 1
	show_info = False
	if g.run_stoploss:
		current_positions = get_positions()
		# 过滤掉动量策略的持仓，只保留小市值策略的股票
		current_positions = {k: v for k, v in current_positions.items() if k not in g.positions[MOM_IDX]}
		# 策略1：个股止损止盈
		if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
			for stock in list(current_positions.keys()):
				if current_positions[stock].volume == 0:
					continue
				if stock in g.all_weather_list or stock == g.etf:
					continue

				price = get_last_price(stock)
				avg_cost = current_positions[stock].avg_price
				if avg_cost <= 0:
					continue
				# 个股盈利止盈
				if price >= avg_cost * 2:
					#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
					print(f"{red_c}⭕\033[0m 收益100%止盈,卖出{stock}")
				# 个股止损
				elif price < avg_cost * (1 - g.stoploss_limit):
					sell_target_value(stock, 0, SC_IDX)
					g.stoploss_map[stock] = g.stoploss_map.setdefault(stock, 3)
					print(f"{stock} 股价{price:.2f} 成本{avg_cost:.2f}")
					print(f"{red_c}❌\033[0m 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
					#if order_info != None:
					#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
					show_info = True
					
					g.reason_to_sell = 'stoploss'
					if stock in g.selected_stocks:
						g.selected_stocks.remove(stock)

		# ---- 策略2/3：大盘止损止盈 ----
		if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
			query_date = datetime.now()
			yesterday = query_date - timedelta(days=1)
			query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
			dt_str = query_date.strftime('%Y%m%d%H%M%S')
			price_data = xtdata.get_market_data_ex(['open', 'close'], 
										  ['399101.SZ'], 
										  period='1d', 
										  start_time='', 
										  end_time=dt_str, 
										  count=1,
										  dividend_type='none')
			#print(price_data)
			df = list(price_data.values())[0]
			down_ratio = (df.iloc[0]['close'] / df.iloc[0]['open'] - 1)
			print("大盘涨幅 {:.2%}".format(down_ratio))
			# 市场大涨大跌止盈止损
			if abs(down_ratio) >= g.stoploss_market:
				g.refresh_hold = True
				if down_ratio < 0:
					g.reason_to_sell = 'stoploss'
					print(f"{red_c}❌\033[0m 大盘惨跌,平均降幅{down_ratio:.2%}")
				else:
					g.reason_to_sell = 'takeprofit'
					print(f"{red_c}⭕\033[0m 大盘大涨,平均涨幅{down_ratio:.2%}")
				for stock in list(current_positions.keys()):
					if stock in g.all_weather_list or stock == g.etf:
						continue
					if stock in g.yesterday_HL_list or is_limit_up(stock):
						continue
					print(f'{red_c}⭕\033[0m 清仓{stock} {get_stock_name(stock)}')
					sell_target_value(stock, 0, SC_IDX)
					#if order_info != None:
					#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
					show_info = True
					if stock in g.selected_stocks:
						g.selected_stocks.remove(stock)

	if show_info:
		print("sleep 30s")
		sleep_sec(30)
		sc_info_position()

	print('stop_loss count ', g.count)

def sell_stocks():
	"""执行卖出"""
	g.stocks_fail_sell = []
	for stock in g.stocks_to_sell:
		print(f'{green_c}✅\033[0m>>>>>>>>>>>>')
		print(f'{green_c}✅\033[0m卖出: {get_stock_name(stock)}')
		sell_target_value(stock, 0, SC_IDX)
		detail = xtdata.get_instrument_detail(stock)
		is_paused = detail['InstrumentStatus'] < 0 if detail else False
		if is_paused or is_limit_down(stock):
			g.stocks_fail_sell.append(stock)
			print(f'{get_stock_name(stock)} 停牌或跌停，卖出失败')

def buy_stocks():
	"""执行买入"""
	if g.stocks_to_buy:
		available_cash = get_strategy_available_cash(SC_IDX)
		position_value = 0
		positions = get_positions()
		for stock, pos in positions.items():
			if stock not in g.positions[MOM_IDX]:
				position_value += pos.market_value

		strategy_total = get_strategy_total(SC_IDX)
		g.each_cash = available_cash / len(g.stocks_to_buy)
		print("====调整每股额度====\n当前可用资金 ", available_cash, "\n持仓市值 ",
		position_value, "\n总资产: ", strategy_total, "\n每股额度 ", g.each_cash)
		# 计算每只股票的目标市值（等权重）
		# 获取当前总资产
		
		target_value_per_stock = g.each_cash  # 计算每只股票的目标市值（等权重）
		for stock in g.stocks_to_buy:
			current_price = get_last_price(stock)
			if current_price is None or current_price == 0:
				continue

			print("")
			available_cash = get_strategy_available_cash(SC_IDX)
			print(f'{green_c}✅\033[0m===可用资金 {available_cash}===')

			if stock == g.etf:
				target_value_per_stock = min(available_cash, target_value_per_stock)
				amount = int(target_value_per_stock / current_price / 100) * 100
				if amount > 0:
					print(f'买入ETF {stock} {get_stock_name(stock)} 目标市值{target_value_per_stock:.2f}, {amount}股 * {current_price}元')
					buy_target_shares(stock, amount, SC_IDX)
			else:
				if g.excepted_position.get(stock) is not None:
					target_value_per_stock = g.excepted_position[stock] * strategy_total
					current_value = 0
					positions = get_positions()
					if stock in positions:
						current_value = positions[stock].market_value
					target_value_per_stock = min(available_cash + current_value, target_value_per_stock)
				
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				print(f'委托买入: {get_stock_name(stock)}, {stock} \n目标价值:{target_value_per_stock:.2f}'
					f'\n预计最终持股{amount}股，每股{current_price:.2f}元，合计:{amount * current_price:.2f}')
				buy_target_value(stock, target_value_per_stock, SC_IDX)
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

def sc_info_position():
	current_date = datetime.now()
	positions = g.xt_trader.query_stock_positions(g.account)
	
	if len(positions) > 0:
		info = g.xt_trader.query_stock_asset(g.account)
		available_cash = info.cash
		position_value = info.market_value
		total_value = info.total_asset
		print(f'******************当日({current_date}) (周{current_date.weekday()+1}) 持仓市值: {position_value:.2f}元*******************')

		#sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for pos in positions:
			stock = pos.stock_code
			stock_name = get_stock_name(stock)
			if pos.volume == 0:
				continue
			if pos.avg_price <= 0:
				continue
			price = pos.market_value / pos.volume
			ratio = (price / pos.avg_price - 1) * 100
			color = red_c if ratio > 0 else green_c
			blank = get_blank(ratio)
			diff_price = price - pos.avg_price
			industry = g.industry_dict.get(stock,None)
			print(f"{green_c}✅\033[0m{stock_name}({stock}) 占比 {pos.market_value / total_value * 100:.2f}% 涨幅: {color}{blank}{ratio:.2f}% ({diff_price * pos.volume:.2f})\033[0m x {pos.volume} = {pos.market_value:.1f}元 {industry}")

		for pos in positions:
			stock = pos.stock_code
			stock_name = get_stock_name(stock)
			if pos.volume == 0:
				print(f"{green_c}✅\033[0m持仓: {stock_name}({stock}) 0股")

		print(f'{green_c}✅\033[0m*******************总资产 {total_value:.2f} 剩余可用金额 {available_cash:.2f}元*******************')

		# 打印各策略资金隔离状况
		for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
			cash = g.cash_reserved[idx]
			stock_set = g.positions[idx]
			holdings_val = 0
			stock_names = []
			for pos in positions:
				stock = pos.stock_code
				if stock in stock_set:
					holdings_val += pos.market_value
					stock_names.append(get_stock_name(stock))

			total = cash + holdings_val
			print(f'  [{name}策略] 预留现金: {cash:,.2f} | 持仓市值: {holdings_val:,.2f} | 总资产: {total:,.2f}')
			#stock_names = [f'{get_stock_name(s)}({s})' for s in stock_set if s in positions]
			if stock_names:
				print(f'    持仓: {", ".join(stock_names)}')
			else:
				print(f'    持仓: (空)')
		print()

		if current_date.hour >= 15:
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

				if abs(cash_diff / available_cash) > 0.3:
					print("资金差额较大，可能代码有问题，请调试。如果当日有转账，则2个策略分走一半差额资金")
					for idx, name in [(MOM_IDX, '动量'), (SC_IDX, '小市值')]:
						g.cash_reserved[idx] += cash_diff / 2
						g.cash_record[idx] = g.cash_reserved[idx]
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
			rate_of_return = daily_return / g.last_pos_value * 100
			color = red_c if daily_return > 0 else green_c
			print('==============================')
			print(f'今日股票收益: {color}{daily_return:.2f}\033[0m 元')
			print(f'收益率:       {color}{rate_of_return:.2f} %\033[0m')
			print('==============================\n\n')
			g.last_pos_value = total_value



if __name__ == '__main__':
	init()
	run_strategy()

	#=============================
	#DEBUG_DAILY_MODE == True
	#=============================
	#judge_date()
	#prepare_stock_list()
	#exec_all_weather()
	#sc_info_position()
	#is_weekday_job(3)

	'''
	init()
	if g.portfolio_value_proportion[SC_IDX] > 0:
		sc_judge_date()
		sc_prepare_stock_list()
		#sc_trade_etf()
		sc_rebalance_sell()
		sc_stop_loss()
		sc_rebalance_buy()
	
		sc_check_limit_up()
		sc_check_remain_amount()
		sc_info_position()

	if g.portfolio_value_proportion[MOM_IDX] > 0:
		mom_rebalance()
	'''
