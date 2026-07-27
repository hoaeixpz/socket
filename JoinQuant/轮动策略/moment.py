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
	# set_slippage(PriceRelatedSlippage(0.002), type="stock")

	# 全局变量
	g.strategys = {}
	g.portfolio_value_proportion = [1]  # 测试版
	g.positions = {i: {} for i in range(len(g.portfolio_value_proportion))}  # 记录每个子策略的持仓股票

	# 子策略执行计划
	if g.portfolio_value_proportion[0] > 0:
		run_daily(etf_rotation_adjust, "11:00")
	# 每日剩余资金购买货币ETF
	run_daily(end_trade, "14:59")


def process_initialize(context):
	g.strategys = {
		name: cls(context, index=idx, name=name, display_name=display_name)
		for display_name, name, cls, idx in [
			("核心资产轮动策略", "etf_rotation_strategy", Etf_Rotation_Strategy, 0),
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
			"513100.XSHG",  # 纳指ETF
			"513520.XSHG",  # 日经ETF
			"513030.XSHG",  # 德国ETF
			# 商品
			"518880.XSHG",  # 黄金ETF
			"159980.XSHE",  # 有色ETF
			"159985.XSHE",  # 豆粕ETF
			"501018.XSHG",  # 南方原油
			# 债券
			"511090.XSHG",  # 30年国债ETF
			# 国内
			"513130.XSHG",  # 恒生科技
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

		log.info(f"--- 得分筛选(>0且<{max_score})结果 ---")
		if filtered_data.empty:
			log.info("  无符合条件的ETF → 选用银华日利(511880.XSHG)")
		else:
			for etf, row in filtered_data.iterrows():
				log.info(f"  ✓ {current_data[etf].name}({etf}): 得分={row['score']:.4f}")

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

		log.info(f"========== [{self.display_name}] 选股汇总 ==========")
		log.info(f"  短期动量选出: {current_data[etf1].name}({etf1})")
		log.info(f"  长期动量选出: {current_data[etf2].name}({etf2})")

		if etf1 != etf2:
			log.info(f"  两者不同 → 各配50%: [{current_data[etf1].name}, {current_data[etf2].name}]")
			return [etf1, etf2]
		else:
			log.info(f"  两者相同 → 全仓: [{current_data[etf1].name}]")
			return [etf1]

	# 调仓
	def adjust(self):
		targets = self.select()
		self._adjust({etf: round(1 / len(targets), 3) for etf in targets})
