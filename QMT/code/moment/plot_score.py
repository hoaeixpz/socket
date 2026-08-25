# 动量得分曲线绘制
# 目的：计算每只ETF的短期(25天)动量得分，超出阈值的分数不参与排序（按0算）但按真实值画，并把所有ETF的得分画成曲线汇总到一张图
# 用法：python plot_score.py

from xtquant import xtdata
import numpy as np
import pandas as pd
from datetime import datetime
import math
import os
import matplotlib
matplotlib.use('Agg')  # 无GUI后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import PercentFormatter

# matplotlib 中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ================================================================
# 配置
# ================================================================

ETF_POOL = [
    "513100.SH",  # 纳指ETF
    "513520.SH",  # 日经ETF
    "513030.SH",  # 德国ETF
    "518880.SH",  # 黄金ETF
    "159980.SZ",  # 有色ETF
    "159985.SZ",  # 豆粕ETF
    #"501018.SH",  # 南方原油
    "511090.SH",  # 30年国债ETF
    #"513130.SH",  # 恒生科技
    #"515980.SH",  # 人工智能
]

ETF_SHORT_MAX = {  # 短期(25天)上限，得分 >= 上限即淘汰（归零）
    "513100.SH": 3,  # 纳指ETF
    "513520.SH": 3,  # 日经ETF
    "513030.SH": 2,  # 德国ETF
    "518880.SH": 2,  # 黄金ETF
    "159980.SZ": 2,  # 有色ETF
    "159985.SZ": 3,  # 豆粕ETF
    "501018.SH": 9,  # 南方原油
    "511090.SH": 1,  # 30年国债ETF
    "513130.SH": 8,  # 恒生科技
    "515980.SH": 10,  # 人工智能
}

SAFE_ETF = '511880.SH'

# ETF代码 -> 中文名，用于图例显示
ETF_NAMES = {
    "513100.SH": "纳指ETF",
    "513520.SH": "日经ETF",
    "513030.SH": "德国ETF",
    "518880.SH": "黄金ETF",
    "159980.SZ": "有色ETF",
    "159985.SZ": "豆粕ETF",
    "501018.SH": "南方原油",
    "511090.SH": "30年国债ETF",
    "513130.SH": "恒生科技",
    "515980.SH": "人工智能",
}

SHORT_DAYS = 25
START_DATE = '20200101'  # 分析起点
END_DATE = '20260823'

# 未在 ETF_SHORT_MAX 中单独配置的ETF，回退使用该全局阈值
CURRENT_SHORT_MAX = 6.0

# 输出目录
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
PLOT_DIR = os.path.join(OUTPUT_DIR, 'plots')
os.makedirs(PLOT_DIR, exist_ok=True)

# 图片横向密度：每个交易日占多少英寸（值越小图越宽、越不挤）
FIG_DAYS_PER_INCH = 4


# ================================================================
# 1. 数据下载
# ================================================================

def download_all_data():
    """一次性下载所有ETF从2020年至今的全部日线数据"""
    print("=" * 60)
    print("Step 1: 下载历史数据...")
    all_data = {}
    for etf in ETF_POOL:
        print(f"  下载 {etf} ...", end=' ')
        xtdata.download_history_data(etf, period='1d', start_time=START_DATE, end_time='')
        history = xtdata.get_market_data_ex(
            ['close'],
            [etf],
            period='1d',
            start_time=START_DATE,
            end_time=END_DATE,
            dividend_type='front',
            count=-1  # 全部数据
        )
        if etf in history and not history[etf].empty:
            closes = history[etf]['close']
            all_data[etf] = closes
            print(f"{len(closes)} 条 (起止: {closes.index[0]} ~ {closes.index[-1]})")
        else:
            print(f"无数据，跳过")
    print(f"  共 {len(all_data)} 只ETF有数据\n")
    return all_data


def calc_score_from_prices(prices):
    """纯数学计算：给定价格序列，返回 (annualized_return, r2, score, min_recent_ratio)

    与原版 calc_momentum_score 逻辑一致，但不依赖 xtdata / get_last_price。
    prices 应为最近 N 天的收盘价（按时间升序）。
    """
    if len(prices) < 4:
        return 0, 0, 0, 1.0

    y = np.log(prices)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))

    slope, intercept = np.polyfit(x, y, 1, w=weights)

    annualized_return = math.exp(slope * 250) - 1

    weighted_mean_y = np.average(y, weights=weights)
    #weighted_mean_y = y.mean()
    ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
    ss_tot = np.sum(weights * (y - weighted_mean_y) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    score = annualized_return * r2

    # 近3日最大跌幅（ratio < 1 表示下跌）
    recent_ratios = [prices[-1] / prices[-2], prices[-2] / prices[-3], prices[-3] / prices[-4]]
    min_ratio = min(recent_ratios)

    return annualized_return, r2, score, min_ratio


# ================================================================
# 2. 逐日滚动计算得分
# ================================================================

def compute_all_scores(all_data):
    """遍历所有交易日，计算每只ETF的短期动量得分"""
    print("=" * 60)
    print("Step 2: 逐日计算短期动量得分...")

    rows = []

    for etf, closes in all_data.items():
        dates = closes.index.tolist()
        # 从第 SHORT_DAYS 天开始（确保短期窗口有足够数据）
        for i in range(SHORT_DAYS, len(dates)):
            date = dates[i]
            # 短期：最近 SHORT_DAYS 天
            short_prices = closes.iloc[i - SHORT_DAYS + 1: i + 1].values
            s_annret, s_r2, s_score, s_dip = calc_score_from_prices(short_prices)

            rows.append({
                'date': date,
                'etf': etf,
                'short_score': s_score,
                'short_annret': s_annret,
                'short_r2': s_r2,
                'short_dip': s_dip,
            })

        print(f"  {etf}: {len(dates) - SHORT_DAYS} 个有效交易日")

    df = pd.DataFrame(rows)
    # xtdata 的 index 是原始整数时间戳，需转成真正的 datetime，否则画图横轴会显示成 1970
    df['date'] = pd.to_datetime(df['date'])
    print(f"  总计 {len(df)} 条记录，日期范围 {df['date'].min()} ~ {df['date'].max()}\n")
    return df


def apply_threshold(df):
    """计算排序分数 rank_score：满足淘汰条件的置 0（不参与 topN 排序），否则等于真实分。

    淘汰条件（二者任一即淘汰）：
      1. 分数超出阈值（ETF_SHORT_MAX，未配置回退 CURRENT_SHORT_MAX）
      2. 连续两天下跌：当日 < 昨日 < 前日
    short_score 保持真实值不变（画图用），rank_score 用于确定 topN（排序用）。
    """
    print("=" * 60)
    print("Step 3: 计算排序分数（淘汰条件：超阈值 / 连续两天下跌）...")
    df = df.copy()
    df['rank_score'] = df['short_score']

    # 条件1：分数超出阈值
    for etf in df['etf'].unique():
        max_score = ETF_SHORT_MAX.get(etf, CURRENT_SHORT_MAX)
        mask = (df['etf'] == etf) & (df['short_score'] >= max_score)
        n_zeroed = int(mask.sum())
        if n_zeroed > 0:
            df.loc[mask, 'rank_score'] = 0.0
            print(f"  {etf}: 阈值={max_score}, 超阈值归零 {n_zeroed} 条")

    # 条件2：连续两天下跌（当日 < 昨日 < 前日）
    df = df.sort_values(['etf', 'date'])
    prev1 = df.groupby('etf')['short_score'].shift(1)   # 昨日
    prev2 = df.groupby('etf')['short_score'].shift(2)   # 前日
    decline2 = (df['short_score'] < prev1) & (prev1 < prev2)
    n_decline = int(decline2.sum())
    if n_decline > 0:
        df.loc[decline2, 'rank_score'] = 0.0
        print(f"  连续两天下跌（当日<昨日<前日）归零: {n_decline} 条")

    print()
    return df


# ================================================================
# 3. 绘制得分曲线
# ================================================================

def plot_scores(df, top_n_list=(1, 2)):
    """上下两个子图分别绘制每日 top1 和 top2 的得分曲线。

    每天取当日得分前 top_n 名的ETF画成曲线：不在前 top_n 的日子用 NaN 断开。
    top_n_list 控制子图数量与各自的排名档位（上→下）。
    同一只ETF在所有子图中颜色保持一致（全局颜色映射）。
    """
    print("=" * 60)
    print(f"Step 4: 绘制得分曲线（top{list(top_n_list)} 上下子图）...")

    n_rows = len(top_n_list)

    # 全量真实得分宽表（index=日期, columns=ETF, 值=得分），所有ETF每个交易日都有分
    score_all = df.pivot_table(index='date', columns='etf', values='short_score', aggfunc='first')

    # 先按各档位统计每只ETF进入前 N 的天数，并汇总出全局ETF全集与总出现天数
    tops = {}       # top_n -> (该档位的 top 数据, 各ETF进入前 N 的天数 Series)
    all_etfs = set()
    total_days = {}
    for top_n in top_n_list:
        top = df.sort_values('rank_score', ascending=False).groupby('date').head(top_n)
        #print(f"top_n: {top_n}")
        #print(top)
        appear_days = top.groupby('etf').size()
        tops[top_n] = (top, appear_days)
        all_etfs.update(appear_days.index.tolist())
        for etf, days in appear_days.items():
            total_days[etf] = total_days.get(etf, 0) + days

    # 全局颜色映射：按总出现天数降序（相同则按代码）固定分配，跨子图一致
    etfs_global = sorted(all_etfs, key=lambda e: (-total_days.get(e, 0), e))
    global_colors = plt.cm.tab20(np.linspace(0, 1, max(len(etfs_global), 1)))
    color_map = {etf: global_colors[i] for i, etf in enumerate(etfs_global)}

    # 宽度随交易日数量自适应，避免时间太长挤在一起
    fig_w = max(16, df['date'].nunique() / FIG_DAYS_PER_INCH)
    fig, axes = plt.subplots(n_rows, 1, figsize=(fig_w, 9 * n_rows), sharex=True)
    if n_rows == 1:
        axes = [axes]

    for ax, top_n in zip(axes, top_n_list):
        top, appear_days = tops[top_n]
        appear_days = appear_days.sort_values(ascending=False)

        # 每天 topN 的成员布尔宽表（True=该ETF当日在前 top_n）
        member = top.pivot_table(index='date', columns='etf', values='short_score', aggfunc='first').notna()
        member = member.reindex(score_all.index)
        # 退出前 top_n 后延迟一天再消失：昨天在前 top_n 的，今天也画（用当日真实得分），
        # 避免切换ETF时曲线之间出现空隙、看起来断断续续
        member_ext = member | member.shift(1, fill_value=False)
        wide = score_all.where(member_ext)

        print(f"  [top{top_n}] 各ETF进入前{top_n}的天数:")
        for etf, days in appear_days.items():
            print(f"    {etf}: {days} 天")
        etfs_in_legend = appear_days.index.tolist()

        for etf in etfs_in_legend:
            name = ETF_NAMES.get(etf, '')
            label = f"{etf} {name}" if name else etf
            ax.plot(wide.index, wide[etf],
                    label=label, color=color_map[etf], linewidth=1.6, alpha=0.95)

        ax.axhline(0, color='black', linewidth=0.8, linestyle='-')
        ax.set_title(f'每日排名前{top_n}', fontsize=13)
        ax.set_ylabel('短期得分', fontsize=11)
        ax.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0), fontsize=9, ncol=1)
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel('日期', fontsize=12)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    for ax in axes:
        plt.setp(ax.get_xticklabels(), rotation=45)

    fig.suptitle('短期动量得分曲线 (25天窗口, 超出阈值不参与排序、按真实值画)', fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    out_path = os.path.join(PLOT_DIR, 'score_top1_top2_daily.png')
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已保存: {out_path}\n")
    return out_path


def main():
    print(f"\n{'=' * 60}")
    print(f"  动量得分曲线")
    print(f"  起始日期: {START_DATE}")
    print(f"  短期窗口: {SHORT_DAYS}天")
    print(f"  阈值: 各ETF见 ETF_SHORT_MAX, 默认={CURRENT_SHORT_MAX}")
    print(f"{'=' * 60}\n")

    # 1. 下载数据
    all_data = download_all_data()

    # 2. 计算得分
    df = compute_all_scores(all_data)

    # 3. 分数超出阈值归零
    df = apply_threshold(df)

    # 4. 绘制曲线（上：top1，下：top2）
    plot_scores(df, (1, 2))


if __name__ == '__main__':
    main()
