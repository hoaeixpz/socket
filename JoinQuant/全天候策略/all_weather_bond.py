# 克隆自聚宽文章：https://www.joinquant.com/post/66368
# 标题：仅100行代码：低风险全天候自平衡年化21%回撤6%
# 作者：黑娃

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
    #set_benchmark('513500.XSHG')
    set_benchmark('511880.XSHG')
    # 开启动态复权模式(真实价格)
    set_option("avoid_future_data", True)   #防止未来函数
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    #log.set_level('order', 'warning')
    #log.set_level('strategy', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.0000, open_commission=0.00005, close_commission=0.0001, min_commission=5), type='fund')
    #set_order_cost(OrderCost(close_tax=0, open_commission=0, close_commission=0, min_commission=0), type='fund')
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
        #'159985.XSHE',   #豆粕ETF       2019/9
        #"163415.XSHE"     #兴全商业模式
        #'601288.XSHG'    # 农业银行
    ]

    g.stocks = [
        "518880.XSHG", #黄金ETF
        "511220.XSHG", #城投债ETF 
        '159985.XSHE', #豆粕ETF 
        "513100.XSHG", #纳指ETF 
       # "512890.XSHG", #红利地波
        "601288.XSHG", #农业银行
        "600900.XSHG", #长江电力
    ]

    g.base_days = 120  # 
    g.nazhi_weight = 0.03
    g.golden_weight = 0.02
    g.weights = {}
    g.refreshed = False
    
    g.recordlist = []
    g.record_max = 0
    g.drawdown_count = 0
    g.drawdown_value = 0
    g.max_down_T = [1.1, 1.7, 2.4, 3.2]
    g.drawdown_stop = True
    g.drawdown_count_day = 60
    g.drawdown_level = 0
    g.last_level = 2
    g.drawdown_month = 0
    
    g.run_day = 1

## 开盘前运行函数
def before_market_open(context):
    current_date = context.current_dt.date()
    #  国债
    date_str = str(context.previous_date)
    
    if date_str > '2015-12-01': # 城投债ETF，
        g.stocks = [
            "518880.XSHG", #黄金ETF
            "511220.XSHG", #城投债ETF 
            "513100.XSHG", #纳指ETF 
            "601288.XSHG", #农业银行
            "600900.XSHG", #长江电力
        ]
        
    if date_str > '2019-06-01': # 10年地方债，
        g.stocks = [
            "518880.XSHG", #黄金ETF
            "511220.XSHG", #城投债ETF 
            "513100.XSHG", #纳指ETF 
            #"512890.XSHG", #红利地波
            "601288.XSHG", #农业银行
            "600900.XSHG", #长江电力
            #"511260.XSHG"  #十年国债
            "511270.XSHG"   #十年地方债
        ]
    
    if date_str > '2020-03-01': # 豆粕，
        g.stocks = [
            "518880.XSHG", #黄金ETF
            #"511220.XSHG", #城投债ETF 
            '159985.XSHE', #豆粕ETF 
            "513100.XSHG", #纳指ETF 
            #"512890.XSHG", #红利地波
            "601288.XSHG", #农业银行
            "600900.XSHG", #长江电力
            #"511260.XSHG"  #十年国债
            "511270.XSHG"   #十年地方债
        ]

    g.weights = {}
        
    #calc_ES_weights(context)
    #calc_Sharpe_weights(context)
    #adjust_weights(context)
    M = current_date.month
    if M < g.drawdown_month:
        M = M + 12
    if M - g.drawdown_month > 1 and g.last_level > 2:
        if g.last_level <= 3:
            g.drawdown_level = 0
            g.last_level = 2
        else:
            g.last_level = g.last_level - (M - g.drawdown_month - 1)

    log.error(f"last {g.last_level} , {g.drawdown_level}")
    calc_ES_weights(context, g.last_level)

    
def calc_ES_weights(context, dd_level):
    alpha = 0.05
    num = int(g.base_days * alpha)
    print("num ", num)
    log.error(f"dd_level: {dd_level}")
    
    df = get_price(
        g.stocks,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close"],
        count= g.base_days,
        fq='pre',
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
            sorted_group = group.sort_values(by='daily_return')
            stock_name = get_security_info(code).display_name
            print(f'{code}  {stock_name}')
            print(sorted_group.head(6))
            ES = sorted_group['daily_return'].head(num).mean()
            weight = -1 / ES
            
        weights[code] = weight
    log.info(f'权重:{weights}')
    
    # 标准化weight
    total_weight = sum([w for w in weights.values()])

    for key, value in weights.items():
        w = value / total_weight * (1 - g.nazhi_weight - g.golden_weight)
        if key == "513100.XSHG":
            w += g.nazhi_weight
        if key == "518880.XSHG":
            w += g.golden_weight
        g.weights[key] = w
        
    if dd_level > 0:
        bond_weight = g.weights["511270.XSHG"] * (1 - dd_level / 4)
        g.weights.pop('511270.XSHG')
        total_weight = sum([w for w in g.weights.values()])

        for key, value in g.weights.items():
            w = value / total_weight
            weights[key] = w * (1 - bond_weight)
        g.weights = weights
        g.weights['511270.XSHG'] = bond_weight

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

def execute_rebalance_sell(context):
    #if g.drawdown_level > 0:
    #    return
    print("-  ")
    print("=====================每月调仓 卖出=========================")
    rebalance_positions_sell(context)
    print("=====================   卖出结束  =========================")
    print("-  ")
    
def rebalance_positions_sell(context):
    # 先卖，后买
    g.refreshed = True
    current_data = get_current_data()
    for stock, pos in context.portfolio.positions.items():
        if stock == "511220.XSHG":
            continue
        stock_data = current_data[stock]
        current_price = stock_data.last_price
        if math.isnan(current_price):
            continue
        target_value = context.portfolio.total_value * g.weights.get(stock, 0)
        if stock == '511270.XSHG':
            #卖出债券类股票
            sell_bond(context, target_value)
            continue
        
        pos = context.portfolio.positions[stock]
        if pos.value > target_value * 1.06:
            amount = (pos.value - target_value) / current_price
            H = int(amount / 100) * 100
            amount = H
            if amount >= 100:
                log.info('>>>>>>>>>>>>>>>>>卖出>>>>>>>>>>>>>>>>')
                log.info(f'{stock} {get_security_info(stock).display_name} 目标市值{target_value:.2f}，当前市值{pos.value:.2f}, 卖出{amount}股 * {current_price}元')
                #order_target_value(stock, target_value)
                order(stock, -amount)

def sell_bond(context, target_value):
    #卖出债券类股票至target_value
    # 511270.XSHG 十年地方债 卖出2/3 份额
    # 511220.XSHG 城投债ETF  卖出1/3 份额
    pos_1 = context.portfolio.positions['511270.XSHG']
    pos_2 = context.portfolio.positions['511220.XSHG']
    value = pos_1.value + pos_2.value
    if value <= target_value * 1.06:
        return
    
    diff_value = value - target_value
    log.info(f'债券需要卖出 {diff_value:.2f} 元')
    
    current_data = get_current_data()
    stock_data = current_data['511270.XSHG']
    current_price = stock_data.last_price
    amount = (pos_1.value - target_value * 3 / 4) / current_price
    H = int(amount / 100) * 100
    amount = H
    log.info(f'511270.XSHG 十年地债 差额{pos_1.value - target_value * 3 / 4:.2f} 计划卖出{amount}股 * {current_price}元')
    if amount >= 100:
        log.info('>>>>>>>>>>>>>>>>>卖出>>>>>>>>>>>>>>>>')
        log.info(f'511270.XSHG 十年地债 目标市值{target_value * 3 / 4:.2f}，当前市值{pos_1.value:.2f}, 卖出{amount}股 * {current_price}元')
        order('511270.XSHG', -amount)
    
    raming_value =  value - target_value - amount * current_price
    log.info(f'剩余需要卖出{raming_value:.2f}元')
        
    stock_data = current_data['511220.XSHG']
    current_price = stock_data.last_price
    amount = raming_value / current_price
    H = int(amount / 100) * 100
    amount = H
    log.info(f'511220.XSHG 城投债 计划卖出{amount}股 * {current_price}元')
    if amount >= 100:
        log.info('>>>>>>>>>>>>>>>>>卖出>>>>>>>>>>>>>>>>')
        log.info(f'511220.XSHG 城投债 目标市值{target_value / 4:.2f}，当前市值{pos_2.value:.2f}, 卖出{amount}股 * {current_price}元')
        order('511220.XSHG', -amount)

def execute_rebalance_buy(context):
    #if g.drawdown_level > 0:
    #    return
    print("-  ")
    print("=====================每月调仓 买入=========================")
    rebalance_positions_buy(context)
    print("=====================   买入结束  =========================")
    print("-  ")
    
def rebalance_positions_buy(context):
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
        if stock == '511270.XSHG':
            #买入债券类股票
            buy_bond(context, target_value)
            continue
        
        pos = context.portfolio.positions[stock]
        if pos.value < target_value:
            log.info(f'{stock} {get_security_info(stock).display_name} 目标股数{target_value / current_price:.2f}')
            
        if pos.value < target_value * 0.94:
            amount = (target_value - pos.value) / current_price
            H = int(amount / 100) * 100
            amount = H
            if amount < 100:
                continue
            log.info('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
            log.info(f'{stock} {get_security_info(stock).display_name} 目标市值{target_value:.2f}，当前市值{pos.value:.2f}, 买入{amount}股 * {current_price}元')
            #order_target_value(stock, target_value)
            order(stock, amount)

def buy_bond(context, target_value):
    #买入至目标target_value价钱的债券类股票
    # 511270.XSHG 十年地方债 买入2/3 份额
    # 511220.XSHG 城投债ETF  买入1/3 份额
    pos_1 = context.portfolio.positions['511270.XSHG']
    pos_2 = context.portfolio.positions['511220.XSHG']
    value = pos_1.value + pos_2.value
    if value >= target_value * 0.94:
        return
    
    diff_value = target_value - value
    log.info(f'债券需要新增 {diff_value:.2f} 元')
    
    current_data = get_current_data()
    stock_data = current_data['511270.XSHG']
    current_price = stock_data.last_price
    amount = (target_value * 3 / 4 - pos_1.value)/ current_price
    H = int(amount / 100) * 100
    amount = H
    log.info(f'511270.XSHG 十年地债 差额{target_value * 3 / 4 - pos_1.value:.2f} 计划买入{amount}股 * {current_price}元')
    if amount >= 100:
        log.info('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
        log.info(f'511270.XSHG 十年地债 目标市值{target_value * 3 / 4:.2f}，当前市值{pos_1.value:.2f}, 买入{amount}股 * {current_price}元')
        order('511270.XSHG', amount)
    
    raming_value = target_value - value - amount * current_price
    log.info(f'剩余需要买入{raming_value:.2f}元')
        
    stock_data = current_data['511220.XSHG']
    current_price = stock_data.last_price
    amount = raming_value / current_price
    H = int(amount / 100) * 100
    amount = H
    log.info(f'511220.XSHG 城投债 计划买入{amount}股 * {current_price}元')
    if amount >= 100:
        log.info('<<<<<<<<<<<<<<<<<买入<<<<<<<<<<<<<<<<<')
        log.info(f'511220.XSHG 城投债 目标市值{target_value / 4:.2f}，当前市值{pos_2.value:.2f}, 买入{amount}股 * {current_price}元')
        order('511220.XSHG', amount)

def rebalance_drawdown(context):
    current_date = context.current_dt.date()
    
    #print("rebalance_drawdown")
    positions = context.portfolio.positions
    total_value = context.portfolio.total_value
    if g.record_max > total_value:
        max_drawdown = (1 - total_value / g.record_max) * 100
        if max_drawdown <= g.max_down_T[0]:
            return
        
        if max_drawdown > g.max_down_T[3]:
            g.drawdown_level = 4
        elif max_drawdown > g.max_down_T[2]:
            g.drawdown_level = 3
        elif max_drawdown > g.max_down_T[1]:
            g.drawdown_level = 2
        else:
            g.drawdown_level = 1
            
        print(f"drawn down: {max_drawdown:.2f} {g.drawdown_level} <-> {g.last_level}")
        if g.drawdown_level <= g.last_level:
            return
        
        g.last_level = g.drawdown_level
        g.drawdown_month = current_date.month
            
        log.error(f"rebalance_drawdown max draw down: {max_drawdown:.2f}% level {g.drawdown_level}")
        
        calc_ES_weights(context,  g.drawdown_level)
        target_value = context.portfolio.total_value * g.weights['511270.XSHG']
        log.info(f'bond target_value {target_value}')
        sell_bond(context, target_value)
        
        pos_1 = context.portfolio.positions['511270.XSHG']
        pos_2 = context.portfolio.positions['511220.XSHG']
        bond_weight = (pos_1.value + pos_2.value) / context.portfolio.total_value
        print(f"债券比重 {bond_weight*100:.2f} %")

        rebalance_positions_buy(context)
        g.drawdown_stop = False

def take_profit(context):
    stocks = g.stocks.copy()
    stocks.remove("511270.XSHG")
    if "511220.XSHG" in stocks:
        stocks.remove("511220.XSHG")
    df = get_price(
        stocks,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close"],
        count= g.base_days,
        fq='pre',
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
                print(f"今日相比于30天前 {last_price_30th}，涨了 {pct_30:.3f} %")
                if pct_30 > 10 and pct < 9.8:
                    positions = context.portfolio.positions
                    pos = positions[code]
                    sell_amount = int((pos.total_amount / 2) / 100) * 100
                    print(f"卖出 1/2 股份，总计{sell_amount}股")
                    order(code, -sell_amount)
                    info_position(context)

def after_code_changed(context):
    unschedule_all()
    # 开盘时运行
    run_monthly(before_market_open, g.run_day, time='09:15')
    run_monthly(execute_rebalance_sell, g.run_day, time='10:00')
    run_monthly(execute_rebalance_buy, g.run_day, time='10:02')
    run_daily(rebalance_drawdown, time='14:50')
    run_daily(take_profit, time='14:55')
    g.max_down_T = [1.1, 1.7, 2.4, 3.2]
    
def after_trading_end(context):
    #print(g.max_down_T)
    current_date = context.current_dt.date()
    total_value = context.portfolio.total_value
    if total_value > g.record_max:
        g.recordlist.clear()
    if g.record_max > total_value:
        max_drawdown = (1 - total_value / g.record_max) * 100
        log.warn(f"max draw down: {max_drawdown:.2f}%")
        
    g.recordlist.append(context.portfolio.total_value)
    if len(g.recordlist) > 120:
        g.recordlist.pop(0)
    g.record_max = max(g.recordlist)
    #print(g.recordlist)
    #print(g.record_max)
    
    if g.refreshed == False:
        return
    g.refreshed = False
    #每日收盘后运行，记录当日持仓情况
    # 获取当前持仓
    
    info_position(context)

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
        