"""
股票 30 交易日滚动涨跌幅统计分析
用法: python stock_return_analysis.py 000001.SZ
"""
import sys
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
from datetime import datetime, timedelta

# xtquant 导入路径（QMT 安装目录）
# 尝试多个可能的 QMT 安装路径
_qmt_paths = [
    r'D:\国金证券QMT交易端\bin.x64\Lib\site-packages',
    r'C:\QMT\国金证券QMT交易端\bin.x64\Lib\site-packages',
    r'C:\QMT\bin.x64\Lib\site-packages',
]
for _p in _qmt_paths:
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from xtquant import xtdata


def get_stock_data(stock_code, years=5):
    """下载并返回 stock_code 过去 years 年的日K线数据（DataFrame），使用后复权价格"""
    xtdata.download_history_data(stock_code, period='1d', incrementally=True)

    end_date = datetime.now().strftime('%Y%m%d')

    raw = xtdata.get_market_data_ex(
        ['close'],
        [stock_code],
        period='1d',
        start_time='',
        end_time=end_date,
        count=years * 252,
        dividend_type='back'  # 后复权，消除分红拆分导致的价格跳空
    )

    df = raw[stock_code]
    if df is None or len(df) == 0:
        raise ValueError(f'未取到 {stock_code} 的历史数据')

    df = df.reset_index()
    df.columns = ['date', 'close']
    df['date'] = pd.to_datetime(df['date'], unit='s' if df['date'].dtype == 'int64' else None)
    df = df.dropna(subset=['close'])
    df = df.sort_values('date').reset_index(drop=True)
    return df


def calc_window_returns(df, window=30):
    """
    滚动窗口涨跌幅:
    (close[N+window] - close[N]) / close[N], 每个交易日 N 都算一次
    返回 DataFrame 含日期、涨跌幅、起止价格, 方便排查异常
    """
    rows = []
    for i in range(len(df) - window):
        p_start = df.loc[i, 'close']
        p_end = df.loc[i + window, 'close']
        ret = (p_end - p_start) / p_start
        rows.append({
            'start_date': df.loc[i, 'date'],
            'end_date': df.loc[i + window, 'date'],
            'start_price': p_start,
            'end_price': p_end,
            'return': ret,
        })
    return pd.DataFrame(rows)


def analyze_returns(returns):
    """统计分析: 最值、正态性检验"""
    arr = returns['return'].values
    stats_dict = {
        '样本数': len(arr),
        '最大值': np.max(arr),
        '最小值': np.min(arr),
        '均值': np.mean(arr),
        '标准差': np.std(arr, ddof=1),
        '75%分位数': np.percentile(arr, 75),
        '偏度': stats.skew(arr),
        '峰度': stats.kurtosis(arr),
    }

    # Shapiro-Wilk 正态性检验
    shapiro_stat, shapiro_p = stats.shapiro(arr)
    stats_dict['Shapiro-Wilk 统计量'] = shapiro_stat
    stats_dict['Shapiro-Wilk p值'] = shapiro_p
    stats_dict['符合正态分布'] = '是 (p >= 0.05)' if shapiro_p >= 0.05 else '否 (p < 0.05)'

    return stats_dict


def show_extreme_windows(returns, top_n=5):
    """打印极端涨跌幅窗口: 最大涨幅 top_n + 最大跌幅 top_n, 含日期和价格"""
    sorted_ret = returns.sort_values('return')

    print(f'  --- 最大跌幅 ({top_n} 个) ---')
    for _, row in sorted_ret.head(top_n).iterrows():
        print(f'  {row["start_date"].date()} ~ {row["end_date"].date()}  '
              f'{row["start_price"]:.3f} -> {row["end_price"]:.3f}  '
              f'{row["return"]*100:+.2f}%')

    print(f'\n  --- 最大涨幅 ({top_n} 个) ---')
    for _, row in sorted_ret.tail(top_n).iloc[::-1].iterrows():
        print(f'  {row["start_date"].date()} ~ {row["end_date"].date()}  '
              f'{row["start_price"]:.3f} -> {row["end_price"]:.3f}  '
              f'{row["return"]*100:+.2f}%')
    print()


def plot_distribution(returns, stock_code, output_dir=None):
    """画分布图: 直方图 + KDE + 正态拟合曲线, 保存 PNG"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei']
    plt.rcParams['axes.unicode_minus'] = False

    arr = returns['return'].values * 100  # 转为百分数
    fig, ax = plt.subplots(figsize=(10, 6))

    # 直方图
    ax.hist(arr, bins=20, density=True, alpha=0.6, color='steelblue', edgecolor='white',
            label='实际分布')

    # KDE 曲线
    kde = stats.gaussian_kde(arr)
    x = np.linspace(arr.min() * 1.2, arr.max() * 1.2, 200)
    ax.plot(x, kde(x), color='darkorange', linewidth=2, label='KDE 密度曲线')

    # 正态拟合曲线
    mu, sigma = np.mean(arr), np.std(arr, ddof=1)
    ax.plot(x, stats.norm.pdf(x, mu, sigma), '--', color='red', linewidth=2,
            label=f'正态拟合 (μ={mu:.2f}%, σ={sigma:.2f}%)')

    ax.set_title(f'{stock_code} 30交易日滚动涨跌幅分布', fontsize=14)
    ax.set_xlabel('涨跌幅 (%)')
    ax.set_ylabel('概率密度')
    ax.legend()
    ax.axvline(0, color='gray', linestyle=':', alpha=0.7)

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f'{stock_code.replace(".", "_")}_return_dist.png')
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return path


def main(stock_code):
    """主流程"""
    print(f'=== {stock_code} 30交易日滚动涨跌幅分析 ===\n')

    # 1. 取数据
    print('[1/4] 获取历史数据...')
    df = get_stock_data(stock_code)
    print(f'      共 {len(df)} 条日K线, 时间范围 {df["date"].min().date()} ~ {df["date"].max().date()}\n')

    # 2. 算涨跌幅
    print('[2/4] 计算 30 交易日滚动涨跌幅...')
    returns = calc_window_returns(df, window=30)
    print(f'      共 {len(returns)} 个窗口\n')

    # 3. 统计分析
    print('[3/4] 统计分析...')
    result = analyze_returns(returns)
    for k, v in result.items():
        if isinstance(v, float):
            print(f'      {k}: {v:.4f}')
        else:
            print(f'      {k}: {v}')
    print()

    # 3.5 极端窗口明细
    print('[3.5/4] 极端涨跌幅窗口...')
    show_extreme_windows(returns)
    print()

    # 4. 画图
    print('[4/4] 绘制分布图...')
    img_path = plot_distribution(returns, stock_code)
    print(f'      图片已保存: {img_path}')
    print('\n=== 分析完成 ===')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python stock_return_analysis.py <股票代码>')
        print('示例: python stock_return_analysis.py 000001.SZ')
        sys.exit(1)

    main(sys.argv[1])
