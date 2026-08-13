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
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import os
import signal

#DEBUG_DAILY_MODE = False
DEBUG_DAILY_MODE = True

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
	dates = get_trading_dates('399101.SZ', today)
	last_trading_day = dates[-1]
	return today == last_trading_day

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

# ================================================================
# 初始化和主流程
# ================================================================

def init():
	print("init")
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
	available_cash = info.cash
	print(f"策略初始化完成：动量ETF轮动, 初始可用资金{available_cash}, 初始资产{info.total_asset}")


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

	# 每天 11:00 调仓
	scheduler.add_job(rebalance, 'cron', hour=11, minute=0)

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
# 下单函数
# ================================================================

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
													stock,
													xtconstant.STOCK_SELL,
													pos.volume,
													xtconstant.MARKET_PEER_PRICE_FIRST,
													0,
													'',
													f'清仓{stock} '
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
					sell_price = current_price - tick_size * 10
					async_seq = g.xt_trader.order_stock_async(g.account,
						stock,
						xtconstant.STOCK_SELL,
						amount,
						xtconstant.FIX_PRICE,
						current_price - 0.1,
						'',
						f'Sell {stock} {target_value}元 '
					)

					print(f"sell {stock} passorder target value {target_value:.2f} current {pos.market_value:.2f} amount {amount} @{sell_price:.2f}")
		break
	print("async_seq ", async_seq)
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
			print(f"{stock} {get_stock_name(stock)} 现价{current_price:.2f} 期望持仓 {target_value:.2f}元,")
			print(f"现有持仓 {current_value:.2f}元，相差 {volume:.2f}元，需要买入股数 {volume / current_price:.2f}不足100股，放弃交易")
		else:
			tick_size = get_tick_size(stock)
			buy_price = current_price + tick_size * 10
			async_seq = g.xt_trader.order_stock_async(g.account,
				                                stock, 
                                                xtconstant.STOCK_BUY, 
                                                amount,
				                                xtconstant.FIX_PRICE, 
                                                buy_price, 
                                                '',
				                                f'Buy {stock} Tgt {target_value}元 '
            )

			print(f"buy {stock} passorder target value {target_value:.2f} current {current_value:.2f} amount {amount} @{buy_price:.2f}")

	print("async_seq ", async_seq)
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
	"515980.SH"   # 人工智能
]
SAFE_ETF = '511220.SH'  # 城投债

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


def calc_momentum_score(etf, days):
	"""计算单只ETF的动量得分。返回 (annualized_return, r2, score)。

	参数:
		etf: ETF代码
		days: 回看窗口天数
	"""
	# 获取历史数据
	xtdata.download_history_data(etf, period='1d', incrementally=True)
	history_data = xtdata.get_market_data_ex(['close'],
											 [etf],
											 period='1d',
											 start_time='',
											 fill_data=False,
											 dividend_type='front',
											 count=days+1)
	if etf not in history_data or history_data[etf].empty:
		return 0, 0, 0, 0

	close_prices = history_data[etf]['close'].values

	prices = close_prices

	# 对数价格加权线性回归
	y = np.log(prices)
	x = np.arange(len(y))
	weights = np.linspace(1, 2, len(y))
	#print(weights)

	slope, intercept = np.polyfit(x, y, 1, w=weights)

	# 年化收益率
	annualized_return = math.exp(slope * 250) - 1

	# 加权R²
	weighted_mean_y = np.average(y, weights=weights)
	ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
	ss_tot = np.sum(weights * (y - weighted_mean_y) ** 2)
	r2 = 1 - ss_res / ss_tot if ss_tot else 0

	# 得分
	score = annualized_return * r2

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
			ann_ret, r2, score, recent_ratio = calc_momentum_score(etf, days)
			name = get_stock_name(etf) or etf
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

	if etf1 != etf2:
		print(f"  两者不同 → 各配50%")
		return [etf1, etf2]
	print(f"  两者相同 → 全仓")
	return [etf1]

# ================================================================
# 策略调度函数
# ================================================================

def rebalance():
	if not is_trading_day():
		print(f"{red_c}⭕ 今天不是交易日\033[0m")
		return

	weekdays = [1, 3, 5]
	is_week_day_job = False
	for day in weekdays:
		if is_weekday_job(day):
			is_week_day_job = True;
			break

	if not is_week_day_job:
		return

	print(f'\n{green_c}✅========== 周{day}调仓 {datetime.now().strftime("%Y-%m-%d")} ==========\033[0m')

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
			if is_limit_up(stock):
				printf(f"  {get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(stock):
				printf(f"  {get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			sell_target_value(stock, 0)
			print("sleep 30s")
			sleep_sec(30)

	# 卖出超配
	for stock, weight in weights.items():
		target = total_value * weight
		pos = all_positions.get(stock)
		current_val = pos.market_value if pos else 0
		price = get_last_price(stock)
		if current_val - target > max(3000, price * 100 if price else 10000):
			print(f"  [减仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			if is_limit_up(stock):
				printf(f"  {get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(stock):
				printf(f"  {get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			sell_target_value(stock, target)
			print("sleep 30s")
			sleep_sec(30)
		else:
			print(f"  [与目标差异太小，不减仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")

	# 买入低配
	for stock, weight in weights.items():
		target = total_value * weight
		pos = all_positions.get(stock)
		current_val = pos.market_value if pos else 0
		price = get_last_price(stock)

		if min(target - current_val, available_cash) > max(3000, price * 100 if price else 10000):
			print(f"  [加仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f}")
			if is_limit_up(stock):
				printf(f"  {get_stock_name(stock)}({stock}) 涨停，跳过")
				continue
			if is_limit_down(stock):
				printf(f"  {get_stock_name(stock)}({stock}) 跌停，跳过")
				continue
			buy_target_value(stock, target)
		else:
			print(f"  [与目标差异太小，不加仓] {get_stock_name(stock)}({stock}): {current_val:,.2f} → {target:,.2f} 策略资金{stra_avi_cash:,.2f}")

	print(f'{green_c}✅========== 调仓结束 ==========\033[0m\n')




if __name__ == '__main__':
	init()
	#run_strategy()

	select_etf()
