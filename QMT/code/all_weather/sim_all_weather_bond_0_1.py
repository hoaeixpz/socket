# -*- coding: utf-8 -*-
"""
全天候 ETF + 债券策略 — 模拟版（无需 QMT 交易连接）
母版：C:\socket\JoinQuant\全天候策略\all_weather_bond.py

用法：修改下方 ACTUAL_POSITIONS 和 AVAILABLE_CASH，然后运行：
	  python sim_all_weather_bond_0_1.py

输出：目标权重、当前持仓 vs 目标、需要买入/卖出的股票和数量（含债券管理）。
"""
from xtquant import xtdata
import math
import unicodedata
from datetime import datetime, timedelta
import sys
import re

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

class Tee:
	"""将输出同时写入终端和日志文件"""
	def __init__(self, log_file_path):
		self.terminal = sys.__stdout__      # 保留原始控制台输出流
		self.log = open(log_file_path, 'a', encoding='utf-8')  # 追加模式

	def write(self, message):
		self.terminal.write(message)					# 打印到控制台
		clean_message = ansi_escape.sub('', message)	# 去除颜色代码
		self.log.write(clean_message)					# 写入日志文件
		self.log.flush()								# 实时写入磁盘

	def flush(self):
		try:
			#self.terminal.flush()
			self.log.flush()
		except ValueError:
			pass

	def close(self):
		self.log.close()
		
		
class G():
	pass
g = G() #创建空的类的实例 用来保存委托状态

# ======================== 手动输入你的实际持仓 ========================

ACTUAL_POSITIONS = {
	"511270.SH": 500,       # 十年地方债
	"600900.SH": 1300,      # 长江电力
	"511220.SH": 1800,      # 城投债ETF（由 buy_bond/sell_bond 管理，不参与权重计算）
	"518880.SH": 3300,      # 黄金ETF
	"601288.SH": 3600,      # 农业银行
	"513100.SH": 16900,     # 纳指ETF
	"159985.SZ": 10900,      # 豆粕ETF
}

AVAILABLE_CASH = 1.7        # 账户可用资金（元）

# ======================== 策略参数 ========================

# 参与权重计算的标的（不含城投债）
stocks = [
	"518880.SH",  # 黄金ETF
	"159985.SZ",  # 豆粕ETF
	"513100.SH",  # 纳指ETF
	"601288.SH",  # 农业银行
	"600900.SH",  # 长江电力
	"511270.SH",  # 十年地方债
]

base_days = 120
nazhi_weight = 0.03    # 纳指固定加成
golden_weight = 0.02   # 黄金固定加成
rebalance_tolerance = 0.06  # 偏离 6% 才交易
weights = {}

# 回撤管理
record_max = 219202
max_down_T = [1.1, 1.7, 2.4, 3.2]
last_level = 2          # 上次回撤等级（防止同一等级重复触发）
force_level = None
force_level = 2         # 不计算，直接设置level为force_level


# ======================== 数据获取 ========================

def get_stock_name(stock):
	detail = xtdata.get_instrument_detail(stock)
	if detail:
		return detail['InstrumentName']
	return stock


def get_last_price(stock):
	try:
		tick = xtdata.get_full_tick([stock])
		if stock in tick and tick[stock] and tick[stock]['lastPrice'] > 0:
			return tick[stock]['lastPrice']
	except Exception as e:
		print(f"get_last_price error: {stock} {e}")

	return None


# ======================== 债券买卖计算 ========================

def calc_bond_trades(target_value, prices, positions_value):
	"""计算债券（十年地方债 3/4 + 城投债 1/4）的买卖计划

	与母版 buy_bond/sell_bond 一致：
	- 511270 十年地方债 占债券总仓位的 3/4
	- 511220 城投债      占债券总仓位的 1/4
	"""
	sells = []
	buys = []

	pos_1_shares = ACTUAL_POSITIONS.get("511270.SH", 0)
	pos_2_shares = ACTUAL_POSITIONS.get("511220.SH", 0)
	p1 = prices.get("511270.SH", 0) or 0
	p2 = prices.get("511220.SH", 0) or 0
	pos_1_value = pos_1_shares * p1
	pos_2_value = pos_2_shares * p2
	current_bond_value = pos_1_value + pos_2_value

	diff_value = target_value - current_bond_value
	print(f"\n  【债券组合】目标 {target_value:,.0f}  当前 {current_bond_value:,.0f}  差值 {diff_value:+,.0f}")

	if diff_value > 0:
		# 需要买入债券
		# 十年地方债：补至 target * 3/4
		target_1 = target_value * 3 / 4
		need_1 = target_1 - pos_1_value
		amount_1 = int(need_1 / p1 / 100) * 100 if p1 > 0 else 0
		if amount_1 >= 100:
			buys.append(("511270.SH", amount_1, p1, f"十年地方债 目标{target_1:,.0f} 补仓"))

		# 城投债：补至 target * 1/4
		target_2 = target_value * 1 / 4
		need_2 = target_2 - pos_2_value
		amount_2 = int(need_2 / p2 / 100) * 100 if p2 > 0 else 0
		if amount_2 >= 100:
			buys.append(("511220.SH", amount_2, p2, f"城投债 目标{target_2:,.0f} 补仓"))

	elif diff_value < 0:
		# 需要卖出债券
		# 十年地方债：超出 target * 3/4 的部分卖出
		target_1 = target_value * 3 / 4
		excess_1 = pos_1_value - target_1
		amount_1 = int(excess_1 / p1 / 100) * 100 if p1 > 0 else 0
		if amount_1 >= 100:
			sells.append(("511270.SH", amount_1, p1, f"十年地方债 减至{target_1:,.0f}"))

		# 城投债：剩余差额
		remaining = -diff_value - amount_1 * p1
		amount_2 = int(remaining / p2 / 100) * 100 if p2 > 0 else 0
		if amount_2 >= 100:
			sells.append(("511220.SH", amount_2, p2, "城投债 补足差额"))

	return sells, buys


# ======================== 获取所有持仓价格 ========================

def cjk_len(s):
	"""计算字符串在终端中的显示宽度（全角字符算2，半角算1）"""
	width = 0
	for ch in s:
		w = unicodedata.east_asian_width(ch)
		if w in ('F', 'W'):   # Fullwidth / Wide
			width += 2
		else:
			width += 1
	return width


def cjk_ljust(s, width):
	"""按显示宽度左对齐"""
	return s + ' ' * max(0, width - cjk_len(s))


def cjk_rjust(s, width):
	"""按显示宽度右对齐"""
	return ' ' * max(0, width - cjk_len(s)) + s


# 表格列宽定义
COL_WIDTHS = {
	'code':   12,   # 代码
	'name':   20,   # 名称
	'price':   8,   # 股价
	'shares':  8,   # 持仓
	'cur_val': 10,  # 当前市值
	'tgt_val': 10,  # 目标市值
	'diff':    10,  # 差值
}


def make_row(code, name, price, shares, cur_val, tgt_val, diff, action):
	"""构建表格行（所有列 CJK 宽度对齐）"""
	cols = [
		cjk_ljust(code, COL_WIDTHS['code']),
		cjk_ljust(name, COL_WIDTHS['name']),
		cjk_rjust(price, COL_WIDTHS['price']),
		cjk_rjust(shares, COL_WIDTHS['shares']),
		cjk_rjust(cur_val, COL_WIDTHS['cur_val']),
		cjk_rjust(tgt_val, COL_WIDTHS['tgt_val']),
		cjk_rjust(diff, COL_WIDTHS['diff']),
	]
	return '  ' + ' '.join(cols) + '  ' + action


def make_header():
	"""构建表头"""
	return make_row('代码', '名称', '股价', '持仓', '当前市值', '目标市值', '差值', '操作')

# ======================== 权重计算（与母版完全一致） ========================

def calc_ES_weights():
	alpha = 0.05
	num = int(base_days * alpha)
	print(f"样本数: {num}（{base_days}天 × {alpha}）")

	for s in stocks:
		xtdata.download_history_data(s, period='1d', incrementally=True)

	query_date = datetime.now().strftime('%Y%m%d')
	price_data = xtdata.get_market_data_ex(['close'], stocks, period='1d',
										   start_time='', end_time=query_date,
										   count=base_days, dividend_type='front')

	raw = {}
	for code in stocks:
		df = price_data.get(code)
		if df is None or len(df) < base_days:
			raw[code] = 0
			print(f"{code} {get_stock_name(code)} 数据不足，权重=0")
		else:
			df['daily_return'] = df['close'].pct_change() * 100
			df = df.iloc[1:].dropna(subset=['daily_return'])
			srt = df['daily_return'].sort_values()
			ES = srt.head(num).mean()
			raw[code] = -1 / ES
			print(f"{code} {get_stock_name(code)}  ES={ES:.3f}  raw={raw[code]:.4f}")

	# 标准化 + 纳指/黄金加成（与母版一致）
	total = sum(raw.values())
	for code in stocks:
		w = raw[code] / total * (1 - nazhi_weight - golden_weight)
		if code == "513100.SH":
			w += nazhi_weight
		if code == "518880.SH":
			w += golden_weight
		weights[code] = w

	# 计算当前权重（基于实际持仓和最新价格）
	total_value = 0
	current_prices = {}
	for code in ACTUAL_POSITIONS:
		price = get_last_price(code)
		current_prices[code] = price
		if price:
			total_value += ACTUAL_POSITIONS.get(code, 0) * price
	total_asset = total_value + AVAILABLE_CASH

	print(f"\n{'='*60}")
	print(f"目标权重 vs 当前权重")
	print(f"{'='*60}")
	print(f" 总资产 {total_asset:.1f}")
	print(f"  {'代码':<14s} {'名称':<15s} {'持仓':<10s} {'市值':<10s}   {'目标权重':<12s} {'当前权重':<12s}")
	print(f"  {'-'*100}")
	actual_stocks = stocks.copy()
	actual_stocks.append("511220.SH")
	for code in actual_stocks:
		name = get_stock_name(code)
		target_wt = weights.get(code,0) * 100
		cur_shares = ACTUAL_POSITIONS.get(code, 0)
		cur_price = current_prices.get(code)
		cur_value = cur_shares * cur_price if cur_price else 0
		cur_wt = cur_value / total_asset * 100 if total_asset > 0 else 0
		print(f"  {code:<14s} {name:<15s} {cur_shares:<10.0f} {cur_value:<10.1f} {target_wt:>12.2f}% {cur_wt:>12.2f}%")
	print(f"{'现金':>70s}    {AVAILABLE_CASH/total_asset*100:7.2f}%")
	print()


def get_all_prices():
	"""获取所有标的的当前价格和市值"""
	prices = {}
	positions_value = {}
	total_value = 0

	all_held = set(stocks) | {"511220.SH"}
	for code in all_held:
		price = get_last_price(code)
		prices[code] = price
		shares = ACTUAL_POSITIONS.get(code, 0)
		value = shares * price if price else 0
		positions_value[code] = value
		total_value += value
	return prices, positions_value, total_value


# ======================== 回撤检测 & 权重重算 ========================

def detect_drawdown(total_asset):
	"""检测回撤等级，与母版 rebalance_drawdown 一致"""
	global record_max, last_level, drawdown_level

	if total_asset > record_max:
		record_max = total_asset
		# 创新高，重置所有回撤状态
		last_level = -1
		drawdown_level = 0
		return 0

	if record_max <= 0:
		return 0

	drawdown = (1 - total_asset / record_max) * 100
	new_level = 0
	if drawdown > max_down_T[3]:
		new_level = 4
	elif drawdown > max_down_T[2]:
		new_level = 3
	elif drawdown > max_down_T[1]:
		new_level = 2
	elif drawdown > max_down_T[0]:
		new_level = 1

	# 只有等级上升时才触发（母版逻辑：if new_level <= last_level: return）
	if new_level <= last_level:
		drawdown_level = new_level
		return 0  # 不触发

	last_level = new_level
	drawdown_level = new_level
	return new_level  # 触发！


def calc_drawdown_weights(prices, positions_value, total_asset, level):
	"""回撤触发后：先卖债券，再重算非债券权重

	与母版 rebalance_drawdown 完全一致：
	1. 卖出债券：保留 (1 - 1/(5-level)) 的债券
	2. 复用 calc_ES_weights 结果，去掉 511270 后重分配
	3. 非债券权重 = 原权重归一化 × (1 - bond_weight)
	"""
	print(f"\n{'='*60}")
	print(f">>> 回撤等级 {level} 触发！执行减仓 <<<")
	print(f"{'='*60}")

	# --- 步骤1：计算债券减仓 ---
	p1 = prices.get("511270.SH", 0) or 0
	p2 = prices.get("511220.SH", 0) or 0
	s1 = ACTUAL_POSITIONS.get("511270.SH", 0)
	s2 = ACTUAL_POSITIONS.get("511220.SH", 0)
	bond_value = s1 * p1 + s2 * p2
	keep_ratio = 1 - 1 / (5 - level)
	target_bond_value = bond_value * keep_ratio

	print(f"  当前债券市值: {bond_value:,.0f}（十年债 {s1*p1:,.0f} + 城投债 {s2*p2:,.0f}）")
	print(f"  保留比例: {keep_ratio*100:.0f}%，目标债券市值: {target_bond_value:,.0f}")

	# 打印债券卖出建议
	bond_sells, _ = calc_bond_trades(target_bond_value, prices, positions_value)
	for code, amount, price, reason in bond_sells:
		print(f"  [卖出] {code} {get_stock_name(code)}: {amount}股 × {price:.2f} = {amount*price:,.0f}元")

	# 假设卖出完成后的债券市值
	new_bond_value = target_bond_value
	bond_weight = new_bond_value / total_asset
	print(f"  卖出后债券占比: {bond_weight*100:.2f}%")

	# --- 步骤2：复用 calc_ES_weights 结果，去掉 511270 后重分配（与母版一致） ---
	print(f"\n  --- 重新分配非债券权重 ---")
	# 用已算好的常规权重，去掉 511270，归一化后 × (1 - bond_weight)
	stock_weights = {k: v for k, v in weights.items() if k != "511270.SH"}
	total_w = sum(stock_weights.values())

	new_weights = {}
	for code, w in stock_weights.items():
		new_weights[code] = w / total_w * (1 - bond_weight)
		print(f"    {code} {get_stock_name(code):12s}  {w*100:5.2f}% → {new_weights[code]*100:6.2f}%")

	# 债券总权重
	new_weights["511270.SH"] = bond_weight

	total_check = sum(new_weights.values())
	print(f"    债券组合（511270+511220 3:1）      {bond_weight*100:6.2f}%")
	print(f"    权重合计: {total_check*100:.2f}%")

	return new_weights

def calc_force_drawndown_weights(force_level):
	bond_weight = weights['511270.SH'] * (4 - force_level) / 4
	stock_weights = {k: v for k, v in weights.items() if k != "511270.SH"}
	total_w = sum(stock_weights.values())

	new_weights = {}
	for code, w in stock_weights.items():
		new_weights[code] = w / total_w * (1 - bond_weight)
		print(f"    {code} {get_stock_name(code):12s}  {w*100:5.2f}% → {new_weights[code]*100:6.2f}%")

	# 债券总权重
	new_weights["511270.SH"] = bond_weight
	total_check = sum(new_weights.values())
	print(f"    债券组合（511270+511220 3:1）      {bond_weight*100:6.2f}%")
	print(f"    权重合计: {total_check*100:.2f}%")

	return new_weights

# ======================== 打印持仓对比 & 交易清单 ========================

def print_position_table(prices, total_asset, use_weights):
	"""打印持仓对比表和交易清单"""
	# 表头
	header = make_header()
	print(f"\n{header}")
	print(f"  {'-'*cjk_len(header)}")

	bond_weights = use_weights.copy()
	if '511270.SH' in bond_weights:
		bond_weights['511270.SH'] = use_weights['511270.SH'] * 3 / 4.0
		bond_weights['511220.SH'] = use_weights['511270.SH'] * 1 / 4.0

	all_codes = list(bond_weights.keys())
	for code in all_codes:
		w = bond_weights.get(code, 0)
		price = prices.get(code)
		if price is None:
			continue
		current_shares = ACTUAL_POSITIONS.get(code, 0)
		current_value = current_shares * price

		target_val = total_asset * w
		diff = target_val - current_value
		if diff > 500 and (target_val == 0 or abs(diff) / target_val > rebalance_tolerance):
			action = f"⭕ 买入 {diff/price/100:.2f}手"
		elif diff < -500 and (target_val == 0 or abs(diff) / target_val > rebalance_tolerance):
			action = f"✅ 卖出 {-diff/price/100:.2f}手"
		else:
			action = "-"

		name = get_stock_name(code)
		print(make_row(code, name,
					   f"{price:.2f}",
					   str(current_shares),
					   f"{current_value:.0f}",
					   f"{total_asset*w:.0f}",
					   f"{total_asset*w - current_value:+.0f}",
					   action))

def print_trade_list(prices, total_asset, use_weights):
	"""打印具体买卖股数"""
	print(f"\n{'='*60}")
	print(f"【交易清单】")
	print(f"{'='*60}")

	has_trades = False

	# 非债券标的
	for code in [s for s in stocks if s != "511270.SH"]:
		w = use_weights.get(code, 0)
		price = prices.get(code)
		if price is None:
			continue
		current_value = ACTUAL_POSITIONS.get(code, 0) * price
		target_value = total_asset * w
		diff = target_value - current_value

		if diff > 500 and abs(diff) / target_value > rebalance_tolerance:
			amount = int(diff / price / 100) * 100
			if amount >= 100:
				print(f"  [买入] {code} {get_stock_name(code)}: \033[31m{amount}\033[0m股 × {price:.2f} = {amount*price:,.0f}元")
				has_trades = True
		elif diff < -500 and abs(diff) / target_value > rebalance_tolerance:
			amount = int(-diff / price / 100) * 100
			if amount >= 100:
				print(f"  [卖出] {code} {get_stock_name(code)}: \033[32m{amount}\033[0m股 × {price:.2f} = {amount*price:,.0f}元")
				has_trades = True

	# 债券交易
	bond_target = total_asset * use_weights.get("511270.SH", 0)
	bond_sells, bond_buys = calc_bond_trades(bond_target, prices, {})

	for code, amount, price, reason in bond_sells:
		print(f"  [卖出] {code} {get_stock_name(code)}: \033[32m{amount}\033[0m股 × {price:.2f} = {amount*price:,.0f}元 ({reason})")
		has_trades = True
	for code, amount, price, reason in bond_buys:
		print(f"  [买入] {code} {get_stock_name(code)}: \033[31m{amount}\033[0m股 × {price:.2f} = {amount*price:,.0f}元 ({reason})")
		has_trades = True

	if not has_trades:
		print(f"  无需调仓（偏离小于 {rebalance_tolerance*100:.0f}% 或金额不足500元）")


# ======================== 止盈检查 ========================

def take_profit_check(prices):
	stocks_no_bond = [s for s in stocks if s not in ("511270.SH", "511220.SH")]
	query_date = datetime.now().strftime('%Y%m%d')
	price_data = xtdata.get_market_data_ex(['close'], stocks_no_bond, period='1d',
										   start_time='', end_time=query_date, count=base_days, dividend_type='front')

	any_triggered = False
	for code in stocks_no_bond:
		shares = ACTUAL_POSITIONS.get(code, 0)
		if shares <= 0:
			continue
		df = price_data.get(code)
		if df is None or len(df) < base_days:
			continue
		df['daily_return'] = df['close'].pct_change() * 100
		df = df.iloc[1:].dropna(subset=['daily_return'])
		srt = df['daily_return'].sort_values()
		last_close = df['close'].iloc[-2]
		price = prices.get(code)
		#print(srt[-6:])
		if price is None:
			continue

		pct = (price - last_close) / last_close * 100
		last_3th = srt.iloc[-3]
		idx_30 = -31 if len(df) >= 31 else 0
		pct_30 = (price - df['close'].iloc[idx_30]) / df['close'].iloc[idx_30] * 100
		
		if pct >= last_3th:    
			if pct_30 > 10 and pct < 9.8:
				sell_amount = int((shares / 2) / 100) * 100
				print(f"  {code} {get_stock_name(code)}: 触发止盈!")
				print(f"    今日涨幅 {pct:.2f}% > 120天第3高 {last_3th:.2f}%, 30日涨幅 {pct_30:.2f}%")
				print(f"    ✅ 建议卖出 1/2 = {sell_amount}股")
				any_triggered = True
			else:
				print(f"  {code} {get_stock_name(code)}: 涨幅达标但未触发({pct_30:.1f}%/30d) < 10%")
				print(f"    今日涨幅 {pct:.2f}% > 120天第3高 {last_3th:.2f}%, 30日涨幅 {pct_30:.2f}%")
		else:
			print(f"  {code} {get_stock_name(code)}: 今日涨幅 {pct:.2f}% <= 阈值 {last_3th:.2f}% , 30日涨幅 {pct_30:.2f}%")

	if not any_triggered:
		print(f"  无触发止盈")


# ======================== 主流程 ========================

if __name__ == "__main__":
	log_name = datetime.now().strftime('%Y%m%d')
	tee = Tee(f"logfiles\\{log_name}_all_weather_bond.log")
	sys.stdout = tee

	print(f"{'='*60}")
	print(f"全天候 ETF + 债券策略 — 模拟计算")
	print(f"{'='*60}\n")

	# 1. 常规 ES 权重计算
	calc_ES_weights()

	# 2. 获取价格和总资产
	prices, positions_value, total_current_value = get_all_prices()
	total_asset = total_current_value + AVAILABLE_CASH

	print(f"{'='*60}")
	print(f"当前资产概览")
	print(f"{'='*60}")
	print(f"  持仓市值: {total_current_value:,.2f}")
	print(f"  可用资金: {AVAILABLE_CASH:,.2f}")
	print(f"  总资产:   {total_asset:,.2f}")

	# 3. 回撤检测
	print(f"\n{'='*60}")
	print(f"【回撤检测】")
	print(f"{'='*60}")
	level = detect_drawdown(total_asset)
	drawdown_pct = (1 - total_asset / record_max) * 100 if record_max > 0 else 0
	print(f"  历史峰值: {record_max:,.0f}  当前: {total_asset:,.0f}  回撤: {drawdown_pct:.2f}%  等级: {drawdown_level}")

	# 4. 根据回撤等级选择权重
	if level > 0:
		# 回撤触发：按母版逻辑卖债券 + 重新分配非债券权重
		use_weights = calc_drawdown_weights(prices, positions_value, total_asset, level)
	else:
		if force_level:
			print(f"强制设置回撤等级为 {force_level} ， 以该等级设置权重")
			use_weights = calc_force_drawndown_weights(force_level)
		elif last_level:
			print(f"  回撤等级 {drawdown_level}，但未跨级（last_level={last_level}），沿用之前的权重")
			use_weights = calc_force_drawndown_weights(last_level)
		else:
			# 无回撤触发：使用常规权重
			use_weights = weights

	# 5. 打印持仓对比和交易清单
	print(f"\n{'='*60}")
	print(f"当前持仓 vs 目标")
	print(f"{'='*60}")
	print_position_table(prices, total_asset, use_weights)
	print_trade_list(prices, total_asset, use_weights)

	# 6. 止盈检查
	print(f"\n{'='*60}")
	print(f"【止盈检查】（排除债券）")
	print(f"{'='*60}")
	take_profit_check(prices)

	print(f"\n{'='*60}")
	print(f"提示：修改文件顶部 ACTUAL_POSITIONS 和 AVAILABLE_CASH 后重新运行即可")
	print(f"{'='*60}")
