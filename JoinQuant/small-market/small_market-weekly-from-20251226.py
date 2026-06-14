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
    g.st_code = set(['000004.XSHE', '000005.XSHE', '000007.XSHE', '000008.XSHE', '000010.XSHE', '000017.XSHE', '000018.XSHE', '000023.XSHE', '000030.XSHE', '000033.XSHE', '000034.XSHE', '000035.XSHE', '000036.XSHE', '000037.XSHE', '000038.XSHE', '000040.XSHE', '000046.XSHE', '000048.XSHE', '000056.XSHE', '000059.XSHE', '000068.XSHE', '000070.XSHE', '000150.XSHE', '000155.XSHE', '000156.XSHE', '000403.XSHE', '000408.XSHE', '000409.XSHE', '000410.XSHE', '000413.XSHE', '000415.XSHE', '000416.XSHE', '000420.XSHE', '000422.XSHE', '000430.XSHE', '000488.XSHE', '000498.XSHE', '000502.XSHE', '000504.XSHE', '000505.XSHE', '000506.XSHE', '000509.XSHE', '000510.XSHE', '000511.XSHE', '000516.XSHE', '000517.XSHE', '000518.XSHE', '000520.XSHE', '000523.XSHE', '000525.XSHE', '000526.XSHE', '000536.XSHE', '000540.XSHE', '000545.XSHE', '000546.XSHE', '000555.XSHE', '000557.XSHE', '000561.XSHE', '000564.XSHE', '000571.XSHE', '000572.XSHE', '000576.XSHE', '000584.XSHE', '000585.XSHE', '000586.XSHE', '000587.XSHE', '000590.XSHE', '000594.XSHE', '000595.XSHE', '000598.XSHE', '000602.XSHE', '000603.XSHE', '000605.XSHE', '000606.XSHE', '000607.XSHE', '000608.XSHE', '000609.XSHE', '000611.XSHE', '000613.XSHE', '000615.XSHE', '000616.XSHE', '000617.XSHE', '000620.XSHE', '000622.XSHE', '000627.XSHE', '000629.XSHE', '000633.XSHE', '000637.XSHE', '000638.XSHE', '000655.XSHE', '000656.XSHE', '000657.XSHE', '000659.XSHE', '000662.XSHE', '000663.XSHE', '000667.XSHE', '000668.XSHE', '000669.XSHE', '000670.XSHE', '000671.XSHE', '000672.XSHE', '000673.XSHE', '000676.XSHE', '000677.XSHE', '000679.XSHE', '000681.XSHE', '000687.XSHE', '000688.XSHE', '000691.XSHE', '000692.XSHE', '000693.XSHE', '000697.XSHE', '000698.XSHE', '000703.XSHE', '000707.XSHE', '000710.XSHE', '000711.XSHE', '000716.XSHE', '000717.XSHE', '000719.XSHE', '000720.XSHE', '000722.XSHE', '000727.XSHE', '000732.XSHE', '000736.XSHE', '000737.XSHE', '000738.XSHE', '000750.XSHE', '000751.XSHE', '000752.XSHE', '000755.XSHE', '000757.XSHE', '000760.XSHE', '000767.XSHE', '000776.XSHE', '000779.XSHE', '000780.XSHE', '000787.XSHE', '000792.XSHE', '000793.XSHE', '000796.XSHE', '000799.XSHE', '000802.XSHE', '000803.XSHE', '000805.XSHE', '000806.XSHE', '000809.XSHE', '000815.XSHE', '000816.XSHE', '000818.XSHE', '000820.XSHE', '000822.XSHE', '000831.XSHE', '000835.XSHE', '000836.XSHE', '000837.XSHE', '000838.XSHE', '000839.XSHE', '000851.XSHE', '000856.XSHE', '000863.XSHE', '000868.XSHE', '000889.XSHE', '000890.XSHE', '000892.XSHE', '000893.XSHE', '000897.XSHE', '000898.XSHE', '000899.XSHE', '000902.XSHE', '000903.XSHE', '000908.XSHE', '000909.XSHE', '000911.XSHE', '000912.XSHE', '000913.XSHE', '000918.XSHE', '000921.XSHE', '000922.XSHE', '000927.XSHE', '000928.XSHE', '000929.XSHE', '000932.XSHE', '000933.XSHE', '000935.XSHE', '000939.XSHE', '000950.XSHE', '000953.XSHE', '000955.XSHE', '000958.XSHE', '000961.XSHE', '000962.XSHE', '000968.XSHE', '000971.XSHE', '000972.XSHE', '000976.XSHE', '000979.XSHE', '000980.XSHE', '000981.XSHE', '000982.XSHE', '000989.XSHE', '000995.XSHE', '000996.XSHE', '001270.XSHE', '001896.XSHE', '002002.XSHE', '002005.XSHE', '002006.XSHE', '002015.XSHE', '002018.XSHE', '002019.XSHE', '002021.XSHE', '002022.XSHE', '002024.XSHE', '002047.XSHE', '002052.XSHE', '002058.XSHE', '002061.XSHE', '002069.XSHE', '002070.XSHE', '002071.XSHE', '002072.XSHE', '002075.XSHE', '002076.XSHE', '002077.XSHE', '002086.XSHE', '002087.XSHE', '002089.XSHE', '002092.XSHE', '002102.XSHE', '002109.XSHE', '002113.XSHE', '002114.XSHE', '002118.XSHE', '002121.XSHE', '002122.XSHE', '002124.XSHE', '002127.XSHE', '002134.XSHE', '002141.XSHE', '002143.XSHE', '002145.XSHE', '002147.XSHE', '002157.XSHE', '002160.XSHE', '002162.XSHE', '002163.XSHE', '002164.XSHE', '002168.XSHE', '002173.XSHE', '002175.XSHE', '002176.XSHE', '002177.XSHE', '002188.XSHE', '002190.XSHE', '002192.XSHE', '002194.XSHE', '002197.XSHE', '002199.XSHE', '002200.XSHE', '002207.XSHE', '002210.XSHE', '002211.XSHE', '002214.XSHE', '002217.XSHE', '002219.XSHE', '002220.XSHE', '002231.XSHE', '002234.XSHE', '002247.XSHE', '002248.XSHE', '002251.XSHE', '002253.XSHE', '002255.XSHE', '002256.XSHE', '002259.XSHE', '002260.XSHE', '002263.XSHE', '002265.XSHE', '002280.XSHE', '002288.XSHE', '002289.XSHE', '002290.XSHE', '002305.XSHE', '002306.XSHE', '002308.XSHE', '002309.XSHE', '002310.XSHE', '002312.XSHE', '002313.XSHE', '002316.XSHE', '002319.XSHE', '002321.XSHE', '002323.XSHE', '002325.XSHE', '002333.XSHE', '002336.XSHE', '002341.XSHE', '002354.XSHE', '002356.XSHE', '002358.XSHE', '002359.XSHE', '002366.XSHE', '002379.XSHE', '002388.XSHE', '002411.XSHE', '002417.XSHE', '002418.XSHE', '002420.XSHE', '002423.XSHE', '002424.XSHE', '002425.XSHE', '002426.XSHE', '002427.XSHE', '002433.XSHE', '002435.XSHE', '002445.XSHE', '002447.XSHE', '002450.XSHE', '002459.XSHE', '002464.XSHE', '002470.XSHE', '002473.XSHE', '002477.XSHE', '002482.XSHE', '002485.XSHE', '002490.XSHE', '002496.XSHE', '002499.XSHE', '002501.XSHE', '002502.XSHE', '002503.XSHE', '002504.XSHE', '002506.XSHE', '002509.XSHE', '002513.XSHE', '002528.XSHE', '002529.XSHE', '002535.XSHE', '002552.XSHE', '002564.XSHE', '002569.XSHE', '002570.XSHE', '002571.XSHE', '002575.XSHE', '002581.XSHE', '002586.XSHE', '002592.XSHE', '002602.XSHE', '002604.XSHE', '002608.XSHE', '002610.XSHE', '002618.XSHE', '002619.XSHE', '002620.XSHE', '002621.XSHE', '002629.XSHE', '002630.XSHE', '002633.XSHE', '002638.XSHE', '002640.XSHE', '002642.XSHE', '002647.XSHE', '002650.XSHE', '002656.XSHE', '002665.XSHE', '002668.XSHE', '002680.XSHE', '002681.XSHE', '002684.XSHE', '002689.XSHE', '002692.XSHE', '002693.XSHE', '002699.XSHE', '002700.XSHE', '002711.XSHE', '002713.XSHE', '002716.XSHE', '002717.XSHE', '002719.XSHE', '002721.XSHE', '002740.XSHE', '002742.XSHE', '002748.XSHE', '002750.XSHE', '002751.XSHE', '002762.XSHE', '002766.XSHE', '002770.XSHE', '002776.XSHE', '002781.XSHE', '002789.XSHE', '002800.XSHE', '002808.XSHE', '002816.XSHE', '002822.XSHE', '002848.XSHE', '002868.XSHE', '002872.XSHE', '002898.XSHE', '002951.XSHE', '003004.XSHE', '003032.XSHE', '600003.XSHG', '600057.XSHG', '600069.XSHG', '600070.XSHG', '600071.XSHG', '600072.XSHG', '600074.XSHG', '600075.XSHG', '600076.XSHG', '600077.XSHG', '600078.XSHG', '600079.XSHG', '600080.XSHG', '600083.XSHG', '600084.XSHG', '600086.XSHG', '600087.XSHG', '600090.XSHG', '600091.XSHG', '600093.XSHG', '600094.XSHG', '600107.XSHG', '600112.XSHG', '600115.XSHG', '600117.XSHG', '600119.XSHG', '600121.XSHG', '600122.XSHG', '600130.XSHG', '600131.XSHG', '600136.XSHG', '600139.XSHG', '600145.XSHG', '600146.XSHG', '600149.XSHG', '600150.XSHG', '600155.XSHG', '600157.XSHG', '600163.XSHG', '600165.XSHG', '600169.XSHG', '600175.XSHG', '600178.XSHG', '600179.XSHG', '600180.XSHG', '600182.XSHG', '600185.XSHG', '600186.XSHG', '600187.XSHG', '600190.XSHG', '600191.XSHG', '600193.XSHG', '600198.XSHG', '600200.XSHG', '600202.XSHG', '600203.XSHG', '600207.XSHG', '600209.XSHG', '600212.XSHG', '600213.XSHG', '600215.XSHG', '600217.XSHG', '600220.XSHG', '600221.XSHG', '600223.XSHG', '600225.XSHG', '600226.XSHG', '600228.XSHG', '600230.XSHG', '600234.XSHG', '600238.XSHG', '600239.XSHG', '600240.XSHG', '600241.XSHG', '600242.XSHG', '600243.XSHG', '600247.XSHG', '600250.XSHG', '600253.XSHG', '600255.XSHG', '600259.XSHG', '600260.XSHG', '600265.XSHG', '600275.XSHG', '600277.XSHG', '600280.XSHG', '600281.XSHG', '600282.XSHG', '600287.XSHG', '600289.XSHG', '600290.XSHG', '600291.XSHG', '600299.XSHG', '600300.XSHG', '600301.XSHG', '600303.XSHG', '600306.XSHG', '600311.XSHG', '600313.XSHG', '600319.XSHG', '600321.XSHG', '600335.XSHG', '600338.XSHG', '600339.XSHG', '600340.XSHG', '600346.XSHG', '600354.XSHG', '600355.XSHG', '600358.XSHG', '600359.XSHG', '600360.XSHG', '600365.XSHG', '600372.XSHG', '600373.XSHG', '600375.XSHG', '600381.XSHG', '600382.XSHG', '600385.XSHG', '600387.XSHG', '600388.XSHG', '600390.XSHG', '600392.XSHG', '600393.XSHG', '600396.XSHG', '600397.XSHG', '600399.XSHG', '600401.XSHG', '600403.XSHG', '600408.XSHG', '600416.XSHG', '600419.XSHG', '600421.XSHG', '600423.XSHG', '600425.XSHG', '600432.XSHG', '600444.XSHG', '600455.XSHG', '600462.XSHG', '600466.XSHG', '600470.XSHG', '600485.XSHG', '600490.XSHG', '600506.XSHG', '600515.XSHG', '600518.XSHG', '600520.XSHG', '600525.XSHG', '600526.XSHG', '600530.XSHG', '600532.XSHG', '600538.XSHG', '600539.XSHG', '600540.XSHG', '600543.XSHG', '600546.XSHG', '600550.XSHG', '600555.XSHG', '600556.XSHG', '600562.XSHG', '600565.XSHG', '600568.XSHG', '600579.XSHG', '600581.XSHG', '600589.XSHG', '600593.XSHG', '600595.XSHG', '600598.XSHG', '600599.XSHG', '600601.XSHG', '600603.XSHG', '600604.XSHG', '600608.XSHG', '600609.XSHG', '600610.XSHG', '600614.XSHG', '600615.XSHG', '600617.XSHG', '600624.XSHG', '600633.XSHG', '600634.XSHG', '600636.XSHG', '600644.XSHG', '600645.XSHG', '600647.XSHG', '600651.XSHG', '600652.XSHG', '600654.XSHG', '600656.XSHG', '600666.XSHG', '600671.XSHG', '600675.XSHG', '600677.XSHG', '600678.XSHG', '600680.XSHG', '600681.XSHG', '600687.XSHG', '600688.XSHG', '600689.XSHG', '600691.XSHG', '600695.XSHG', '600696.XSHG', '600698.XSHG', '600699.XSHG', '600701.XSHG', '600702.XSHG', '600705.XSHG', '600706.XSHG', '600707.XSHG', '600710.XSHG', '600711.XSHG', '600714.XSHG', '600715.XSHG', '600716.XSHG', '600719.XSHG', '600721.XSHG', '600722.XSHG', '600725.XSHG', '600726.XSHG', '600727.XSHG', '600728.XSHG', '600732.XSHG', '600733.XSHG', '600734.XSHG', '600735.XSHG', '600740.XSHG', '600747.XSHG', '600749.XSHG', '600751.XSHG', '600753.XSHG', '600757.XSHG', '600759.XSHG', '600760.XSHG', '600766.XSHG', '600767.XSHG', '600769.XSHG', '600771.XSHG', '600773.XSHG', '600777.XSHG', '600778.XSHG', '600779.XSHG', '600781.XSHG', '600792.XSHG', '600793.XSHG', '600800.XSHG', '600804.XSHG', '600806.XSHG', '600807.XSHG', '600811.XSHG', '600815.XSHG', '600816.XSHG', '600817.XSHG', '600821.XSHG', '600823.XSHG', '600831.XSHG', '600836.XSHG', '600844.XSHG', '600847.XSHG', '600854.XSHG', '600856.XSHG', '600860.XSHG', '600866.XSHG', '600868.XSHG', '600870.XSHG', '600871.XSHG', '600876.XSHG', '600877.XSHG', '600882.XSHG', '600885.XSHG', '600887.XSHG', '600890.XSHG', '600891.XSHG', '600892.XSHG', '600894.XSHG', '600896.XSHG', '600898.XSHG', '600961.XSHG', '600962.XSHG', '600978.XSHG', '600980.XSHG', '600984.XSHG', '600988.XSHG', '601005.XSHG', '601020.XSHG', '601106.XSHG', '601113.XSHG', '601258.XSHG', '601268.XSHG', '601399.XSHG', '601519.XSHG', '601558.XSHG', '601777.XSHG', '601798.XSHG', '601918.XSHG', '601919.XSHG', '601975.XSHG', '603001.XSHG', '603003.XSHG', '603007.XSHG', '603021.XSHG', '603023.XSHG', '603030.XSHG', '603032.XSHG', '603039.XSHG', '603117.XSHG', '603133.XSHG', '603157.XSHG', '603188.XSHG', '603261.XSHG', '603268.XSHG', '603322.XSHG', '603363.XSHG', '603377.XSHG', '603388.XSHG', '603389.XSHG', '603398.XSHG', '603517.XSHG', '603555.XSHG', '603557.XSHG', '603559.XSHG', '603580.XSHG', '603595.XSHG', '603603.XSHG', '603608.XSHG', '603721.XSHG', '603729.XSHG', '603779.XSHG', '603789.XSHG', '603810.XSHG', '603813.XSHG', '603822.XSHG', '603825.XSHG', '603828.XSHG', '603838.XSHG', '603843.XSHG', '603863.XSHG', '603869.XSHG', '603879.XSHG', '603880.XSHG', '603959.XSHG', '603963.XSHG', '603996.XSHG', '605081.XSHG', '605199.XSHG'])
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