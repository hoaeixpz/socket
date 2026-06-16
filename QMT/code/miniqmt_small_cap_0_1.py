from xtquant import xtdata
from xtquant.xttype import StockAccount
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant import xtconstant
import time
from datetime import datetime, timedelta
import math
import sys
import subprocess
import psutil
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
import signal
import re

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

def sleep_sec(seconds):
	time.sleep(seconds)

def sleep_mins(minutes):
	min = minutes * 60 + 1
	print("sleep ", min)
	time.sleep(min)

def sleep_hours(hours):
	time.sleep(3600 * hours)

def init():
	print("init")
	# path为mini qmt客户端安装目录下userdata_mini路径
	#path = 'C:\\QMT\\国金证券QMT交易端\\userdata_mini'
	#path = 'D:\\国金证券QMT交易端\\userdata_mini'
	path = 'C:\\QMT\\userdata_mini'
	session_id = int(time.time())
	g.xt_trader = XtQuantTrader(path, session_id)
	g.callback = MyXtQuantTraderCallback()
	g.xt_trader.register_callback(g.callback)
	g.xt_trader.start()
	connect_result = g.xt_trader.connect()
	print('建立交易连接，返回0表示连接成功', connect_result)

	g.account = StockAccount('8885388757')

	info = g.xt_trader.query_stock_asset(g.account)
	available_cash = info.cash

	# 设置全局变量
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
	g.last_pos_value = info.total_asset
	g.sell_done = False
	g.run_stoploss = True
	g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
	g.stoploss_limit = 0.1  # 止损线
	g.stoploss_market = 0.05  # 市场趋势止损参数
	g.stoploss_map = {}    #记录止损股票，3日内该股票不再买入
	g.etf = '511880.SH'  # 空仓月份持有银华日利ETF
	#g.etf = '513500.SH'
	g.all_weather_list = [  "518880.SH",  #黄金ETF
							"511220.SH",  #城投ETF
							"513100.SH",  #纳指ETF
							"512890.SH"]  #红利低波ETF

	g.count = 0

	g.industry_dict = get_sw2_industry()
	# 每天执行调仓函数
	# 聚宽会自动将非交易日的触发顺延至下一个交易日
	#ContextInfo.run_time("sell_func", "1nDay", "2025-01-03 10:00:00","SH")
	#ContextInfo.run_time("buy_func", "1nDay", "2025-01-03 14:00:00","SH")
	#ContextInfo.run_time("myHandlebar","5nSecond","2025-01-03 13:20:00","SH")
	print(f'策略初始化完成：每月初调仓，持有市值最小的{g.stock_num}只股票, 初始可用资金{available_cash}, 初始资产{g.last_pos_value}')

def closeQMT():
	current_date = datetime.now()
	if current_date.weekday() != 0:
		return
	kill_process_by_name("XtMiniQmt.exe")

def reopenQMT():
	current_date = datetime.now()
	if current_date.weekday() != 0:
		return
	open_QMT()

def reconnect():
	current_date = datetime.now()
	if current_date.weekday() != 0:
		return
	print("reconnect")
	# path为mini qmt客户端安装目录下userdata_mini路径
	#path = 'C:\\QMT\\国金证券QMT交易端\\userdata_mini'
	#path = 'D:\\国金证券QMT交易端\\userdata_mini'
	path = 'C:\\QMT\\userdata_mini'
	session_id = int(time.time())
	g.xt_trader = XtQuantTrader(path, session_id)
	print("new g.xt_trader")
	g.xt_trader.register_callback(g.callback)
	g.xt_trader.start()
	print("start")
	connect_result = g.xt_trader.connect()
	print('建立交易连接，返回0表示连接成功', connect_result)


def kill_process_by_name(name):
	"""终止所有名称包含 name 的进程 (使用psutil)"""
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
	current_date = datetime.now()
	today = current_date.strftime('%Y%m%d')
	date = get_trading_dates('399101.SZ', today)
	last_trading_day = date[-1]
	return today == last_trading_day

def is_weekday_job():
	if DEBUG_DAILY_MODE:
		return True

	current_date = datetime.now()
	dt_str = current_date.strftime('%Y%m%d')
	date = get_trading_dates('399101.SZ', dt_str)
	#print(date)
	for day in range(1, g.weekday + 1):
		yesterday = current_date - timedelta(days=day)
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = date[-(day+1)]
		#print("yesterday: ", yesterday)
		#print(dt_str)
		#print("last date: ", last_date)
		if day < g.weekday:
			if last_date != dt_str:
				return False
		else:
			if last_date != dt_str:
				if (current_date.weekday() + 1) != g.weekday:
					print(f'{current_date} 是周{current_date.weekday() + 1}')
				return True
	return False

def shutdown_scheduler(signum, frame):
	"""信号处理函数"""
	print(f"\n收到信号 {signum}，正在关闭调度器...")
	scheduler.shutdown(wait=False)
	print("调度器已安全关闭")
	tee.close()
	sys.exit(0)

def run_strategy():

	task_time = [[9,30],  #judge_date
				[ 9,31],  #prepare_stock_list
				[ 9,35],  #trade_etf
				[10, 0],  #rebalance_sell
				[10, 2],  #stop_loss
				[10,10],  #rebalance_buy
				[14, 0],  #check_limit_up
				[14, 2],  #check_remain_amount
				[15, 1],  #info_position
				[15,10],  #closeQMT
				[18, 0],  #reopenQMT
				[18, 2]]  #reconnect
	'''
	task_time = [["*",55],  #judge_date
				["*",56],  #prepare_stock_list
				["*",57],  #trade_etf
				["*",58],  #rebalance_sell
				["*",59],  #stop_loss
				["*",0],  #rebalance_buy
				["*",1],  #check_limit_up
				["*",2],  #check_remain_amount
				["*",3]]  #info_position
	'''
	signal.signal(signal.SIGINT, shutdown_scheduler)
	signal.signal(signal.SIGTERM, shutdown_scheduler)

	scheduler.add_job(judge_date,         'cron', hour=task_time[0][0],  minute=task_time[0][1])
	scheduler.add_job(prepare_stock_list, 'cron', hour=task_time[1][0],  minute=task_time[1][1])
	scheduler.add_job(trade_etf,          'cron', hour=task_time[2][0],  minute=task_time[2][1])
	scheduler.add_job(rebalance_sell,     'cron', hour=task_time[3][0],  minute=task_time[3][1])
	scheduler.add_job(stop_loss,          'cron', hour=task_time[4][0],  minute=task_time[4][1])
	scheduler.add_job(rebalance_buy,      'cron', hour=task_time[5][0],  minute=task_time[5][1])
	scheduler.add_job(check_limit_up,     'cron', hour=task_time[6][0],  minute=task_time[6][1])
	scheduler.add_job(check_remain_amount,'cron', hour=task_time[7][0],  minute=task_time[7][1])
	scheduler.add_job(info_position,      'cron', hour=task_time[8][0],  minute=task_time[8][1])
	scheduler.add_job(closeQMT,           'cron', hour=task_time[9][0],  minute=task_time[9][1])
	scheduler.add_job(reopenQMT,          'cron', hour=task_time[10][0], minute=task_time[10][1])
	scheduler.add_job(reconnect,          'cron', hour=task_time[11][0], minute=task_time[11][1])

	try:
		print("start")
		scheduler.start()
	except (KeyboardInterrupt, SystemExit):
		print("服务已手动停止")

	while True:
		print("sleep a day")
		sleep_hours(24)

def judge_date():
	g.is_trading_day = is_trading_day()
	print(f'今天是交易日吗 {g.is_trading_day}')
	
	current_date = datetime.now()
	current_month = current_date.month
	g.count = 1
	if current_month == 1 or current_month == 4:
		if g.trade == True:
			print(f'{green_c}✅\033[0m========== 一月和四月份清仓，日期：%s ==========' % current_date)
		g.trade = False
	elif (current_month == 12 or current_month == 3) and current_date.day > 27:
		if 5 - current_date.weekday() + current_date.day > 31:
			if g.trade == True:
				print(f'{green_c}✅\033[0m========== 一月和四月份清仓，日期：%s ==========' % current_date)
			g.trade = False
	else:
		g.trade = True
	print('judge_date count ',g.count)

def prepare_stock_list():
	if not g.is_trading_day:
		return
	#获取已持有列表
	g.count += 1
	g.hold_list= []
	g.limitup_stocks = []
	g.trade_day = False
	g.hold_list = get_current_holding_stocks()
	
	#获取昨日涨停列表
	current_date = datetime.now()
	yesterday = current_date - timedelta(days=1)
	g.yesterday_HL_list = []

	for stock in g.hold_list:
		dt_str = yesterday.strftime('%Y%m%d')
		last_date = get_trading_dates(stock, dt_str, 1)
		last_date = last_date[0]
		query_date = datetime.strptime(last_date+'150000', '%Y%m%d%H%M%S')

		if is_specified_date_limit_up(stock, query_date):
			g.yesterday_HL_list.append(stock)

	if g.yesterday_HL_list != []:
		print("")
		print(f"************昨日({yesterday})涨停 **************")
		print(g.yesterday_HL_list)
		print("")


	g.stock_pool = get_normal_stocks()
	g.stoploss_map = {k: v-1 for k, v in g.stoploss_map.items() if v-1 > 0}

	print('prepare_stock_list count ',g.count)

def collect_sell_buy_stocks():
	g.stocks_to_sell = []
	g.stocks_to_buy = []
	current_holdings = get_current_holding_stocks()
	current_holdings.append("002910.SZ")
	for stock in current_holdings:
		if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
			if not is_limit_up(stock):
				g.stocks_to_sell.append(stock)
			else:
				print(f"{red_c}⚪\033[0m {stock} {get_stock_name(stock)} 转为涨停股，今日不卖出。")
				g.today_HL_list.append(stock)
			
	for stock in g.selected_stocks:
		if (stock not in current_holdings) and (stock not in g.yesterday_HL_list):
			g.stocks_to_buy.append(stock)

def trade_etf():
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
	query_date = datetime.now()
	yesterday = query_date - timedelta(days=200)
	#dt_str = yesterday.strftime('%Y%m%d')
	#print(dt_str)
	for stock in g.all_weather_list:
		xtdata.download_history_data(stock,period='1d',incrementally=True)

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
	total_weight = sum([w for w in weights.values()])
	
	fin_weights = {key: value/total_weight for key, value in weights.items()}
		
	for stock, w in fin_weights.items():
		print(f'{stock} {get_stock_name(stock)} 权重{100*w:.2f}%')

	info = g.xt_trader.query_stock_asset(g.account)
	available_cash = info.cash
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
			buy_target_shares(stock, amount)
			sleep_sec(1)
			g.refresh_hold = True
		else:
			print('=====================================')
			print(f"{stock} {get_stock_name(stock)} 未买入, 目标市值{target_value:.2f}, 股价 {current_price}元, amount {target_value / current_price:.2f}")

def rebalance_sell():
	if not is_weekday_job():
		return
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = datetime.now()
	print(f'{green_c}✅\033[0m========== 执行周度调仓，日期：{current_date} ==========')

	info_position()
	#yesterday = current_date - timedelta(days=1)
	#query_date = yesterday.replace(hour=15, minute=0, second=0, microsecond=0)
	query_date = current_date
	g.selected_stocks = get_small_cap_stocks(g.stock_pool, query_date, g.stock_num)
	for stock in g.stoploss_map.keys():
		if stock in g.selected_stocks:
			g.selected_stocks.remove(stock)
			print(f"{stock} {get_stock_name(stock)} 前{3 - g.stoploss_map[stock]}日止损卖出，3日内不再买入")
        

	collect_sell_buy_stocks()
	current_holdings = get_current_holding_stocks()

	if len(g.stocks_to_buy) > 0 or len(g.stocks_to_sell) > 0:
		print(f"{green_c}✅\033[0m当前持股 {len(current_holdings)}只")
		current_holdings.sort()
		for stock in current_holdings:
			print(get_stock_name(stock))
			
		print(f"{green_c}✅\033[0m需要买入股票 {len(g.stocks_to_buy)}只")
		print(f"{green_c}✅\033[0m需要卖出股票 {len(g.stocks_to_sell)}只")
		for stock in g.stocks_to_buy:
			print(f"{green_c}✅\033[0m待买入 ", get_stock_name(stock))
		for stock in g.stocks_to_sell:
			print(f'{green_c}✅\033[0m待卖出: %s' % get_stock_name(stock))
			
			
		print(f"{green_c}✅\033[0m今日({current_date})为卖出时间，执行卖出操作")
		print(f'{green_c}✅\033[0m------------------------------------------')
		# 执行卖出逻辑
		sell_stocks()
		# 标记卖出已完成
		g.sell_done = True
		#log_selection_details(g.selected_stocks, prev_date)

	else:
		print('未选到符合条件的股票，本日不调仓')

	print('rebalance_sell count ',g.count)

def rebalance_buy():
	if not is_weekday_job():
		return
	if not g.sell_done:                     #卖出股票后才有钱买入
		return
	if g.reason_to_sell == 'takeprofit':    #止盈之后不再买入
		return
	if g.trade is False:
		return
	g.trade_day = True

	g.count += 1
	
	current_date = datetime.now()
	print(f'{green_c}✅\033[0m========== 执行周度调仓，日期：{current_date} ==========')
	# 执行买入逻辑
	if len(g.stocks_to_buy):
		print(f"{green_c}✅\033[0m今日({current_date})为买入时间，执行买入操作")
		print(f'{green_c}✅\033[0m+++++++++++++++++++++++++++++++++++++++++')
		print(f"{green_c}✅\033[0m需要买入股票 {len(g.stocks_to_buy)}只")
		for stock in g.stocks_to_buy:
			print(get_stock_name(stock))
		
	calc_position()
	buy_stocks()
	# 重置卖出标记
	g.sell_done = False
	print("sleep 30s")
	sleep_sec(30)
	info_position()
	print('rebalance_buy count ',g.count)

def calc_position():
	CASH_YU = 5000
	info = g.xt_trader.query_stock_asset(g.account)
	total_value = info.total_asset
	current_holdings = get_current_holding_stocks()
	holding_num = len(current_holdings) + len(g.stocks_to_buy)
	'''
	if holding_num != g.stock_num:
		fail_sell_stock_num = len(g.stocks_fail_sell) + len(g.yesterday_HL_list)
		print(f'❌ ❌  有{fail_sell_stock_num}只股票没能卖出，调整买入计划')
		print(f'等权买入股票')
		available_cash = context.portfolio.available_cash
		for stock in g.stocks_to_buy:
			g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / total_value
			print(f'期望持仓: {get_stock_name(stock)}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')
		return
	'''
	if  holding_num != len(g.selected_stocks):
		print(f'{red_c}❌❌\033[0m 股票数量异常，期望最终持仓{holding_num}只，实际选中{len(g.selected_stocks)}只')
		
	positions = get_positions()
	fail_pos = 0
	for stock in g.stocks_fail_sell:
		fp = positions[stock].market_value / total_value
		fail_pos += fp
		print(f'停牌股 {get_stock_name(stock)} 占仓位比重为 {fp*100:.2f}%')
	HL_count = 0
	for stock in current_holdings:
		if (stock in g.yesterday_HL_list) or (stock in g.today_HL_list):
			fp = positions[stock].market_value / total_value
			fail_pos += fp
			HL_count += 1
			print(f'涨停股 {get_stock_name(stock)} 占仓位比重为 {fp*100:.2f}%')
				
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
		if stock in g.stocks_fail_sell or stock in g.yesterday_HL_list or stock in g.today_HL_list:
			continue
		g.excepted_position[stock] = p
		
	for stock, pos in g.excepted_position.items():
		stock_name = get_stock_name(stock)
		print(' 期望持仓: %s(%s), 占比 %.2f%%' % (stock_name, stock, pos * 100))
		
	position_dict = {} #记录实际仓位比重
	position_sum = 0
	#计算已有持仓的股票占比
	for stock, pos in positions.items():
		current_price = get_last_price(stock)
		if current_price is None or current_price == 0:
			continue
		position_sum += pos.market_value
		position_dict[stock] = pos.market_value / total_value, current_price
	
	#计算待买入的股票的持仓占比
	for stock in g.stocks_to_buy:
		stock_name = get_stock_name(stock)
		target_value = total_value * g.excepted_position[stock]
		current_price = get_last_price(stock)
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
	if abs(avai_cash) > CASH_YU or avai_cash < 0:
		print(f'{red_c}⚪⚪\033[0m剩余资金过大 {total_value - position_sum:.2f}')
		cash = 0
		for stock, exce_pos in g.excepted_position.items():
			if stock in g.stocks_fail_sell:
				continue
			pos, stock_price = position_dict[stock]
			diff_pos = exce_pos - pos
			#if abs(diff_pos) > 0.04:
			if abs(diff_pos) * total_value > CASH_YU or abs(diff_pos) > 0.04:
				stock_name = get_stock_name(stock)
				print(f'{stock_name} 持仓与期望相差较大，持仓{pos*100:.2f}%,期望{exce_pos*100:.2f}%,金额相差{diff_pos*total_value:.2f}')
				if diff_pos > 0:
					g.stocks_to_buy.append(stock)
					cash -= diff_pos*total_value
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
					if positions[stock]['canuse_amount'] < 100:
						continue

					sell_target_value(stock, exce_pos*total_value)
					cash -= diff_pos*total_value
					print(f'调整{stock_name}市值，卖出{abs(diff_pos) * total_value:.2f}元')
					#update_stock_price(stock, order_info.m_dPrice, -order_info.m_nVolume)

		if cash > 0:
			print("sleep 30s")
			sleep_sec(30)
			print(f"卖出部分股票后，多出现金 {cash:.2f}")

		avai_cash += cash
		if cash != 0:
			print(f'重新分配之后资金为{avai_cash:.2f}')
		
		if avai_cash > CASH_YU:
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
				stock_name = get_stock_name(stock)
				cash = diff_pos*total_value
				avai_cash -= cash
				if avai_cash > 0:
					g.stocks_to_buy.append(stock)
					print(f'{stock_name} 持仓与期望相差{diff_pos*100:.2f}% {diff_pos*total_value:.2f}，补仓')
			
				
			'''
			each_cash = avai_cash / len(g.stocks_to_buy)
			for stock in g.stocks_to_buy:
				stock_name = get_stock_name(stock)
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
			info = g.xt_trader.query_stock_asset(g.account)
			available_cash = info.cash
			for stock in g.stocks_to_buy:
				g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / total_value
				print(f'期望持仓: {get_stock_name(stock)}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')

	position_dict = dict(sorted(position_dict.items(), key=lambda x: x[0]))
	for stock, pos in position_dict.items():
		stock_name = get_stock_name(stock)
		print(f' 预估持仓: {stock_name}({stock}), 占比 {pos[0] * 100:.2f}% 单价 {pos[1]:.2f}')
		
	for stock, exce_pos in g.excepted_position.items():
		if stock in g.stocks_fail_sell:
			continue
		pos, stock_price = position_dict[stock]
		diff_value = (exce_pos - pos) * total_value
		
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
					print(f'{green_c}✅\033[0m调整买入数量，追加{num}手,仓位占比调整为{g.excepted_position[stock] * 100:.2f}%')
					
		'''
		amount = int(diff_value / current_price / 100) * 100
		if amount > 0:
			if stock not in g.stocks_to_buy:
				g.stocks_to_buy.append(stock)
			print(f'{stock_name}({stock}) 可以再买入{amount}')
		'''
	
def check_limit_up():
	if not g.is_trading_day:
		return
	g.count += 1
	now_time = datetime.now()
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
				sell_target_value(stock, 0)
				g.reason_to_sell = 'limitup'
				g.limitup_stocks.append(stock)
			else:
				print(f"{stock} {get_stock_name(stock)}涨停，继续持有")

	print('check_limit_up count ',g.count)

#如果昨天有股票卖出或者买入失败，剩余的金额今天买入
def check_remain_amount():
	if not g.is_trading_day:
		return
	g.count += 1
	info = g.xt_trader.query_stock_asset(g.account)
	available_cash = info.cash
	if g.reason_to_sell == 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
		g.hold_list = get_current_holding_stocks()
		flag = True
		if len(g.hold_list) < g.stock_num or flag:
			print(f'现有持仓:')
			for stock_code in g.hold_list:
				stock_name = get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
			print('涨停卖出')
			for stock_code in g.limitup_stocks:
				stock_name = get_stock_name(stock_code)
				print(f'  {stock_name} {stock_code}')
				
			# 计算需要买入的股票数量
			current_date = datetime.now()
			prev_date = current_date - timedelta(days=1)
			g.selected_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
			for stock_code in g.limitup_stocks:
				if stock_code in g.selected_stocks:
					g.selected_stocks.remove(stock_code)

			for stock_code in g.stoploss_map.keys():
				if stock_code in g.selected_stocks:
					g.selected_stocks.remove(stock_code)
					print(f"{stock_code} {get_stock_name(stock_code)} 前{3 - g.stoploss_map[stock_code]}日止损卖出，3日内不再买入")
			
			current_holdings = get_current_holding_stocks()
			if len(current_holdings) > 3:
				g.selected_stocks = current_holdings
				
			collect_sell_buy_stocks()
			if len(g.stocks_to_buy) > 0:
				print(f"需要买入股票 {len(g.stocks_to_buy)}只")
				for stock in g.stocks_to_buy:
					print("待买入 ", get_stock_name(stock))
				
			#num_stocks_to_buy = min(len(g.limitup_stocks), g.stock_num - len(g.hold_list))
			#num_stocks_to_buy = g.stock_num - len(g.hold_list)
			#g.stocks_to_buy = [stock for stock in g.selected_stocks if stock not in g.hold_list and stock not in g.limitup_stocks][:num_stocks_to_buy]
			#sell_stocks(context)
			print('有余额可用'+str(round((available_cash),2))+'元。买入'+ str(g.stocks_to_buy))
			info_position()
			calc_position()
			buy_stocks()
			#info_position()
			g.refresh_hold = True
		g.reason_to_sell = ''
	elif g.reason_to_sell == 'stoploss' or g.reason_to_sell == 'takeprofit':
		print('止盈止损后，有余额可用'+str(round((available_cash),2))+'元。买入'+ str(g.etf))
		g.stocks_to_buy = [g.etf]
		buy_stocks()
		g.reason_to_sell = ''
		g.refresh_hold = True

	print("sleep 20s")
	sleep_sec(20)
	info_position()
	print('check_remain_amount count ',g.count)

#止盈止损
def stop_loss():
	if not g.is_trading_day:
		return
	g.count += 1
	show_info = False
	if g.run_stoploss:
		current_positions = get_positions()

		if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
			for stock in current_positions.keys():
				if current_positions[stock].volume == 0:
					continue

				price = get_last_price(stock)
				avg_cost = current_positions[stock].avg_price
				# 个股盈利止盈
				if price >= avg_cost * 2:
					#order_target_value(stock, 0, 'BUY1', ContextInfo, ContextInfo.account)
					print(f"{red_c}⚪\033[0m 收益100%止盈,卖出{stock}")
				# 个股止损
				elif price < avg_cost * (1 - g.stoploss_limit):
					sell_target_value(stock, 0)
					g.stoploss_map[stock] = g.stoploss_map.setdefault(stock, 3)
					print(f"{stock} 股价{price:.2f} 成本{avg_cost:.2f}")
					print(f"{red_c}❌\033[0m 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
					#if order_info != None:
					#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
					show_info = True
					
					g.reason_to_sell = 'stoploss'
					if stock in g.selected_stocks:
						g.selected_stocks.remove(stock)

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
					for stock in current_positions.keys():
						if stock == g.etf:
							continue
						if stock in g.all_weather_list:
							continue
						if stock in g.yesterday_HL_list or is_limit_up(stock):
							continue
						print(f'{red_c}❌\033[0m 清仓{stock} {get_stock_name(stock)}')
						sell_target_value(stock, 0)
						#if order_info != None:
						#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
						show_info = True
						if stock in g.selected_stocks:
							g.selected_stocks.remove(stock)
				else:
					g.reason_to_sell = 'takeprofit'
					print(f"{red_c}⚪\033[0m 大盘大涨,平均涨幅{down_ratio:.2%}")
					for stock in current_positions.keys():
						if stock == g.etf:
							continue
						if stock in g.all_weather_list:
							continue
						if stock in g.yesterday_HL_list or is_limit_up(stock):
							continue
						print(f'{red_c}⚪\033[0m 清仓{stock} {get_stock_name(stock)}')
						sell_target_value(stock, 0)
						#if order_info != None:
						#	print(f'卖出 {order_info.m_nVolume}股 * {order_info.m_dPrice:.2f}元')
						show_info = True
						if stock in g.selected_stocks:
							g.selected_stocks.remove(stock)
	
	if show_info == True:
		print("sleep 30s")
		sleep_sec(30)
		info_position()

	print('stop_loss count ',g.count)

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

def get_last_price(stock):
	full_tick_dict = xtdata.get_full_tick([stock])
	for key, price in full_tick_dict.items():
		if key == stock and price:
			if price['lastPrice'] == 0:
				print(stock, " 获取当前价格异常,股价为0")
			return price['lastPrice']
	print(stock, " 获取当前价格异常")
	return None

def get_market(stock_list):
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
		gb = guben[key]
		value = price['lastPrice']
		#print(gb, " ", value)
		if gb is None or math.isnan(gb) or math.isnan(value):
			continue
		market[key] = gb * value

	return market

def get_small_cap_stocks(stock_list, query_date, n=5):
	#获取市值最小的n只股票（修正版：全局排序）
	# 用于存储所有查询到的市值数据
	market = get_market(stock_list)
	#print('market')
	#print(market)
	sorted_market = dict(sorted(market.items(), key=lambda x:x[1], reverse=False))
	#print(sorted_market)

	if n > 30:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[0:10]:
			stock_name = get_stock_name(stock)
			cap_in_10k = round(cap/100000000.0, 2)
			rank = rank + 1
			marker = '  <== 选中' if rank <= n else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 流通市值: {cap_in_10k} 亿元{marker}')

	#selected_stocks = list(sorted_market)[0:n]
	selected_stocks = small_cap_get_stock_industry(list(sorted_market)[:100], n)

	flag = False
	for stock_code in selected_stocks:
		if stock_code not in g.selected_stocks:
			flag = True
			break

	if flag:
		print(f"get_small_cap_stocks   {query_date}    head {n}")
		rank = 0
		for stock, cap in list(sorted_market.items())[0:20]:
			stock_name = get_stock_name(stock)
			cap_in_10k = round(cap/100000000.0, 2)
			industry = g.industry_dict[stock]
			rank = rank + 1
			marker = '  <== 选中' if stock in selected_stocks else ''
			print(f'    第{rank:>2}名: {stock_name}({stock}), 流通市值: {cap_in_10k} 亿元 {industry} {marker}')

	return selected_stocks

def small_cap_get_stock_industry(stock_list, num):
    #return stock_list[:num]
    """行业分散选股"""
    try:
        selected_stocks = []
        industry_list = []
        
        for stock_code in stock_list:
            if stock_code in g.industry_dict:
                info = g.industry_dict[stock_code]
                if True:
                    industry_name = info
                    if industry_name not in industry_list:
                        industry_list.append(industry_name)
                        selected_stocks.append(stock_code)
                        if len(industry_list) >= num:
                            break
        return selected_stocks
    except Exception as e:
        print(f"行业筛选错误: {e}")
        return stock_list[:num]
	
def get_normal_stocks():
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

		if stock not in current_holdings and is_limit_up(stock):  # 涨停
			print(f'涨停 {stock} {stock_name}')
			continue

		if stock not in current_holdings and is_limit_down(stock):  # 涨停
			print(f'跌停 {stock} {stock_name}')
			continue

		non_st_stocks.append(stock)

	print(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
	return non_st_stocks

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
		current_holdings.append(pos.stock_code)

	return current_holdings

def sell_stocks():
	# 执行卖出
	for stock in g.stocks_to_sell:
		print(f'{green_c}✅\033[0m>>>>>>>>>>>>')
		print(f'{green_c}✅\033[0m卖出: ',get_stock_name(stock))
		sell_target_value(stock, 0)
		detail = xtdata.get_instrument_detail(stock)
		is_paused = detail['InstrumentStatus'] < 0
		is_dieting = is_limit_down(stock)
		if is_paused or is_dieting:
			g.stocks_fail_sell.append(stock)

def buy_stocks():
	if len(g.stocks_to_buy) > 0:
		info = g.xt_trader.query_stock_asset(g.account)
		available_cash = info.cash
		position_value = info.market_value
		total_value = info.total_asset
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
			current_price = get_last_price(stock)
			if current_price is None or current_price == 0:
				continue

			info = g.xt_trader.query_stock_asset(g.account)
			print(f'===可用资金 {info.cash}===')

			if stock == g.etf:
				target_value_per_stock = min(info.cash, target_value_per_stock)
				amount = int(target_value_per_stock / current_price / 100) * 100
				if amount > 0:
					print(f'买入ETF {stock} {get_stock_name(stock)} 目标市值{target_value_per_stock:.2f}, {amount}股 * {current_price}元')
					buy_target_shares(stock, amount)
			else:
				if g.excepted_position.get(stock) is not None:
					target_value_per_stock = g.excepted_position[stock] * total_value
					current_value = 0
					positions = get_positions()
					if stock in positions.keys():
						current_value = positions[stock].market_value
					target_value_per_stock = min(info.cash + current_value, target_value_per_stock)
				
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				print(f'委托买入: {get_stock_name(stock)}, {stock} \n目标价值:{target_value_per_stock:.2f}'
					f'\n预计最终持股{amount}股，每股{current_price:.2f}元，合计:{amount * current_price:.2f}')
				buy_target_value(stock, target_value_per_stock)
			sleep_sec(1)

def get_sell_one_price(stock):
	#获取卖一价
	tick_data = xtdata.get_full_tick([stock])
	if stock in tick_data:
		sell_price = tick_data[stock]['askPrice']
		if sell_price[0] > 0:
			return sell_price[0]
		else:
			print(f"{stock} 涨停，没有卖手价")

	return None

def sell_target_value(stock, target_value):
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
					async_seq = g.xt_trader.order_stock_async(g.account, 
											 				stock,							#stock_code
											 				xtconstant.STOCK_SELL,			#order_type
															amount,							#order_volume
															xtconstant.FIX_PRICE,			#price_type: 以固定价格卖出
															current_price - 0.1,			#price: 当price_type是FIXED时，需要填确切价格
															'',                             #strategy_name
															f'Sell {stock} {target_value}元 '   #order_remark
					)

					print(f"sell {stock} passorder target value {target_value:.2f} current {pos.market_value:.2f} amount {amount:.2f}")
		break
	print("async_seq ", async_seq)
	if async_seq == -1 or async_seq == None:
		print(f"sell_target_value failed {stock} {get_stock_name(stock)}")

def buy_target_value(stock, target_value):
	if DEBUG_DAILY_MODE:
		return
	positions = get_positions()
	async_seq = None
	current_value = 0
	if stock in positions.keys():
		current_value = positions[stock].market_value

	volume = target_value - current_value
	if volume > 0:
		current_price = get_last_price(stock)
		amount = int(volume / current_price / 100) * 100
		if amount < 100:
			print(f"{stock} {get_stock_name(stock)} 现价{current_price:.2f} 期望持仓 {target_value:.2f}元,")
			print(f"现有持仓 {current_value:.2f}元，相差 {volume:.2f}元，需要买入股数 {volume / current_price:.2f}不足100股，放弃交易")
		else:
			#sell_1_price = get_sell_one_price(stock)
			buy_price = current_price + 0.1
			async_seq = g.xt_trader.order_stock_async(g.account, 
										 			stock,								#stock_code
										 			xtconstant.STOCK_BUY,				#order_type
													amount,								#order_volume
													xtconstant.FIX_PRICE,				#price_type: 以对手最优价买入，既卖一价
													buy_price,							#price: 当price_type是FIXED时，需要填确切价格
													'',                                 #strategy_name
													f'Buy {stock} Tgt {target_value}元 '	#order_remark
			)

			print(f"buy {stock} passorder target value {target_value:.2f} current {current_value:.2f} amount {amount:.2f}")

	print("async_seq ", async_seq)
	if async_seq == -1 or async_seq == None:
		print(f"buy_target_value failed {stock} {get_stock_name(stock)}")

def buy_target_shares(stock, target_share):
	if DEBUG_DAILY_MODE:
		return

	current_price = get_last_price(stock)
	#sell_1_price = get_sell_one_price(stock)
	buy_price = current_price + 0.1
	async_seq = g.xt_trader.order_stock_async(g.account, 
											stock,								#stock_code
											xtconstant.STOCK_BUY,               #order_type
											target_share,                       #order_volume
											xtconstant.FIX_PRICE,               #price_type: 以对手最优价买入，既卖一价
											buy_price,							#price: 当price_type是FIXED时，需要填确切价格
											'',                                 #strategy_name
											f'Buy {stock} {target_share}股'     #order_remark
											)  
	print(f"buy {stock} passorder share {target_share}")
	if async_seq == -1:
		print(f"buy_target_shares failed {stock} {get_stock_name(stock)}")

def get_positions():
	positions = {}
	objlist = g.xt_trader.query_stock_positions(g.account)
	for obj in objlist:
		stock = obj.stock_code
		positions[stock] = obj

	return positions

def info_position():
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
			diff_price = price - pos.avg_price
			industry = g.industry_dict.get(stock,None)
			print(f"{green_c}✅\033[0m持仓: {stock_name}({stock}), 占比 {pos.market_value / total_value * 100:.2f}%, 涨跌幅: {color}{ratio:.2f}% ({diff_price * pos.volume:.2f})\033[0m, 数量: {pos.volume}, 市值: {pos.market_value:.1f}元 {industry}")

		for pos in positions:
			stock = pos.stock_code
			stock_name = get_stock_name(stock)
			if pos.volume == 0:
				print(f"{green_c}✅\033[0m持仓: {stock_name}({stock}) 0股")

		print(f'{green_c}✅\033[0m*******************总资产 {total_value:.2f} | {info.total_asset:.2f} 剩余可用金额 {available_cash:.2f}元*******************\n\n')

		if current_date.hour == 15:
			daily_return = total_value - g.last_pos_value
			rate_of_return = daily_return / g.last_pos_value * 100
			color = red_c if daily_return > 0 else green_c
			print('==============================')
			print(f'今日股票收益: {color}{daily_return:.2f}\033[0m 元')
			print(f'收益率:       {color}{rate_of_return:.2f} %\033[0m')
			print('==============================\n\n')
			g.last_pos_value = total_value

def get_sw2_industry():
	'''
	获取股票对应的申万二级行业
	'''
	sector_list = xtdata.get_sector_list()
	sw2_list = [s for s in sector_list if s[:3].lower()=='sw2' and '加权' not in s] #获取申万二级行业

	stocks = xtdata.get_stock_list_in_sector('399101.SZ')
	ret = {}
	for sw2 in sw2_list:
		s_list = xtdata.get_stock_list_in_sector(sw2)
		for stock in stocks:
			if stock in s_list:
				ret[stock] = sw2[3:]
	
	#print(ret)
	return ret

#print(get_specified_date_price('399101.SZ', datetime(2026,3,15)))
#print(xtdata.get_instrument_detail('002883.SZ'))

def debug():
	init()
	'''
	g.stoploss_map['002828.SZ'] = 3
	g.stoploss_map['002188.SZ'] = 2
	g.stoploss_map['002524.SZ'] = 1
	g.stoploss_map['002820.SZ'] = 2
	g.stoploss_map['002910.SZ'] = 1
	judge_date()
	prepare_stock_list()
	current_positions = get_positions()
	print(g.stoploss_map)

	current_date = datetime.now()
	query_date = current_date
	g.selected_stocks = get_small_cap_stocks(g.stock_pool, query_date, g.stock_num)
	for stock in g.stoploss_map.keys():
		if stock in g.selected_stocks:
			g.selected_stocks.remove(stock)
			print(f"{stock} {get_stock_name(stock)} 前{3 - g.stoploss_map[stock]}日止损卖出，3日内不再买入")
	'''
	#print(is_weekday_job())
	#get_current_holding_stocks()
	#get_normal_stocks()
	#print(get_last_price('399101.SZ'))
	#print(get_specified_date_price('399101.SZ', '20260315'))
	#get_small_cap_stocks(g.stock_pool, datetime.now(), g.stock_num)

	'''
	buy_target_value('002817.SZ', 684.3)
	buy_target_shares('002817.SZ', 100)
	g.stocks_to_buy = ['002486.SZ']
	buy_stocks()
	sleep_mins(1)
	'''
	'''
	stock = '688500.SH'
	tick = xtdata.get_full_tick([stock])
	print(tick)
	sell_1 = get_sell_one_price(stock)
	print("卖一价 ", sell_1)
	current_price = get_last_price(stock)
	print(current_price)
	'''
        

if __name__ == "__main__":
	#=============================
	#DEBUG_DAILY_MODE == False
	#=============================
	init()
	run_strategy()

	#=============================
	#DEBUG_DAILY_MODE == True
	#=============================
	#judge_date()
	#prepare_stock_list()
	#exec_all_weather()
	#info_position()

	#init()
	#judge_date()
	#prepare_stock_list()
	#trade_etf()
	#rebalance_sell()
	#stop_loss()
	#rebalance_buy()
	#check_limit_up()
	#check_remain_amount()
	#info_position()
	#debug()
