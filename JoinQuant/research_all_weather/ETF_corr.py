# 导入必要库
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from jqdata import *

# 设置中文字体（聚宽环境可能已配置）
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def analyze_etf_correlation(context, etf_pool, start_date, end_date):
    """
    分析ETF相关性并绘制图表
    """
    print("=" * 60)
    print("ETF相关性分析")
    print("=" * 60)
    
    # 1. 获取价格数据
    print("正在获取ETF价格数据...")
    price_data = get_etf_prices(list(etf_pool.keys()), start_date, end_date)
    
    if price_data.empty:
        print("错误：未能获取到有效价格数据")
        return
    
    # 2. 计算收益率
    print("正在计算收益率...")
    returns_data = calculate_returns(price_data)
    
    # 3. 计算相关性矩阵
    print("正在计算相关性矩阵...")
    correlation_matrix = returns_data.corr()
    
    # 4. 打印相关性分析结果
    print_correlation_results(correlation_matrix, etf_pool)
    
    annual_returns = calculate_annual_rate(price_data)
    sar = annual_returns.sort_values()
    print("=====年化收益率======")
    for stock, ar in sar.items():
        print(stock, " ", etf_pool[stock][0], " ", ar)
    
    # 5. 绘制相关性热力图
    plot_correlation_heatmap(correlation_matrix, etf_pool)
    
    # 6. 绘制价格走势图
    plot_price_trends(price_data, etf_pool)
    
    # 7. 绘制散点矩阵图
    plot_scatter_matrix(returns_data, etf_pool)
    
    # 8. 计算滚动相关性
    print("\n正在计算滚动相关性...")
    analyze_rolling_correlation(returns_data, etf_pool)
    
    print("\n分析完成！")

def get_etf_prices(etf_codes, start_date, end_date):
    """
    获取ETF价格数据
    """
    price_df = pd.DataFrame()
    
    for etf in etf_codes:
        try:
            # 获取上市日期
            info = get_security_info(etf)
            start_date_info = info.start_date.strftime('%Y-%m-%d') if hasattr(info, 'start_date') else '未知'

            # 获取日线数据
            df = get_price(etf, start_date=start_date, end_date=end_date,
                          frequency='daily', fields=['close'])

            if not df.empty:
                # 重命名列名为ETF名称
                etf_name = etf
                price_df[etf] = df['close']
                print(f"成功获取 {etf} 数据: {len(df)} 个交易日, 上市日期: {start_date_info}")
                #print(df['close'])
            else:
                print(f"警告: {etf} 数据为空, 上市日期: {start_date_info}")

        except Exception as e:
            print(f"获取 {etf} 数据时出错: {e}")
    
    return price_df

def calculate_returns(price_data):
    """
    计算日收益率
    """
    # 计算日收益率（对数收益率）
    returns = np.log(price_data / price_data.shift(1))
    returns = returns.dropna()
    return returns

def calculate_annual_rate(price_data):
    #print(price_data['300487.XSHE'])
    #print(price_data[-5:])
    r = price_data.iloc[-1] / price_data.iloc[0]
    num = len(price_data)
    ar = r ** (1 / (num / 250)) - 1
    ar = ar * 100
    return ar

def print_correlation_results(corr_matrix, etf_pool):
    """
    打印相关性分析结果
    """
    print("\n" + "=" * 60)
    print("ETF相关性矩阵")
    print("=" * 60)
    print(type(corr_matrix))
    
    # 创建带名称的索引
    etf_names = [f"{etf_pool[code][0]}\n({code})" for code in corr_matrix.columns]
    
    # 打印相关性矩阵
    corr_df = pd.DataFrame(corr_matrix.values, 
                          index=etf_names, 
                          columns=etf_names)
    print(corr_df.round(3))
    
    # 找出相关性最高和最低的配对
    print("\n" + "=" * 60)
    print("相关性极值分析")
    print("=" * 60)
    
    # 排除对角线
    corr_values = corr_matrix.where(~np.eye(corr_matrix.shape[0], dtype=bool)).stack()
    
    max_corr = corr_values.max()
    min_corr = corr_values.min()
    max_pair = corr_values.idxmax()
    min_pair = corr_values.idxmin()
    
    print(f"最高相关性: {max_corr:.3f}")
    print(f"  配对: {etf_pool[max_pair[0]][0]} ({max_pair[0]}) 与 {etf_pool[max_pair[1]][0]} ({max_pair[1]})")
    
    print(f"最低相关性: {min_corr:.3f}")
    print(f"  配对: {etf_pool[min_pair[0]][0]} ({min_pair[0]}) 与 {etf_pool[min_pair[1]][0]} ({min_pair[1]})")
    
    stock_mean_corr = {}
    for stock in corr_matrix.columns:
        corr_stock = corr_matrix[stock]
        stock_mean_corr[stock] = (corr_stock.sum() - 1) / (len(corr_stock) - 1)

    stock_mean_corr = dict(sorted(stock_mean_corr.items(), key=lambda x:x[1]))
    # 平均相关性
    avg_corr = corr_values.mean()
    print(f"平均相关性: {avg_corr:.3f}")
    for stock, mc in stock_mean_corr.items():
        print(f"{stock} {etf_pool[stock][0]} {mc:.3f}")
    

def plot_correlation_heatmap(corr_matrix, etf_pool):
    """
    绘制相关性热力图
    """
    plt.figure(figsize=(12, 10))
    
    # 创建带名称的索引
    etf_names = [f"{etf_pool[code][0]}\n({code[:6]})" for code in corr_matrix.columns]
    
    # 绘制热力图
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    sns.heatmap(corr_matrix, 
                #mask=mask,
                annot=True, 
                fmt='.2f',
                cmap='RdBu',
                #cmap='coolwarm',
                center=0,
                vmin=-1, vmax=1,
                xticklabels=etf_names,
                yticklabels=etf_names,
                square=True,
                cbar_kws={"shrink": 0.8})
    
    plt.title('ETF收益率相关性矩阵热力图', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.show()

def plot_price_trends(price_data, etf_pool):
    """
    绘制价格走势图
    """
    plt.figure(figsize=(14, 8))
    
    # 归一化价格（以起始日=100）
    normalized_prices = price_data / price_data.iloc[0] * 100
    
    for etf in price_data.columns:
        etf_info = etf_pool[etf]
        plt.plot(normalized_prices.index, 
                normalized_prices[etf], 
                label=f"{etf_info[0]} ({etf[:6]})",
                linewidth=2,
                alpha=0.8,
                color=etf_info[2] if len(etf_info) > 2 else None)
    
    plt.title('ETF价格走势（归一化）', fontsize=16, fontweight='bold')
    plt.xlabel('日期')
    plt.ylabel('归一化价格（起始日=100）')
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

def plot_scatter_matrix(returns_data, etf_pool, sample_size=100):
    """
    绘制散点矩阵图
    """
    if len(returns_data.columns) > 6:
        print("ETF数量过多，散点矩阵图可能过于密集，将展示前6个ETF")
        selected_etfs = returns_data.columns[:6]
        returns_data = returns_data[selected_etfs]
    
    # 创建带名称的列
    returns_named = returns_data.copy()
    returns_named.columns = [f"{etf_pool[code][0]}\n({code[:6]})" 
                           for code in returns_named.columns]
    
    # 随机抽样以避免过度密集
    if len(returns_named) > sample_size:
        returns_sample = returns_named.sample(sample_size, random_state=42)
    else:
        returns_sample = returns_named
    
    # 绘制散点矩阵图
    pd.plotting.scatter_matrix(returns_sample, 
                              figsize=(15, 15),
                              diagonal='hist',
                              hist_kwds={'bins': 20, 'alpha': 0.7},
                              density_kwds={'alpha': 0.5},
                              alpha=0.5,
                              s=20)
    
    plt.suptitle('ETF收益率散点矩阵图', fontsize=18, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.show()

def analyze_rolling_correlation(returns_data, etf_pool, window=60):
    """
    分析滚动相关性
    """
    if len(returns_data.columns) < 2:
        print("ETF数量不足，无法计算滚动相关性")
        return
    
    # 选择两个代表性ETF（例如第一和第二个）
    etf1 = returns_data.columns[0]
    etf2 = returns_data.columns[-1]
    
    # 计算滚动相关性
    rolling_corr = returns_data[etf1].rolling(window=window).corr(returns_data[etf2])

    # 绘制滚动相关性
    plt.figure(figsize=(12, 6))
    plt.plot(rolling_corr.index, rolling_corr.values, 
             linewidth=2, color='darkblue', alpha=0.8)
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    plt.axhline(y=rolling_corr.mean(), color='red', 
                linestyle='--', alpha=0.7, 
                label=f'平均相关性: {rolling_corr.mean():.3f}')
    
    plt.title(f'{etf_pool[etf1][0]} vs {etf_pool[etf2][0]} - {window}日滚动相关性', 
              fontsize=14, fontweight='bold')
    plt.xlabel('日期')
    plt.ylabel('滚动相关性')
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    # 统计信息
    print(f"\n滚动相关性统计 ({window}日窗口):")
    print(f"  均值: {rolling_corr.mean():.3f}")
    print(f"  标准差: {rolling_corr.std():.3f}")
    print(f"  最大值: {rolling_corr.max():.3f}")
    print(f"  最小值: {rolling_corr.min():.3f}")
    print(f"  当前值: {rolling_corr.iloc[-1]:.3f}")

def generate_stock_pool(etf_list):
    """手选 10 种高辨识度颜色，避开了人眼难分辨的蓝绿相近色"""
    manual_colors = [
        "#e6194b",  # 红
        "#3cb44b",  # 绿
        "#ffe119",  # 黄
        "#4363d8",  # 蓝
        "#f58231",  # 橙
        "#911eb4",  # 紫
        "#42d4f4",  # 青
        "#f032e6",  # 洋红
        "#9a6324",  # 棕
        "#800000",  # 深红
    ]

    etf_pool = {}
    for i, etf in enumerate(etf_list):
        stock = etf[0]
        name = etf[1]
        etf_pool[stock] = [name, 100, manual_colors[i]]

    return etf_pool
    
# 运行分析
if __name__ == "__main__":
    # 创建模拟的context对象（在聚宽环境中会自动提供）
    class MockContext:
        pass
    
    context = MockContext()
    

    # 定义ETF池（按照资产类别分组，同类资产使用相近色调）
    '''
    etf_pool = {
        # 宽基指数ETF - 蓝色系
        #'510300.XSHG': ['沪深300ETF', 100, '#1f77b4'],       # 深蓝色
        '512890.XSHG': ['红利低波ETF', 100, '#17becf'],       # 青色
        #'159920.XSHE': ['恒生ETF', 100, '#1c6cab'],          # 中蓝色

        # 海外市场ETF - 绿色系
        '159941.XSHE': ['纳指ETF', 100, '#2ca02c'],          # 绿色
        #'513500.XSHG': ['标普500ETF', 100, '#2e8b57'],       # 深绿色
        #'513520.XSHG': ['日经ETF', 100, '#3cb371'],          # 浅绿色
        #'513030.XSHG': ['德国ETF', 100, '#98fb98'],          # 淡绿色
        #'513080.XSHG': ['法国ETF', 100, '#90ee90'],          # 亮绿色

        # 商品类ETF - 金色系
        '518800.XSHG': ['黄金ETF', 100, '#ffd700'],          # 金色
        #'159980.XSHE': ['有色ETF', 100, '#daa520'],          # 金黄色
        '159985.XSHE': ['豆粕ETF', 100, '#b8860b'],          # 暗金色

        # 可转债ETF - 橙色系
        #'511180.XSHG': ['可转债ETF1', 100, '#ff7f0e'],       # 橙色
        #'511380.XSHG': ['可转债ETF2', 100, '#ff8c00'],       # 暗橙色

        # 利率债ETF - 紫色系
        #'511010.XSHG': ['国债ETF', 100, '#9467bd'],          # 紫色
        #'511520.XSHG': ['政金债ETF', 100, '#8a2be2'],        # 蓝紫色

        # 信用债ETF - 红色系
        '511220.XSHG': ['城投债ETF', 100, '#d62728'],        # 红色
        #'511360.XSHG': ['短融ETF', 100, '#ff4500'],          # 橙红色
    }
    '''
    
    '''
    etf_pool = {
        # 宽基指数ETF - 蓝色系
        #'510300.XSHG': ['沪深300ETF', 100, '#1f77b4'],       # 深蓝色
        '512890.XSHG': ['红利低波ETF', 100, '#8a2be2'],       # 蓝紫色
        #'510630.XSHG': ['消费30', 100, '#1c6cab'],          # 中蓝色
        #"159920.XSHE": ['恒生ETF', 100, '#1c6cab'],

        # 海外市场ETF - 绿色系
        '513100.XSHG': ['纳指ETF', 100, '#ff4500'],          # 绿色
        #'513500.XSHG': ['标普500ETF', 100, '#2e8b57'],       # 深绿色
        #'513520.XSHG': ['日经ETF', 100, '#3cb371'],          # 浅绿色
        #'513030.XSHG': ['德国ETF', 100, '#98fb98'],          # 淡绿色
        #'513080.XSHG': ['法国ETF', 100, '#90ee90'],          # 亮绿色

        # 商品类ETF - 金色系
        '518880.XSHG': ['黄金ETF', 100, '#ffd700'],          # 金色
        #'159980.XSHE': ['有色ETF', 100, '#daa520'],          # 金黄色
        '159985.XSHE': ['豆粕ETF', 100, '#b8860b'],          # 暗金色

        # 可转债ETF - 橙色系
        #'511180.XSHG': ['可转债ETF1', 100, '#ff7f0e'],       # 橙色
        #'511380.XSHG': ['可转债ETF2', 100, '#ff8c00'],       # 暗橙色
        

        # 利率债ETF - 紫色系
        #'511010.XSHG': ['国债ETF', 100, '#9467bd'],          # 紫色
        #'511520.XSHG': ['政金债ETF', 100, '#8a2be2'],        # 蓝紫色
        #'511260.XSHG': ['十年国债ETF', 100, '#8f671f']
        '511270.XSHG': ['10年地方债ETF', 100, '#8a2be2'],

        # 信用债ETF - 红色系
        '511220.XSHG': ['城投债ETF', 100, '#d62728'],        # 红色
        #'161115.XSHE': ['易基岁丰添利', 100, '#ff4500'],
        #'511360.XSHG': ['短融ETF', 100, '#ff4500'],          # 橙红色

        '600900.XSHG': ['长江电力', 100, '#17becf'],
        '601288.XSHG': ['农业银行', 100, '#90ee90']
        #'161706.XSHE': ['招商成长LOF', 100, '#d62728'],
        #'163415.XSHE': ['兴全商业模式', 100, '#ff7f0e'],
        #'501046.XSHG': ['财通福鑫', 100, '#ff4500'],
    }
    '''

    etf_list = [
               ['511220.XSHG', '城投ETF'],
               ['513100.XSHG', '纳指ETF'],
               #['513500.XSHG', '标普500'],
               ['512040.XSHG', '国信价值'],
               ['518880.XSHG', '黄金ETF'],
               ['159985.XSHE', '豆粕ETF华夏'],
               #['512890.XSHG', '红利低波'],
               ['513000.XSHG', '225ETF'],
               ['511270.XSHG', '10年地债'],
               ['600900.XSHG', '长江电力'],
               ['601225.XSHG', '陕西煤业'],
               ['000429.XSHE', '粤高速A'],
               ['601288.XSHG', '农业银行'],
               ['601899.XSHG', '紫金矿业'],
    ]
    
    etf_pool = {}
    stock_pool = generate_stock_pool(etf_list)
    for stock, value in stock_pool.items():
        etf_pool[stock] = value
    
    
    # 设置时间范围
    start_date = '2020-04-01'
    end_date = '2026-04-01'
    
    # 执行分析
    print("analyze_etf_correlation")
    analyze_etf_correlation(context, etf_pool, start_date, end_date)