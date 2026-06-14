# 根据每只股票前120个交易日的收益率分配比重，
# 取120个交易日里最大的5%，即收益率最大的6个交易日，
# 取这6个交易日的收益率均值，均值越大的股票，比重越大。
# 同时避免超买超卖，根据这120个交易日的整体趋势，
# 如果整体趋势向上，可能超买，则稍微降低比重，反之增大比重。
# 具体做法：取120个交易日的均值AR，将前6大交易日的均值ES，
# 个股比重weight正比于 ES * (1 - AR)。
# 每日下午检测每只股票当日涨幅，如果能挤进过去120个交易日涨幅前3
# 则卖出这只股票一半股份


# 导入函数库
from jqdata import *
from datetime import time
import datetime
#最优化投资组合的推导是一个约束最优化问题
import scipy.optimize as sco

# 初始化函数，设定基准等等
def initialize(context):
    # g.base_index = '562500.XSHG'
    # g.base_index = '399300.XSHE'
    
    # 设定沪深300作为基准
    custom_benchmark = {
        "518880.XSHG": 0.2, #黄金ETF
        '159985.XSHE': 0.2, #豆粕ETF 
        "513100.XSHG": 0.2, #纳指ETF 
        "601288.XSHG": 0.2, #农业银行
        "600900.XSHG": 0.2 #长江电力
    }
    set_benchmark(custom_benchmark)
    #set_benchmark('511880.XSHG')
    # 开启动态复权模式(真实价格)
    set_option("avoid_future_data", True)   #防止未来函数
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    #log.set_level('order', 'error')
    log.set_level('order', 'warning')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.0000, open_commission=0.00005, close_commission=0.0001, min_commission=5), type='fund')
    set_slippage(FixedSlippage(0.001), type="fund")
 
    g.stocks = [
        #"518880.XSHG",  # 黄金ETF      2013/7
        # '511090.XSHG', # 三十年国债  2023/6
        #"511260.XSHG",  # 十年国债     2017/8
        #"511010.XSHG",  # 五年国债     2013/4
        #"511220.XSHG",    #城投债ETF    2014/11
        
        #"513100.XSHG",  # 纳指ETF      2013/6
        #"159920.XSHE",  # 恒生ETF      2012/11
        ##"515080.XSHG",  # 中证红利     2019/12
        #"512890.XSHG",    #红利地波     2018/12
        #"510300.XSHG",  # 沪深300      2012/5
        #'159985.XSHE',   #豆粕ETF       2019/12
        #"163415.XSHE"     #兴全商业模式
        #'601288.XSHG'    # 农业银行
        #"159697.XSHE"    #石油ETF       2023/5
    ]

    g.stocks = [
        "518880.XSHG", #黄金ETF
        #"511220.XSHG", #城投债ETF 
        '159985.XSHE', #豆粕ETF 
        "513100.XSHG", #纳指ETF 
       # "512890.XSHG", #红利地波
        "601288.XSHG", #农业银行
        "600900.XSHG", #长江电力
    ]

    g.base_days = 120  # 
    g.nazhi_weight = 0.0#3
    g.golden_weight = 0.0#2
    g.weights = {}
    g.refreshed = False
    
    g.recordlist = []
    g.record_max = 0

## 开盘前运行函数
def before_market_open(context):
    current_date = context.current_dt.date()
    #  国债
    date_str = str(context.previous_date)
    
    if date_str > '2015-12-01': # 城投债ETF，
        g.stocks = [
            "518880.XSHG", #黄金ETF
            #"511220.XSHG", #城投债ETF 
            "513100.XSHG", #纳指ETF 
            "601288.XSHG", #农业银行
            "600900.XSHG", #长江电力
        ]
    
    if date_str > '2020-06-01': # 豆粕，
        g.stocks = [
            "518880.XSHG", #黄金ETF
            #"511220.XSHG", #城投债ETF 
            '159985.XSHE', #豆粕ETF 
            "513100.XSHG", #纳指ETF 
            #"512890.XSHG", #红利地波
            "601288.XSHG", #农业银行
            #"600025.XSHG", #华能水电
            "600900.XSHG", #长江电力
            #"501018.XSHG", #南方原油
            #"515980.XSHG", #人工智能
            #"511260.XSHG"  #十年国债
        ]
    '''  
    if date_str > '2023-12-01': # 石油，
        g.stocks = [
            "518880.XSHG", #黄金ETF
            #"511220.XSHG", #城投债ETF 
            '159985.XSHE', #豆粕ETF 
            "513100.XSHG", #纳指ETF 
            #"512890.XSHG", #红利地波
            "601288.XSHG", #农业银行
            #"600025.XSHG", #华能水电
            "600900.XSHG", #长江电力
            #"511260.XSHG"  #十年国债
            #"159697.XSHE", #石油ETF
        ]
    '''
    g.weights = {}
        
    calc_ES_weights(context)
    #calc_Sharpe_weights(context)
    #adjust_weights(context)
    
def calc_ES_weights(context):
    alpha = 0.05
    num = int(g.base_days * alpha)
    print("num ", num)
    
    df = get_price(
        g.stocks,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close"],
        count= g.base_days,
        panel=False
    )
    weights = {}
    
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        if group.shape[0] < g.base_days:
            # 基础权重
            weight = 0
        else:
            group['daily_return'] = group['close'].pct_change() * 100
            group = group.iloc[1:]
            group = group.dropna(subset=['daily_return'])
            sorted_group = group.sort_values(by='daily_return')
            stock_name = get_security_info(code).display_name
            print(f'{code}  {stock_name}')
            print(sorted_group.tail(6))
            ES = sorted_group['daily_return'].tail(num).mean()
            print(f"ES {ES:.3f}")
            AR = sorted_group['daily_return'].mean()
            print(f"AR {AR:.3f}")
            weight = ES * (1 - AR)
            
        weights[code] = weight
    log.info(f'权重:{weights}')
    
    # 标准化weight
    total_weight = sum([w for w in weights.values()])
    for key, value in weights.items():
        w = value / total_weight
        g.weights[key] = w
        
    for stock, w in g.weights.items():
        log.info(f'{stock} {get_security_info(stock).display_name} 权重{100*w:.2f}%')
        
def calc_Sharpe_weights(context):
    date_str = str(context.previous_date)
    if date_str < '2015-12-01':
        df = get_price(
            g.stocks,
            end_date=context.previous_date,
            frequency="daily",
            fields=["close"],
            count= g.base_days * 2
        )
    else:
        df = get_price(
            g.stocks,
            start_date='2015-01-01',
            end_date=context.previous_date,
            frequency="daily",
            fields=["close"]
        )
    noa = len(g.stocks)
    
    data = df['close']
    #print(data)
    returns = np.log(data / data.shift(1))
    returns = returns.dropna()
    #print(returns)
    
    #约束是所有参数(权重)的总和为1。这可以用minimize函数的约定表达如下
    cons = ({'type':'eq', 'fun':lambda x: np.sum(x)-1})
    
    #我们还将参数值(权重)限制在0和1之间。这些值以多个元组组成的一个元组形式提供给最小化函数
    bnds = tuple((0,1) for x in range(noa))
    
    risk_free = 0.04
    def statistics(weights):
        weights = np.array(weights)
        port_returns = np.sum(returns.mean()*weights)*252
        port_variance = np.sqrt(np.dot(weights.T, np.dot(returns.cov()*252,weights)))
        return np.array([port_returns, port_variance, (port_returns - risk_free)/port_variance])
        
    def min_sharpe(weights):
        return -statistics(weights)[2]
    #优化函数调用中忽略的唯一输入是起始参数列表(对权重的初始猜测)。我们简单的使用平均分布。
    opts = sco.minimize(min_sharpe, noa*[1./noa,], method = 'SLSQP', bounds = bnds, constraints = cons)
    
    print("最优sharpe权重")
    print(opts.x.round(3))
    best_r = np.sum(returns.mean()*252*opts.x)
    best_var = np.sqrt(np.dot(opts.x.T, np.dot(returns.cov()*252, opts.x)))
    print(f"年化收益 {best_r} 年化标准差{best_var}")
    
    i = 0
    for s in g.stocks:
        g.weights[s] = opts.x[i]
        i += 1
        
    if best_var > 0.04:
        no_risk_w = 1 - (0.04  /  best_var)
        print(f"年化标准差过大，增加城投比重{no_risk_w}")
        print("改变前比重：")
        for stock, w in g.weights.items():
            log.info(f'{stock} {get_security_info(stock).display_name} 权重{100*w:.2f}%')
            
        for key, value in g.weights.items():
            w = value * (1 - no_risk_w)
            g.weights[key] = w
            
        if g.weights.get("511220.XSHG") is None:
            g.weights["511220.XSHG"] = no_risk_w
            g.stocks.append("511220.XSHG")
        else:
            g.weights["511220.XSHG"] += no_risk_w
            
        print("改变后比重：")
    
    for stock, w in g.weights.items():
        log.info(f'{stock} {get_security_info(stock).display_name} 权重{100*w:.2f}%')  
    
def adjust_weights(context):
    current_data = get_current_data()
    cash = context.portfolio.total_value
    print('cash')
    print(cash)
    total_diff = 0
    iter_stop = 4
    while cash > 1000:
        target_cash = 0
        total_diff = 0
        weights = {}
        for stock, w in g.weights.items():
            stock_data = current_data[stock]
            current_price = stock_data.last_price
            if math.isnan(current_price):
                continue
        
            target_value = context.portfolio.total_value * w
            target_amount = int(target_value / current_price / 100) * 100
            weights[stock] = target_amount * current_price
            target_cash += weights[stock]
            total_diff += abs(weights[stock] / context.portfolio.total_value - w)
        
        print(f"与目标差异 {total_diff*100} %")
        #break
        cash = context.portfolio.total_value - target_cash
        if cash > 1000:
            print(f"剩余金额 {cash}")
            total_weight = sum([w for w in weights.values()])
            g.weights = {key: value/total_weight for key, value in weights.items()}
            for stock, w in g.weights.items():
                log.info(f'{stock} {get_security_info(stock).display_name} 权重{100*w:.2f}%')
                
        iter_stop -= 1
        if iter_stop < 0:
            break

def rebalance_positions_sell(context):
    # 先卖，后买
    month = context.current_dt.month
    year = context.current_dt.year
    #if month % 12 != 1 or year % 8:
    #    return
    g.refreshed = True
    current_data = get_current_data()
    for stock, pos in context.portfolio.positions.items():
        stock_data = current_data[stock]
        current_price = stock_data.last_price
        if math.isnan(current_price):
            continue
        target_value = context.portfolio.total_value * g.weights.get(stock, 0)
        pos = context.portfolio.positions[stock]
        if pos.value > target_value * 1.06:
            amount = int((pos.value - target_value) / current_price / 100) * 100
            if amount > 100:
                log.info('>>>>>>>>>>>>>>>>>卖出>>>>>>>>>>>>>>>>')
                log.info(f'{stock} {get_security_info(stock).display_name} 目标市值{target_value:.2f}，当前市值{pos.value:.2f}, 卖出{amount}股 * {current_price}元')
                #order_target_value(stock, target_value)
                order(stock, -amount)

def rebalance_positions_buy(context):
    month = context.current_dt.month
    year = context.current_dt.year
    #if month % 12 != 1 or year % 8:
    #    return
    # 后买，
    g.refreshed = True
    current_data = get_current_data()
    for stock, w in g.weights.items():
        if w <= 0.00001:
            continue
        stock_data = current_data[stock]
        current_price = stock_data.last_price
        if math.isnan(current_price):
            continue
        target_value = context.portfolio.total_value * w
        pos = context.portfolio.positions[stock]
        if pos.value < target_value:
            log.info(f'{stock} {get_security_info(stock).display_name} 目标股数{target_value / current_price:.2f}')
            
        if pos.value < target_value * 0.94:
            amount = int((target_value - pos.value) / current_price / 100) * 100
            if amount < 100:
                continue
            log.info('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
            log.info(f'{stock} {get_security_info(stock).display_name} 目标市值{target_value:.2f}，当前市值{pos.value:.2f}, 买入{amount}股 * {current_price}元')
            #order_target_value(stock, target_value)
            order(stock, amount)

def take_profit(context):
    df = get_price(
        g.stocks,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close"],
        count= g.base_days,
        panel=False
    )
    
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        if group.shape[0] < g.base_days:
            # 基础权重
            continue
        else:
            group['daily_return'] = group['close'].pct_change() * 100
            group = group.iloc[1:]
            group = group.dropna(subset=['daily_return'])
            sorted_group = group.sort_values(by='daily_return')
            last_close_price = group['close'].iloc[-1]
            current_data = get_current_data()
            stock_data = current_data[code]
            current_price = stock_data.last_price
            pct = (current_price - last_close_price) / last_close_price * 100
            last_3th = sorted_group['daily_return'].iloc[-3]
            if pct >last_3th:
                print("=====================================")
                print(code)
                print(f"今日涨幅 {pct:.3f} % 大于过去120天第3名 {last_3th:.3f} %")
                print(sorted_group.tail(6))
                last_price_30th = group['close'].iloc[-30]
                pct_30 = (current_price - last_price_30th) / last_price_30th * 100
                print(f"今日相比于30天前，涨了 {pct_30:.3f} %")
                if pct_30 > 10:
                    positions = context.portfolio.positions
                    pos = positions[code]
                    sell_amount = int((pos.total_amount / 2) / 100) * 100
                    print(f"卖出 1/2 股份，总计{sell_amount}股")
                    order(code, -sell_amount)
                    info_position(context)


def after_code_changed(context):
    unschedule_all()
    # 开盘时运行
    run_monthly(before_market_open, 1, time='09:59')
    run_monthly(rebalance_positions_sell, 1, time='10:00')
    run_monthly(rebalance_positions_buy, 1, time='10:02')
    run_daily(take_profit, time='14:45')
    
def info_position(context):
    positions = context.portfolio.positions
    
    if len(positions) > 0:
        current_date = context.current_dt.date()
        log.info(f'✅*******************当日(周{current_date.weekday()+1})持仓市值: %.2f元*******************' % context.portfolio.positions_value)
        sorted_pos = dict(sorted(positions.items(), key=lambda x: x[0]))
        for stock, pos in sorted_pos.items():
            stock_name = get_security_info(stock).display_name
            price = pos.value / pos.total_amount
            log.info('✅持仓: %s(%s), 占比 %.2f%%,  数量: %d, 市值: %.2f元' % 
                    (stock_name, stock, pos.value / context.portfolio.total_value * 100, pos.total_amount, pos.value))
            #g.stock_prices[stock] = [pos.value, pos.total_amount]
        log.info(f'✅*******************总资产 %.2f  剩余可用金额 %.2f元*******************\n\n' % (context.portfolio.total_value, context.portfolio.available_cash))
        
def after_trading_end(context):
    total_value = context.portfolio.total_value
    if total_value > g.record_max:
        g.recordlist.clear()
    if g.record_max > total_value:
        max_drawdown = (1 - total_value / g.record_max) * 100
        log.error(f"max draw down: {max_drawdown:.2f}%")
        
    g.recordlist.append(context.portfolio.total_value)
    if len(g.recordlist) > 120:
        g.recordlist.pop(0)
    g.record_max = max(g.recordlist)

    if g.refreshed == False:
        return
    g.refreshed = False
    #每日收盘后运行，记录当日持仓情况
    # 获取当前持仓
    info_position(context)
