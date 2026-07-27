# 克隆自聚宽文章：https://www.joinquant.com/post/58963
# 标题：质疑动量 、理解动量 、Allin动量
# 作者：O_iX

# 导入函数库
from jqdata import *
from jqfactor import get_factor_values
import datetime
import math
from scipy.optimize import minimize
import redis
import numpy as np
import pandas as pd
import json
import time


# -------------------- Redis配置 --------------------
REDIS_CONFIG = {
	"host": "...",  # Redis服务器地址
	"port": 123,  # Redis端口，默认6379
	"username": "...",  # Redis账号（如果没有账号则不需要此项）
	"password": "...",  # Redis密码（没有密码设为None）
}


def get_redis_connection() -> redis.Redis:
	"""创建并返回一个新的Redis连接"""
	try:
		conn = redis.Redis(
			host=REDIS_CONFIG["host"],
			port=REDIS_CONFIG["port"],
			password=None,  # 先不使用密码
			decode_responses=True,
			socket_connect_timeout=3,  # 3秒连接超时
			socket_timeout=5,  # 5秒操作超时
		)
		# 使用execute_command直接进行AUTH认证
		auth_response = conn.execute_command("AUTH", REDIS_CONFIG["username"], REDIS_CONFIG["password"])

		# 检查认证是否成功
		if not auth_response:
			raise redis.AuthenticationError(f"Redis ACL认证失败: {auth_response}")

		return conn
	except redis.AuthenticationError as e:
		log.error(f"Redis认证失败: {e}")
		# 尝试提供更具体的错误信息
		if "WRONGPASS" in str(e):
			log.error("用户名或密码错误")
		elif "NOAUTH" in str(e):
			log.error("需要认证但未提供凭证")
		raise

	except redis.ConnectionError as e:
		log.error(f"Redis连接失败: {e}")
		# 检查常见连接问题
		if "refused" in str(e).lower():
			log.error("请检查Redis服务是否运行以及端口是否正确")
		elif "timeout" in str(e).lower():
			log.error("连接超时，请检查网络或防火墙设置")
		raise

	except Exception as e:
		log.error(f"未知错误: {e}")
		raise


def set_strategy_data(strategy_name, strategy_data):
	"""
	推送策略数据到Redis

	参数:
		strategy_name: 策略标识符
		strategy_data: 要缓存的策略数据字典
	"""
	r = None  # 初始化变量，确保finally块可以访问
	try:
		# 序列化数据并存储到Redis
		r = get_redis_connection()  # 获取新连接
		serialized_data = json.dumps(strategy_data, ensure_ascii=False)
		r.set(strategy_name, serialized_data)
		log.info(f"策略 {strategy_name} 数据推送成功")
		return True

	except Exception as e:
		log.error(f"操作失败: {e}")
		return False

	finally:
		if r is not None:
			try:
				# 直接关闭底层连接
				if hasattr(r, "connection") and r.connection:
					r.connection.disconnect()

				# 额外确保连接池被清理
				if hasattr(r, "connection_pool"):
					r.connection_pool.disconnect()
			except Exception as e:
				log.warning(f"关闭连接时出错: {e}")


# -------------------- 运行调度函数 --------------------
def initialize(context):

	set_benchmark("510880.XSHG")  # 设定沪深300作为基准
	g.redis_option = False  # 是否连接 Redis
	set_option("avoid_future_data", True)  # 打开防未来函数
	set_option("use_real_price", True)  # 开启动态复权模式(真实价格)
	log.info("初始函数开始运行且全局只运行一次")  # 输出内容到日志 log.info()
	log.set_level("order", "error")  # 过滤掉order系列API产生的比error级别低的log
    #log.set_level('strategy', 'error')
	# set_slippage(PriceRelatedSlippage(0.002), type="stock")

	# 全局变量
	g.strategys = {}
	g.portfolio_value_proportion = [0.5, 0.5]  # 50% ETF轮动, 50% 小市值轮动
	g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票

	# 子策略执行计划
	if g.portfolio_value_proportion[0] > 0:
		run_daily(etf_rotation_adjust, "11:00")

	# 小市值轮动子策略调度
	if len(g.portfolio_value_proportion) > 1 and g.portfolio_value_proportion[1] > 0:
		run_daily(small_cap_judge_date, "9:00")
		run_daily(small_cap_prepare_stock_list, "9:05")
		run_daily(small_cap_trade_etf, "9:35")
		run_weekly(small_cap_rebalance, 2, "10:00")     # 周二卖出
		run_daily(small_cap_stop_loss, "10:02")
		run_weekly(small_cap_rebalance, 2, "10:10")     # 周二买入
		run_daily(small_cap_trade_afternoon, "14:00", reference_security='399101.XSHE')

	# 每日剩余资金购买货币ETF
	run_daily(end_trade, "14:59")


def process_initialize(context):
	g.strategys = {
		name: cls(context, index=idx, name=name, display_name=display_name)
		for display_name, name, cls, idx in [
			("核心资产轮动策略", "etf_rotation_strategy", Etf_Rotation_Strategy, 0),
			("小市值轮动策略", "small_cap_rotation_strategy", Small_Cap_Rotation_Strategy, 1),
		]
	}


# 事件处理
def on_event(context, event):
	# 处理分红事件
	if event.name == "Dividends":
		for d in event.dividends:
			scale = d.get("scale_factor", 1)
			if scale != 1:
				print(f"收到送股事件: {event.security}:{event.dividends}")
				code = event.security.code
				for pid, pos in g.positions.items():
					if code in pos:
						old = pos[code]
						pos[code] = int(old * scale)
						print(f"调整持仓: 组合 {pid}, 股票 {code}, 数量 {old} -> {pos[code]}")


# 尾盘处理
def end_trade(context):

	marked = {s for d in g.positions.values() for s in d}
	for stock in context.portfolio.positions:
		if stock not in marked and order_target_value(stock, 0):
			log.info(f"卖出{stock}因送股未记录在持仓中")


# -------------------- 各子策略调度函数 --------------------
def etf_rotation_adjust(context):
	g.strategys["etf_rotation_strategy"].adjust()


# -------------------- 小市值策略调度函数 --------------------
def small_cap_judge_date(context):
	g.strategys["small_cap_rotation_strategy"].judge_date()


def small_cap_prepare_stock_list(context):
	g.strategys["small_cap_rotation_strategy"].prepare_stock_list()


def small_cap_trade_etf(context):
	g.strategys["small_cap_rotation_strategy"].trade_etf()


def small_cap_rebalance(context):
	g.strategys["small_cap_rotation_strategy"].adjust()


def small_cap_stop_loss(context):
	g.strategys["small_cap_rotation_strategy"].stop_loss()


def small_cap_trade_afternoon(context):
	g.strategys["small_cap_rotation_strategy"].trade_afternoon()


# -------------------- 策略基类 --------------------
class Strategy:

	def __init__(self, context, index, name, display_name):
		self.context = context
		self.index = index
		self.name = name
		self.display_name = display_name
		self.stock_sum = 1
		self.hold_list = []
		self.min_money = 10000  # 最小交易额(限制手续费)
		self.pass_months = [1, 4]
		self.def_stocks = ["511260.XSHG", "518880.XSHG", "512800.XSHG"]  # 债券ETF、黄金ETF、银行ETF
		# self.def_stocks = ["511520.XSHG", "518880.XSHG", "512800.XSHG"]  # 债券ETF、黄金ETF、银行ETF

	# 获取持仓市值
	def get_total_value(self):
		if not g.positions[self.index]:
			return 0
		return sum(self.context.portfolio.positions[key].price * value for key, value in g.positions[self.index].items())

	# 调仓(targets为字典，key为股票代码，value为目标市值)
	def _adjust(self, targets):

		current_data = get_current_data()

		if g.redis_option:
			# 传输信息
			strategy_data = {
				"id": self.index,
				"display_name": self.display_name,
				"last_updated": int(time.time() * 1000),
				"holdings": {
					(stock[:6] + (".SH" if stock.endswith(".XSHG") else ".SZ")): {
						"stock_name": current_data[stock].name,
						"proportion": weight,
					}
					for stock, weight in targets.items()
				},
			}
			set_strategy_data(self.name, strategy_data)

		# 获取已持有列表
		self.hold_list = list(g.positions[self.index].keys())
		portfolio = self.context.portfolio

		# 获取目标策略市值
		target_value = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]

		# ---------- 打印调仓前状态 ----------
		log.info(f"========== [{self.display_name}] 开始调仓 ==========")
		log.info(f"  当前日期: {self.context.current_dt.strftime('%Y-%m-%d %H:%M')}")
		log.info(f"  总资产: {portfolio.total_value:,.2f}, 可用资金: {portfolio.available_cash:,.2f}, 策略分配资金: {target_value:,.2f}")
		log.info(f"  目标持仓:")
		for stock, weight in targets.items():
			log.info(f"    {current_data[stock].name}({stock}): 权重={weight:.1%}, 目标市值={target_value * weight:,.2f}")
		log.info(f"  当前持仓:")
		if not self.hold_list:
			log.info(f"    (空仓)")
		else:
			for stock in self.hold_list:
				pos = g.positions[self.index].get(stock, 0)
				price = current_data[stock].last_price
				log.info(f"    {current_data[stock].name}({stock}): {pos}股, 市值={pos * price:,.2f}")

		# 清仓被调出的
		for stock in self.hold_list:
			if stock not in targets:
				log.error(f"  [调出] {current_data[stock].name}({stock}) → 清仓")
				self.order_target_value_(stock, 0)

		# 先卖出
		for stock, weight in targets.items():
			target = target_value * weight
			price = current_data[stock].last_price
			value = g.positions[self.index].get(stock, 0) * price
			if value - target > max(self.min_money, price * 100):
				log.error(f"  [减仓] {current_data[stock].name}({stock}): 当前市值={value:,.2f} → 目标市值={target:,.2f}")
				self.order_target_value_(stock, target)

		# 后买入
		for stock, weight in targets.items():
			target = target_value * weight
			price = current_data[stock].last_price
			value = g.positions[self.index].get(stock, 0) * price
			if min(target - value, portfolio.available_cash) > max(self.min_money, price * 100):
				log.error(f"  [加仓] {current_data[stock].name}({stock}): 当前市值={value:,.2f} → 目标市值={target:,.2f}")
				self.order_target_value_(stock, target)

		# ---------- 打印调仓后持仓 ----------
		log.info(f"--- 调仓后持仓 ---")
		hold_list = list(g.positions[self.index].keys())
		if not hold_list:
			log.info(f"  (空仓)")
		else:
			total_hold_value = 0
			for stock in hold_list:
				pos = g.positions[self.index].get(stock, 0)
				price = current_data[stock].last_price
				hold_value = pos * price
				total_hold_value += hold_value
				log.info(f"  {current_data[stock].name}({stock}): {pos}股, 市值={hold_value:,.2f}, 占比={hold_value / target_value * 100:.1f}%")
			log.info(f"  持仓总市值: {total_hold_value:,.2f}")
		log.info(f"========== [{self.display_name}] 调仓结束 ==========")

	# 自定义下单(涨跌停不交易)
	def order_target_value_(self, security, value):
		current_data = get_current_data()

		# 检查标的是否停牌、涨停、跌停
		if current_data[security].paused:
			log.info(f"    ✗ {current_data[security].name}({security}): 今日停牌，跳过")
			return False

		if current_data[security].last_price == current_data[security].high_limit:
			log.info(f"    ✗ {current_data[security].name}({security}): 当前涨停，跳过")
			return False

		if current_data[security].last_price == current_data[security].low_limit:
			log.info(f"    ✗ {current_data[security].name}({security}): 当前跌停，跳过")
			return False

		# 获取当前标的的价格
		price = current_data[security].last_price

		# 获取当前策略的持仓数量
		current_position = g.positions[self.index].get(security, 0)

		# 计算目标持仓数量
		target_position = (int(value / price) // 100) * 100 if price != 0 else 0

		# 计算需要调整的数量
		adjustment = target_position - current_position

		# 检查是否当天买入卖出
		closeable_amount = self.context.portfolio.positions[security].closeable_amount if security in self.context.portfolio.positions else 0
		if adjustment < 0 and closeable_amount == 0:
			log.info(f"    ✗ {current_data[security].name}({security}): 当天买入不可卖出，跳过")
			return False

		# 下单并更新持仓
		if adjustment != 0:
			direction = "买入" if adjustment > 0 else "卖出"
			o = order(security, adjustment)
			if o:
				# 更新持仓数量
				filled = o.filled if o.is_buy else -o.filled
				g.positions[self.index][security] = filled + current_position
				# 如果目标持仓为零，移除该证券
				if g.positions[self.index][security] == 0:
					g.positions[self.index].pop(security, None)
				# 更新持有列表
				self.hold_list = list(g.positions[self.index].keys())
				log.error(f"    ✓ {direction} {current_data[security].name}({security}): "
						 f"{abs(filled)}股 @ {o.price:.3f}, "
						 f"成交金额={abs(filled) * o.price:,.2f}, "
						 f"当前持仓={g.positions[self.index].get(security, 0)}股")
				return True
			else:
				log.error(f"    ✗ {direction} {current_data[security].name}({security}): 下单失败")
				return False
		return False

	# 基础过滤(过滤科创北交、ST、停牌、次新股/日)
	def filter_basic_stock(self, stock_list, include_kcbj=False, days=360):
		"""默认过滤ST停牌、科创北交、次新股(上市不满360天)"""
		current_data = get_current_data()

		stock_list = stock_list if include_kcbj else [stock for stock in stock_list if not (stock[0] == "4" or stock[0] == "8" or stock[:2] == "68")]

		return [
			stock
			for stock in stock_list
			if not current_data[stock].paused
			and not current_data[stock].is_st
			and "ST" not in current_data[stock].name
			and "*" not in current_data[stock].name
			and "退" not in current_data[stock].name
			and not self.context.previous_date - get_security_info(stock).start_date < datetime.timedelta(days)
		]

	# 过滤当前时间涨跌停的股票
	def filter_limitup_limitdown_stock(self, stock_list):
		current_data = get_current_data()
		return [
			stock
			for stock in stock_list
			if current_data[stock].last_price < current_data[stock].high_limit and current_data[stock].last_price > current_data[stock].low_limit
		]

	# 过滤近几日涨停过的股票
	def filter_limitup_stock(self, stock_list, days):
		df = get_price(
			stock_list,
			end_date=self.context.previous_date,
			frequency="daily",
			fields=["close", "high_limit"],
			count=days,
			panel=False,
		)
		df = df[df["close"] == df["high_limit"]]
		filterd_stocks = df.code.drop_duplicates().tolist()
		return [stock for stock in stock_list if stock not in filterd_stocks]

	# 过滤重复行业，每个行业允许持有的最大股票数量为n
	def filter_industry(self, stocks, n):
		industry_map = {s: info.get("sw_l1", {}).get("industry_name", "") for s, info in get_industry(stocks).items()}
		counts = {}
		result = []
		for s in stocks:
			ind = industry_map.get(s, "")
			if counts.get(ind, 0) < n:
				result.append(s)
				counts[ind] = counts.get(ind, 0) + 1

		return result

	# 检查持仓中曾经涨停但当前未涨停的股票
	def _check(self):
		hold = list(g.positions[self.index].keys())
		if not hold:
			return []
		current_data = get_current_data()
		filtered = self.filter_limitup_stock(hold, 3)
		return [s for s in hold if s not in filtered and current_data[s].last_price < current_data[s].high_limit]

	# 识别无法交易的股票（停牌、涨跌停）
	def filter_untradeable_stock(self, stocks):
		current_data = get_current_data()
		return [
			stock
			for stock in stocks
			if current_data[stock].paused or current_data[stock].last_price in (current_data[stock].high_limit, current_data[stock].low_limit)
		]

	# 根据调仓逻辑计算最终保留的股票列表
	def get_adjusted_stocks(self, selected, sell):
		fixed = self.filter_untradeable_stock(list(g.positions[self.index].keys()))
		sum = len(self.def_stocks) if selected == self.def_stocks else self.stock_sum - len(fixed)
		return fixed + [s for s in selected if s not in fixed and s not in sell][:sum]

	# 排除金融行业股票
	def filter_financial_stocks(self, stocks):
		"""过滤掉金融行业的股票"""
		financial_industries = ["银行I", "非银金融I"]
		industry_data = get_industry(stocks)
		return [stock for stock in stocks if not industry_data[stock].get("sw_l1", {}).get("industry_name", "") in financial_industries]


# -------------------- 各具体策略类 --------------------
# 核心资产轮动策略
class Etf_Rotation_Strategy(Strategy):
	def __init__(self, context, index, name, display_name):
		super().__init__(context, index, name, display_name)

		self.etf_pool = [
			# 境外
			"513100.XSHG",  # 纳指ETF 2013/05
			"513520.XSHG",  # 日经ETF 2019/06
			"513030.XSHG",  # 德国ETF 2014/10
			# 商品
			"518880.XSHG",  # 黄金ETF 2013/08
			"159980.XSHE",  # 有色ETF 2019/11
			"159985.XSHE",  # 豆粕ETF 2019/10
			"501018.XSHG",  # 南方原油 2016/06
			# 债券
			"511090.XSHG",  # 30年国债ETF 2023/05
			#"511220.XSHG",  # 城投债ETF 2014/11
			# 国内
			"513130.XSHG",  # 恒生科技 2021/05
			#"600900.XSHG",  # 长江电力 2003/12
			#"601088.XSHG",  # 中国神华 2007/07
			#"000429.XSHE",  # 粤高速A 1998/03
			#"601899.XSHG",  # 紫金矿业 2008/06
			#"601288.XSHG",  # 农业银行 2010/08
		]

	# 选取ETF
	def filter(self, max_score, days):
		data = pd.DataFrame(index=self.etf_pool, columns=["annualized_returns", "r2", "score"])
		current_data = get_current_data()

		label = "短期动量" if days == 25 else "长期动量"
		log.info(f"========== [{self.display_name}] {label}选股开始 (窗口={days}天, 得分上限={max_score}) ==========")

		for etf in self.etf_pool:
			# 获取数据
			df = attribute_history(etf, days, "1d", ["close", "high"])
			prices = np.append(df["close"].values, current_data[etf].last_price)

			# 设置参数
			y = np.log(prices)
			x = np.arange(len(y))
			weights = np.linspace(1, 2, len(y))

			# 计算年化收益率
			slope, intercept = np.polyfit(x, y, 1, w=weights)
			data.loc[etf, "annualized_returns"] = math.exp(slope * 250) - 1

			# 计算R²
			ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
			ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
			data.loc[etf, "r2"] = 1 - ss_res / ss_tot if ss_tot else 0

			# 计算得分
			data.loc[etf, "score"] = data.loc[etf, "annualized_returns"] * data.loc[etf, "r2"]

			# 过滤近3日跌幅超过5%的ETF
			recent_min_ratio = min(prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4])
			dip_filtered = recent_min_ratio < 0.95

			log.info(
				f"  {current_data[etf].name}({etf}): "
				f"年化收益={data.loc[etf, 'annualized_returns']:.4%}, "
				f"R²={data.loc[etf, 'r2']:.4f}, "
				f"得分={data.loc[etf, 'score']:.4f}, "
				f"近3日最低比={recent_min_ratio:.4f}"
				f"{' [近3日跌超5%→淘汰]' if dip_filtered else ''}"
			)

			# 过滤近3日跌幅超过5%的ETF
			if dip_filtered:
				data.loc[etf, "score"] = 0

		# 过滤ETF，并按得分降序排列
		filtered_data = data[(data["score"] > 0) & (data["score"] < max_score)].sort_values(by="score", ascending=False)

		log.warn(f"--- 得分筛选(>0且<{max_score})结果 ---")
		if filtered_data.empty:
			log.warn("  无符合条件的ETF → 选用银华日利(511880.XSHG)")
		else:
			for etf, row in filtered_data.iterrows():
				log.warn(f"  ✓ {current_data[etf].name}({etf}): 得分={row['score']:.4f}")

		if filtered_data.empty:
			return "511880.XSHG"

		selected = filtered_data.index.tolist()[0]
		log.info(f"  >>> {label}最终选出: {current_data[selected].name}({selected})")
		return selected

	# 选股
	def select(self):
		current_data = get_current_data()
		# 短期动量选股
		etf1 = self.filter(6, 25)
		# 长期动量选股
		etf2 = self.filter(0.5, 250)

		log.warn(f"========== [{self.display_name}] 选股汇总 ==========")
		log.warn(f"  短期动量选出: {current_data[etf1].name}({etf1})")
		log.warn(f"  长期动量选出: {current_data[etf2].name}({etf2})")

		if etf1 != etf2:
			log.warn(f"  两者不同 → 各配50%: [{current_data[etf1].name}, {current_data[etf2].name}]")
			return [etf1, etf2]
		else:
			log.warn(f"  两者相同 → 全仓: [{current_data[etf1].name}]")
			return [etf1]

	# 调仓
	def adjust(self):
		targets = self.select()
		self._adjust({etf: round(1 / len(targets), 3) for etf in targets})


# -------------------- 小市值轮动策略 --------------------
class Small_Cap_Rotation_Strategy(Strategy):
	"""小市值周度轮动策略 — 每周二从中小综指选市值最小、行业分散的N只股票持有。
	   1月/4月切换全天候ETF避险，具备三重止损保护。"""

	def __init__(self, context, index, name, display_name):
		super().__init__(context, index, name, display_name)

		# ===== 策略参数 =====
		self.stock_sum = 9  # 持有股票数量
		self.weekday = 2  # 周二调仓
		self.pool = '399101.XSHE'  # 中小综指
		self.etf = '511880.XSHG'  # 空仓月份持有银华日利ETF
		self.all_weather_list = ["518880.XSHG", "511010.XSHG", "513100.XSHG", "601288.XSHG"]
		self.position_step = 0.00  # 等权配置

		# ===== 止损参数 =====
		self.stoploss_strategy = 3  # 1=个股止损, 2=大盘止损, 3=联合
		self.stoploss_limit = 0.1  # 个股止损线 10%
		self.stoploss_market = 0.05  # 大盘止损线 5%
		self.run_stoploss = True

		# ===== 状态变量 =====
		self.stock_pool = []
		self.selected_stocks = []
		self.stocks_to_buy = []
		self.stocks_to_sell = []
		self.stocks_fail_sell = []
		self.yesterday_HL_list = []
		self.limitup_stocks = []
		self.excepted_position = {}
		self.limitup_map = {}
		self.stoploss_map = {}
		self.trade_enabled = True  # 1月/4月为False
		self.sell_done = False
		self.reason_to_sell = ''
		self.refresh_hold = False
		self.trade_day = False
		self.each_cash = 0
		self.last_month = None

	# ================================================================
	# 调度入口方法
	# ================================================================

	def judge_date(self):
		"""检测是否1月/4月，设置空仓标志"""
		current_date = self.context.current_dt.date()
		current_month = current_date.month
		if current_month == 1 or current_month == 4:
			if self.trade_enabled:
				log.info('✅========== 一月和四月份清仓，日期：%s ==========' % current_date)
			self.trade_enabled = False
		else:
			self.trade_enabled = True

	def prepare_stock_list(self):
		"""刷新持仓列表、检测昨日涨停、止损冷却递减"""
		self.hold_list = []
		self.limitup_stocks = []
		self.trade_day = False

		for stock in list(g.positions[self.index].keys()):
			self.hold_list.append(stock)

		# 获取昨日涨停列表
		if self.hold_list:
			df = get_price(
				self.hold_list,
				end_date=self.context.previous_date,
				frequency='daily',
				fields=['close', 'high_limit', 'low_limit'],
				count=1,
				panel=False,
				fill_paused=False,
			)
			df = df[df['close'] == df['high_limit']]
			self.yesterday_HL_list = list(df.code)
			if self.yesterday_HL_list:
				log.info("")
				log.info("************昨日(%s)涨停 **************" % self.context.previous_date)
				log.info(list(df.code))
				log.info("")

			for stock in self.yesterday_HL_list:
				self.limitup_map[stock] = self.limitup_map.setdefault(stock, 0) + 1
		else:
			self.yesterday_HL_list = []

		# 2024年后全天候ETF切换为30年国债
		date_str = str(self.context.previous_date)
		if date_str > '2024-01-01':
			self.all_weather_list = ["518880.XSHG", "511090.XSHG", "513100.XSHG", "601288.XSHG"]

		# 止损冷却递减
		self.stoploss_map = {k: v - 1 for k, v in self.stoploss_map.items() if v - 1 > 0}

	def trade_etf(self):
		"""1月/4月空仓期：切换全天候ETF"""
		if self.trade_enabled:
			return

		current_holdings = list(g.positions[self.index].keys())
		date_str = str(self.context.previous_date)

		if date_str < '2014-01-01':
			if current_holdings != [self.etf]:
				log.info('买入ETF')
				self.selected_stocks = [self.etf]
				self.collect_sell_buy_stocks()
				self.sell_stocks()
				self.buy_stocks()
		else:
			all_weather = False
			for stock in current_holdings:
				if stock not in self.all_weather_list:
					log.info('使用全天候策略')
					all_weather = True
					break
			if all_weather:
				self.selected_stocks = self.all_weather_list.copy()
				self.collect_sell_buy_stocks()
				self.sell_stocks()
				self.exec_all_weather()

	def exec_all_weather(self):
		"""全天候ETF：-1/ES 风险平价权重"""
		df = get_price(
			self.all_weather_list,
			end_date=self.context.previous_date,
			frequency="daily",
			fields=["close"],
			count=120,
			panel=False,
		)
		weights = {}
		for code, group in df.groupby('code'):
			group = group.sort_values('time')
			if group.shape[0] < 120:
				weight = 0
			else:
				group['daily_return'] = group['close'].pct_change() * 100
				sorted_group = group.sort_values(by='daily_return')
				ES = sorted_group['daily_return'].head(6).mean()
				weight = -1 / ES
			weights[code] = weight

		log.info('全天候权重:%s' % weights)

		total_weight = sum([w for w in weights.values()])
		fin_weights = {key: value / total_weight for key, value in weights.items()}

		for stock, w in fin_weights.items():
			log.info('%s %s 权重%.2f%%' % (stock, get_security_info(stock).display_name, 100 * w))

		# 策略可用资金 = 总可用资金 × 本策略占比
		strategy_budget = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
		available_cash = min(self.context.portfolio.available_cash, strategy_budget)
		log.info('available_cash: %s' % available_cash)

		current_data = get_current_data()
		for stock in self.all_weather_list:
			stock_data = current_data[stock]
			current_price = stock_data.last_price
			if math.isnan(current_price):
				continue
			target_value = available_cash * fin_weights[stock]
			amount = int(target_value / current_price / 100) * 100
			if amount > 0:
				log.info('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
				log.info('%s %s 目标市值%.2f, 买入%d股 * %.2f元' % (
					stock, get_security_info(stock).display_name, target_value, amount, current_price))
				self.order_target_value_(stock, amount * current_price)
				self.refresh_hold = True

	def adjust(self):
		"""周度调仓：10:00卖出 / 10:10买入"""
		if not self.trade_enabled:
			return
		self.trade_day = True

		current_date = self.context.current_dt.date()
		current_time = self.context.current_dt.time()
		morning_sell_time = datetime.time(10, 0)
		afternoon_buy_time = datetime.time(10, 10)

		log.info('✅========== 执行周度调仓，日期：%s ==========' % current_date)
		prev_date = current_date - datetime.timedelta(days=1)

		# ---- 卖出阶段 (10:00) ----
		if current_time == morning_sell_time:
			self.info_position()
			no_st_codes = self.get_normal_stocks(self.context.current_dt.date())
			self.stock_pool = no_st_codes
			self.selected_stocks = self.get_small_cap_stocks(self.stock_pool, prev_date, self.stock_sum)

			# 移除止损冷却期的股票
			for stock in list(self.stoploss_map.keys()):
				if stock in self.selected_stocks:
					self.selected_stocks.remove(stock)
					log.error("%s %s 前%d日止损卖出" % (
						stock, get_security_info(stock).display_name, 3 - self.stoploss_map.get(stock, 0)))

			self.collect_sell_buy_stocks()
			current_holdings = list(g.positions[self.index].keys())

			if len(self.stocks_to_buy) > 0 or len(self.stocks_to_sell) > 0:
				log.info("✅当前持股 %d只" % len(current_holdings))
				for stock in current_holdings:
					log.info("✅%s" % get_security_info(stock).display_name)

				log.info("✅需要买入股票 %d只" % len(self.stocks_to_buy))
				log.info("✅需要卖出股票 %d只" % len(self.stocks_to_sell))
				for stock in self.stocks_to_buy:
					log.info("✅待买入 %s" % get_security_info(stock).display_name)
				for stock in self.stocks_to_sell:
					log.info('✅待卖出: %s' % get_security_info(stock).display_name)

				log.info("✅今日(%s)为卖出时间，执行卖出操作" % current_time)
				log.info('✅------------------------------------------')

				self.sell_stocks()
				self.sell_done = True
				self.log_selection_details(self.selected_stocks, prev_date)
			else:
				log.warn('未选到符合条件的股票，本日不调仓')

		# ---- 买入阶段 (10:10) ----
		elif current_time == afternoon_buy_time and self.sell_done and self.reason_to_sell != 'takeprofit':
			if len(self.stocks_to_buy):
				log.info("✅今日(%s)为买入时间，执行买入操作" % current_time)
				log.info('✅+++++++++++++++++++++++++++++++++++++++++')
				log.info("✅需要买入股票 %d只" % len(self.stocks_to_buy))
				for stock in self.stocks_to_buy:
					log.info(get_security_info(stock).display_name)

			self.calc_position()
			self.buy_stocks()
			self.sell_done = False
			self.info_position()
		else:
			log.info("今日(%s)非调仓日，不执行操作" % current_date)

	def stop_loss(self):
		"""三重止损检查"""
		show_info = False
		if not self.run_stoploss:
			return

		current_positions = self.context.portfolio.positions

		# ---- 策略1：个股止损 ----
		if self.stoploss_strategy == 1 or self.stoploss_strategy == 3:
			for stock in list(current_positions.keys()):
				# 只处理本策略持仓
				if stock not in g.positions[self.index]:
					continue
				price = current_positions[stock].price
				avg_cost = current_positions[stock].avg_cost
				# 个股盈利止盈
				if price >= avg_cost * 2:
					if self.order_target_value_(stock, 0):
						show_info = True
					log.debug("⭕ 收益100%止盈,卖出{}".format(stock))
				# 个股止损
				elif price < avg_cost * (1 - self.stoploss_limit):
					success = self.order_target_value_(stock, 0)
					self.stoploss_map[stock] = self.stoploss_map.setdefault(stock, 3)
					log.debug(f"⭕ 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
					if success:
						show_info = True
					self.reason_to_sell = 'stoploss'
					if stock in self.selected_stocks:
						self.selected_stocks.remove(stock)

		# ---- 策略2/3：大盘止损 ----
		if self.stoploss_strategy == 2 or self.stoploss_strategy == 3:
			stock_df = get_price(
				security=get_index_stocks(self.pool),
				end_date=self.context.previous_date,
				frequency='daily',
				fields=['close', 'open'],
				count=1,
				panel=False,
			)
			down_ratio = (stock_df['close'] / stock_df['open'] - 1).mean()
			log.debug("大盘降幅{:.2%}".format(down_ratio))

			if abs(down_ratio) >= self.stoploss_market:
				self.refresh_hold = True
				if down_ratio < 0:
					self.reason_to_sell = 'stoploss'
					log.debug("⭕ 大盘惨跌,平均降幅{:.2%}".format(down_ratio))
				else:
					self.reason_to_sell = 'takeprofit'
					log.debug("⭕ 大盘大涨,平均涨幅{:.2%}".format(down_ratio))

				for stock in list(current_positions.keys()):
					if stock == self.etf:
						continue
					if stock in self.all_weather_list:
						continue
					if stock in self.yesterday_HL_list:
						continue
					if stock not in g.positions[self.index]:
						continue
					log.debug('⭕ 清仓%s %s' % (stock, get_security_info(stock).display_name))
					self.order_target_value_(stock, 0)
					show_info = True
					if stock in self.selected_stocks:
						self.selected_stocks.remove(stock)

		if show_info:
			self.info_position()

	def trade_afternoon(self):
		"""下午盘处理：涨停开板卖出 + 补仓"""
		self.check_limit_up()
		self.check_remain_amount()

	def check_limit_up(self):
		"""检测昨日涨停股是否开板，开板则卖出"""
		now_time = self.context.current_dt
		if not self.yesterday_HL_list:
			return

		for stock in self.yesterday_HL_list:
			if stock not in g.positions[self.index]:
				continue
			current_data = get_price(
				stock,
				end_date=now_time,
				frequency='1m',
				fields=['close', 'high_limit'],
				skip_paused=False,
				fq='pre',
				count=1,
				panel=False,
				fill_paused=True,
			)
			close_price = current_data.iloc[0, 1] / 1.1
			rise_ratio = (current_data.iloc[0, 0] - close_price) / close_price * 100

			if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
				self.order_target_value_(stock, 0)
				self.reason_to_sell = 'limitup'
				self.limitup_stocks.append(stock)
				log.warn("%s %s %d 涨幅%.2f%%" % (
					stock, get_security_info(stock).display_name,
					self.limitup_map.get(stock, 0), rise_ratio))
				self.limitup_map.pop(stock, None)
			else:
				log.info("%s %s涨停，继续持有" % (stock, get_security_info(stock).display_name))

	def check_remain_amount(self):
		"""涨停卖出后次日补仓"""
		if self.reason_to_sell == 'limitup':
			self.hold_list = list(g.positions[self.index].keys())
			flag = True

			if len(self.hold_list) < self.stock_sum or flag:
				log.info('现有持仓:')
				for stock_code in self.hold_list:
					log.info('  %s %s' % (get_security_info(stock_code).display_name, stock_code))
				log.info('涨停卖出')
				for stock_code in self.limitup_stocks:
					log.info('  %s %s' % (get_security_info(stock_code).display_name, stock_code))

				current_date = self.context.current_dt.date()
				prev_date = current_date - datetime.timedelta(days=1)
				self.selected_stocks = self.get_small_cap_stocks(self.stock_pool, prev_date, self.stock_sum)

				for stock_code in self.limitup_stocks:
					if stock_code in self.selected_stocks:
						self.selected_stocks.remove(stock_code)

				for stock in list(self.stoploss_map.keys()):
					if stock in self.selected_stocks:
						self.selected_stocks.remove(stock)
						log.error("%s %s 前%d日止损卖出" % (
							stock, get_security_info(stock).display_name,
							3 - self.stoploss_map.get(stock, 0)))

				current_holdings = list(g.positions[self.index].keys())
				if len(current_holdings) > 3:
					self.selected_stocks = current_holdings

				self.collect_sell_buy_stocks()
				if len(self.stocks_to_buy) > 0:
					log.info("需要买入股票 %d只" % len(self.stocks_to_buy))
					for stock in self.stocks_to_buy:
						log.info("待买入 %s" % get_security_info(stock).display_name)

				log.info('有余额可用' + str(round(self.context.portfolio.cash, 2)) + '元。买入' + str(self.stocks_to_buy))
				self.info_position()
				self.calc_position()
				self.buy_stocks()
				self.refresh_hold = True
			self.reason_to_sell = ''

		elif self.reason_to_sell == 'stoploss' or self.reason_to_sell == 'takeprofit':
			log.info('止盈止损后，有余额可用' + str(round(self.context.portfolio.cash, 2)) + '元。买入' + str(self.etf))
			self.stocks_to_buy = [self.etf]
			self.buy_stocks()
			self.reason_to_sell = ''
			self.refresh_hold = True

	# ================================================================
	# 选股流水线
	# ================================================================

	def get_normal_stocks(self, target_date):
		"""获取正常交易的股票列表（过滤退市、ST、停牌等）"""
		MKT_index = self.pool
		all_stocks = get_index_stocks(MKT_index, target_date)
		log.info('在 %s，%s 共有 %d 只股票' % (target_date, MKT_index, len(all_stocks)))

		all_stocks = self.filter_chuangye_beijiao_codes(all_stocks)
		log.info('去除科创版，北交所等，共有 %d 只股票' % len(all_stocks))

		non_st_stocks = self.filter_st_stocks(all_stocks, target_date)
		log.info('过滤ST/*ST股票后，剩余 %d 只' % len(non_st_stocks))

		trading_stocks = self.filter_paused_stocks(non_st_stocks, target_date)
		log.info('过滤停牌，涨跌停股票后，剩余 %d 只' % len(trading_stocks))

		mature_stocks = self.filter_new_stock(trading_stocks, min_days=180)
		log.info('过滤上市不足180天股票后，剩余 %d 只' % len(mature_stocks))

		return mature_stocks

	def get_small_cap_stocks(self, stock_list, query_date, n=5):
		"""获取市值最小的n只股票，行业分散"""
		all_data_frames = []
		batch_size = 30

		for i in range(0, len(stock_list), batch_size):
			batch_stocks = stock_list[i:i + batch_size]
			try:
				q = query(
					valuation.code,
					valuation.market_cap
				).filter(
					valuation.code.in_(batch_stocks)
				)
				df_batch = get_fundamentals(q, date=query_date.strftime('%Y-%m-%d'))
				if df_batch is not None and len(df_batch) > 0:
					all_data_frames.append(df_batch)
			except Exception as e:
				log.error('查询市值数据时出错（批次 %d）: %s' % (i // batch_size + 1, str(e)))
				continue

		if not all_data_frames:
			log.warn("未获取到任何股票的市值数据")
			return []

		df_all = pd.concat(all_data_frames, ignore_index=True)
		df_sorted = df_all.sort_values('market_cap', ascending=True)

		if n > 30:
			print("get_small_cap_stocks   %s    head %d" % (query_date, n))
			rank = 0
			for idx, row in df_sorted.head(10).iterrows():
				stock_name = get_security_info(row['code']).display_name
				cap_in_10k = row['market_cap']
				rank = rank + 1
				marker = '  <== 选中' if rank <= n else ''
				log.info('    第%2d名: %s(%s), 流通市值: %.2f 亿元%s' % (rank, stock_name, row['code'], cap_in_10k, marker))

		selected_stocks = self.small_cap_get_stock_industry(list(df_sorted.code)[:100], n)

		# 如果有新选中的股票（不在原有持仓中），打印详情
		flag = False
		for stock_code in selected_stocks:
			if stock_code not in self.selected_stocks:
				flag = True
				break

		if flag:
			print("get_small_cap_stocks   %s    head %d" % (query_date, n))
			rank = 0
			for idx, row in df_sorted.head(25).iterrows():
				stock = row['code']
				stock_name = get_security_info(stock).display_name
				cap_in_10k = row['market_cap']
				rank = rank + 1
				industrys = get_industry(security=[stock])
				info = industrys[stock]
				industry_name = info['sw_l2']['industry_name']
				marker = '  <== 选中' if stock in selected_stocks else ''
				log.info('    第%2d名: %s(%s), 流通市值: %.2f 亿元 %s%s' % (
					rank, stock_name, row['code'], cap_in_10k, industry_name, marker))

		return selected_stocks

	def small_cap_get_stock_industry(self, stock_list, num):
		"""SW2行业分散选股，每个行业最多1只"""
		try:
			result = get_industry(security=stock_list)
			selected_stocks = []
			industry_list = []

			for stock_code in stock_list:
				if stock_code in result:
					info = result[stock_code]
					if 'sw_l2' in info and info['sw_l2']:
						industry_name = info['sw_l2']['industry_name']
						if industry_name not in industry_list:
							industry_list.append(industry_name)
							selected_stocks.append(stock_code)
							if len(industry_list) >= num:
								break
			return selected_stocks
		except Exception as e:
			log.error("行业筛选错误: %s" % e)
			return stock_list[:num]

	# ================================================================
	# 过滤辅助方法
	# ================================================================

	def filter_chuangye_beijiao_codes(self, all_stocks):
		"""过滤创业板(30)、科创板(688)、北交所(8)、三板(4)"""
		filtered_stocks = []
		for stock in all_stocks:
			if stock.startswith('30') or stock.startswith('688') or stock.startswith('8') or stock.startswith('4'):
				continue
			filtered_stocks.append(stock)
		return filtered_stocks

	def filter_st_stocks(self, stock_list, target_date):
		"""过滤ST/*ST股票"""
		non_st_list = []
		if len(stock_list) == 0:
			return non_st_list

		current_data = get_current_data()
		for stock in stock_list:
			if current_data[stock].is_st:
				continue
			non_st_list.append(stock)
		return non_st_list

	def filter_paused_stocks(self, stock_list, target_date):
		"""过滤停牌及涨跌停股票（已持仓的涨跌停不过滤）"""
		trading_stocks = []
		if len(stock_list) == 0:
			return trading_stocks

		last_prices = history(1, unit='1m', field='close', security_list=stock_list)
		current_data = get_current_data()

		for stock in stock_list:
			if current_data[stock].paused:
				continue
			# 涨停：已持仓的可保留，未持仓的过滤
			if not (stock in self.context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit):
				continue
			# 跌停：已持仓的可保留，未持仓的过滤
			if not (stock in self.context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit):
				continue
			trading_stocks.append(stock)

		return trading_stocks

	def filter_new_stock(self, stock_list, min_days):
		"""过滤上市不足min_days天的股票"""
		yesterday = self.context.previous_date
		return [
			stock for stock in stock_list
			if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=min_days)
		]

	# ================================================================
	# 交易执行方法
	# ================================================================

	def collect_sell_buy_stocks(self):
		"""对比选中股票与当前持仓，确定买卖清单"""
		self.stocks_to_sell = []
		self.stocks_to_buy = []
		current_holdings = list(g.positions[self.index].keys())

		for stock in current_holdings:
			if (stock not in self.selected_stocks) and (stock not in self.yesterday_HL_list):
				self.stocks_to_sell.append(stock)

		for stock in self.selected_stocks:
			if (stock not in current_holdings) and (stock not in self.yesterday_HL_list):
				self.stocks_to_buy.append(stock)

	def sell_stocks(self):
		"""执行卖出"""
		self.stocks_fail_sell = []
		for stock in self.stocks_to_sell:
			log.info('✅>>>>>>>>>>>>')
			log.info('✅卖出: %s' % get_security_info(stock).display_name)
			success = self.order_target_value_(stock, 0)
			if success:
				log.info('卖出 %s 成功' % stock)
			else:
				current_data = get_current_data()
				last_prices = history(1, unit='1m', field='close', security_list=[stock])
				is_limit_down = last_prices[stock][-1] <= current_data[stock].low_limit
				if current_data[stock].paused or is_limit_down:
					self.stocks_fail_sell.append(stock)
				else:
					log.error("卖出%s %s 失败，原因未知(非停牌非跌停)" % (
						stock, get_security_info(stock).display_name))

	def buy_stocks(self):
		"""执行买入"""
		if len(self.stocks_to_buy) == 0:
			return

		available_cash = self.context.portfolio.available_cash
		position_value = self.context.portfolio.positions_value
		total_value = self.context.portfolio.total_value

		# 限制买入金额不超过本策略分配的资金
		strategy_budget = total_value * g.portfolio_value_proportion[self.index]
		strategy_current_value = sum(
			self.context.portfolio.positions[key].price * value
			for key, value in g.positions[self.index].items()
		) if g.positions[self.index] else 0
		max_buy = max(0, strategy_budget - strategy_current_value)
		available_cash = min(available_cash, max_buy)

		self.each_cash = available_cash / len(self.stocks_to_buy)
		log.info("====调整每股额度====\n当前可用资金 %s\n持仓市值 %s\n总资产: %s\n每股额度 %s" % (
			available_cash, position_value, total_value, self.each_cash))

		current_data = get_current_data()
		target_value_per_stock = self.each_cash

		for stock in self.stocks_to_buy:
			stock_data = current_data[stock]
			current_price = stock_data.last_price
			if math.isnan(current_price):
				continue

			if stock == self.etf:
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100
				self.order_target_value_(stock, amount * current_price)
				log.info('买入: %s, %s \n目标价值:%.2f\n预计买入%d股，每股%.2f元，合计:%.2f' % (
					get_security_info(stock).display_name, stock,
					target_value_per_stock, amount, current_price, amount * current_price))
			else:
				if self.excepted_position.get(stock) is not None:
					target_value_per_stock = self.excepted_position[stock] * total_value
				order_info = self.order_target_value_(stock, target_value_per_stock)
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100
				log.info('委托买入: %s, %s \n目标价值:%.2f\n预计买入%d股，每股%.2f元，合计:%.2f' % (
					get_security_info(stock).display_name, stock,
					target_value_per_stock, amount, current_price, amount * current_price))

	def calc_position(self):
		"""计算等权仓位，含失败卖出和涨停锁定股的偏差修正"""
		total_value = self.context.portfolio.total_value
		current_holdings = list(g.positions[self.index].keys())
		holding_num = len(current_holdings) + len(self.stocks_to_buy)

		if holding_num != len(self.selected_stocks):
			log.info('⭕ ⭕ 股票数量异常，期望最终持仓%d只，实际选中%d只' % (holding_num, len(self.selected_stocks)))

		positions = self.context.portfolio.positions
		fail_pos = 0
		for stock in self.stocks_fail_sell:
			if stock in positions:
				fp = positions[stock].value / total_value
				fail_pos += fp
				log.info('停牌股 %s 占仓位比重为 %.2f%%' % (get_security_info(stock).display_name, fp * 100))

		HL_count = 0
		for stock in self.yesterday_HL_list:
			if stock in current_holdings and stock in positions:
				fp = positions[stock].value / total_value
				fail_pos += fp
				HL_count += 1
				log.info('涨停股 %s 占仓位比重为 %.2f%%' % (get_security_info(stock).display_name, fp * 100))

		self.excepted_position = {}
		if holding_num - len(self.stocks_fail_sell) - HL_count <= 1:
			log.info('涨停股数量 %d, 异常股票数量%d, 可调整股票数量: 0。 无需调整' % (
				HL_count, len(self.stocks_fail_sell)))
			return

		p = (1 - fail_pos) / (holding_num - len(self.stocks_fail_sell) - HL_count)

		for i in range(len(self.selected_stocks)):
			stock = self.selected_stocks[i]
			if stock in self.stocks_fail_sell or stock in self.yesterday_HL_list:
				continue
			self.excepted_position[stock] = p + ((holding_num - 1) / 2 - i) * self.position_step

		for stock, pos in self.excepted_position.items():
			stock_name = get_security_info(stock).display_name
			log.info(' 期望持仓: %s(%s), 占比 %.2f%%' % (stock_name, stock, pos * 100))

		current_data = get_current_data()
		position_dict = {}
		position_sum = 0

		# 计算已有持仓的股票占比
		for stock, pos in positions.items():
			if stock not in g.positions[self.index]:
				continue
			stock_data = current_data[stock]
			position_sum += pos.value
			position_dict[stock] = [pos.value / total_value, stock_data.last_price]

		# 计算待买入的持仓占比
		for stock in self.stocks_to_buy:
			stock_name = get_security_info(stock).display_name
			target_value = total_value * self.excepted_position[stock]
			stock_data = current_data[stock]
			current_price = stock_data.last_price
			if math.isnan(current_price):
				self.excepted_position.pop(stock)
				continue
			amount = int(target_value / current_price / 100) * 100
			need_cash = amount * current_price
			log.info('预计买入%s(%s)  %d 股 * %.2f,总计 %.2f' % (stock_name, stock, amount, current_price, need_cash))
			position_sum += need_cash
			position_dict[stock] = [need_cash / total_value, current_price]

		avai_cash = total_value - position_sum
		log.info('预计持仓 %s 剩余金额 %.2f' % (position_sum, avai_cash))

		# 偏差修正：如果剩余资金过大，重新分配
		if abs(avai_cash) > 5000 or avai_cash < 0:
			cash = 0
			for stock, exce_pos in self.excepted_position.items():
				if stock in self.stocks_fail_sell:
					continue
				pos, stock_price = position_dict[stock]
				diff_pos = exce_pos - pos
				if abs(diff_pos) * total_value > 5000 or abs(diff_pos) > 0.04:
					stock_name = get_security_info(stock).display_name
					log.info('%s 持仓与期望相差较大，持仓%.2f%%,期望%.2f%%,金额相差%.2f' % (
						stock_name, pos * 100, exce_pos * 100, diff_pos * total_value))
					if diff_pos > 0:
						self.stocks_to_buy.append(stock)
						cash -= diff_pos * total_value
					else:
						old_pos = g.positions[self.index].get(stock, 0)
						self.order_target_value_(stock, exce_pos * total_value)
						if g.positions[self.index].get(stock, 0) != old_pos:
							cash -= diff_pos * total_value
							log.info('调整%s市值' % stock_name)

			avai_cash += cash
			if cash != 0:
				log.info('重新分配之后资金为%.2f' % avai_cash)

			if avai_cash > 5000:
				log.info('重新分配之后资金仍有剩余，追加买入')
				pos_dict = {}
				for stock, exce_pos in self.excepted_position.items():
					if stock in self.stocks_fail_sell or stock in self.stocks_to_buy:
						continue
					pos, stock_price = position_dict[stock]
					diff_pos = exce_pos - pos
					if diff_pos > 0:
						pos_dict[stock] = diff_pos

				sorted_pos = list(sorted(pos_dict.items(), key=lambda x: x[1], reverse=True))
				for stock, diff_pos in sorted_pos:
					stock_name = get_security_info(stock).display_name
					c = diff_pos * total_value
					avai_cash -= c
					if avai_cash > 0:
						self.stocks_to_buy.append(stock)
						log.info('%s 持仓与期望相差%.2f%% %.2f，补仓' % (stock_name, diff_pos * 100, diff_pos * total_value))

			elif avai_cash < 0 and cash == 0 and len(self.stocks_to_buy) > 0:
				log.info('未重新分配资金，调整买入仓位比重')
				available_cash = self.context.portfolio.available_cash
				for stock in self.stocks_to_buy:
					self.excepted_position[stock] = available_cash / len(self.stocks_to_buy) / total_value
					log.info('期望持仓: %s(%s)，占比%.2f%%' % (
						get_security_info(stock).display_name, stock,
						self.excepted_position[stock] * 100))

		# 日志：预估持仓
		for stock, pos in position_dict.items():
			stock_name = get_security_info(stock).display_name
			log.info(' 预估持仓: %s(%s), 占比 %.2f%% 单价 %.2f' % (stock_name, stock, pos[0] * 100, pos[1]))

		# 调整买入数量（微调手数）
		for stock, exce_pos in self.excepted_position.items():
			if stock in self.stocks_fail_sell or stock not in position_dict:
				continue
			pos, stock_price = position_dict[stock]
			diff_value = (exce_pos - pos) * total_value
			stock_name = get_security_info(stock).display_name
			stock_data = current_data[stock]
			current_price = stock_data.last_price

			if stock in self.stocks_to_buy and diff_value > 0:
				excepted_value = exce_pos * total_value
				current_value = pos * total_value
				num = int((excepted_value - current_value) / current_price / 100)
				log.info('调整%s买入数量，期望买入%.2f,当前%.2f,相差%.2f' % (
					stock_name, excepted_value, current_value, diff_value))
				while True:
					new_value = current_value + current_price * num * 100
					diff_v = excepted_value - new_value
					log.info('单价%.2f，新市值%.2f，差值%.2f' % (current_price, new_value, diff_v))
					if abs(round(diff_v, 2)) <= abs(round(diff_value, 2)):
						diff_value = diff_v
						num += 1
					else:
						num -= 1
						break
				if num > 0:
					self.excepted_position[stock] = (current_value + current_price * num * 100) / total_value
					log.info('调整买入数量，追加%d手,仓位占比调整为%.2f%%' % (num, self.excepted_position[stock] * 100))

	# ================================================================
	# 辅助方法
	# ================================================================

	def calc_ES_weights(self, stocks):
		"""计算ES风险平价权重"""
		if not stocks:
			return {}

		df = get_price(
			stocks,
			end_date=self.context.previous_date,
			frequency="daily",
			fields=["close"],
			count=120,
			panel=False,
		)
		weights = {}
		for code, group in df.groupby('code'):
			group = group.sort_values('time')
			if group.shape[0] < 120:
				weight = 1 / len(stocks)
			else:
				group['daily_return'] = group['close'].pct_change() * 100
				sorted_group = group.sort_values(by='daily_return')
				ES = sorted_group['daily_return'].head(6).mean()
				if ES < 0.00001:
					weight = 1 / len(stocks)
				else:
					weight = -1 / ES
			weights[code] = weight

		total_weight = sum([w for w in weights.values()])
		weights = {key: value / total_weight for key, value in weights.items()}
		log.info('ES权重:%s' % weights)
		return weights

	def log_selection_details(self, selected_stocks, query_date):
		"""记录选股详情（用于调试和分析）"""
		if len(selected_stocks) == 0:
			return
		if len(self.stocks_to_buy) == 0 and len(self.stocks_to_sell) == 0:
			return

		q = query(
			valuation.code,
			valuation.circulating_market_cap,
			valuation.market_cap,
			indicator.inc_net_profit_to_shareholders_year_on_year
		).filter(
			valuation.code.in_(selected_stocks)
		)

		df = get_fundamentals(q, date=query_date.strftime('%Y-%m-%d'))
		if df is not None and len(df) > 0:
			current_data = get_current_data()
			log.info('✅=== 本日选中股票详情 ===')
			for _, row in df.iterrows():
				stock_code = row['code']
				current_name = current_data[stock_code].name
				stock_name = get_security_info(stock_code).display_name
				cmc = row['circulating_market_cap']
				mc = row['market_cap']
				zcl = row['inc_net_profit_to_shareholders_year_on_year']
				log.info('✅股票: %s/%s(%s), 流通市值: %.2f万元, 总市值: %.2f万元,净利润增长率: %.2f%%' % (
					stock_name, current_name, stock_code, cmc, mc, zcl))

	def info_position(self):
		"""打印当前持仓信息"""
		positions = self.context.portfolio.positions
		own_positions = {s: p for s, p in positions.items() if s in g.positions[self.index]}
		if len(own_positions) > 0:
			strategy_value = sum(p.value for p in own_positions.values())
			log.info('******************当日(%s) [%s]持仓市值: %.2f元*******************' % (
				self.context.current_dt, self.display_name, strategy_value))
			sorted_pos = dict(sorted(own_positions.items(), key=lambda x: x[0]))
			for stock, pos in sorted_pos.items():
				stock_name = get_security_info(stock).display_name
				price = pos.value / pos.total_amount if pos.total_amount > 0 else 0
				avg_cost = positions[stock].avg_cost
				ratio = (price / avg_cost - 1) * 100 if avg_cost > 0 else 0
				diff_price = price - avg_cost
				cangwei = pos.value / self.context.portfolio.total_value * 100
				log.info('✅持仓: %s(%s), 占比 %.2f%%, 涨跌幅: %.2f%% (%.2f), 数量: %d, 市值: %.2f元' % (
					stock_name, stock, cangwei, ratio, diff_price * pos.total_amount,
					pos.total_amount, pos.value))
			strategy_budget = self.context.portfolio.total_value * g.portfolio_value_proportion[self.index]
			log.info('✅*****[%s]策略市值: %.2f/%.2f, 总资产 %.2f, 剩余可用金额 %.2f元*****\n\n' % (
				self.display_name, strategy_value, strategy_budget,
				self.context.portfolio.total_value, self.context.portfolio.available_cash))
		else:
			log.info('[%s] 当前空仓' % self.display_name)
