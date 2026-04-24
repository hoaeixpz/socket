import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 3个CSV文件路径
csv_files = {
    #'result_zhai': os.path.join(current_dir, 'result_zhai.csv'),
    'result_small': os.path.join(current_dir, 'result_small.csv'),
    'result_quantianhou': os.path.join(current_dir, 'result_quantianhou.csv'),
}

def process_strategy(df, name):
    """
    处理单个策略数据，返回日期、每日收益率、策略收益
    """
    df = df.copy()
    df['日期'] = pd.to_datetime(df['时间']).dt.date
    df = df.sort_values('日期').reset_index(drop=True)
    
    # 计算每日收益率（基于策略收益列）
    strategy_returns = df['策略收益']/100
    daily_returns = strategy_returns.diff() / (1 + strategy_returns.shift(1))
    daily_returns.iloc[0] = float('nan')  # 第一天没有前日数据
    
    result = pd.DataFrame({
        '日期': df['日期'],
        f'{name}_每日收益率': daily_returns,
        f'{name}_策略收益': strategy_returns
    })
    return result

def merge_by_date(results, base_name='result_small'):
    """
    按日期对齐整合多个策略数据
    使用inner join，只保留所有策略都有数据的日期
    """
    merged_df = results[base_name]
    for name in results.keys():
        if name != base_name:
            merged_df = pd.merge(merged_df, results[name], on='日期', how='inner')
    merged_df = merged_df.sort_values('日期').reset_index(drop=True)
    return merged_df

def analyze_correlation(merged_df):
    """
    分析策略每日收益率之间的相关性，并绘制热力图
    """
    # 提取每日收益率列
    data = merged_df.filter(like='每日收益率').dropna()
    
    # 计算相关性矩阵
    corr_matrix = data.corr()
    
    print("=== 相关性矩阵 ===")
    print(corr_matrix.round(4))
    
    # 绘制热力图
    plt.figure(figsize=(8, 6))
    plt.imshow(corr_matrix, cmap='RdYlBu_r', vmin=-1, vmax=1, aspect='auto')
    plt.colorbar(label='Correlation')
    
    # 设置标签
    strategy_names = [col.replace('_每日收益率', '') for col in corr_matrix.columns]
    plt.xticks(range(len(strategy_names)), strategy_names, rotation=45)
    plt.yticks(range(len(strategy_names)), strategy_names)
    
    # 在每个格子中显示数值
    for i in range(len(corr_matrix)):
        for j in range(len(corr_matrix)):
            plt.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}', 
                    ha='center', va='center', color='black', fontsize=12)
    
    plt.title('Strategy Daily Returns Correlation Heatmap')
    plt.tight_layout()
    plt.show()
    
    return corr_matrix


def get_best_weights(merged_df, iter_num = 1000):
    risk_free = 0.04
    data = merged_df.filter(like='每日收益率')
    noa = len(data.columns)
    
    returns = data.dropna()
    print(data.head(10))
    print(returns.head(10))
    print("mean ", returns.mean())
    
    port_returns = []
    port_variance = []
    
    for p in range(iter_num):
        if p % 500 == 0:
            print("iter ",p)
        weights = np.random.random(noa)
        weights /=np.sum(weights)
        port_returns.append(np.sum(returns.mean()*252*weights))
        port_variance.append(np.sqrt(np.dot(weights.T, np.dot(returns.cov()*252, weights))))

    port_returns = np.array(port_returns)
    port_variance = np.array(port_variance)
    
    
    if iter_num != 0:
        plt.figure(figsize = (8,4))
        plt.scatter(port_variance, port_returns, c=(port_returns-risk_free)/port_variance, marker = 'o')
        #（ri-rf）/标准差，夏普比（c: 这是scatter()函数的颜色参数，通过 c 参数指定颜色映射，它使得每个点的颜色根据夏普比率的大小而变化。
        plt.grid(True)
        plt.xlim(-0.01, 0.3)
        plt.ylim(-risk_free * 2, 0.3)
        plt.xlabel('excepted volatility')
        plt.ylabel('expected return')
        plt.colorbar(label = 'Sharpe ratio')
    
    #最优化投资组合的推导是一个约束最优化问题
    import scipy.optimize as sco
    
    #约束是所有参数(权重)的总和为1。这可以用minimize函数的约定表达如下
    cons = ({'type':'eq', 'fun':lambda x: np.sum(x)-1})
    
    #我们还将参数值(权重)限制在0和1之间。这些值以多个元组组成的一个元组形式提供给最小化函数
    bnds = tuple((0,1) for x in range(noa))
    
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
    #print(stock_set)
    best_r = np.sum(returns.mean()*252*opts.x)
    best_var = np.sqrt(np.dot(opts.x.T, np.dot(returns.cov()*252, opts.x)))
    print(f"年化收益 {best_r} 年化标准差{best_var}")
    
    def min_variance(weights):
        return statistics(weights)[1]

    optv = sco.minimize(min_variance, noa*[1./noa,],method = 'SLSQP', bounds = bnds, constraints = cons)
    print("最优std权重")
    print(optv.x.round(3))
    #print(stock_set)
    best_r = np.sum(returns.mean()*252*optv.x)
    best_var = np.sqrt(np.dot(optv.x.T, np.dot(returns.cov()*252, optv.x)))
    print(f"年化收益 {best_r} 年化标准差{best_var}")
    
    return [opts.x.round(3), optv.x.round(3)]


# 读取并处理每个文件
results = {}

for name, filepath in csv_files.items():
    df = pd.read_csv(filepath, encoding='gbk')
    result = process_strategy(df, name)
    results[name] = result
    print(f"=== {name} ===")
    print(result[['日期', f'{name}_每日收益率']].head(10))
    print()

# 按日期对齐整合成一个DataFrame
merged_df = merge_by_date(results, 'result_small')

print("=== 整合后的DataFrame ===")
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
print(merged_df.head(20))
print()
print(merged_df.tail(20))
print(f"总行数: {len(merged_df)}")
print(f"日期范围: {merged_df['日期'].min()} ~ {merged_df['日期'].max()}")

# 计算每个策略的总体收益率
# 公式: R = ∏(1 + r_t) - 1，去除NaN值
print("\n=== 各策略总体收益率（每日收益率连乘法）===")
for name in csv_files.keys():
    col = f'{name}_每日收益率'
    daily_returns = merged_df[col].dropna()  # 去除NaN值
    total_return = (1 + daily_returns).prod() - 1
    print(f"{name}: {total_return:.4f} ({total_return*100:.2f}%)")

get_best_weights(merged_df, 10000)

analyze_correlation(merged_df)


