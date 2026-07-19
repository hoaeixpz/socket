# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是聚宽（JoinQuant）量化平台的研究环境，核心目标是：

**从全市场筛选出长期看涨的标的（ETF + 个股），用于全天候（All Weather）策略。**

整体工作流：
1. `analysis_stock.py` — 早期探索脚本，用年化收益/ES 指标分析 ETF
2. `filter_stocks.py` — 正式筛选脚本，多维打分 + 硬性淘汰 → 输出排名
3. `filter.md` — 用户自定义的筛选规则（补充硬性淘汰条件）
4. 筛选结果 → 填入 QMT（`C:\socket\QMT\code\all_weather\`）执行实盘/模拟交易

代码运行在聚宽的在线研究平台（JoinQuant Research）上，依赖聚宽专用的 `jqdata` SDK。

## 环境

- **平台**: JoinQuant（聚宽）在线量化研究平台
- **Python 版本**: 聚宽研究环境内置（通常为 Python 3.x）
- **核心依赖**: `pandas`, `numpy`, `matplotlib`, `seaborn`, `jqdata`（聚宽专有数据 API）
- **运行方式**: 代码在聚宽平台的 Notebook/研究环境中直接执行，不在本地运行

## 关键 API（jqdata）

聚宽特有函数，本地无法调用：

- `get_price(security, start_date, end_date, frequency, fields, fq)` — 获取标的历史价格数据
- `get_all_securities(types)` — 获取所有证券的基本信息（名称、上市日期、退市日期、类型）
- 以上函数只能在聚宽平台上运行，无本地测试环境

## 代码结构

### `filter_stocks.py` — 全市场长期看涨筛选（主力脚本）

硬性淘汰 → 多维打分 → ETF 去重 → 排名输出。

**硬性淘汰规则**（见 `filter.md`）：
1. 上市不满 5 年
2. 科创板(688)/创业板(300,301)/北交所(8xxx,4xxx)
3. 有过 ST 历史
4. 曾长期停牌（单月 > 10 天）
5. 全周期年化收益 ≤ 0

**多维打分**（各维度百分位排名后等权加权 25%）：
- 年化收益 / ES（Expected Shortfall, α=0.05）
- 年化收益 / 最大回撤（Calmar 比率）
- 趋势 R²（对数价格线性回归拟合度，斜率为负时 R² 取负）
- 多头均线占比（MA20 > MA60 > MA120 的天数比例）

**ETF 去重**：提取指数名称，跟踪同一指数的 ETF 只保留得分最高的。

主函数 `main()` 返回完整排名 DataFrame，并分 ETF/LOF/个股三类打印 Top N。

### `analysis_stock.py` — 早期探索脚本（已由 filter_stocks.py 取代）

核心思路是用年化收益率/ES 做单指标排序。保留了停牌过滤、滚动窗口分析等可复用的工具函数。

### 相关目录（项目其他部分）

- `C:\socket\QMT\code\all_weather\` — QMT（国金量化交易终端）实盘/模拟交易代码，策略的实际执行端
- `C:\socket\` — 根目录辅助脚本：`test_charts.py`（图表测试）、`create_good_stocks.py`（股票筛选）、`stock_roe_analyzer_demo.py`（ROE 分析）等
