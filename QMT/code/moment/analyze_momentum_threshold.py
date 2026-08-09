# 动量得分阈值统计分析
# 目的：统计过去几年的短/长期动量得分分布，为 max_score 阈值（当前短期=6, 长期=0.5）提供数据支撑
# 用法：python analyze_momentum_threshold.py

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
    "501018.SH",  # 南方原油
    "511090.SH",  # 30年国债ETF
    "513130.SH",  # 恒生科技
    "515980.SH",  # 人工智能
]

SAFE_ETF = '511880.SH'

SHORT_DAYS = 25
LONG_DAYS = 250
START_DATE = '20200101'  # 分析起点

# 当前使用的经验阈值
CURRENT_SHORT_MAX = 6.0
CURRENT_LONG_MAX = 0.5

# 尖峰检测阈值：得分超过此值视为"异常突起"（默认各ETF自用P97）
SPIKE_THRESHOLD = None  # None = 每只ETF用各自的 P97

# 输出目录
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
PLOT_DIR = os.path.join(OUTPUT_DIR, 'plots')
os.makedirs(PLOT_DIR, exist_ok=True)

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
            end_time='',
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
    """遍历所有交易日，计算每只ETF的短期和长期动量得分"""
    print("=" * 60)
    print("Step 2: 逐日计算动量得分...")

    rows = []
    total_combos = 0

    for etf, closes in all_data.items():
        dates = closes.index.tolist()
        # 从第 LONG_DAYS 天开始（确保短期和长期都有足够数据）
        for i in range(LONG_DAYS, len(dates)):
            date = dates[i]
            # 短期：最近 SHORT_DAYS 天
            short_prices = closes.iloc[i - SHORT_DAYS + 1 : i + 1].values
            s_annret, s_r2, s_score, s_dip = calc_score_from_prices(short_prices)
            # 长期：最近 LONG_DAYS 天
            long_prices = closes.iloc[i - LONG_DAYS + 1 : i + 1].values
            l_annret, l_r2, l_score, l_dip = calc_score_from_prices(long_prices)

            rows.append({
                'date': date,
                'etf': etf,
                'short_score': s_score,
                'short_annret': s_annret,
                'short_r2': s_r2,
                'short_dip': s_dip,
                'long_score': l_score,
                'long_annret': l_annret,
                'long_r2': l_r2,
                'long_dip': l_dip,
            })
            total_combos += 1

        print(f"  {etf}: {len(dates) - LONG_DAYS} 个有效交易日")

    df = pd.DataFrame(rows)
    print(f"  总计 {len(df)} 条记录，日期范围 {df['date'].min()} ~ {df['date'].max()}\n")
    return df


# ================================================================
# 3. 统计分析
# ================================================================

def percentile_table(series, name, current_threshold):
    """打印分位数表格，并标注当前阈值所在位置"""
    percentiles = [1, 5, 10, 25, 50, 75, 80, 85, 90, 95, 99]
    values = np.percentile(series.dropna(), percentiles)

    # 计算当前阈值对应的分位数
    pct_current = (series < current_threshold).mean() * 100

    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")
    print(f"  样本数: {len(series.dropna()):,}")
    print(f"  均值: {series.mean():.4f}  标准差: {series.std():.4f}")
    print(f"  最小值: {series.min():.4f}  最大值: {series.max():.4f}")
    print()

    header = "".join(f"  P{p:>2}" for p in percentiles)
    print(f"  {header}")
    vals = "".join(f"  {v:>4.2f}" for v in values)
    print(f"  {vals}")
    print()
    print(f"  ★ 当前阈值 {current_threshold} 对应分位数: {pct_current:.1f}% "
          f"(即约 {100 - pct_current:.1f}% 的样本会被上限淘汰)")
    print(f"  ★ P90 = {np.percentile(series.dropna(), 90):.4f}")
    print(f"  ★ P95 = {np.percentile(series.dropna(), 95):.4f}")
    print(f"  ★ P99 = {np.percentile(series.dropna(), 99):.4f}")

    return values, percentiles, pct_current


def analyze(df):
    """完整的统计分析"""
    print("=" * 60)
    print("Step 3: 统计分析")

    # ---- 全量统计 ----
    short_stats = percentile_table(df['short_score'], "短期动量得分 (25天) 全量分布", CURRENT_SHORT_MAX)
    long_stats = percentile_table(df['long_score'], "长期动量得分 (250天) 全量分布", CURRENT_LONG_MAX)

    # ---- 按 ETF 分别统计 ----
    print(f"\n{'=' * 60}")
    print("  按ETF分别统计短期得分 (当前阈值 {:.1f})".format(CURRENT_SHORT_MAX))
    print(f"{'─' * 60}")
    for etf in ETF_POOL:
        sub = df[df['etf'] == etf]['short_score']
        if len(sub) == 0:
            continue
        p90 = np.percentile(sub, 90)
        p95 = np.percentile(sub, 95)
        pct = (sub < CURRENT_SHORT_MAX).mean() * 100
        label = _get_etf_label(etf)
        print(f"  {label:>12s}: 均值={sub.mean():6.4f}  P90={p90:6.4f}  P95={p95:6.4f}  淘汰率={100-pct:.1f}%")

    print(f"\n  按ETF分别统计长期得分 (当前阈值 {CURRENT_LONG_MAX})")
    print(f"{'─' * 60}")
    for etf in ETF_POOL:
        sub = df[df['etf'] == etf]['long_score']
        if len(sub) == 0:
            continue
        p90 = np.percentile(sub, 90)
        p95 = np.percentile(sub, 95)
        pct = (sub < CURRENT_LONG_MAX).mean() * 100
        label = _get_etf_label(etf)
        print(f"  {label:>12s}: 均值={sub.mean():6.4f}  P90={p90:6.4f}  P95={p95:6.4f}  淘汰率={100-pct:.1f}%")

    return short_stats, long_stats


# ================================================================
# 4. 画图
# ================================================================

def _clip_scores(series):
    """裁掉极端值 (P0.5~P99.5) 提高直方图可读性，返回 (clipped_array, p90, p95)"""
    clean = series.dropna()
    lo, hi = np.percentile(clean, [0.5, 99.5])
    clipped = clean[(clean >= lo) & (clean <= hi)]
    p90 = np.percentile(clean, 90)
    p95 = np.percentile(clean, 95)
    return clipped, p90, p95


def _draw_hist_with_refs(ax, data, title, threshold, p90, p95, color_hist, color_thresh):
    """在一张图上画直方图 + 阈值参考线"""
    ax.hist(data, bins=80, color=color_hist, alpha=0.7, edgecolor='white')
    ax.axvline(threshold, color=color_thresh, linewidth=2, linestyle='--',
               label=f'当前阈值={threshold}')
    ax.axvline(p90, color='orange', linewidth=1.5, linestyle=':',
               label=f'P90={p90:.3f}')
    ax.axvline(p95, color='red', linewidth=1.5, linestyle=':',
               label=f'P95={p95:.3f}')
    ax.set_title(title)
    ax.set_ylabel('频次')
    ax.legend(fontsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))


def _draw_cdf(ax, data, title, threshold, p90, p95, color_hist, color_thresh):
    """画累计分布图 (CDF)"""
    ax.hist(data, bins=80, cumulative=True, color=color_hist, alpha=0.7,
            edgecolor='white', density=True)
    ax.axvline(threshold, color=color_thresh, linewidth=2, linestyle='--')
    ax.axhline(0.9, color='orange', linewidth=1, linestyle=':')
    ax.axhline(0.95, color='red', linewidth=1, linestyle=':')
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_title(title)
    ax.set_xlabel('得分')


def plot_distributions(df):
    """画得分分布直方图 + 累计分布图"""
    print("\n" + "=" * 60)
    print("Step 4: 画图...")

    # 准备数据
    s_clipped, s_p90, s_p95 = _clip_scores(df['short_score'])
    l_clipped, l_p90, l_p95 = _clip_scores(df['long_score'])

    df_no_dip = df[df['short_dip'] >= 0.95]
    nd_clipped, nd_p90, nd_p95 = _clip_scores(
        df_no_dip['short_score'] if len(df_no_dip) > 0 else df['short_score']
    )

    # 2行 × 3列 总布局
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('动量得分分布统计', fontsize=16, fontweight='bold')

    # Row 0: 短期动量
    _draw_hist_with_refs(axes[0][0], s_clipped,
                         f'短期动量得分 (25天, N={len(df):,})',
                         CURRENT_SHORT_MAX, s_p90, s_p95, 'steelblue', 'darkblue')
    _draw_cdf(axes[0][1], s_clipped,
              f'短期动量得分 — 累计分布 CDF',
              CURRENT_SHORT_MAX, s_p90, s_p95, 'steelblue', 'darkblue')
    _draw_hist_with_refs(axes[0][2], nd_clipped,
                         f'短期 排除近3日急跌>5% (N={len(df_no_dip):,})',
                         CURRENT_SHORT_MAX, nd_p90, nd_p95, 'mediumseagreen', 'darkgreen')

    # Row 1: 长期动量 + 散点图
    _draw_hist_with_refs(axes[1][0], l_clipped,
                         f'长期动量得分 (250天, N={len(df):,})',
                         CURRENT_LONG_MAX, l_p90, l_p95, 'coral', 'darkred')
    _draw_cdf(axes[1][1], l_clipped,
              f'长期动量得分 — 累计分布 CDF',
              CURRENT_LONG_MAX, l_p90, l_p95, 'coral', 'darkred')

    # 散点: 短期 vs 长期
    ax_scatter = axes[1][2]
    sample = df.sample(min(5000, len(df))) if len(df) > 5000 else df
    ax_scatter.scatter(sample['short_score'], sample['long_score'], alpha=0.3, s=2, color='purple')
    ax_scatter.axvline(CURRENT_SHORT_MAX, color='darkblue', linewidth=1, linestyle='--', alpha=0.5)
    ax_scatter.axhline(CURRENT_LONG_MAX, color='darkred', linewidth=1, linestyle='--', alpha=0.5)
    ax_scatter.set_xlabel('短期得分')
    ax_scatter.set_ylabel('长期得分')
    ax_scatter.set_title(f'短期 vs 长期得分 (抽样 N={len(sample)})')

    plt.tight_layout()
    path = os.path.join(PLOT_DIR, 'score_distribution.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    print(f"  已保存: {path}")
    plt.close(fig)


def plot_by_etf(df):
    """按ETF分别画短期/长期得分分布（箱线图）"""
    print("  画ETF对比图...")

    fig, axes = plt.subplots(2, 1, figsize=(16, 8))

    for idx, (col, title, threshold) in enumerate([
        ('short_score', '短期动量得分 (25天)', CURRENT_SHORT_MAX),
        ('long_score', '长期动量得分 (250天)', CURRENT_LONG_MAX),
    ]):
        ax = axes[idx]
        etf_list = []
        data_list = []
        for etf in ETF_POOL:
            sub = df[df['etf'] == etf][col].dropna()
            if len(sub) == 0:
                continue
            etf_list.append(etf)
            lo, hi = np.percentile(sub, [1, 99])
            data_list.append(sub[(sub >= lo) & (sub <= hi)].values)

        bp = ax.boxplot(data_list, tick_labels=etf_list, patch_artist=True, showfliers=True,
                        flierprops=dict(marker='o', markersize=2, alpha=0.3))
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
            patch.set_alpha(0.7)
        ax.axhline(threshold, color='red', linewidth=1.5, linestyle='--',
                   label=f'当前阈值={threshold}')
        ax.set_title(title)
        ax.legend()
        ax.tick_params(axis='x', rotation=30)

    plt.tight_layout()
    path = os.path.join(PLOT_DIR, 'score_by_etf.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    print(f"  已保存: {path}")
    plt.close(fig)


def _get_etf_label(etf):
    """返回 '代码 名称' 作为图标题"""
    detail = xtdata.get_instrument_detail(etf)
    name = detail['InstrumentName'] if detail else None
    if '恒生科技' in name:
        name = '恒生科技ETF'
    if '人工智能' in name:
        name = '人工智能ETF'
    return f'{etf} {name}' if name else etf


def plot_score_timeseries(df):
    """画每只ETF的得分时序图（短期 + 长期各一张）"""
    for score_col, threshold, label, filename in [
        ('short_score', CURRENT_SHORT_MAX, '短期动量得分 (25天)', 'score_timeseries_short.png'),
        ('long_score',  CURRENT_LONG_MAX,  '长期动量得分 (250天)', 'score_timeseries_long.png'),
    ]:
        print(f"  画{label}时序图...")

        n = len(ETF_POOL)
        cols = 2
        rows = (n + 1) // 2
        fig, axes = plt.subplots(rows, cols, figsize=(16, 3 * rows))
        axes_flat = axes.flatten() if isinstance(axes, np.ndarray) else [axes]

        y_max = threshold * 1.5
        last_i = -1
        for i, etf in enumerate(ETF_POOL):
            ax = axes_flat[i]
            sub = df[df['etf'] == etf]
            if len(sub) == 0:
                ax.set_visible(False)
                continue
            last_i = i
            scores = sub[score_col].values
            clipped = np.clip(scores, None, y_max)
            ax.plot(pd.to_datetime(sub['date']), clipped, linewidth=0.5, alpha=0.8, color='steelblue')
            exceed = scores > y_max
            if exceed.any():
                ax.scatter(pd.to_datetime(sub['date'][exceed]), [y_max] * exceed.sum(),
                           color='red', s=3, alpha=0.5, marker='^')
            ax.axhline(threshold, color='red', linewidth=1, linestyle='--')
            ax.set_ylim(None, y_max)
            ax.set_title(_get_etf_label(etf), fontsize=9)
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            ax.tick_params(labelsize=7)
        for j in range(last_i + 1, len(axes_flat)):
            axes_flat[j].set_visible(False)

        plt.suptitle(f'{label}时序', fontsize=14, fontweight='bold')
        plt.tight_layout()
        path = os.path.join(PLOT_DIR, filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"  已保存: {path}")
        plt.close(fig)


def plot_per_etf_histograms(df):
    """每只ETF单独画短/长期得分的直方图"""
    print("  画每只ETF直方图...")

    for etf in ETF_POOL:
        sub = df[df['etf'] == etf]
        if len(sub) == 0:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        label = _get_etf_label(etf)

        for ax, col, days, threshold in [
            (axes[0], 'short_score', 25, CURRENT_SHORT_MAX),
            (axes[1], 'long_score', 250, CURRENT_LONG_MAX),
        ]:
            clipped, p90, p95 = _clip_scores(sub[col])
            _draw_hist_with_refs(ax, clipped,
                                 f'{label}   {days}天动量', threshold,
                                 p90, p95, 'steelblue', 'red')

        plt.tight_layout()
        safe_name = etf.replace('.', '_')
        path = os.path.join(PLOT_DIR, f'hist_{safe_name}.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)

    print(f"  已保存 {len(ETF_POOL)} 张直方图")


# ================================================================
# 4.5 日跌幅分析 — 验证策略中 "近3日跌幅>5%" 过滤参数的合理性
# ================================================================

DIP_THRESHOLDS = [0.03, 0.04, 0.05, 0.06, 0.07]  # 待评估的跌幅阈值


def analyze_daily_returns(all_data):
    """统计每只ETF的日跌幅分布，评估 5% 阈值在各 ETF 上的合理性。"""
    print("\n" + "=" * 60)
    print("Step 4.5: 日跌幅分析 — 评估 5% 过滤阈值")

    rows = []
    for etf in ETF_POOL:
        closes = all_data.get(etf)
        if closes is None or len(closes) < 2:
            continue
        daily_ret = closes.pct_change().dropna()
        neg_ret = daily_ret[daily_ret < 0]
        total = len(daily_ret)

        row = {'etf': etf, 'total': total}
        for th in DIP_THRESHOLDS:
            count = (neg_ret < -th).sum()
            row[f'dip_{int(th*100)}pct'] = count
        row['p90'] = np.percentile(neg_ret, 90) * 100
        row['p95'] = np.percentile(neg_ret, 95) * 100
        row['p99'] = np.percentile(neg_ret, 99) * 100
        row['max_drop'] = neg_ret.min() * 100
        row['all_rets'] = daily_ret.values
        rows.append(row)

    # 表格
    print(f"\n  {'ETF':>12s}  {'样本':>5s}  {'P90':>7s}  {'P95':>7s}  {'P99':>7s}  {'最大':>7s}  "
          + "".join(f"  {'跌' + str(int(t*100)) + '%':>6s}" for t in DIP_THRESHOLDS))
    print(f"  {'─' * 110}")
    for r in rows:
        label = _get_etf_label(r['etf'])
        print(f"  {label:>12s}  {r['total']:>5d}  {r['p90']:>+6.1f}%  {r['p95']:>+6.1f}%  "
              f"{r['p99']:>+6.1f}%  {r['max_drop']:>+6.1f}%  "
              + "".join(f"  {r[f'dip_{int(t*100)}pct']:>5d}" for t in DIP_THRESHOLDS))

    # 全量汇总
    all_negs = np.concatenate([r['all_rets'] for r in rows])
    all_negs = all_negs[all_negs < 0]
    all_total = sum(r['total'] for r in rows)
    print(f"  {'─' * 110}")
    print(f"  {'[全部]':>12s}  {all_total:>5d}  {'':>7s}  {'':>7s}  {'':>7s}  {'':>7s}  "
          + "".join(f"  {(all_negs < -t).sum():>5d}" for t in DIP_THRESHOLDS)
          + f"  (合计 {len(all_negs)} 个负收益样本)")

    print(f"\n  ★ 当前策略阈值: 5%，全量触发率 = {(all_negs < -0.05).sum() / all_total * 100:.2f}%")
    print(f"  ★ 若改为 3%，触发率 = {(all_negs < -0.03).sum() / all_total * 100:.2f}%")
    print(f"  ★ 若改为 7%，触发率 = {(all_negs < -0.07).sum() / all_total * 100:.2f}%")

    return rows


def plot_daily_return_dist(all_data):
    """画全量日收益分布直方图 + 按ETF分面直方图"""
    print("  画日收益分布图...")

    all_rets = []
    for etf in ETF_POOL:
        closes = all_data.get(etf)
        if closes is None or len(closes) < 2:
            continue
        daily_ret = closes.pct_change().dropna()
        all_rets.append(daily_ret.values)

    # 图1: 全量叠加
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    fig.suptitle('日收益率分布 — 评估5%跌幅阈值', fontsize=14, fontweight='bold')

    ax = axes[0]
    all_flat = np.concatenate(all_rets) * 100
    lo, hi = np.percentile(all_flat, [0.5, 99.5])
    clipped = all_flat[(all_flat >= lo) & (all_flat <= hi)]
    ax.hist(clipped, bins=120, color='steelblue', alpha=0.7, edgecolor='white')
    for th, color in zip(DIP_THRESHOLDS, ['orange', 'gold', 'red', 'darkred', 'maroon']):
        ax.axvline(-th * 100, color=color, linewidth=1.5, linestyle='--',
                   label=f'{int(th*100)}% (触发 {(all_flat < -th*100).sum()}次)')
    ax.set_title(f'全部ETF日收益分布 (N={len(all_flat):,})')
    ax.set_xlabel('日收益率 (%)')
    ax.set_ylabel('频次')
    ax.legend(fontsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # 图2: 按ETF分面（各ETF的负收益部分）
    ax = axes[1]
    colors = plt.cm.tab10(np.linspace(0, 1, len(ETF_POOL)))
    for i, etf in enumerate(ETF_POOL):
        closes = all_data.get(etf)
        if closes is None or len(closes) < 2:
            continue
        daily_ret = closes.pct_change().dropna() * 100
        neg = daily_ret[daily_ret < 0]
        # 只画负值部分的 KDE 近似（直方图太密改用密度曲线）
        if len(neg) > 10:
            ax.hist(neg, bins=60, density=True, alpha=0.3, color=colors[i],
                    histtype='stepfilled', label=_get_etf_label(etf))
    for th, color in zip(DIP_THRESHOLDS, ['orange', 'gold', 'red', 'darkred', 'maroon']):
        ax.axvline(-th * 100, color=color, linewidth=1, linestyle='--', alpha=0.7)
    ax.set_title('各ETF负日收益分布 (密度)')
    ax.set_xlabel('日收益率 (%)')
    ax.set_ylabel('密度')
    ax.legend(fontsize=6, ncol=2)
    ax.set_xlim(-12, 0)

    plt.tight_layout()
    path = os.path.join(PLOT_DIR, 'daily_return_dist.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    print(f"  已保存: {path}")
    plt.close(fig)


# ================================================================
# 5. 尖峰检测 & 事后收益分析
# ================================================================

POST_SPIKE_WINDOWS = [5, 10, 20, 40, 60]  # 尖峰结束后N日的收益窗口


def detect_spikes(df, spike_threshold, score_col='short_score'):
    """检测每只ETF得分连续超过阈值的"尖峰"事件。

    如果 spike_threshold 为 None，则每只ETF使用自己该得分列的 P95 作为阈值。
    返回列表，每个元素为一个尖峰事件：
    {etf, start_date, end_date, duration, peak_score, peak_date, threshold}
    """
    spikes = []

    for etf in ETF_POOL:
        sub = df[df['etf'] == etf].sort_values('date').copy()
        if len(sub) == 0:
            continue

        # 每只ETF用自己的 P97 作为阈值，或使用全局统一阈值
        if spike_threshold is None:
            etf_threshold = np.percentile(sub[score_col].dropna(), 97)
        else:
            etf_threshold = spike_threshold

        scores = sub[score_col].values
        dates = sub['date'].values
        in_spike = False
        start_idx = None

        for i in range(len(scores)):
            if not in_spike and scores[i] > etf_threshold:
                in_spike = True
                start_idx = i
            elif in_spike and scores[i] <= etf_threshold:
                # 尖峰结束
                seg_scores = scores[start_idx:i]
                peak_idx = start_idx + np.argmax(seg_scores)
                spikes.append({
                    'etf': etf,
                    'start_date': dates[start_idx],
                    'end_date': dates[i - 1],
                    'duration': i - start_idx,
                    'peak_score': scores[peak_idx],
                    'peak_date': dates[peak_idx],
                    'end_idx': i - 1,
                    'threshold': etf_threshold,
                })
                in_spike = False
                start_idx = None

        # 如果数据末尾仍在尖峰中
        if in_spike and start_idx is not None:
            seg_scores = scores[start_idx:]
            peak_idx = start_idx + np.argmax(seg_scores)
            spikes.append({
                'etf': etf,
                'start_date': dates[start_idx],
                'end_date': dates[-1],
                'duration': len(scores) - start_idx,
                'peak_score': scores[peak_idx],
                'peak_date': dates[peak_idx],
                'end_idx': len(scores) - 1,
                'threshold': etf_threshold,
            })

    return spikes


def compute_post_spike_returns(df, all_data, spikes, score_label='短期'):
    """为每个尖峰事件计算从 start_date（得分首超阈值日）卖出后N日收益。

    同时在 spikes 列表上原地增加字段：
    close_at_start, ret_{N}d
    """
    print("\n" + "=" * 60)
    print(f"Step 5: {score_label}尖峰卖出后收益分析 (基准=start_date)")

    for sp in spikes:
        etf = sp['etf']
        closes = all_data[etf]
        start_date = sp['start_date']

        # 找到尖峰开始日在价格序列中的位置
        try:
            pos = closes.index.get_loc(start_date)
        except KeyError:
            pos = closes.index.searchsorted(start_date)
            if pos >= len(closes):
                pos = len(closes) - 1

        sp['close_at_start'] = closes.iloc[pos]

        for w in POST_SPIKE_WINDOWS:
            future_pos = pos + w
            if future_pos < len(closes):
                future_price = closes.iloc[future_pos]
                sp[f'ret_{w}d'] = future_price / sp['close_at_start'] - 1
            else:
                sp[f'ret_{w}d'] = None

    # 统计汇总
    spikes_df = pd.DataFrame(spikes)
    valid = spikes_df.dropna(subset=['ret_5d'])

    if len(valid) == 0:
        print("  无有效的卖出后收益数据")
        return spikes_df

    threshold_label = "各ETF自用P97" if SPIKE_THRESHOLD is None else f"{SPIKE_THRESHOLD_EFFECTIVE:.4f}"
    print(f"\n  检测到 {len(spikes_df)} 次{score_label}尖峰事件")
    print(f"  阈值策略: {threshold_label}")
    print(f"  收益基准: start_date（得分首超阈值日卖出）→ N日后")
    print()

    # 按ETF统计
    print(f"  {'ETF':>12s}  {'阈值':>6s}  {'次数':>4s}  {'平均持时':>6s}  {'平均峰值':>8s}  "
          f"{'卖出5d':>8s}  {'卖出10d':>8s}  {'卖出20d':>8s}  {'卖出60d':>8s}")
    print(f"  {'─' * 100}")

    for etf in ETF_POOL:
        sub = valid[valid['etf'] == etf]
        if len(sub) == 0:
            continue
        etf_th = sub['threshold'].iloc[0]
        avg_dur = sub['duration'].mean()
        avg_peak = sub['peak_score'].mean()
        r5 = sub['ret_5d'].mean() * 100
        r10 = sub['ret_10d'].mean() * 100
        r20 = sub['ret_20d'].mean() * 100
        r60 = sub['ret_60d'].mean() * 100
        pos5 = (sub['ret_5d'] > 0).mean() * 100
        name = _get_etf_label(etf)
        print(f"  {name} {etf_th:>6.2f}  {len(sub):>4d}  {avg_dur:>5.1f}天  {avg_peak:>8.2f}  "
              f"{r5:>+7.2f}%  {r10:>+7.2f}%  {r20:>+7.2f}%  {r60:>+7.2f}%  (正收益率5d={pos5:.0f}%)")

    # 全量汇总
    print(f"  {'─' * 100}")
    all_r5 = valid['ret_5d'].mean() * 100
    all_r10 = valid['ret_10d'].mean() * 100
    all_r20 = valid['ret_20d'].mean() * 100
    all_r60 = valid['ret_60d'].mean() * 100
    all_pos5 = (valid['ret_5d'] > 0).mean() * 100
    avg_dur_all = valid['duration'].mean()
    print(f"  {'[全部]':>12s}  {'—':>6s}  {len(valid):>4d}  {avg_dur_all:>5.1f}天  {'—':>8s}  "
          f"{all_r5:>+7.2f}%  {all_r10:>+7.2f}%  {all_r20:>+7.2f}%  {all_r60:>+7.2f}%  (正收益率5d={all_pos5:.0f}%)")

    return spikes_df


def plot_spikes(spikes_df, score_label='短期'):
    """画尖峰卖出后收益分布图"""
    print(f"  画{score_label}尖峰卖出后收益分布图...")

    valid = spikes_df.dropna(subset=['ret_5d'])
    if len(valid) == 0:
        print("  无数据，跳过")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    threshold_label = "各ETF自用P97" if SPIKE_THRESHOLD is None else f"{SPIKE_THRESHOLD:.2f}"
    fig.suptitle(f'{score_label}动量尖峰卖出后收益分布 (阈值={threshold_label}, 基准=start_date)',
                 fontsize=14, fontweight='bold')

    # 1. 卖出后N日收益分布（箱线图）
    ax = axes[0][0]
    ret_data = []
    labels = []
    for w in POST_SPIKE_WINDOWS:
        col = f'ret_{w}d'
        vals = valid[col].dropna() * 100
        if len(vals) > 0:
            ret_data.append(vals.values)
            labels.append(f'{w}日')
    ax.boxplot(ret_data, tick_labels=labels, patch_artist=True, showfliers=True,
               flierprops=dict(marker='o', markersize=2, alpha=0.3))
    ax.axhline(0, color='black', linewidth=0.5, linestyle='-')
    ax.set_title('从start_date卖出后N日收益分布')
    ax.set_ylabel('收益 (%)')
    ax.set_xlabel('持有天数')

    # 2. 按ETF的卖出后5日收益箱线图
    ax = axes[0][1]
    etf_ret = {}
    for etf in ETF_POOL:
        sub = valid[valid['etf'] == etf]['ret_5d'].dropna() * 100
        if len(sub) > 0:
            etf_ret[etf] = sub.values
    if etf_ret:
        ax.boxplot(etf_ret.values(), tick_labels=etf_ret.keys(), patch_artist=True,
                   showfliers=True, flierprops=dict(marker='o', markersize=2, alpha=0.3))
        ax.axhline(0, color='black', linewidth=0.5, linestyle='-')
        ax.set_title('卖出后5日收益 (按ETF)')
        ax.set_ylabel('收益 (%)')
        ax.tick_params(axis='x', rotation=30)

    # 3. 尖峰持续时间 vs 卖出后收益散点图
    ax = axes[1][0]
    ax.scatter(valid['duration'], valid['ret_5d'] * 100, alpha=0.4, s=5, color='steelblue')
    ax.axhline(0, color='black', linewidth=0.5, linestyle='-')
    ax.set_xlabel('尖峰持续天数')
    ax.set_ylabel('卖出后5日收益 (%)')
    ax.set_title('持时 vs 卖出后收益')

    # 4. 峰值大小 vs 卖出后收益散点图
    ax = axes[1][1]
    ax.scatter(valid['peak_score'], valid['ret_5d'] * 100, alpha=0.4, s=5, color='coral')
    ax.axhline(0, color='black', linewidth=0.5, linestyle='-')
    ax.set_xlabel('尖峰峰值 (短期得分)')
    ax.set_ylabel('卖出后5日收益 (%)')
    ax.set_title('峰值 vs 卖出后收益')

    plt.tight_layout()
    fname = f'spike_analysis_{score_label}.png'
    path = os.path.join(PLOT_DIR, fname)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    print(f"  已保存: {path}")
    plt.close(fig)


def print_spike_details(spikes_df, score_label='短期'):
    """打印每次尖峰的详细信息"""
    valid = spikes_df.dropna(subset=['ret_5d'])
    if len(valid) == 0:
        return

    print(f"\n  {'─' * 105}")
    print(f"  【{score_label}尖峰详情】按卖出后5日收益排序 (从start_date到start_date+5d)")
    print(f"  {'─' * 105}")

    # 按卖出后5日收益从差到好排列
    sorted_spikes = valid.sort_values('ret_5d')
    for _, sp in sorted_spikes.iterrows():
        name = _get_etf_label(sp['etf'])
        r5 = sp['ret_5d'] * 100
        r20 = sp['ret_20d'] * 100 if not pd.isna(sp.get('ret_20d')) else float('nan')
        sd = pd.Timestamp(sp['start_date']).strftime('%Y-%m-%d')
        ed = pd.Timestamp(sp['end_date']).strftime('%Y-%m-%d')
        print(f"  {sd} ~ {ed}  "
              f"{name:<25s}  持时{sp['duration']:>3.0f}天  峰值{sp['peak_score']:>8.2f}  "
              f"卖出5d={r5:>+6.2f}%  卖出20d={r20:>+6.2f}%")


# ================================================================
# 6. 主流程
# ================================================================

def main():
    print(f"\n{'=' * 60}")
    print(f"  动量得分阈值分析")
    print(f"  起始日期: {START_DATE}")
    print(f"  短期窗口: {SHORT_DAYS}天 | 长期窗口: {LONG_DAYS}天")
    print(f"  当前阈值: 短期={CURRENT_SHORT_MAX}, 长期={CURRENT_LONG_MAX}")
    print(f"{'=' * 60}\n")

    # 1. 下载数据
    all_data = download_all_data()

    # 2. 计算得分
    df = compute_all_scores(all_data)

    # 3. 统计
    analyze(df)

    # 4. 画图
    plot_distributions(df)
    plot_by_etf(df)
    plot_score_timeseries(df)
    plot_per_etf_histograms(df)

    # 4.5 日跌幅分析 — 验证 5% 阈值合理性
    analyze_daily_returns(all_data)
    plot_daily_return_dist(all_data)

    # 5. 尖峰检测 & 卖出后收益分析（None = 每只ETF用各自的P97）
    # 短期 + 长期各跑一遍
    global SPIKE_THRESHOLD_EFFECTIVE
    SPIKE_THRESHOLD_EFFECTIVE = SPIKE_THRESHOLD
    for score_col, label in [('short_score', '短期'), ('long_score', '长期')]:
        spikes_df = detect_spikes(df, SPIKE_THRESHOLD, score_col=score_col)
        if len(spikes_df) > 0:
            spikes_df = compute_post_spike_returns(df, all_data, spikes_df, score_label=label)
            plot_spikes(spikes_df, score_label=label)
            print_spike_details(spikes_df, score_label=label)

    print(f"\n{'=' * 60}")
    print(f"  分析完成！图表保存在: {PLOT_DIR}")
    print(f"{'=' * 60}\n")


if __name__ == '__main__':
    main()
