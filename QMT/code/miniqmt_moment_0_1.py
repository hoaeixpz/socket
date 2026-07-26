# 克隆自聚宽文章：https://www.joinquant.com/post/58963
# 标题：质疑动量 、理解动量 、Allin动量
# 作者：O_iX
# MiniQMT移植版 — ETF双动量轮动策略

from xtquant import xtdata
from xtquant.xttype import StockAccount
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant import xtconstant
import time
from datetime import datetime, timedelta
import math
import sys
import re
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
import signal

#DEBUG_DAILY_MODE = False
DEBUG_DAILY_MODE = True

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class Tee:
	"""将输出同时写入终端和日志文件"""
	def __init__(self, log_file_path):
		self.terminal = sys.__stdout__
		self.log = open(log_file_path, 'a', encoding='utf-8')

	def write(self, message):
		self.terminal.write(message)
		clean_message = ansi_escape.sub('', message)
		self.log.write(clean_message)
		self.log.flush()

	def flush(self):
		try:
			self.terminal.flush()
			self.log.flush()
		except ValueError:
			pass

	def close(self):
		self.log.close()

if not DEBUG_DAILY_MODE:
	log_name = datetime.now().strftime('%Y%m%d')
	tee = Tee(f"logfiles/{log_name}.log")
	sys.stdout = tee

red_c = '\033[31m'
green_c = '\033[32m'

scheduler = BackgroundScheduler()

class G():
	pass
g = G()

class MyXtQuantTraderCallback(XtQuantTraderCallback):
	def on_disconnected(self):
		print(datetime.now(), '连接断开回调')

	def on_stock_order(self, order):
		print(datetime.now(), '委托回调 投资备注', order.order_remark)

	def on_stock_trade(self, trade):
		print(datetime.now(), '成交回调', trade.order_remark,
			f"委托方向(48买 49卖) {trade.offset_flag} 成交价格 {trade.traded_price} 成交数量 {trade.traded_volume}")

	def on_order_error(self, order_error):
		print(f"委托报错回调 {order_error.order_remark} {order_error.error_msg}")

	def on_cancel_error(self, cancel_error):
		print(datetime.now(), sys._getframe().f_code.co_name)

	def on_order_stock_async_response(self, response):
		print(f"异步委托回调 投资备注: {response.order_remark}")

	def on_cancel_order_stock_async_response(self, response):
		print(datetime.now(), sys._getframe().f_code.co_name)

	def on_account_status(self, status):
		print(datetime.now(), sys._getframe().f_code.co_name)


# ================================================================
# 工具函数
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
	return None

def get_trading_dates(stock, dt_str, days=7):
	xtdata.download_history_data(stock, period='1d', incrementally=True)
	history_data = xtdata.get_market_data_ex(['close'],
											 [stock],
											 period='1d',
											 start_time='',
											 end_time=dt_str,
											 count=days)
	dates = history_data[stock].index.tolist()
	return dates

def is_trading_day():
	if DEBUG_DAILY_MODE:
		return True
	current_date = datetime.now()
	today = current_date.strftime('%Y%m%d')
	date = get_trading_dates('399101.SZ', today)
	last_trading_day = date[-1]
	return today == last_trading_day

def is_weekday_job(weekday):
	"""检查今天是否是指定星期几（含节假日顺延）"""
	if DEBUG_DAILY_MODE:
		return True
	current_date = datetime.now()
	dt_str = current_date.strftime('%Y%m%d')
	today_weekday = current_date.weekday()
	if today_weekday == weekday:
		return True
	# 检查是否因节假日顺延：往回找到最近交易日
	for days_back in range(1, weekday + 1):
		check_date = current_date - timedelta(days=days_back)
		check_str = check_date.strftime('%Y%m%d')
		dates = get_trading_dates('399101.SZ', check_str)
		if dates and len(dates) >= 1:
			last_td = dates[-1]
			if last_td == dt_str:
				return True
	return False

def get_last_price(stock):
	"""获取股票最新价"""
	try:
		tick = xtdata.get_full_tick([stock])
		if stock in tick and tick[stock]:
			return tick[stock]['lastPrice']
	except:
		pass
	return None

def get_positions():
	"""获取当前持仓dict: {stock_code: position_object}"""
	positions = g.xt_trader.query_stock_positions(g.account)
	result = {}
	for pos in positions:
		if pos.volume > 0:
			result[pos.stock_code] = pos
	return result

def is_limit_up(stock):
	"""判断是否涨停"""
	try:
		tick = xtdata.get_full_tick([stock])
		if stock in tick and tick[stock]:
			return tick[stock]['lastPrice'] >= tick[stock]['limitUp']
	except:
		pass
	return False

def is_limit_down(stock):
	"""判断是否跌停"""
	try:
		tick = xtdata.get_full_tick([stock])
		if stock in tick and tick[stock]:
			return tick[stock]['lastPrice'] <= tick[stock]['limitDown']
	except:
		pass
	return False


# ================================================================
# 下单函数
# ================================================================

def sell_target_value(stock, target_value):
	"""卖出至目标市值"""
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
				stock, xtconstant.STOCK_SELL, pos.volume,
				xtconstant.MARKET_PEER_PRICE_FIRST, 0, '',
				f'清仓{stock} ')
		else:
			volume = pos.market_value - target_value
			if volume > 0:
				current_price = get_last_price(stock)
				amount = int(volume / current_price / 100) * 100
				if amount < 100:
					print(f"{stock} {get_stock_name(stock)} 现价{current_price:.2f} 差额{volume:.2f}不足100股，放弃")
				else:
					async_seq = g.xt_trader.order_stock_async(g.account,
						stock, xtconstant.STOCK_SELL, amount,
						xtconstant.FIX_PRICE, current_price - 0.1, '',
						f'Sell {stock} {target_value}元 ')
					print(f"sell {stock} target {target_value:.2f} current {pos.market_value:.2f} amount {amount}")
		break
	if async_seq == -1 or async_seq is None:
		print(f"sell_target_value failed {stock} {get_stock_name(stock)}")


def buy_target_value(stock, target_value):
	"""买入至目标市值"""
	if DEBUG_DAILY_MODE:
		return
	positions = get_positions()
	async_seq = None
	current_value = 0
	if stock in positions:
		current_value = positions[stock].market_value

	volume = target_value - current_value
	if volume > 0:
		current_price = get_last_price(stock)
		amount = int(volume / current_price / 100) * 100
		if amount < 100:
			print(f"{stock} {get_stock_name(stock)} 现价{current_price:.2f} 差额{volume:.2f}不足100股，放弃")
		else:
			buy_price = current_price + 0.1
			async_seq = g.xt_trader.order_stock_async(g.account,
				stock, xtconstant.STOCK_BUY, amount,
				xtconstant.FIX_PRICE, buy_price, '',
				f'Buy {stock} Tgt {target_value}元 ')
			print(f"buy {stock} target {target_value:.2f} current {current_value:.2f} amount {amount}")
	if async_seq == -1 or async_seq is None:
		print(f"buy_target_value failed {stock} {get_stock_name(stock)}")


# ================================================================
# 动量策略核心
# ================================================================

ETF_POOL = [
	"513100.SH",  # 纳指ETF
	"513520.SH",  # 日经ETF
	"513030.SH",  # 德国ETF
	"518880.SH",  # 黄金ETF
	"159980.SZ",  # 有色ETF
	"159985.SZ",  # 豆粕ETF
	"501018.SH",  # 南方原油
	"511090.SH",  # 30年国债ETF
	"513130.SH",  # 恒生科技
]

SAFE_ETF = '511880.SH'  # 银华日利（货币ETF，空仓避险用）


def calc_momentum_score(etf, days):
	"""计算单只ETF的动量得分。返回 (annualized_return, r2, score)。

	参数:
		etf: ETF代码
		days: 回看窗口天数
	"""
	# 获取历史数据
	xtdata.download_history_data(etf, period='1d', incrementally=True)
	history_data = xtdata.get_market_data_ex(['close', 'high'],
											 [etf],
											 period='1d',
											 start_time='',
											 count=days)
	if etf not in history_data or history_data[etf].empty:
		return 0, 0, 0

	close_prices = history_data[etf]['close'].values

	# 追加今日最新价
	current_price = get_last_price(etf)
	if current_price is None:
		return 0, 0, 0
	prices = np.append(close_prices, current_price)

	# 对数价格加权线性回归
	y = np.log(prices)
	x = np.arange(len(y))
	weights = np.linspace(1, 2, len(y))

	slope, intercept = np.polyfit(x, y, 1, w=weights)

	# 年化收益率
	annualized_return = math.exp(slope * 250) - 1

	# 加权R²
	ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
	ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
	r2 = 1 - ss_res / ss_tot if ss_tot else 0

	# 得分
	score = annualized_return * r2

	# 近3日急跌过滤（任意一天跌幅>5%则得分归零）
	if len(prices) >= 4:
		recent_ratios = [prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]]
		if min(recent_ratios) < 0.95:
			score = 0

	return annualized_return, r2, score


def select_etf():
	"""双动量选股：短期(25天) + 长期(250天)。

	返回: ETF代码列表（1只或2只）
	"""
	def filter_etf(max_score, days, label):
		print(f"\n========== [{label}] 开始 (窗口={days}天, 得分上限={max_score}) ==========")
		results = {}
		for etf in ETF_POOL:
			ann_ret, r2, score = calc_momentum_score(etf, days)
			name = get_stock_name(etf) or etf
			is_filtered = (score <= 0 or score >= max_score)
			print(f"  {name}({etf}): 年化={ann_ret:.4%} R²={r2:.4f} 得分={score:.4f}{' [淘汰]' if is_filtered else ''}")
			if not is_filtered:
				results[etf] = score

		if not results:
			print(f"  无符合条件的ETF → 选用银华日利({SAFE_ETF})")
			return SAFE_ETF

		selected = max(results, key=results.get)
		print(f"  >>> {label}最终选出: {get_stock_name(selected)}({selected})")
		return selected

	etf1 = filter_etf(6, 25, "短期动量")
	etf2 = filter_etf(0.5, 250, "长期动量")

	print(f"\n========== 选股汇总 ==========")
	print(f"  短期动量选出: {get_stock_name(etf1)}({etf1})")
	print(f"  长期动量选出: {get_stock_name(etf2)}({etf2})")

	if etf1 != etf2:
		print(f"  两者不同 → 各配50%: [{get_stock_name(etf1)}, {get_stock_name(etf2)}]")
		return [etf1, etf2]
	else:
		print(f"  两者相同 → 全仓: [{get_stock_name(etf1)}]")
		return [etf1]


# ================================================================
# 策略调度函数
# ================================================================

def rebalance():
	"""周一调仓"""
	if not is_trading_day():
		print(f"{red_c}⭕ 今天不是交易日\033[0m")
		return

	print(f'\n{green_c}✅========== 执行动量日度调仓，日期：{datetime.now().strftime("%Y-%m-%d")} ==========\033[0m')

	# 选股
	targets = select_etf()
	weights = {etf: 1.0 / len(targets) for etf in targets}

	# 获取总资产
	asset = g.xt_trader.query_stock_asset(g.account)
	total_value = asset.total_asset
	available_cash = asset.cash
	print(f"\n  总资产: {total_value:,.2f}, 可用资金: {available_cash:,.2f}")

	# 获取当前持仓（策略管理的ETF）
	all_positions = get_positions()
	hold_list = list(all_positions.keys())
	# 仅关注策略ETF池内的持仓
	strategy_holdings = [s for s in hold_list if s in ETF_POOL or s == SAFE_ETF]

	print(f"  当前策略持仓: {[(get_stock_name(s), s) for s in strategy_holdings] if strategy_holdings else '空仓'}")

	# 清仓不在目标中的
	for stock in strategy_holdings:
		if stock not in weights:
			print(f"  [调出] {get_stock_name(stock)}({stock}) → 清仓")
			sell_target_value(stock, 0)

	# 卖出超配
	for stock, weight in weights.items():
		target = total_value * weight
		pos = all_positions.get(stock)
		current_val = pos.market_value if pos else 0
		if current_val - target > max(10000, get_last_price(stock) * 100):
			print(f"  [减仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			sell_target_value(stock, target)

	# 买入低配
	for stock, weight in weights.items():
		target = total_value * weight
		pos = all_positions.get(stock)
		current_val = pos.market_value if pos else 0
		if min(target - current_val, available_cash) > max(1000, get_last_price(stock) * 100):
			print(f"  [加仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			buy_target_value(stock, target)

	print(f'{green_c}✅========== 调仓结束 ==========\033[0m\n')


# ================================================================
# 初始化和主流程
# ================================================================

def init():
	print("init")
	path = 'C:\\QMT\\国金证券QMT交易端\\userdata_mini'
	#path = 'C:\\QMT\\userdata_mini'
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
	print(f"策略初始化完成：动量ETF轮动, 初始可用资金{available_cash}, 初始资产{info.total_asset}")


def shutdown_scheduler(signum, frame):
	print(f"\n收到信号 {signum}，正在关闭调度器...")
	scheduler.shutdown(wait=False)
	print("调度器已安全关闭")
	tee.close()
	sys.exit(0)


def run_strategy():
	signal.signal(signal.SIGINT, shutdown_scheduler)
	signal.signal(signal.SIGTERM, shutdown_scheduler)

	# 每天 11:00 调仓
	scheduler.add_job(rebalance, 'cron', hour=11, minute=0)

	scheduler.start()
	print("调度器已启动")
	while True:
		time.sleep(24 * 3600)


if __name__ == '__main__':
	init()
	#run_strategy()

	rebalance()
