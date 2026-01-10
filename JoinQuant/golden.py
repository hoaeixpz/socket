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
    
    # 设置交易佣金和税费（聚宽默认设置，此处为显式优化）
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, 
                            open_commission=0.0003, close_commission=0.0003, 
                            close_today_commission=0, min_commission=5), type='stock')
    # 设置滑点（可根据需要调整）
    set_slippage(FixedSlippage(0.0003))
    
    log.set_level('order', 'warning')
    
    # 设置全局变量
    g.stock_pool = []
    g.selected_stocks = []
    g.stocks_to_buy = []
    g.stocks_to_sell = []
    g.hold_list = []
    g.limitup_stocks = []
    g.yesterday_HL_list = []  #昨日涨停股票
    g.st_code = set()
    g.reason_to_sell = ''
    g.refresh_hold = False
    g.trade = True
    g.stock_num = 9  # 每月持有的股票数量 5
    g.weekday = 1  #每周二调仓
    g.each_cash = context.portfolio.starting_cash / g.stock_num
    #g.frozen_cash = 0  #大跌清仓后，将卖出所得的钱冻结，只能用于购买ETF
    g.sell_done = False
    g.last_month = None
    g.run_stoploss = True
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.1  # 止损线
    g.stoploss_market = 0.05  # 市场趋势止损参数
    g.etf = '511880.XSHG'  # 空仓月份持有银华日利ETF
    #g.etf = '513500.XSHG'
    #g.SIGNAL = "small"
    current_date = context.current_dt.date()
    
    # 每天执行调仓函数
    # 聚宽会自动将非交易日的触发顺延至下一个交易日
    run_daily(prepare_stock_list, time='9:05')
    run_daily(judge_date, time='9:00')
    run_daily(trade_etf, time='9:35')
    run_daily(rebalance, time='10:00', reference_security='000300.XSHG')
    run_daily(stop_loss, time='10:02') # 止损函数
    run_daily(rebalance, time='10:10', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='10:30') #检查涨停股
    run_daily(check_limit_up, time='14:00') #检查涨停股
    run_daily(check_remain_amount, time='14:35')
    run_daily(stop_loss, time='14:45') # 止损函数
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
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] >= df['high_limit'] / 1.1 * 1.0995]
        g.yesterday_HL_list = list(df.code)
        if g.yesterday_HL_list != []:
            log.info("")
            log.info(f"************昨日({context.previous_date})涨停 **************")
            log.info(list(df.code))
            log.info("")
    else:
        g.yesterday_HL_list = []
'''
def create_signal_big_small_market(context):
    index_large = '000300.XSHG'
    index_small = '399101.XSHE'
    current_date = context.current_dt.date()
    current_data = get_current_data()
    
    price_large = get_price(index_large, "2009-01-01", current_date, fields=['close'])
    price_small = get_price(index_small, "2009-01-01", current_date, fields=['close'])

    # 3. 计算归一化的收益率曲线 (以起始日为1000基准)
    # 这才是真正可比的“走势”
    norm_large = price_large['close'] / price_large['close'].iloc[0] * 1000
    norm_small = price_small['close'] / price_small['close'].iloc[0] * 1000
    
    relative_strength = norm_small / norm_large
    ma_5 = relative_strength.rolling(window=40).mean()
    ma_5 = ma_5[40:]
    ma_5_diff = ma_5.diff() * 10

    is_positive = ma_5_diff > 0
    #print(is_positive)
    consecutive_5_sum = is_positive.rolling(window=5).sum()
    is_consecutive_5_positive_sum = (consecutive_5_sum == 5)  # 和等于5表示连续5个都是True
    is_consecutive_5_negative_sum = (consecutive_5_sum == 0)  # 和等于0表示连续5个都是False

    small_dates = is_consecutive_5_positive_sum.index[
        is_consecutive_5_positive_sum & (~is_consecutive_5_positive_sum.shift(1).fillna(False))
    ]
    #print(is_consecutive_5_negative_sum)
    big_dates = is_consecutive_5_negative_sum.index[
        is_consecutive_5_negative_sum & (~is_consecutive_5_negative_sum.shift(1).fillna(False))
    ]
    
    if is_consecutive_5_positive_sum[-1] == True:
        g.SIGNAL = "small"
        
    if is_consecutive_5_negative_sum[-1] == True:
        g.SIGNAL = "big"
'''

def trade_etf(context):
    if g.trade is False:
        current_holdings = list(context.portfolio.positions.keys())
        if current_holdings != [g.etf]:
            log.info('买入ETF')
            g.selected_stocks = [g.etf]
            sell_stocks(context)
            buy_stocks(context)
            
def rebalance(context):
    if g.trade is False:
        return
    #每月调仓函数：选股并调整持仓
    # 获取当前日期（回测运行的日期）
    # 获取当前日期是当月的第几个交易日
    
    current_date = context.current_dt.date()
    
    current_month = current_date.month
    current_time = context.current_dt.time()
    # 定义上午和下午的执行时间点
    morning_sell_time = datetime.time(10, 0)  # 上午开盘后
    afternoon_buy_time = datetime.time(10, 10) # 下午临近收盘
    # 获取当前月的所有交易日
    
    # 找到当前日期在当月是第几个交易日

    '''
    if current_month != g.last_month:
    #if (current_date.month == 1 or current_date.month == 4 or current_date.month == 7 or current_date.month == 11) and trade_day_index == 1:
        g.last_month = current_month
        no_st_codes = get_normal_stocks(current_date)
        #g.stock_pool = filter_growth_from_list(no_st_codes, prev_date, -50)
        g.stock_pool = no_st_codes
        #print(f'{len(g.stock_pool)}只股票连续3年净利润增长率 > 20%')
        g.stock_pool = get_small_cap_stocks(g.stock_pool, prev_date, 100)
        current_holdings = list(context.portfolio.positions.keys())
        if len(current_holdings) == 0:
            g.stocks_to_buy = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
            buy_stocks(context)
            
        #elif len(current_holdings) == g.stock_num:
        #    balance_position(context)
    '''
    
    if current_date.weekday() != g.weekday:  # 周二
        return
    log.info('✅========== 执行周度调仓，日期：%s ==========' % current_date)
    prev_date = current_date - datetime.timedelta(days=1)
    # 判断是否为每月第一个交易日（卖出日）
    if current_time == morning_sell_time:
        no_st_codes = get_normal_stocks(context, current_date)
        #g.stock_pool = filter_growth_from_list(no_st_codes, prev_date, -50)
        g.stock_pool = no_st_codes
        # 3. 获取市值数据（使用前一交易日数据，避免未来函数）
        g.selected_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
        
        if len(g.selected_stocks) == 0:
            log.warn('未选到符合条件的股票，本日不调仓')
        else:
            # 执行卖出逻辑
            sell_stocks(context)
            # 标记卖出已完成
            g.sell_done = True
            
            log_selection_details(g.selected_stocks, prev_date)

    # 判断是否为下午交易时间（买入日）
    elif current_time == afternoon_buy_time and g.sell_done:
        # 执行买入逻辑
        if len(g.stocks_to_buy):
            current_time = context.current_dt.time()
            log.info(f"✅今日({current_time})为买入时间，执行买入操作")
            log.info('✅+++++++++++++++++++++++++++++++++++++++++')
            log.info(f"✅需要买入股票 {len(g.stocks_to_buy)}只")
        
        buy_stocks(context)
        # 重置卖出标记
        g.sell_done = False
    else:
        log.info(f"今日({current_date})非调仓日，不执行操作")
    
    #print(f"在 {current_date} 符合条件的股票数量: {len(filtered_stocks)}")

#def trade_afternoon(context):
#    check_limit_up(context)
#    check_remain_amount(context)
    
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        current_holdings = list(context.portfolio.positions.keys())
        for stock in g.yesterday_HL_list:
            is_morning = now_time.hour < 12
            is_afternoon = now_time.hour > 12
            if stock not in current_holdings:
                continue
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            close_price = current_data.iloc[0,1] / 1.1
            rise_ratio = (current_data.iloc[0,0] - close_price) / close_price * 100
            log.info(f'{now_time} {stock} {get_security_info(stock).display_name} 股价{current_data.iloc[0,0]} 涨幅{rise_ratio:.2f}%')
            if (is_morning and rise_ratio < 4) or (is_afternoon and rise_ratio < 8):
                log.info(f"{stock} {get_security_info(stock).display_name}涨停打开，卖出")
                order_target_value(stock, 0)
                g.reason_to_sell = 'limitup'
                g.limitup_stocks.append(stock)
            else:
                log.info(f"{stock} {get_security_info(stock).display_name}涨停，继续持有")

#如果昨天有股票卖出或者买入失败，剩余的金额今天买入
def check_remain_amount(context):
    if g.reason_to_sell is 'limitup': #判断提前售出原因，如果是涨停售出则次日再次交易，如果是止损售出则不交易
        g.hold_list = list(context.portfolio.positions.keys())
        if len(g.hold_list) < g.stock_num:
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
            small_cap_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
            
            #num_stocks_to_buy = min(len(g.limitup_stocks), g.stock_num - len(g.hold_list))
            num_stocks_to_buy = g.stock_num - len(g.hold_list)
            g.stocks_to_buy = [stock for stock in small_cap_stocks if stock not in g.hold_list and stock not in g.limitup_stocks][:num_stocks_to_buy]
            log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。买入'+ str(g.stocks_to_buy))
            buy_stocks(context)
            g.refresh_hold = True
        g.reason_to_sell = ''
    elif False and g.reason_to_sell is 'stoploss':
        log.info('止盈止损后，有余额可用'+str(round((context.portfolio.cash),2))+'元。买入'+ str(g.etf))
        g.stocks_to_buy = [g.etf]
        buy_stocks(context)
        g.reason_to_sell = ''
        g.refresh_hold = True

#止盈止损
def stop_loss(context):
    if g.run_stoploss:
        current_positions = context.portfolio.positions

        if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
            for stock in current_positions.keys():
                price = current_positions[stock].price
                avg_cost = current_positions[stock].avg_cost
                # 个股盈利止盈
                if price >= avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("⭕ 收益100%止盈,卖出{}".format(stock))
                # 个股止损
                elif price < avg_cost * (1 - g.stoploss_limit):
                    order_info = order_target_value(stock, 0)
                    log.debug(f"⭕ 收益止损,卖出{stock},跌幅 { (1 - price / avg_cost) * 100:.2f}%")
                    if order_info != None and order_info.filled > 0:
                        log.debug(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')
                    g.reason_to_sell = 'stoploss'

        if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.current_dt, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            down_ratio = abs((stock_df['close'] / (stock_df['high_limit'] / 1.1) - 1).mean())
            # 市场大跌止损
            if down_ratio >= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("⭕ 大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                g.refresh_hold = True
                for stock in current_positions.keys():
                    if stock == g.etf:
                        continue
                    log.debug(f'⭕ 清仓{stock} {get_security_info(stock).display_name}')
                    order_info = order_target_value(stock, 0)
                    if order_info != None and order_info.filled > 0:
                        log.debug(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')

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
        print(f"get_small_cap_stocks   {query_date}    head {n}")
        rank = 0
        for idx, row in df_sorted.head(10).iterrows():
            stock_name = get_security_info(row['code']).display_name
            # 市值通常很大，除以10000显示为“万元”，更易读
            #cap_in_10k = row['circulating_market_cap']
            cap_in_10k = row['market_cap']
            rank = rank + 1
            marker = '  <== 选中' if rank <= n else ''
            log.info(f'    第{rank:>2}名: {stock_name}({row["code"]}), 流通市值: {cap_in_10k:.2f} 亿元{marker}')
    
    # 取全局最小的N只股票
    selected_stocks = df_sorted['code'].head(n).tolist()
    
    flag = False
    for stock_code in selected_stocks:
        if stock_code not in g.selected_stocks:
            flag = True
            break
            
    if flag:
        print(f"get_small_cap_stocks   {query_date}    head {n}")
        rank = 0
        for idx, row in df_sorted.head(10).iterrows():
            stock_name = get_security_info(row['code']).display_name
            # 市值通常很大，除以10000显示为“万元”，更易读
            #cap_in_10k = row['circulating_market_cap']
            cap_in_10k = row['market_cap']
            rank = rank + 1
            marker = '  <== 选中' if rank <= n else ''
            log.info(f'    第{rank:>2}名: {stock_name}({row["code"]}), 流通市值: {cap_in_10k:.2f} 亿元{marker}')
            
    
    return selected_stocks
    
def sell_stocks(context):
    # 当前持仓的股票列表
    g.stocks_to_sell = []
    g.stocks_to_buy = []
    current_holdings = list(context.portfolio.positions.keys())
    for stock in current_holdings:
        if (stock not in g.selected_stocks) and (stock not in g.yesterday_HL_list):
            g.stocks_to_sell.append(stock)

            
    for stock in g.selected_stocks:
        if (stock not in current_holdings) and (stock not in g.yesterday_HL_list):
            g.stocks_to_buy.append(stock)
    
    if len(g.stocks_to_buy) > 0 or len(g.stocks_to_sell) > 0:
        current_time = context.current_dt.time()
        log.info(f"✅今日({current_time})为卖出时间，执行卖出操作")
        log.info('✅------------------------------------------')
        log.info(f"✅当前持股 {len(current_holdings)}只")
        for stock in current_holdings:
            log.info(f"✅{get_security_info(stock).display_name}")
        log.info(f"✅需要买入股票 {len(g.stocks_to_buy)}只")
        log.info(f"✅需要卖出股票 {len(g.stocks_to_sell)}只")
        for stock in g.stocks_to_buy:
            log.info("✅待买入 ", get_security_info(stock).display_name)
        for stock in g.stocks_to_sell:
            log.info('✅待卖出: %s' % get_security_info(stock).display_name)
    
    # 执行卖出
    for stock in g.stocks_to_sell:
        log.info('✅>>>>>>>>>>>>')
        log.info('✅卖出: %s' % get_security_info(stock).display_name)
        order_info = order_target_value(stock, 0)
        if order_info != None and order_info.filled > 0:
            log.info(f'卖出 {order_info.filled}股 * {order_info.price:.2f}元')
    
def buy_stocks(context):
    for stock in g.stocks_to_buy:
        log.info(get_security_info(stock).display_name)
    if len(g.stocks_to_buy) > 0:
        available_cash = context.portfolio.available_cash
        position_value = context.portfolio.positions_value
        total_cash = context.portfolio.cash
        total_value = context.portfolio.total_value
        g.each_cash = available_cash / len(g.stocks_to_buy)
        #if g.stocks_to_buy != [g.etf]:
        #    g.each_cash = min(g.each_cash, total_value * 1.5 / g.stock_num)
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
            raw_amount = target_value_per_stock / current_price
            amount = int(raw_amount / 100) * 100  # 向下取整到100股的倍数
            if stock == g.etf:
                order(stock, amount)
                log.info(f'买入: {get_security_info(stock).display_name}, {stock} \n目标价值:{target_value_per_stock:.2f}'
                         f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
            else:
                order_info = order_target_value(stock, target_value_per_stock)
                if order_info != None and order_info.filled > 0:
                    log.info(f'买入: {get_security_info(stock).display_name}, {stock} \n目标价值:{target_value_per_stock:.2f}'
                         f'\n预计买入{amount}股，每股{current_price}元，合计:{amount * current_price:.2f}')
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
    #print(st_code_list)
    #print(f"Total {len(st_code_list)}")

# 可选：每日盘后记录函数（非必需）
def after_trading_end(context):
    current_date = context.current_dt.date()
    if current_date.weekday() != g.weekday and g.refresh_hold == False and g.trade == True:  # 周一
        return
    g.refresh_hold = False
    #每日收盘后运行，记录当日持仓情况
    # 获取当前持仓
    positions = context.portfolio.positions
    
    if len(positions) > 0:
        log.info(f'✅*******************当日(周{current_date.weekday()+1})持仓市值: %.2f元*******************' % context.portfolio.total_value)
        for stock, pos in positions.items():
            stock_name = get_security_info(stock).display_name
            log.info('✅  持仓: %s(%s), 数量: %d, 市值: %.2f元 %.2f%%' % 
                    (stock_name, stock, pos.total_amount, pos.value, pos.value / context.portfolio.total_value * 100))
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
        #    continue
            
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
    #    print(stock)
    
    # 2. 过滤ST/*ST股票
    non_st_stocks = filter_st_stocks(all_stocks, target_date)
    
    #non_st_stocks = all_stocks
    log.info(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
    
    # 3. 过滤停牌股票
    trading_stocks = filter_paused_stocks(context, non_st_stocks, target_date)
    

    log.info(f'过滤停牌，涨跌停股票后，剩余 {len(trading_stocks)} 只')
    
    return trading_stocks
    
    # 4. 过滤新上市股票（上市不足30天）
    mature_stocks = filter_new_stocks(trading_stocks, target_date, min_days=30)
    log.info(f'过滤上市不足30天股票后，剩余 {len(mature_stocks)} 只')
    
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
            g.st_code.add(stock)
            #print(f'ST {stock} {current_data[stock].name}')
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
            #print(f'停牌 {stock} {current_data[stock].name}')
            continue
        if not (stock in context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit):  # 涨停
            continue
        if not (stock in context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit):  # 跌停
            continue
        trading_stocks.append(stock)
    
    return trading_stocks

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
            else:
                log.debug(f'股票 {stock} 上市仅 {days_listed} 天，小于 {min_days} 天，跳过')
                
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