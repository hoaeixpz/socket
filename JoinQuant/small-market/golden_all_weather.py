# 导入函数库
from jqdata import *
import pandas as pd
import math
import datetime

# 初始化函数，设定基准等等
def initialize(context):
	#初始化函数，设定策略参数、基准、费用等
	log.info('初始函数开始运行且全局只运行一次')
	# 设置基准收益率对比（沪深300指数）
	#set_benchmark('000300.XSHG')
	# 中证500
	set_benchmark('000905.XSHG')
	# 使用真实价格回测
	set_option('use_real_price', True)
	
	set_option('avoid_future_data', True)
	
	# 设置交易佣金和税费（聚宽默认设置，此处为显式优化）
	set_order_cost(OrderCost(open_tax=0, close_tax=0.001, 
							open_commission=0.0003, close_commission=0.0003, 
							close_today_commission=0, min_commission=5), type='stock')
	#set_order_cost(OrderCost(open_tax=0, close_tax=0, 
	#						open_commission=0, close_commission=0, 
	#					   close_today_commission=0, min_commission=0), type='stock')
	# 设置滑点（可根据需要调整）
	set_slippage(FixedSlippage(0.0003))
	
	log.set_level('order', 'warning')
	
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
	g.each_cash = context.portfolio.starting_cash / g.stock_num
	g.sell_done = False
	g.last_month = None
	g.run_stoploss = True
	g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
	g.stoploss_limit = 0.1  # 止损线
	g.stoploss_market = 0.05  # 市场趋势止损参数
	g.etf = '511880.XSHG'  # 空仓月份持有银华日利ETF
	#g.etf = '513500.XSHG'
	g.all_weather_list = ["518880.XSHG", "511010.XSHG", "513100.XSHG", "601288.XSHG"]
	#g.SIGNAL = "small"
	current_date = context.current_dt.date()
	
	# 每天执行调仓函数
	# 聚宽会自动将非交易日的触发顺延至下一个交易日
	run_daily(prepare_stock_list, time='9:05')
	run_daily(judge_date, time='9:00')
	run_daily(trade_etf, time='9:35')
	run_weekly(rebalance, g.weekday, time='10:00')
	run_daily(stop_loss, time='10:02') # 止损函数
	run_weekly(rebalance, g.weekday, time='10:10')
	
	run_daily(trade_afternoon, time='14:00', reference_security='399101.XSHE')
	#run_daily(create_signal_big_small_market, time='9:05')
	
	
	log.info('策略初始化完成：每月初调仓，持有市值最小的{}只股票'.format(g.stock_num))

def judge_date(context):
	current_date = context.current_dt.date()
	current_month = current_date.month
	if current_month == 1 or current_month == 4:
		if g.trade == True:
			log.info('✅========== 一月和四月份清仓，日期：%s ==========' % current_date)
		g.trade = False
	else:
		g.trade = True

def prepare_stock_list(context):
	#获取已持有列表
	g.hold_list= []
	g.limitup_stocks = []
	g.trade_day = False
	for position in list(context.portfolio.positions.values()):
		stock = position.security
		g.hold_list.append(stock)
	#获取昨日涨停列表
	if g.hold_list != []:
		df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
		df = df[df['close'] == df['high_limit']]
		g.yesterday_HL_list = list(df.code)
		if g.yesterday_HL_list != []:
			log.info("")
			log.info(f"************昨日({context.previous_date})涨停 **************")
			log.info(list(df.code))
			log.info("")
	else:
		g.yesterday_HL_list = []

	date_str = str(context.previous_date)
	if date_str > '2024-01-01':
		g.all_weather_list = ["518880.XSHG", "511090.XSHG", "513100.XSHG", "601288.XSHG"]

def collect_sell_buy_stocks(context):
	g.stocks_to_sell = []
	g.stocks_to_buy = []
	current_holdings = list(context.portfolio.positions.keys())
	for stock in current_holdings:
		if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
			g.stocks_to_sell.append(stock)
			
	for stock in g.selected_stocks:
		if (stock not in current_holdings) and (stock not in g.yesterday_HL_list):
			g.stocks_to_buy.append(stock)
			
def trade_etf(context):
	if g.trade is False:
		current_holdings = list(context.portfolio.positions.keys())
		date_str = str(context.previous_date)
		if date_str < '2014-01-01':
			if current_holdings != [g.etf]:
				log.info('买入ETF')
				g.selected_stocks = [g.etf]
				collect_sell_buy_stocks(context)
				sell_stocks(context)
				buy_stocks(context)
		else:
			all_weather = False
			for stock in current_holdings:
				if stock not in g.all_weather_list:
					log.info('使用全天候策略')
					all_weather = True
					break
			if all_weather:
				g.selected_stocks = g.all_weather_list.copy()
				collect_sell_buy_stocks(context)
				sell_stocks(context)
				exec_all_weather(context)
				
				
def exec_all_weather(context):
	df = get_price(
		g.all_weather_list,
		end_date=context.previous_date,
		frequency="daily",
		fields=["close"],
		count= 120,
		panel=False,
	)
	weights = {}
	
	for code, group in df.groupby('code'):
		group = group.sort_values('time')
		if group.shape[0] < 120:
			# 基础权重
			weight = 0
		else:
			group['daily_return'] = group['close'].pct_change() * 100
			sorted_group = group.sort_values(by='daily_return')
			ES = sorted_group['daily_return'].head(6).mean()
			weight = -1 / ES
			
		weights[code] = weight
	log.info(f'权重:{weights}')
	
	# 标准化weight
	total_weight = sum([w for w in weights.values()])
	
	fin_weights = {key: value/total_weight for key, value in weights.items()}
	#for key, value in weights.items():
	#	w = value / total_weight
	#	fin_weights[key] = w
		
	for stock, w in fin_weights.items():
		log.info(f'{stock} {get_security_info(stock).display_name} 权重{100*w:.2f}%')

	available_cash = context.portfolio.available_cash
	log.info('available_cash: ', available_cash)
	current_data = get_current_data()
	for stock in g.all_weather_list:
		stock_data = current_data[stock]
		current_price = stock_data.last_price
		if math.isnan(current_price):
			continue
		target_value = available_cash * fin_weights[stock]
		amount = int(target_value / current_price / 100) * 100
		if amount > 0:
			log.info('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
			log.info(f'{stock} {get_security_info(stock).display_name} 目标市值{target_value:.2f}, 买入{amount}股 * {current_price}元')
			#order_target_value(stock, target_value)
			order(stock, amount)
			g.refresh_hold = True

def rebalance(context):
	if g.trade is False:
		return
	g.trade_day = True
	#每月调仓函数：选股并调整持仓
	# 获取当前日期（回测运行的日期）
	# 获取当前日期是当月的第几个交易日
	
	current_date = context.current_dt.date()
	#log.info("current_date ", current_date)
	
	current_month = current_date.month
	current_time = context.current_dt.time()
	# 定义上午和下午的执行时间点
	morning_sell_time = datetime.time(10, 0)  # 上午开盘后
	afternoon_buy_time = datetime.time(10, 10) # 下午临近收盘
	# 获取当前月的所有交易日
	
	# 找到当前日期在当月是第几个交易日

	
	#if current_date.weekday() != g.weekday:  # 周二
	#	return
	log.info('✅========== 执行周度调仓，日期：%s ==========' % current_date)
	prev_date = current_date - datetime.timedelta(days=1)
	# 判断是否为每月第一个交易日（卖出日）
	if current_time == morning_sell_time:
		info_position(context)
		no_st_codes = get_normal_stocks(context, current_date)
		#g.stock_pool = filter_growth_from_list(no_st_codes, prev_date, -50)
		g.stock_pool = no_st_codes
		# 3. 获取市值数据（使用前一交易日数据，避免未来函数）
		g.selected_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
		
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
			sell_stocks(context)
			# 标记卖出已完成
			g.sell_done = True
			
			log_selection_details(g.selected_stocks, prev_date)
			
		else:
			log.info('未选到符合条件的股票，本日不调仓')

			

	# 判断是否为下午交易时间（买入日）
	elif current_time == afternoon_buy_time and g.sell_done:
		# 执行买入逻辑
		if len(g.stocks_to_buy):
			current_time = context.current_dt.time()
			log.info(f"✅今日({current_time})为买入时间，执行买入操作")
			log.info('✅+++++++++++++++++++++++++++++++++++++++++')
			log.info(f"✅需要买入股票 {len(g.stocks_to_buy)}只")
			for stock in g.stocks_to_buy:
				log.info(get_security_info(stock).display_name)
		
		calc_position(context)
		buy_stocks(context)
		# 重置卖出标记
		g.sell_done = False
		info_position(context)
	else:
		log.info(f"今日({current_date})非调仓日，不执行操作")
	
	#log.info(f"在 {current_date} 符合条件的股票数量: {len(filtered_stocks)}")

def calc_position(context):
	total_value = context.portfolio.total_value
	current_holdings = list(context.portfolio.positions.keys())
	holding_num = len(current_holdings) + len(g.stocks_to_buy)
	'''
	if holding_num != g.stock_num:
		fail_sell_stock_num = len(g.stocks_fail_sell) + len(g.yesterday_HL_list)
		log.info(f'⭕ ⭕  有{fail_sell_stock_num}只股票没能卖出，调整买入计划')
		log.info(f'等权买入股票')
		available_cash = context.portfolio.available_cash
		for stock in g.stocks_to_buy:
			g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / total_value
			log.info(f'期望持仓: {get_security_info(stock).display_name}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')
		return
	'''
	if  holding_num != len(g.selected_stocks):
		log.info(f'⭕ ⭕ 股票数量异常，期望最终持仓{holding_num}只，实际选中{len(g.selected_stocks)}只')
		
	positions = context.portfolio.positions
	fail_pos = 0
	for stock in g.stocks_fail_sell:
		fp = positions[stock].value / total_value
		fail_pos += fp
		log.info(f'停牌股 {get_security_info(stock).display_name} 占仓位比重为 {fp*100:.2f}%')
	HL_count = 0
	for stock in g.yesterday_HL_list:
		if stock in current_holdings:
			fp = positions[stock].value / total_value
			fail_pos += fp
			HL_count += 1
			log.info(f'涨停股 {get_security_info(stock).display_name} 占仓位比重为 {fp*100:.2f}%')
				
	g.excepted_position = {}
	if holding_num - len(g.stocks_fail_sell) - HL_count <= 1:
		log.info(f'涨停股数量 {HL_count}, 异常股票数量{len(g.stocks_fail_sell)}, 可调整股票数量: 0。 无需调整')
		return
	p = (1 - fail_pos) / (holding_num - len(g.stocks_fail_sell) - HL_count)
	
	#计算买入之后期望每只股票的持仓占比
	#'''
	for i in range(len(g.selected_stocks)):
		stock = g.selected_stocks[i]
		if stock in g.stocks_fail_sell or stock in g.yesterday_HL_list:
			continue
		g.excepted_position[stock] = p + ((holding_num - 1) / 2 - i) * g.position_step
		
	'''
	need_stocks = []
	for i in range(len(g.selected_stocks)):
		stock = g.selected_stocks[i]
		if stock in g.stocks_fail_sell or stock in g.yesterday_HL_list:
			continue
		need_stocks.append(stock)
	weights = calc_ES_weights(context, need_stocks)
	for s, w in weights.items():
		g.excepted_position[s] = (1 - fail_pos) * w
	'''	
		
	for stock, pos in g.excepted_position.items():
		stock_name = get_security_info(stock).display_name
		log.info(' 期望持仓: %s(%s), 占比 %.2f%%' % (stock_name, stock, pos * 100))
		
	current_data = get_current_data()
	position_dict = {} #记录实际仓位比重
	position_sum = 0
	#计算已有持仓的股票占比
	for stock, pos in positions.items():
		stock_data = current_data[stock]
		position_sum += pos.value
		position_dict[stock] = [pos.value / total_value, stock_data.last_price]
	
	#计算待买入的股票的持仓占比
	for stock in g.stocks_to_buy:
		stock_name = get_security_info(stock).display_name
		target_value = total_value * g.excepted_position[stock]
		stock_data = current_data[stock]
		current_price = stock_data.last_price
		if math.isnan(current_price):
			g.excepted_position.pop(stock)
			continue
		amount = int(target_value / current_price / 100) * 100
		need_cash = amount * current_price
		log.info(f'预计买入{stock_name}({stock})  {amount} 股 * {current_price:.2f},总计 {need_cash:.2f}')
		position_sum += need_cash
		position_dict[stock] = [need_cash / total_value, current_price]
		
	avai_cash = total_value - position_sum
	log.info(f'预计持仓 {position_sum} 剩余金额 {avai_cash:.2f}')
	if abs(avai_cash) > 5000 or avai_cash < 0:
		log.info(f'❌❌剩余资金过大 {total_value - position_sum}')
		cash = 0
		for stock, exce_pos in g.excepted_position.items():
			if stock in g.stocks_fail_sell:
				continue
			pos, stock_price = position_dict[stock]
			diff_pos = exce_pos - pos
			#if abs(diff_pos) > 0.04:
			if abs(diff_pos) * total_value > 5000 or abs(diff_pos) > 0.04:
				stock_name = get_security_info(stock).display_name
				log.info(f'{stock_name} 持仓与期望相差较大，持仓{pos*100:.2f}%,期望{exce_pos*100:.2f}%,金额相差{diff_pos*total_value:.2f}')
				if diff_pos > 0:
					g.stocks_to_buy.append(stock)
					cash -= diff_pos*total_value
				else:
					order_info= order_target_value(stock, exce_pos*total_value)
					if order_info != None and order_info.filled != 0:
						cash -= diff_pos*total_value
						log.info(f'调整{stock_name}市值，卖出{order_info.filled}股 * {order_info.price}')
						update_stock_price(stock, order_info.price, -order_info.filled)
						
		
		avai_cash += cash
		if cash != 0:
			log.info(f'重新分配之后资金为{avai_cash}')
		
		if avai_cash > 5000:
			log.info(f'重新分配之后资金仍有剩余，追加买入')
			pos_dict = {}
			for stock, exce_pos in g.excepted_position.items():
				if stock in g.stocks_fail_sell or stock in g.stocks_to_buy:
					continue
				pos, stock_price = position_dict[stock]
				diff_pos = exce_pos - pos
				if diff_pos > 0:
					pos_dict[stock] = diff_pos
					
			sorted_pos = list(sorted(pos_dict.items(), key=lambda x: x[1], reverse=True))
			#log.info(sorted_pos)
			for stock, diff_pos in sorted_pos:
				stock_name = get_security_info(stock).display_name
				cash = diff_pos*total_value
				avai_cash -= cash
				if avai_cash > 0:
					g.stocks_to_buy.append(stock)
					log.info(f'{stock_name} 持仓与期望相差{diff_pos*100:.2f}% {diff_pos*total_value:.2f}，补仓')
			
				
			'''
			each_cash = avai_cash / len(g.stocks_to_buy)
			for stock in g.stocks_to_buy:
				stock_name = get_security_info(stock).display_name
				stock_data = current_data[stock]
				current_price = stock_data.last_price
				amount = int(each_cash / current_price / 100) * 100
				need_cash = amount * current_price
				target_value = total_value * g.excepted_position[stock]
				g.excepted_position[stock] = (target_value + need_cash) / total_value
				log.info(f'调整{stock_name}买入数量,增加{amount}股')
			'''
		elif avai_cash < 0 and cash == 0 and len(g.stocks_to_buy) > 0:
			log.info(f'未重新分配资金，调整买入仓位比重')
			available_cash = context.portfolio.available_cash
			for stock in g.stocks_to_buy:
				g.excepted_position[stock] = available_cash / len(g.stocks_to_buy) / total_value
				log.info(f'期望持仓: {get_security_info(stock).display_name}({stock})，占比{g.excepted_position[stock] * 100:.2f}%')
			
			
	
	for stock, pos in position_dict.items():
		stock_name = get_security_info(stock).display_name
		log.info(f' 预估持仓: {stock_name}({stock}), 占比 {pos[0] * 100:.2f}% 单价 {pos[1]}')
		
	for stock, exce_pos in g.excepted_position.items():
		if stock in g.stocks_fail_sell:
			continue
		pos, stock_price = position_dict[stock]
		diff_value = (exce_pos - pos) * total_value
		
		stock_name = get_security_info(stock).display_name
		stock_data = current_data[stock]
		current_price = stock_data.last_price
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
				log.info(f'调整{stock_name}买入数量，期望买入{excepted_value:.2f},当前{current_value},相差{diff_value:.2f}')
				while True:
					new_value = current_value + current_price * num * 100
					diff_v = excepted_value - new_value
					log.info(f'单价{current_price}，新市值{new_value:.2f}，差值{diff_v:.2f}')
					if abs(round(diff_v,2)) <= abs(round(diff_value,2)):
						diff_value = diff_v
						num += 1
					else:
						num -= 1
						break
				if num > 0:
					g.excepted_position[stock] = (current_value + current_price * num * 100) / total_value
					log.info(f'调整买入数量，追加{num}手,仓位占比调整为{g.excepted_position[stock] * 100:.2f}%')
					
		'''
		amount = int(diff_value / current_price / 100) * 100
		if amount > 0:
			if stock not in g.stocks_to_buy:
				g.stocks_to_buy.append(stock)
			log.info(f'{stock_name}({stock}) 可以再买入{amount}')
		'''

def pop_stock_price(stock):
	return
	g.stock_prices.pop(stock)
	
def update_stock_price(stock, current_price, amount):
	return
	if g.stock_prices.get(stock) is None:
		g.stock_prices[stock] = [current_price * amount, amount]
	else:
		[sz,a] = g.stock_prices[stock]
		sz += current_price * amount
		a += amount
		g.stock_prices[stock] = [sz, a]

def trade_afternoon(context):
	check_limit_up(context)
	check_remain_amount(context)
	
def check_limit_up(context):
	now_time = context.current_dt
	if g.yesterday_HL_list != []:
		#对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
		for stock in g.yesterday_HL_list:
			current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
			close_price = current_data.iloc[0,1] / 1.1
			rise_ratio = (current_data.iloc[0,0] - close_price) / close_price * 100
			log.info(f'{now_time} {stock} {get_security_info(stock).display_name} 股价{current_data.iloc[0,0]} 涨幅{rise_ratio:.2f}%')
			if current_data.iloc[0,0] <	current_data.iloc[0,1]:
				log.info(f"{stock} {get_security_info(stock).display_name}涨停打开，卖出")
				order_info = order_target_value(stock, 0)
				if order_info != None and order_info.filled > 0:
					pop_stock_price(stock)
				g.reason_to_sell = 'limitup'
				g.limitup_stocks.append(stock)
			else:
				log.info(f"{stock} {get_security_info(stock).display_name}涨停，继续持有")

#如果昨天有股票卖出或者买入失败，剩余的金额今天买入
def check_remain_amount(context):
	if g.reason_to_sell is 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
		g.hold_list = list(context.portfolio.positions.keys())
		now_time = context.current_dt
		flag = True
		if len(g.hold_list) < g.stock_num or flag:
			log.info(f'现有持仓:')
			for stock_code in g.hold_list:
				stock_name = get_security_info(stock_code).display_name
				log.info(f'  {stock_name} {stock_code}')
			log.info('涨停卖出')
			for stock_code in g.limitup_stocks:
				stock_name = get_security_info(stock_code).display_name
				log.info(f'  {stock_name} {stock_code}')
				
			# 计算需要买入的股票数量
			current_date = context.current_dt.date()
			prev_date = current_date - datetime.timedelta(days=1)
			g.selected_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
			for stock_code in g.limitup_stocks:
				if stock_code in g.selected_stocks:
					g.selected_stocks.remove(stock_code)
			
			current_holdings = list(context.portfolio.positions.keys())
			if len(current_holdings) > 3:
				g.selected_stocks = current_holdings
				
			collect_sell_buy_stocks(context)
			if len(g.stocks_to_buy) > 0:
				log.info(f"需要买入股票 {len(g.stocks_to_buy)}只")
				for stock in g.stocks_to_buy:
					log.info("待买入 ", get_security_info(stock).display_name)
				
			#num_stocks_to_buy = min(len(g.limitup_stocks), g.stock_num - len(g.hold_list))
			#num_stocks_to_buy = g.stock_num - len(g.hold_list)
			#g.stocks_to_buy = [stock for stock in g.selected_stocks if stock not in g.hold_list and stock not in g.limitup_stocks][:num_stocks_to_buy]
			#sell_stocks(context)
			log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。买入'+ str(g.stocks_to_buy))
			info_position(context)
			calc_position(context)
			buy_stocks(context)
			#info_position(context)
			g.refresh_hold = True
		g.reason_to_sell = ''
	elif g.reason_to_sell is 'stoploss':
		log.info('止盈止损后，有余额可用'+str(round((context.portfolio.cash),2))+'元。买入'+ str(g.etf))
		g.stocks_to_buy = [g.etf]
		buy_stocks(context)
		g.reason_to_sell = ''
		g.refresh_hold = True

#止盈止损
def stop_loss(context):
	show_info = False
	if g.run_stoploss:
		current_positions = context.portfolio.positions

		if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
			for stock in current_positions.keys():
				price = current_positions[stock].price
				avg_cost = current_positions[stock].avg_cost
				# 个股盈利止盈
				if price >= avg_cost * 2:
					order_target_value(stock, 0)
					pop_stock_price(stock)
					log.debug("⭕ 收益100%止盈,卖出{}".format(stock))
				# 个股止损
				elif price < avg_cost * (1 - g.stoploss_limit):
					order_info = order_target_value(stock, 0)
					log.debug(f"⭕ 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
					if order_info != None and order_info.filled > 0:
						log.debug(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')
						pop_stock_price(stock)
						show_info = True
					g.reason_to_sell = 'stoploss'
					if stock in g.selected_stocks:
						g.selected_stocks.remove(stock)

		if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
			stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close','open'], count=1, panel=False)
			#log.info(stock_df)
			#pre_stock_df = get_price(security='399101.XSHE', end_date=context.previous_date - datetime.timedelta(days=1), frequency='daily', fields=['close'], count=1, panel=False)
			#down_ratio = abs(stock_df.close[0] / pre_stock_df.close[0] - 1)
			#log.info("⭕ 大盘降幅{:.2%}".format(stock_df.close[0] / pre_stock_df.close[0] - 1))
			down_ratio = (stock_df['close'] / stock_df['open'] - 1).mean()
			log.debug("大盘降幅{:.2%}".format(down_ratio))
			# 市场大跌止损
			if abs(down_ratio) >= g.stoploss_market:
				g.reason_to_sell = 'stoploss'
				g.refresh_hold = True
				if down_ratio < 0:
					log.debug("⭕ 大盘惨跌,平均降幅{:.2%}".format(down_ratio))
					for stock in current_positions.keys():
						if stock == g.etf:
							continue
						if stock in g.all_weather_list:
							continue
						log.debug(f'⭕ 清仓{stock} {get_security_info(stock).display_name}')
						order_info = order_target_value(stock, 0)
						if order_info != None and order_info.filled > 0:
							log.debug(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')
							pop_stock_price(stock)
							show_info = True
						if stock in g.selected_stocks:
							g.selected_stocks.remove(stock)
				else:
					log.debug("⭕ 大盘大涨,平均涨幅{:.2%}".format(down_ratio))
					for stock in current_positions.keys():
						if stock == g.etf:
							continue
						if stock in g.all_weather_list:
							continue
						if stock in g.yesterday_HL_list:
							continue
						log.debug(f'⭕ 清仓{stock} {get_security_info(stock).display_name}')
						order_info = order_target_value(stock, 0)
						if order_info != None and order_info.filled > 0:
							log.debug(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')
							pop_stock_price(stock)
							show_info = True
						if stock in g.selected_stocks:
							g.selected_stocks.remove(stock)
	
	if show_info == True:
		info_position(context)

def balance_position(context):
	positions = context.portfolio.positions
	max_stock = None
	min_stock = None
	max_ratio = None
	min_ratio = None
	for stock, pos in positions.items():
		r = pos.value / context.portfolio.total_value * 100
		if min_ratio is None or r < min_ratio:
			min_stock = stock
			min_ratio = r
		if max_ratio is None or r > max_ratio:
			max_stock = stock
			max_ratio = r
					
	if max_ratio - min_ratio > 14:
		log.info(f'\n===================最大股票仓位比最小仓位高出 {max_ratio - min_ratio} 个点，调整仓位====================')
		stock_name = get_security_info(min_stock).display_name
		log.info('最小占比  持仓: %s(%s),  %.2f%%' % (stock_name, min_stock, min_ratio))
		stock_name = get_security_info(max_stock).display_name
		log.info('最大占比  持仓: %s(%s),  %.2f%%' % (stock_name, max_stock, max_ratio))
		
		balance_value = context.portfolio.total_value / 200 * (max_ratio - min_ratio)
		log.info(f'卖出 {get_security_info(max_stock).display_name} {balance_value}，买入{get_security_info(min_stock).display_name} {balance_value}')
		order_value(max_stock, -balance_value)
		order_value(min_stock,  balance_value)

def get_small_cap_stocks(stock_list, query_date, n=5):
	#获取市值最小的n只股票（修正版：全局排序）
	# 用于存储所有查询到的市值数据
	all_data_frames = []
	batch_size = 30
	
	for i in range(0, len(stock_list), batch_size):
		batch_stocks = stock_list[i:i+batch_size]
		
		try:
			q = query(
				valuation.code,
				#valuation.circulating_market_cap
				valuation.market_cap
			).filter(
				valuation.code.in_(batch_stocks)
			)
			# 查询当前批次的数据
			df_batch = get_fundamentals(q, date=query_date.strftime('%Y-%m-%d'))
			
			if df_batch is not None and len(df_batch) > 0:
				# 关键：将批次结果暂存起来，不在这里排序
				all_data_frames.append(df_batch)
				
		except Exception as e:
			log.error('查询市值数据时出错（批次 %d）: %s' % (i//batch_size + 1, str(e)))
			continue
	
	# 所有批次查询完成后，检查是否获取到数据
	if not all_data_frames:
		log.warn("未获取到任何股票的市值数据")
		return []
	
	# 关键步骤：合并所有批次的数据
	df_all = pd.concat(all_data_frames, ignore_index=True)
	
	# 关键步骤：进行全局排序
	#df_sorted = df_all.sort_values('circulating_market_cap', ascending=True)
	df_sorted = df_all.sort_values('market_cap', ascending=True)
	if n > 30:
		print(f"get_small_cap_stocks   {query_date}	head {n}")
		rank = 0
		for idx, row in df_sorted.head(10).iterrows():
			stock_name = get_security_info(row['code']).display_name
			# 市值通常很大，除以10000显示为“万元”，更易读
			#cap_in_10k = row['circulating_market_cap']
			cap_in_10k = row['market_cap']
			rank = rank + 1
			marker = '  <== 选中' if rank <= n else ''
			log.info(f'	第{rank:>2}名: {stock_name}({row["code"]}), 流通市值: {cap_in_10k:.2f} 亿元{marker}')
	
	# 取全局最小的N只股票
	selected_stocks = df_sorted['code'].head(n).tolist()
	
	flag = False
	for stock_code in selected_stocks:
		if stock_code not in g.selected_stocks:
			flag = True
			break
			
	if flag:
		print(f"get_small_cap_stocks   {query_date}	head {n}")
		rank = 0
		for idx, row in df_sorted.head(10).iterrows():
			stock_name = get_security_info(row['code']).display_name
			# 市值通常很大，除以10000显示为“万元”，更易读
			#cap_in_10k = row['circulating_market_cap']
			cap_in_10k = row['market_cap']
			rank = rank + 1
			marker = '  <== 选中' if rank <= n else ''
			log.info(f'	第{rank:>2}名: {stock_name}({row["code"]}), 流通市值: {cap_in_10k:.2f} 亿元{marker}')
			
	
	return selected_stocks
	
def sell_stocks(context):
	# 执行卖出
	g.stocks_fail_sell = []
	for stock in g.stocks_to_sell:
		log.info('✅>>>>>>>>>>>>')
		log.info('✅卖出: %s' % get_security_info(stock).display_name)
		order_info = order_target_value(stock, 0)
		if order_info != None and order_info.filled > 0:
			log.info(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')
			pop_stock_price(stock)
		else:
			g.stocks_fail_sell.append(stock)
	
def buy_stocks(context):
	if len(g.stocks_to_buy) > 0:
		available_cash = context.portfolio.available_cash
		position_value = context.portfolio.positions_value
		total_value = context.portfolio.total_value
		g.each_cash = available_cash / len(g.stocks_to_buy)
		#if g.stocks_to_buy != [g.etf]:
		#	g.each_cash = min(g.each_cash, total_value * 1.5 / g.stock_num)
		log.info("====调整每股额度====\n当前可用资金 ", available_cash, "\n持仓市值 ", 
		position_value, "\n总资产: ", total_value, "\n每股额度 ", g.each_cash)
		# 计算每只股票的目标市值（等权重）
		# 获取当前总资产
		current_data = get_current_data()
		
		target_value_per_stock = g.each_cash
		#buy_num  = len(g.stocks_to_buy)
		for stock in g.stocks_to_buy:
			stock_data = current_data[stock]
			current_price = stock_data.last_price
			if math.isnan(current_price):
				continue
			
			if stock == g.etf:
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				order(stock, amount)
				log.info(f'买入: {get_security_info(stock).display_name}, {stock} \n目标价值:{target_value_per_stock:.2f}'
						 f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
				update_stock_price(stock, current_price, amount)
			else:
				if g.excepted_position.get(stock) is not None:
					target_value_per_stock = g.excepted_position[stock] * total_value
				order_info = order_target_value(stock, target_value_per_stock)
				raw_amount = target_value_per_stock / current_price
				amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
				log.info(f'委托买入: {get_security_info(stock).display_name}, {stock} \n目标价值:{target_value_per_stock:.2f}'
					f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
				if order_info != None and order_info.filled > 0:
					raw_amount = target_value_per_stock / current_price
					amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
					log.info(f'实际买入{order_info.filled}股，每股{order_info.price}元，合计:{order_info.filled * order_info.price:.2f}')
					update_stock_price(stock, order_info.price, order_info.filled)
				else:
					log.info(f'股票 {stock} 买入失败，跳过')
			'''
			stock_data = current_data[stock]
			# 获取当前有效价格（优先使用现价）
			current_price = stock_data.last_price
			if current_price is None or current_price <= 0:
				current_price = stock_data.open_price
			
			if current_price is None or current_price <= 0:
				current_price = stock_data.pre_close
				
			raw_amount = target_value_per_stock / current_price
			amount = int(raw_amount / 105) * 100  # 向下取整到100股的倍数
			
			if amount <= 0:
				log.info(f'股票 {stock} 目标市值 {target_value_per_stock:.2f} 对应股数不足1手，跳过')
			else:
				log.info(f'买入: {get_security_info(stock).display_name}, {stock} \n股价: {current_price:.2f} \n股数 :{amount}\n合计:{amount * current_price:.2f}')
				order(stock, amount)
			'''

def log_selection_details(selected_stocks, query_date):
	#记录选股详情（可选，用于调试和分析）
	if len(selected_stocks) == 0:
		return
	
	if len(g.stocks_to_buy) == 0 and len(g.stocks_to_sell) == 0:
		return
	
	# 获取选中股票的详细信息
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
			mc =  row['market_cap']
			zcl = row['inc_net_profit_to_shareholders_year_on_year']
			log.info(f'✅股票: {stock_name}/{current_name}({stock_code}), 流通市值: {cmc:.2f}万元, 总市值: {mc:.2f}万元,净利润增长率: {zcl:.2f}%')
			
	#st_code_list = list(g.st_code)
	#log.info(st_code_list)
	#log.info(f"Total {len(st_code_list)}")

def info_position(context):
	positions = context.portfolio.positions
	
	if len(positions) > 0:
		log.info(f'******************当日({context.current_dt})持仓市值: %.2f元*******************' % context.portfolio.positions_value)
		sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in sorted_pos.items():
			stock_name = get_security_info(stock).display_name
			price = pos.value / pos.total_amount
			#ratio = (price / (g.stock_prices[stock][0]/g.stock_prices[stock][1]) - 1) * 100
			#diff_price = price - g.stock_prices[stock][0]/g.stock_prices[stock][1]
			ratio = 0
			diff_price = 0
			log.info('✅持仓: %s(%s), 占比 %.2f%%, 涨跌幅: %.2f%% (%.2f), 数量: %d, 市值: %.2f元' % 
					(stock_name, stock, pos.value / context.portfolio.total_value * 100, ratio, diff_price*pos.total_amount, pos.total_amount, pos.value))
		log.info(f'✅*******************总资产 %.2f  剩余可用金额 %.2f元*******************\n\n' % (context.portfolio.total_value, context.portfolio.available_cash))

# 可选：每日盘后记录函数（非必需）
def after_trading_end(context):
	current_date = context.current_dt.date()
	if not g.trade_day and g.refresh_hold == False:
		return
	g.refresh_hold = False
	#每日收盘后运行，记录当日持仓情况
	# 获取当前持仓
	positions = context.portfolio.positions
	
	if len(positions) > 0:
		log.info(f'✅*******************当日(周{current_date.weekday()+1})持仓市值: %.2f元*******************' % context.portfolio.positions_value)
		sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
		for stock, pos in sorted_pos.items():
			stock_name = get_security_info(stock).display_name
			price = pos.value / pos.total_amount
			#ratio = (price / (g.stock_prices[stock][0]/g.stock_prices[stock][1]) - 1) * 100
			#diff_price = price - g.stock_prices[stock][0]/g.stock_prices[stock][1]
			ratio = 0
			diff_price = 0
			log.info('✅持仓: %s(%s), 占比 %.2f%%, 涨跌幅: %.2f%% (%.2f), 数量: %d, 市值: %.2f元' % 
					(stock_name, stock, pos.value / context.portfolio.total_value * 100, ratio, diff_price*pos.total_amount, pos.total_amount, pos.value))
			#g.stock_prices[stock] = [pos.value, pos.total_amount]
		log.info(f'✅*******************总资产 %.2f  剩余可用金额 %.2f元*******************\n\n' % (context.portfolio.total_value, context.portfolio.available_cash))

#"""
	
	


def filter_chuangye_beijiao_codes(all_stocks):
	"""
	过滤掉创业板、科创板、北交所、三板股票
	"""
	
	# 过滤条件
	filtered_stocks = []
	for stock in all_stocks:
		# 方法1：通过股票代码前缀过滤
		if stock.startswith('30') or stock.startswith('688') or stock.startswith('8') or stock.startswith('4'):
			#filtered_stocks.append(stock)
			continue
		
		#if "002260" in stock or "000835" in stock or "600091" in stock or "600890" in stock or "603157" in stock or "603996" in stock:
		#	continue
			
		filtered_stocks.append(stock)
	
	return filtered_stocks
'''
def get_stock_list(context, target_date):
	final_list = []
	MKT_index = '399101.XSHE'
	initial_list = filter_stocks(context, get_index_stocks(MKT_index), target_date)
	q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(initial_list),valuation.market_cap.between(5,300)).order_by(valuation.market_cap.asc())
	df_fun = get_fundamentals(q)
	df_fun = df_fun[:g.stock_num*3]
	final_list  = list(df_fun.code)
	return final_list
'''
def get_normal_stocks(context, target_date):
	"""
	获取指定日期正常交易的股票列表（过滤退市、ST、停牌等）
	
	参数：
	target_date: 目标日期，datetime.date对象
	
	返回：
	list: 正常交易股票的代码列表
	"""
	
	# 1. 获取指定日期所有未退市的股票
	#all_stocks = get_all_securities(types=['stock'], date=target_date).index.tolist()
	MKT_index = '399101.XSHE'
	#MKT_index = '000852.XSHG'
	all_stocks = get_index_stocks(MKT_index, target_date)
	log.info(f'在 {target_date}，{MKT_index} 共有 {len(all_stocks)} 只股票')
	
	all_stocks = filter_chuangye_beijiao_codes(all_stocks)
	
	log.info(f'去除科创版，北交所等，共有 {len(all_stocks)} 只股票')
	#for stock in all_stocks:
	#	log.info(stock)
	
	# 2. 过滤ST/*ST股票
	non_st_stocks = filter_st_stocks(all_stocks, target_date)
	
	#non_st_stocks = all_stocks
	log.info(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
	
	# 3. 过滤停牌股票
	trading_stocks = filter_paused_stocks(context, non_st_stocks, target_date)
	

	log.info(f'过滤停牌，涨跌停股票后，剩余 {len(trading_stocks)} 只')
	
	
	# 4. 过滤新上市股票（上市不足30天）
	mature_stocks = filter_new_stock(context, trading_stocks, min_days=180)
	log.info(f'过滤上市不足30天股票后，剩余 {len(mature_stocks)} 只')
	
	return mature_stocks
	
	# 5. 过滤无交易数据或异常价格的股票
	final_stocks = filter_abnormal_stocks(mature_stocks, target_date)
	log.info(f'过滤异常股票后，最终剩余 {len(final_stocks)} 只正常交易股票')
	
	return final_stocks

def filter_st_stocks(stock_list, target_date):
	"""
	过滤ST/*ST股票
	
	参数：
	stock_list: 股票代码列表
	target_date: 目标日期
	
	返回：
	list: 非ST股票列表
	"""
	non_st_list = []
	
	if len(stock_list) == 0:
		return non_st_list
	'''
	stock_list = []
	stock_list.append('000019.XSHE')
	stock_list.append('002629.XSHE')
	'''
	current_data = get_current_data()
	for stock in stock_list:
		if stock in g.st_code:
			continue
		if current_data[stock].is_st:
			#g.st_code.add(stock)
			#log.info(f'ST {stock} {current_data[stock].name}')
			continue
		non_st_list.append(stock)
			
	return non_st_list

def filter_paused_stocks(context, stock_list, target_date):
	"""
	过滤停牌股票
	
	参数：
	stock_list: 股票代码列表
	target_date: 目标日期
	
	返回：
	list: 正常交易股票列表
	"""
	trading_stocks = []
	
	if len(stock_list) == 0:
		return trading_stocks
		
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	
	current_data = get_current_data()
	for stock in stock_list:
		if current_data[stock].paused:
			continue
		if not (stock in context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit):  # 涨停
			continue
		if not (stock in context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit):  # 跌停
			continue
		trading_stocks.append(stock)
	
	return trading_stocks

def filter_new_stock(context, stock_list, min_days):
	yesterday = context.previous_date
	return [stock for stock in stock_list if
			not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=min_days)]

def filter_new_stocks(stock_list, target_date, min_days=30):
	"""
	过滤新上市股票
	
	参数：
	stock_list: 股票代码列表
	target_date: 目标日期
	min_days: 最小上市天数
	
	返回：
	list: 上市超过min_days天的股票列表
	"""
	mature_stocks = []
	
	for stock in stock_list:
		try:
			# 获取股票上市日期
			info = get_security_info(stock)
			if info is None:
				continue
			
			list_date = info.start_date
			
			# 计算上市天数
			days_listed = (target_date - list_date.date()).days
			
			if days_listed >= min_days:
				mature_stocks.append(stock)
			#else:
			#	log.debug(f'股票 {stock} 上市仅 {days_listed} 天，小于 {min_days} 天，跳过')
				
		except Exception as e:
			log.error(f'获取股票 {stock} 上市日期时出错: {e}')
			# 出错时默认通过，保守策略
			mature_stocks.append(stock)
	
	return mature_stocks

def filter_abnormal_stocks(stock_list, target_date):
	"""
	过滤异常价格股票
	
	参数：
	stock_list: 股票代码列表
	target_date: 目标日期
	
	返回：
	list: 正常价格股票列表
	"""
	normal_stocks = []
	
	if len(stock_list) == 0:
		return normal_stocks
	
	# 获取前一天的收盘价
	prev_date = target_date - datetime.timedelta(days=1)
	
	try:
		price_data = get_price(
			stock_list, 
			end_date=prev_date, 
			count=5,  # 获取最近5天，检查是否有连续交易
			fields=['close', 'volume'],
			panel=False
		)
		
		# 按股票分组
		for stock in stock_list:
			stock_data = price_data[price_data['code'] == stock]
			
			if len(stock_data) == 0:
				log.debug(f'股票 {stock} 无价格数据，跳过')
				continue
			
			# 检查最近5天是否有交易
			has_trade = False
			for i in range(len(stock_data)):
				close_price = stock_data['close'].iloc[i]
				volume = stock_data['volume'].iloc[i]
				
				if (not pd.isna(close_price) and close_price > 0 and 
					not pd.isna(volume) and volume > 0):
					has_trade = True
					break
			
			if has_trade:
				normal_stocks.append(stock)
			else:
				log.debug(f'股票 {stock} 最近5天无有效交易，跳过')
				
	except Exception as e:
		log.error(f'批量检查价格异常时出错: {e}')
		# 出错时返回原始列表
		return stock_list
	
	return normal_stocks

def filter_growth_from_list(stock_list, target_date, growth_threshold = -5):
	"""
	从给定股票列表中筛选连续3年净利润增长率 > threshold的股票
	stock_list: 股票代码列表
	target_date: 查询日期
	growth_threshold: 增长率阈值，默认20%
	返回: 符合条件的股票代码列表
	"""
	if not stock_list:
		return []
	
	# 确定最近3个完整年度
	current_year = target_date.year
	years_needed = [str(current_year - i) for i in range(1, 4)]  # [2022, 2021, 2020]
	
	# 存储每年增长率的字典
	growth_by_year = {year: {} for year in years_needed}
	
	# 分批查询每年的数据
	batch_size = 100
	for year in years_needed:
		for i in range(0, len(stock_list), batch_size):
			batch = stock_list[i:i+batch_size]
			
			# 查询该年份的净利润增长率
			q = query(
				indicator.code,
				#indicator.inc_net_profit_year_on_year
				indicator.inc_net_profit_to_shareholders_year_on_year
			).filter(
				indicator.code.in_(batch)
			)
			
			df = get_fundamentals(q, statDate=year)
			if df is not None and not df.empty:
				for _, row in df.iterrows():
					growth_by_year[year][row['code']] = row['inc_net_profit_to_shareholders_year_on_year']
					#if "000632" in row['code']:
					#print(year,"  ",row['code'])
					#print(row['inc_net_profit_to_shareholders_year_on_year'])
	
	# 找出在3年数据中都存在的股票
	common_stocks = set(growth_by_year[years_needed[0]].keys())
	for year in years_needed[1:]:
		common_stocks.intersection_update(growth_by_year[year].keys())
	
	# 筛选连续3年增长率都大于阈值的股票
	result = []
	for stock in common_stocks:
		if len(years_needed) != 3:
			continue
		flag = True
		for year in years_needed:
			if growth_by_year[year][stock] < growth_threshold:
				flag = False
				break
		if flag:
			result.append(stock)
	
	return result
