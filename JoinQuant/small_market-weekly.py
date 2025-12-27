# 导入函数库
from jqdata import *
import pandas as pd
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
    set_slippage(FixedSlippage(0.00))
    
    # 设置全局变量
    g.stock_pool = []
    g.selected_stocks = []
    g.stocks_to_buy = []
    g.stocks_to_sell = []
    g.st_code = set()
    g.stock_num = 5  # 每月持有的股票数量
    g.each_cash = context.portfolio.starting_cash / g.stock_num
    g.sell_done = False
    g.last_month = None
    current_date = context.current_dt.date()
    
    # 每天执行调仓函数
    # 聚宽会自动将非交易日的触发顺延至下一个交易日
    run_daily(rebalance, time='09:40', reference_security='000300.XSHG')
    run_daily(rebalance, time='14:30', reference_security='000300.XSHG')
    
    log.info('策略初始化完成：每月初调仓，持有市值最小的{}只股票'.format(g.stock_num))

def rebalance(context):
    #每月调仓函数：选股并调整持仓
    # 获取当前日期（回测运行的日期）
    # 获取当前日期是当月的第几个交易日
    
    current_date = context.current_dt.date()
    if current_date.weekday() != 4:  # 周一
        return
    current_month = current_date.month
    current_time = context.current_dt.time()
    # 定义上午和下午的执行时间点
    morning_sell_time = datetime.time(9, 40)  # 上午开盘后
    afternoon_buy_time = datetime.time(14, 30) # 下午临近收盘
    # 获取当前月的所有交易日
    
    # 找到当前日期在当月是第几个交易日
    
    log.info('========== 执行日度调仓，日期：%s ==========' % current_date)
    prev_date = current_date - datetime.timedelta(days=1)
    
    if current_month != g.last_month:
    #if (current_date.month == 1 or current_date.month == 4 or current_date.month == 7 or current_date.month == 11) and trade_day_index == 1:
        g.last_month = current_month
        no_st_codes = get_normal_stocks(current_date)
        g.stock_pool = filter_growth_from_list(no_st_codes, prev_date, -50)
        #g.stock_pool = no_st_codes
        #print(f'{len(g.stock_pool)}只股票连续3年净利润增长率 > 20%')
        g.stock_pool = get_small_cap_stocks(g.stock_pool, prev_date, 100)
        current_holdings = list(context.portfolio.positions.keys())
        if len(current_holdings) == 0:
            g.stocks_to_buy = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
            buy_stocks(context)
    
    # 判断是否为每月第一个交易日（卖出日）
    if current_time == morning_sell_time:
        # 3. 获取市值数据（使用前一交易日数据，避免未来函数）
        g.selected_stocks = get_small_cap_stocks(g.stock_pool, prev_date, g.stock_num)
        # 执行卖出逻辑
        sell_stocks(context)
        # 标记卖出已完成
        g.sell_done = True

        
        
    # 判断是否为下午交易时间（买入日）
    elif current_time == afternoon_buy_time and g.sell_done:
        # 执行买入逻辑
        buy_stocks(context)
        # 重置卖出标记
        g.sell_done = False
    else:
        log.info(f"今日({current_date})非调仓日，不执行操作")
    
    #print(f"在 {current_date} 符合条件的股票数量: {len(filtered_stocks)}")

    
    if len(g.selected_stocks) == 0:
        log.warn('未选到符合条件的股票，本日不调仓')
        return
    
    log_selection_details(g.selected_stocks, prev_date)

def filter_stocks(stock_list, current_date):
    #过滤股票池：排除ST、停牌、上市不足60天的股票
    filtered = []
    
    # 获取前一个交易日日期，用于检查状态
    prev_date = current_date - datetime.timedelta(days=1)
    
    for stock in stock_list:
        try:
            # 检查ST状态
            st_data = get_extras('is_st', stock, start_date=prev_date, end_date=prev_date, df=True)
            is_st = False
            if stock in st_data.columns and len(st_data[stock]) > 0:
                st_value = st_data[stock].iloc[0]
                is_st = not pd.isna(st_value) and st_value == 1
            
            if is_st:
                continue
            
            # 检查是否停牌（通过获取前一天价格判断）
            price_data = get_price(stock, end_date=prev_date, count=1, fields=['close', 'volume'])
            if len(price_data) == 0:
                continue  # 无价格数据，可能停牌或异常
                
            close_price = price_data['close'].iloc[0]
            volume = price_data['volume'].iloc[0]
            if pd.isna(close_price) or close_price <= 0 or pd.isna(volume) or volume <= 0:
                continue  # 价格或成交量异常，视为停牌
            
            # 检查上市天数（过滤上市不足60天的新股，减少波动影响）
            stock_info = get_security_info(stock)
            if stock_info is None:
                continue
                
            list_date = stock_info.start_date.date()
            days_listed = (current_date - list_date).days
            if days_listed < 60:
                continue
            
            filtered.append(stock)
            
        except Exception as e:
            # 如果检查过程中出错，保守起见排除该股票
            log.debug('过滤股票 %s 时出错: %s' % (stock, str(e)))
            continue
    
    return filtered

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
    current_holdings = list(context.portfolio.positions.keys())
    g.stocks_to_sell = [s for s in current_holdings if s not in g.selected_stocks]
    g.stocks_to_buy= [s for s in g.selected_stocks if s not in current_holdings]
    
    if len(g.stocks_to_buy) > 0 or len(g.stocks_to_sell) > 0:
        current_time = context.current_dt.time()
        log.info(f"今日({current_time})为卖出时间，执行卖出操作")
        log.info('------------------------------------------')
        log.info(f"当前持股 {len(current_holdings)}只")
        for stock in current_holdings:
            log.info(get_security_info(stock).display_name)
        log.info(f"需要买入股票 {len(g.stocks_to_buy)}只")
        log.info(f"需要卖出股票 {len(g.stocks_to_sell)}只")
        for stock in g.stocks_to_buy:
            log.info("买入 ", get_security_info(stock).display_name)
        for stock in g.stocks_to_sell:
            log.info('卖出: %s' % get_security_info(stock).display_name)
    
    # 执行卖出
    for stock in g.stocks_to_sell:
        log.info('>>>>>>>>>>>>')
        log.info('卖出: %s' % get_security_info(stock).display_name)
        order_target_value(stock, 0)
    
def buy_stocks(context):
    if len(g.stocks_to_buy):
        current_time = context.current_dt.time()
        log.info(f"今日({current_time})为下午买入时间，执行买入操作")
        log.info('+++++++++++++++++++++++++++++++++++++++++')
        log.info(f"需要买入股票 {len(g.stocks_to_buy)}只")
        
    for stock in g.stocks_to_buy:
        log.info(get_security_info(stock).display_name)
    if len(g.stocks_to_buy) > 0:
        available_cash = context.portfolio.available_cash
        g.each_cash = available_cash / len(g.stocks_to_buy)
        position_value = context.portfolio.positions_value
        total_cash = context.portfolio.cash
        total_value = context.portfolio.total_value
        log.info("====调整每股额度====\n当前可用资金 ", available_cash, "\n持仓市值 ", position_value, "\n总资产: ", total_value, "\n每股额度 ", g.each_cash)
        # 计算每只股票的目标市值（等权重）
        # 获取当前总资产
        current_data = get_current_data()
        
        target_value_per_stock = g.each_cash
        
        for stock in g.stocks_to_buy:
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
        log.info('=== 本日选中股票详情 ===')
        for _, row in df.iterrows():
            stock_code = row['code']
            stock_name = get_security_info(stock_code).display_name
            cmc = row['circulating_market_cap']
            mc =  row['market_cap']
            zcl = row['inc_net_profit_to_shareholders_year_on_year']
            log.info(f'股票: {stock_name}({stock_code}), 流通市值: {cmc:.2f}万元, 总市值: {mc:.2f}万元,净利润增长率: {zcl:.2f}%')
            
    #st_code_list = list(g.st_code)
    #print(st_code_list)
    #print(f"Total {len(st_code_list)}")

# 可选：每日盘后记录函数（非必需）
def after_market_close(context):
    #每日收盘后运行，记录当日持仓情况
    # 获取当前持仓
    positions = context.portfolio.positions
    
    if len(positions) > 0:
        log.info('当日持仓市值: %.2f元' % context.portfolio.total_value)
        for stock, pos in positions.items():
            stock_name = get_security_info(stock).display_name
            log.info('  持仓: %s(%s), 数量: %d, 市值: %.2f元' % 
                    (stock_name, stock, pos.total_amount, pos.value))
#"""
    
    


def filter_chuangye_beijiao_codes(all_stocks):
    """
    过滤掉创业板、科创板、北交所股票
    """
    
    # 过滤条件
    filtered_stocks = []
    for stock in all_stocks:
        # 方法1：通过股票代码前缀过滤
        if stock.startswith('30') or stock.startswith('688') or stock.startswith('8'):
            continue
        
        #if "002260" in stock or "000835" in stock or "600091" in stock or "600890" in stock or "603157" in stock or "603996" in stock:
        #    continue
            
        filtered_stocks.append(stock)
    
    return filtered_stocks

def get_normal_stocks(target_date):
    """
    获取指定日期正常交易的股票列表（过滤退市、ST、停牌等）
    
    参数：
    target_date: 目标日期，datetime.date对象
    
    返回：
    list: 正常交易股票的代码列表
    """
    
    # 1. 获取指定日期所有未退市的股票
    all_stocks = get_all_securities(types=['stock'], date=target_date).index.tolist()
    
    all_stocks = filter_chuangye_beijiao_codes(all_stocks)
    
    log.info(f'在 {target_date}，全市场共有 {len(all_stocks)} 只未退市股票')
    #for stock in all_stocks:
    #    print(stock)
    
    # 2. 过滤ST/*ST股票
    non_st_stocks = filter_st_stocks(all_stocks, target_date)
    
    #non_st_stocks = all_stocks
    log.info(f'过滤ST/*ST股票后，剩余 {len(non_st_stocks)} 只')
    
    # 3. 过滤停牌股票
    trading_stocks = filter_paused_stocks(non_st_stocks, target_date)
    

    log.info(f'过滤停牌股票后，剩余 {len(trading_stocks)} 只')
    
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

    # 获取前一天的数据，因为当天可能还没有ST标记更新
    for day in range(1,4):
        prev_date = target_date - datetime.timedelta(days=day)
        #print(f'day {day}')
    
    
        try:
        # 方法1：使用df=True获取DataFrame格式
            st_info = get_extras('is_st', stock_list, start_date=prev_date, end_date=prev_date, df=True)
            #print(">>>>>>>>>> st info")
            #print(st_info)
            #print("<<<<<<<<<< st info")
            
            for stock in stock_list:
                if stock in g.st_code:
                    st_value = 1
                    continue
                if stock in st_info.columns:
                    # 获取ST标记值，先检查是否有数据
                    if len(st_info[stock]) > 0 and not pd.isna(st_info[stock].iloc[0]):
                        st_value = st_info[stock].iloc[0]
                        # 检查是否为ST (1表示ST，0表示非ST)
                        if st_value == 1:
                            #print(f"{day}天前 {stock} 判定为ST")
                            g.st_code.add(stock)
                        
                
        except Exception as e:
            log.error(f'批量获取ST状态时出错: {e}')
            # 出错时使用逐个检查的方式
            for stock in stock_list:
                if is_st_stock_individual(stock, prev_date):
                    g.st_code.add(stock)
    
    non_st_list = stock_list.copy()
    for st in stock_list:
        if st in g.st_code:
            non_st_list.remove(st)
            #log.debug(f'股票 {st} 是ST/*ST股票(st_value={st_value})，已过滤')
            
    return list(non_st_list)

def is_st_stock_individual(stock_code, target_date):
    """
    单独检查单只股票是否为ST股票
    
    参数：
    stock_code: 股票代码
    target_date: 目标日期
    
    返回：
    bool: True=ST股票，False=非ST股票
    """
    try:
        # 获取前一天的数据
        prev_date = target_date
        
        # 使用df=True获取DataFrame
        st_df = get_extras('is_st', stock_code, start_date=prev_date, end_date=prev_date, df=True)
        
        # 检查返回的DataFrame是否有效
        if st_df is None or len(st_df) == 0:
            log.debug(f'股票 {stock_code} 未获取到ST数据，默认非ST')
            return False
        
        if stock_code not in st_df.columns:
            log.debug(f'股票 {stock_code} 不在ST数据列中，默认非ST')
            return False
        
        # 检查是否有数据
        if len(st_df[stock_code]) == 0:
            log.debug(f'股票 {stock_code} ST数据为空，默认非ST')
            return False
        
        st_value = st_df[stock_code].iloc[0]
        
        if pd.isna(st_value):
            log.debug(f'股票 {stock_code} ST数据为NaN，默认非ST')
            return False
        
        # ST值为1表示ST，0表示非ST
        return bool(st_value)
        
    except Exception as e:
        log.error(f'检查股票 {stock_code} 的ST状态时出错: {e}')
        # 出错时默认不是ST，保守策略
        return False

def filter_paused_stocks(stock_list, target_date):
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
    
    # 获取前一天的交易数据来判断是否停牌
    prev_date = target_date - datetime.timedelta(days=1)
    
    try:
        # 使用panel=False获取更友好的数据格式
        price_data = get_price(
            stock_list, 
            end_date=prev_date, 
            count=1, 
            fields=['close', 'volume', 'high', 'low', 'paused'],
            panel=False
        )
        
        # 如果没有数据，直接返回空列表
        if price_data is None or len(price_data) == 0:
            log.warning(f'在 {prev_date} 未获取到价格数据')
            return trading_stocks
        
        # 按股票代码分组
        for stock in stock_list:
            stock_data = price_data[price_data['code'] == stock]
            
            if len(stock_data) == 0:
                # 没有价格数据，可能停牌
                #log.debug(f'股票 {stock} 在 {prev_date} 无价格数据，可能停牌')
                continue
            
            # 检查停牌标志
            if 'paused' in stock_data.columns:
                is_paused = stock_data['paused'].iloc[0]
                if is_paused == 1:
                    #log.debug(f'股票 {stock} 在 {prev_date} 停牌(paused=1)')
                    continue
            
            # 检查价格和成交量
            close_price = stock_data['close'].iloc[0]
            volume = stock_data['volume'].iloc[0]
            high = stock_data['high'].iloc[0]
            low = stock_data['low'].iloc[0]
            
            # 判断是否停牌的条件
            if (pd.isna(close_price) or close_price <= 0 or 
                pd.isna(volume) or volume <= 0 or
                (pd.isna(high) and pd.isna(low)) or 
                (high == 0 and low == 0)):
                log.debug(f'股票 {stock} 在 {prev_date} 价格/成交量异常，可能停牌')
            else:
                trading_stocks.append(stock)
                
    except Exception as e:
        log.error(f'批量检查停牌状态时出错: {e}')
        # 出错时逐个检查
        for stock in stock_list:
            if not is_paused_stock_individual(stock, target_date):
                trading_stocks.append(stock)
    
    return trading_stocks

def is_paused_stock_individual(stock_code, target_date):
    """
    单独检查单只股票是否停牌
    
    参数：
    stock_code: 股票代码
    target_date: 目标日期
    
    返回：
    bool: True=停牌，False=正常交易
    """
    try:
        # 获取前一天的交易数据
        prev_date = target_date - datetime.timedelta(days=1)
        
        price_data = get_price(
            stock_code, 
            end_date=prev_date, 
            count=1, 
            fields=['close', 'volume', 'paused']
        )
        
        if len(price_data) == 0:
            return True  # 无数据，视为停牌
        
        # 检查停牌标志
        if 'paused' in price_data.columns:
            is_paused = price_data['paused'].iloc[0]
            if is_paused == 1:
                return True
        
        # 检查价格和成交量
        close_price = price_data['close'].iloc[0]
        volume = price_data['volume'].iloc[0]
        
        if (pd.isna(close_price) or close_price <= 0 or 
            pd.isna(volume) or volume <= 0):
            return True
            
        return False
        
    except Exception as e:
        log.error(f'检查股票 {stock_code} 停牌状态时出错: {e}')
        return True  # 出错时默认视为停牌，保守策略

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
                    #    print(year,"  ",row['code'])
                    #    print(row['inc_net_profit_to_shareholders_year_on_year'])
    
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
