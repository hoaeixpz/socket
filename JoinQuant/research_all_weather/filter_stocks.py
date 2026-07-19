# -*- coding: utf-8 -*-
"""
全天候策略 — 全市场股票/ETF 长期看涨筛选
============================================
在聚宽研究平台运行，筛选出适合放入全天候策略的长期看涨标的。

硬性淘汰规则：
  1. 上市不满 5 年
  2. 科创板(688)、创业板(300/301)、北交所(8xxx/4xxx)
  3. 有过 ST 历史
  4. 曾出现长期停牌（单月停牌 > 10 天）
  5. 年化收益 < 3.5%（收益太低的直接淘汰）
  6. 最大回撤 > 50%（回撤太大的直接淘汰）

多维打分（各维度百分位排名后等权加总）：
  - 年化收益 / ES（Expected Shortfall, α=0.05）
  - 年化收益 / 最大回撤（Calmar 比率）
  - 趋势 R²（对数价格线性回归的拟合优度）
  - 多头均线占比（MA20 > MA60 > MA120 的天数比例）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from jqdata import *
import random

# 设置中文字体（聚宽环境）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# ============================================================================
# 配置
# ============================================================================

# 分析周期：过去 5 年
END_DATE = '2026-07-18'
START_DATE = '2016-01-01'

# 最少需要的交易日数（5 年约 250*5=1250，设 1000 作为宽松门槛）
MIN_TRADING_DAYS = 1000

# 年化收益低于此值直接淘汰（%）
MIN_ANNUAL_RETURN = 3.5        # ETF/LOF 门槛
MIN_ANNUAL_RETURN_STOCK = 7.5  # 个股门槛（更高）

# 最大回撤超过此值直接淘汰（%）
MAX_DRAWDOWN_LIMIT = 50

# 停牌过滤：单月停牌超过此天数则剔除
MAX_PAUSED_DAYS_PER_MONTH = 10

# 需要排除的板块代码前缀
EXCLUDE_PREFIXES = (
    '688',      # 科创板
    '300', '301',  # 创业板
    '8', '4',      # 北交所、新三板
)

# ====== 调试模式 ======
# 设置为 None 或 [] 则分析全市场；填入代码列表则只分析这几只，快速验证
# 例如: DEBUG_CODES = ['510300.XSHG', '511880.XSHG', '518800.XSHG', '000001.XSHE']
DEBUG_CODES = None
#DEBUG_CODES = ['510300.XSHG', '511880.XSHG', '518800.XSHG', '000001.XSHE', '513100.XSHG', '600900.XSHG', '601288.XSHG', '159985.XSHE']

# 调试时打印每只股票的详细指标
DEBUG_VERBOSE = False

# 评分权重
WEIGHTS = {
    'ret_es':     0.27,   # 年化收益 / ES
    'calmar':     0.25,   # 年化收益 / 最大回撤
    'trend_r2':   0.25,   # 趋势 R²
    'ma_ratio':   0.23,   # 多头均线占比
}

# ============================================================================
# 第一步：获取并过滤全市场标的
# ============================================================================

def get_filtered_securities(start_date=START_DATE):
    """
    获取全市场标的，应用硬性淘汰规则。
    使用聚宽 API 按类型分别获取 ETF / LOF / 个股，不再手动判断代码前缀。
    返回 DataFrame: index=股票代码, columns=['display_name', 'type', 'category']
    """
    # 上市满5年：以 END_DATE 为基准，上市日须早于 5 年前
    listing_cutoff = pd.to_datetime(END_DATE) - pd.DateOffset(years=5)
    cutoff_date = pd.to_datetime('2100-01-01')

    # ====== 分别获取四类标的 ======
    def _fetch(api_type, label):
        """获取某一类型标的，打印每步过滤数量"""
        raw = get_all_securities(types=[api_type])
        n_raw = len(raw)

        df = raw.copy()
        df['start_date'] = pd.to_datetime(df['start_date'])
        df['end_date']  = pd.to_datetime(df['end_date'])

        # 排除退市
        df = df[df['end_date'] > cutoff_date]
        n_delisted = n_raw - len(df)

        # 上市满 5 年
        df = df[df['start_date'] < listing_cutoff]
        n_short = n_raw - n_delisted - len(df)

        df['category'] = api_type
        print(f"  {label}: 原始{n_raw}只 → 退市-{n_delisted} → 不满5年-{n_short} → 剩余{len(df)}只")
        return df

    print("\n[获取全市场标的]")
    total_raw = get_all_securities(types=['stock'])
    print(f"  全市场个股总数: {len(total_raw)}只")

    etf_df   = _fetch('etf',  'ETF   ')
    lof_df   = _fetch('lof',  'LOF   ')
    stock_df = _fetch('stock','个股   ')

    # ====== 个股专属过滤 ======
    # --- 板块排除 ---
    n_before_board = len(stock_df)
    mask_exclude = pd.Series(False, index=stock_df.index)
    for prefix in EXCLUDE_PREFIXES:
        mask_exclude |= stock_df.index.str.extract(r'(\d+)')[0].str.startswith(prefix)
    stock_df = stock_df[~mask_exclude]
    print(f"  板块排除(科创/创业/北交): {n_before_board}只 → 剔除{n_before_board - len(stock_df)}只 → 剩余{len(stock_df)}只")

    # --- ST 历史 ---
    n_before_st = len(stock_df)
    stock_df = _filter_st_history(stock_df)
    print(f"  ST过滤后个股剩余: {len(stock_df)}只 (剔除{n_before_st - len(stock_df)}只)")

    # ====== 合并（去重） ======
    n_before_merge = len(etf_df) + len(lof_df) + len(stock_df)
    sec = pd.concat([etf_df, lof_df, stock_df])
    sec = sec[~sec.index.duplicated(keep='first')]
    if n_before_merge > len(sec):
        print(f"  合并去重: {n_before_merge}只 → 去重{n_before_merge - len(sec)}只 → 剩余{len(sec)}只")

    # --- 长期停牌 ---
    print(f"\n[停牌检查] 共{len(sec)}只需要检查")
    n_before_sus = len(sec)
    sec = _filter_long_suspension(sec, start_date)
    print(f"  停牌过滤后剩余: {len(sec)}只 (剔除{n_before_sus - len(sec)}只)")

    # --- 杂项 ---
    sec = sec[sec['type'] != 'fjm']
    # 问题标的 + 重复ETF（见 filter.md 第6条，保留每组第一个，排除其余）
    exclude_codes = [
        # 问题标的
        '161019.XSHE', '161117.XSHE', '168401.XSHE',
        '169201.XSHE', '501006.XSHG',
        # 纳指ETF 重复 → 保留 513100
        '159941.XSHE', '513300.XSHG', '161130.XSHE',
        # 标普500 重复 → 保留 513500
        '161128.XSHE', '161125.XSHE',
        # 黄金ETF 重复 → 保留 518880
        '159937.XSHE', '518850.XSHG', '518800.XSHG',
        '159934.XSHE', '159812.XSHE', '518660.XSHG',
    ]
    sec = sec[~sec.index.isin(exclude_codes)]

    # ====== 汇总 ======
    n_etf   = (sec['category'] == 'etf').sum()
    n_lof   = (sec['category'] == 'lof').sum()
    n_stock = (sec['category'] == 'stock').sum()

    print(f"\n[过滤完成] 共{len(sec)}只标的进入指标计算")
    print(f"  ETF:  {n_etf}")
    print(f"  LOF:  {n_lof}")
    print(f"  个股: {n_stock}")

    return sec


def _filter_st_history(sec_df):
    """
    排除有过 ST 历史的股票。
    聚宽中 ST 判断方法：检查过去 5 年每日 ST 状态。
    """
    print(f"  正在检查ST历史 (共{len(sec_df)}只)...")
    stock_list = list(sec_df.index)
    batch_size = 100
    st_stocks = set()

    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i:i + batch_size]
        try:
            st_data = get_extras('is_st', batch,
                                 start_date=START_DATE,
                                 end_date=END_DATE,
                                 df=True)
            if st_data is not None and not st_data.empty:
                # st_data 中任何一天为 True 就标记
                for col in st_data.columns:
                    if st_data[col].any():
                        st_stocks.add(col)
        except Exception as e:
            # 某些标的不支持 get_extras，容错跳过
            pass

    if st_stocks:
        print(f"  发现 {len(st_stocks)} 只有 ST 历史，已排除")

    sec_df = sec_df[~sec_df.index.isin(st_stocks)]
    return sec_df


def _filter_long_suspension(sec_df, start_date):
    """
    排除曾出现长期停牌的标的（单月停牌 > MAX_PAUSED_DAYS_PER_MONTH 天）。
    抽样检查而非全量（效率考虑）。
    """
    print("正在检查停牌历史...")
    bad_stocks = set()
    check_list = list(sec_df.index)

    for i, code in enumerate(check_list):
        if (i + 1) % 200 == 0:
            print(f"  已检查 {i+1}/{len(check_list)}...")
        try:
            df = get_price(code, start_date=start_date, end_date='2025-12-31',
                          fields=['paused'], fq='pre')
            # 按月份统计停牌天数
            paused = df[df['paused'] > 0]
            if len(paused) > 0:
                month_series = paused.index.strftime('%Y-%m')
                max_paused = month_series.value_counts().max()
                if max_paused > MAX_PAUSED_DAYS_PER_MONTH:
                    bad_stocks.add(code)
        except Exception:
            pass

    if bad_stocks:
        print(f"  发现 {len(bad_stocks)} 只长期停牌标的，已排除")

    sec_df = sec_df[~sec_df.index.isin(bad_stocks)]
    return sec_df


# ============================================================================
# 第二步：获取价格数据
# ============================================================================

def get_price_data(code, start_date=START_DATE, end_date=END_DATE):
    """获取单只标的的价格数据，返回收盘价 Series 或 None"""
    try:
        df = get_price(code, start_date=start_date, end_date=end_date,
                      frequency='daily', fields=['close'], fq='pre')
        # 去掉上市前/退市后的 NaN，只保留有效交易日
        prices = df['close'].dropna()
        if len(prices) < MIN_TRADING_DAYS:
            return None
        return prices
    except Exception:
        return None


# ============================================================================
# 第三步：计算各项指标
# ============================================================================

def calculate_annual_return(prices):
    """年化收益率（%）"""
    total_return = prices.iloc[-1] / prices.iloc[0]
    n_days = len(prices)
    annual_return = (total_return ** (250 / n_days) - 1) * 100
    return annual_return


def calculate_returns(prices):
    """日收益率（%）"""
    return (prices / prices.shift(1) - 1) * 100


def calculate_expected_shortfall(returns, alpha=0.05):
    """
    计算 Expected Shortfall (CVaR)
    α = 0.05 → 取收益率最差的 5% 天数的均值，取正数
    """
    n = int(len(returns) * alpha)
    if n < 3:
        n = 3
    lowest = returns.nsmallest(n)
    return abs(lowest.mean())


def calculate_max_drawdown(prices):
    """计算最大回撤（%），返回正数"""
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax * 100
    return abs(drawdown.min())


def calculate_trend_r2(prices):
    """
    趋势 R²：对数价格对时间做线性回归，返回 R²。
    R² 越高说明股价走势越接近一条稳定的趋势线（越"漂亮"）。
    """
    log_prices = np.log(prices.values)
    x = np.arange(len(log_prices))

    # 线性回归
    A = np.vstack([x, np.ones_like(x)]).T
    slope, intercept = np.linalg.lstsq(A, log_prices, rcond=None)[0]

    # R²
    y_pred = slope * x + intercept
    ss_res = np.sum((log_prices - y_pred) ** 2)
    ss_tot = np.sum((log_prices - np.mean(log_prices)) ** 2)

    if ss_tot < 1e-10:
        return 0.0
    r2 = 1 - ss_res / ss_tot

    # 如果斜率为负，R² 取负（惩罚下行趋势）
    if slope < 0:
        r2 = -r2

    return r2


def calculate_ma_alignment_ratio(prices):
    """
    多头均线占比：MA20 > MA60 > MA120 的天数占总天数的比例。
    需要至少 120 天数据才计算。
    """
    if len(prices) < 120:
        return 0.0

    ma20  = prices.rolling(20).mean()
    ma60  = prices.rolling(60).mean()
    ma120 = prices.rolling(120).mean()

    # MA20 > MA60 > MA120 的布尔序列
    aligned = (ma20 > ma60) & (ma60 > ma120)

    # 从第 120 天开始算
    valid = aligned.iloc[120:]
    if len(valid) == 0:
        return 0.0

    return valid.sum() / len(valid)


def calculate_all_metrics(prices, min_annual_return=MIN_ANNUAL_RETURN):
    """
    计算单只标的所有指标。
    始终返回 dict，包含 'passed' (bool) 和 'fail_reason' (str)。

    硬淘汰条件：
      - 数据不足（None 或交易日 < MIN_TRADING_DAYS）
      - 年化收益 < min_annual_return
    """
    # 数据不足
    if prices is None:
        return {'passed': False, 'fail_reason': '无法获取价格数据'}
    if len(prices) < MIN_TRADING_DAYS:
        return {'passed': False,
                'fail_reason': f'交易日不足 (仅{len(prices)}天, 需要{MIN_TRADING_DAYS}天)',
                'n_days': len(prices)}

    annual_ret = calculate_annual_return(prices)

    # 年化收益不达标：硬淘汰，但仍计算完整指标供调试查看
    if annual_ret < min_annual_return:
        metrics = _compute_raw_metrics(prices, annual_ret)
        metrics['passed'] = False
        metrics['fail_reason'] = f'年化收益<{min_annual_return}% ({annual_ret:.2f}%)'
        return metrics

    returns = calculate_returns(prices).dropna()
    if len(returns) < 100:
        return {'passed': False,
                'fail_reason': f'有效收益率数据不足 (仅{len(returns)}天)',
                'n_days': len(prices)}

    metrics = _compute_raw_metrics(prices, annual_ret, returns)

    # 最大回撤过大
    if metrics['max_drawdown'] > MAX_DRAWDOWN_LIMIT:
        metrics['passed'] = False
        metrics['fail_reason'] = f'最大回撤>{MAX_DRAWDOWN_LIMIT}% ({metrics["max_drawdown"]:.1f}%)'
        return metrics

    metrics['passed'] = True
    metrics['fail_reason'] = ''
    return metrics


def _compute_raw_metrics(prices, annual_ret, returns=None):
    """计算全部原始指标，即使股票被淘汰也计算。"""
    if returns is None:
        returns = calculate_returns(prices).dropna()

    es = calculate_expected_shortfall(returns) if len(returns) >= 3 else 0.0
    if es < 1e-8:
        es = 1e-8

    max_dd = calculate_max_drawdown(prices)
    if max_dd < 1e-8:
        max_dd = 1e-8

    trend_r2 = calculate_trend_r2(prices)
    ma_ratio = calculate_ma_alignment_ratio(prices)

    return {
        'annual_return': round(annual_ret, 2),
        'es':            round(es, 4),
        'max_drawdown':  round(max_dd, 2),
        'ret_es':        round(annual_ret / es, 2),
        'calmar':        round(annual_ret / max_dd, 2),
        'trend_r2':      round(trend_r2, 4),
        'ma_ratio':      round(ma_ratio, 4),
        'n_days':        len(prices),
    }


# ============================================================================
# 第四步：综合打分与排名
# ============================================================================

def percentile_rank(series):
    """将 Series 转换为百分位排名（0-100）"""
    return series.rank(pct=True) * 100


def compute_composite_score(metrics_df):
    """
    对每个维度做百分位排名，加权求和得到综合得分。
    """
    score_df = pd.DataFrame(index=metrics_df.index)

    # 每个指标做百分位排名
    for col in ['ret_es', 'calmar', 'trend_r2', 'ma_ratio', 'annual_return']:
        score_df[f'{col}_pct'] = percentile_rank(metrics_df[col])

    # 加权总分
    score_df['composite_score'] = (
        score_df['ret_es_pct']   * WEIGHTS['ret_es'] +
        score_df['calmar_pct']   * WEIGHTS['calmar'] +
        score_df['trend_r2_pct'] * WEIGHTS['trend_r2'] +
        score_df['ma_ratio_pct'] * WEIGHTS['ma_ratio']
    )

    # 合并原始指标
    result = metrics_df.join(score_df)
    result = result.sort_values('composite_score', ascending=False)

    return result


def _build_debug_securities(code_list):
    """
    调试模式：根据指定代码列表构建 securities DataFrame。
    分类型获取（与 get_filtered_securities 一致），category 由我们指定而非依赖 API 的 type 字段。
    跳过所有硬性过滤。
    """
    # 分类型获取，每个类型自己标 category
    frames = {}
    for api_type in ('etf', 'lof', 'stock'):
        df = get_all_securities(types=[api_type])
        df['category'] = api_type
        frames[api_type] = df
    all_sec = pd.concat(frames.values())
    # 去重：同一代码可能出现在多个类型中，保留靠前的（etf > lof > stock）
    all_sec = all_sec[~all_sec.index.duplicated(keep='first')]

    valid_codes = []
    valid_rows = []
    missing = []

    for code in code_list:
        if code in all_sec.index:
            row = all_sec.loc[code]
            valid_codes.append(code)
            valid_rows.append({
                'display_name': row['display_name'],
                'type': row['type'],
                'category': row['category'],
            })
        else:
            missing.append(code)

    if missing:
        print(f"  警告: 以下代码未找到，已跳过: {missing}")

    if not valid_rows:
        raise ValueError("调试代码列表中没有有效的标的！")

    df = pd.DataFrame(valid_rows, index=valid_codes)
    df = df[~df.index.duplicated(keep='first')]
    return df


def _print_debug_metrics(m):
    """调试模式：打印每只标的的完整指标和状态。"""
    status = "[通过]" if m['passed'] else f"[淘汰] {m.get('fail_reason', '')}"
    code = m.get('code', '?')
    name = m.get('display_name', '?')

    # 有完整指标时打印详细数据
    if 'annual_return' in m:
        print(f"  {status}")
        print(f"    {code} {name}")
        print(f"    年化收益={m['annual_return']:.1f}% | "
              f"最大回撤={m['max_drawdown']:.1f}% | "
              f"ES={m['es']:.2f}%")
        print(f"    Ret/ES={m['ret_es']:.1f} | "
              f"Calmar={m['calmar']:.2f} | "
              f"R²={m['trend_r2']:.3f} | "
              f"MA多头比={m['ma_ratio']:.3f} | "
              f"交易日={m['n_days']}天")
    else:
        print(f"  {status}: {code} {name}")


# ============================================================================
# 第六步：主流程
# ============================================================================

def main():
    print("=" * 70)
    print("全天候策略 — 全市场长期看涨标的筛选")
    print(f"分析周期: {START_DATE} → {END_DATE}")
    if DEBUG_CODES:
        print(f"*** 调试模式: 仅分析指定的 {len(DEBUG_CODES)} 只标的 ***")
        if not DEBUG_VERBOSE:
            print("   (提示: 设置 DEBUG_VERBOSE = True 可查看每只标的的详细指标)")
    print("=" * 70)

    # 1. 获取过滤后的标的列表
    if DEBUG_CODES:
        # 调试模式：直接使用指定代码，跳过全市场扫描
        print("\n[1/4] 调试模式 — 跳过全市场扫描...")
        securities = _build_debug_securities(DEBUG_CODES)
    else:
        print("\n[1/4] 获取并过滤标的...")
        securities = get_filtered_securities()

    if len(securities) == 0:
        print("无符合条件的标的，退出。")
        return

    # 2. 逐个获取价格并计算指标
    print(f"\n[2/4] 计算指标 (共 {len(securities)} 只)...")
    results = []
    success_count = 0
    fail_count = 0

    code_list = list(securities.index)
    for i, code in enumerate(code_list):
        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(code_list)} "
                  f"(通过: {success_count}, 淘汰: {fail_count})")

        prices = get_price_data(code)
        info = securities.loc[code]

        cat = info['category']
        min_ret = MIN_ANNUAL_RETURN_STOCK if cat == 'stock' else MIN_ANNUAL_RETURN
        metrics = calculate_all_metrics(prices, min_annual_return=min_ret)

        # 始终记录 code / display_name / category
        metrics['code'] = code
        metrics['display_name'] = info['display_name']
        metrics['category'] = info['category']

        if DEBUG_VERBOSE:
            _print_debug_metrics(metrics)

        if not metrics['passed']:
            fail_count += 1
            continue

        success_count += 1
        results.append(metrics)

    print(f"\n  完成! 通过: {success_count}, 淘汰: {fail_count}")

    if len(results) == 0:
        print("所有标的均未通过筛选（年化收益≤0或数据不足），退出。")
        return

    # 3. 构建 DataFrame 并打分
    print(f"\n[3/4] 综合打分与排名...")
    metrics_df = pd.DataFrame(results).set_index('code')

    # 注意：不要对 display_name 和 category 做百分位排名
    meta_cols = metrics_df[['display_name', 'category']].copy()
    metric_cols = metrics_df.drop(columns=['display_name', 'category'])

    scored = compute_composite_score(metric_cols)
    scored = scored.join(meta_cols)

    final = scored

    # ====================================================================
    # 输出结果
    # ====================================================================

    # 按类别分组输出 Top N
    print("\n" + "=" * 70)
    print("筛选结果")
    print("=" * 70)

    _print_section(final, 'etf',   'ETF 基金',   top_n=50)
    _plot_category_heatmap(final, 'etf', 'ETF 基金', top_n=50)

    _print_section(final, 'lof',   'LOF 基金',   top_n=10)
    _plot_category_heatmap(final, 'lof', 'LOF 基金', top_n=10)

    _print_section(final, 'stock', '个股',       top_n=50)
    _plot_category_heatmap(final, 'stock', '个股', top_n=50)

    # 完整排名（按年化收益排序）
    print("\n\n")
    print("=" * 70)
    print("完整排名 — 按年化收益排序（前 100）")
    print("=" * 70)

    # 取总分前 100，按年化收益排序显示
    top100 = final.head(100)
    ranked = top100.sort_values('annual_return', ascending=False)
    _print_ranking(ranked)

    # 热力图
    print("\n\n[热力图] 正在生成...")
    plot_heatmap(final, top_n=100)

    return final


def _cjk_pad(text, width):
    """CJK-aware ljust: 中文字符按 2 宽度计算，补齐到指定宽度。"""
    if not isinstance(text, str):
        text = str(text)
    text_width = sum(2 if ord(c) > 127 else 1 for c in text)
    return text + ' ' * max(0, width - text_width)


def _print_ranking(df):
    """打印完整排名（已排序的 DataFrame），使用 CJK 对齐"""
    header = (f"{_cjk_pad('代码', 14)}{_cjk_pad('名称', 24)}{_cjk_pad('类型', 8)}"
              f"{'总分':>6} {'年化%':>8} {'最大回撤%':>9} "
              f"{'Ret/ES':>8} {'Calmar':>7} {'R²':>8} {'MA比':>7}")
    print(header)
    print("-" * len(header))

    for code, row in df.iterrows():
        cat = row.get('category', '')
        line = (f"{_cjk_pad(code, 14)}{_cjk_pad(row['display_name'], 24)}{_cjk_pad(cat, 8)}"
                f"{row['composite_score']:>6.1f} {row['annual_return']:>8.1f} "
                f"{row['max_drawdown']:>9.1f} {row['ret_es']:>8.1f} "
                f"{row['calmar']:>7.2f} {row['trend_r2']:>8.3f} "
                f"{row['ma_ratio']:>7.3f}")
        print(line)


def _print_section(df, category, title, top_n=30):
    """打印某一类别的前 N 名"""
    subset = df[df['category'] == category]
    if len(subset) == 0:
        print(f"\n--- {title}: 无符合条件的标的 ---")
        return

    print(f"\n--- {title} (共 {len(subset)} 只, 显示前 {min(top_n, len(subset))}) ---")
    header = (f"{_cjk_pad('代码', 14)}{_cjk_pad('名称', 24)}"
              f"{'总分':>6} {'年化%':>8} {'最大回撤%':>9} "
              f"{'Ret/ES':>8} {'Calmar':>7} {'R²':>8} {'MA比':>7}")
    print(header)
    print("-" * len(header))

    top = subset.head(top_n)
    for code, row in top.iterrows():
        line = (f"{_cjk_pad(code, 14)}{_cjk_pad(row['display_name'], 24)}"
                f"{row['composite_score']:>6.1f} {row['annual_return']:>8.1f} "
                f"{row['max_drawdown']:>9.1f} {row['ret_es']:>8.1f} "
                f"{row['calmar']:>7.2f} {row['trend_r2']:>8.3f} "
                f"{row['ma_ratio']:>7.3f}")
        print(line)


# ============================================================================
# 热力图
# ============================================================================

def _plot_category_heatmap(df, category, title, top_n=30):
    """为某一类别的 Top N 绘制热力图"""
    subset = df[df['category'] == category]
    if len(subset) == 0:
        return
    n = min(top_n, len(subset))
    print(f"\n[{title}热力图] Top {n}")
    plot_heatmap(subset, top_n=n)


def plot_heatmap(df, top_n=30):
    """
    热力图：取总分前 Top N，按年化收益排序显示。
    列 = 年化收益 + 四个打分指标。
    颜色 = 百分位排名（绿高红低），格子内标注原始值。
    """
    # 取总分前 top_n，再按年化收益降序排列
    top = df.head(top_n).copy()
    top = top.sort_values('annual_return', ascending=False)

    pct_cols = ['annual_return_pct', 'ret_es_pct', 'calmar_pct', 'trend_r2_pct', 'ma_ratio_pct']
    raw_cols  = ['annual_return',     'ret_es',     'calmar',     'trend_r2',     'ma_ratio']
    labels    = ['年化收益%', 'Ret/ES', 'Calmar', 'R²', 'MA比']

    heat_data = top[pct_cols].copy()
    heat_data.columns = labels

    # 行标签：代码 + 简称
    row_labels = []
    for code, row in top.iterrows():
        name = row['display_name']
        short = name[:8] if len(name) > 8 else name
        row_labels.append(f"{code[:9]}\n{short}")

    # 画图
    n_rows = len(heat_data)
    fig_height = max(8, n_rows * 0.45)
    fig, ax = plt.subplots(figsize=(11, fig_height))

    # 生成标注文本（百分位 + 原始值）
    annot_text = []
    for i in range(n_rows):
        row_annot = []
        for pct_col, raw_col, label in zip(pct_cols, raw_cols, labels):
            pct_val = top[pct_col].iloc[i]
            raw_val = top[raw_col].iloc[i]
            if '年化' in label:
                row_annot.append(f"{pct_val:.0f}\n({raw_val:.1f}%)")
            else:
                row_annot.append(f"{pct_val:.0f}\n({raw_val:.1f})")
        annot_text.append(row_annot)

    sns.heatmap(heat_data,
                annot=np.array(annot_text),
                fmt='',
                xticklabels=labels,
                yticklabels=row_labels,
                cmap='RdYlGn_r',
                vmin=0, vmax=100,
                linewidths=0.5,
                linecolor='white',
                cbar_kws={'label': '百分位排名'},
                ax=ax)

    ax.set_title(f'Top {n_rows} 标的 指标热力图\n(格子内: 百分位↑ + 括号内: 原始值, 按年化收益排序)', fontsize=13, pad=15)
    ax.set_xlabel('')
    ax.set_ylabel('')
    plt.tight_layout()
    plt.show()


# ============================================================================
# 运行
# ============================================================================

if __name__ == '__main__':
    result_df = main()
