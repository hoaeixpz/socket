# 尖峰检测逻辑分析文档

## 1. 整体数据流

```mermaid
flowchart TD
    A["download_all_data()<br/>下载每只ETF从2020至今全部日线close"] --> B["compute_all_scores()<br/>逐日滚动计算短期(25天)和长期(250天)动量得分"]
    B --> C["df 包含: date, etf, short_score, long_score, ..."]
    C --> D["detect_spikes()<br/>检测短期得分连续超过阈值的'尖峰'事件"]
    D --> E["spikes 列表<br/>每个尖峰: start_date, end_date, peak_score, ..."]
    E --> F["compute_post_spike_returns()<br/>计算尖峰结束后N日收益"]
    F --> G["输出: 尖峰汇总表 + 事后收益"]
```

## 2. detect_spikes() 详细流程

```mermaid
flowchart TD
    subgraph 每只ETF独立处理
        A[遍历该ETF每天短期得分] --> B{得分 > 阈值?}
        B -->|是 且 之前不在尖峰中| C["标记尖峰开始<br/>记录 start_date"]
        B -->|是 且 已在尖峰中| D[继续, 不做特殊处理]
        B -->|否 且 在尖峰中| E["标记尖峰结束<br/>记录 end_date = 昨天<br/>记录 peak_score = 期间得分最大值<br/>记录 duration = 持续天数"]
        B -->|否 且 不在尖峰中| F[跳过]
    end
```

**阈值确定逻辑**:
- 若 `SPIKE_THRESHOLD` 是数字 → 所有 ETF 共用该阈值
- 若 `SPIKE_THRESHOLD = None` → 每只 ETF 用自己的 P90/P95

## 3. compute_post_spike_returns() 详细流程

```mermaid
flowchart TD
    A[遍历每个尖峰事件] --> B[取该ETF的全部收盘价序列 closes]
    B --> C["找到 end_date 在 closes 中的位置 pos"]
    C --> D["记录 close_at_end = closes[pos]<br/>(尖峰结束日收盘价)"]
    D --> E["对每个窗口 w in [5,10,20,40,60]:"]
    E --> F["future_pos = pos + w"]
    F --> G["ret_wd = closes[future_pos] / close_at_end - 1"]
```

**关键公式**:
```
事后N日收益率 = (结束日后第N个交易日的收盘价) / (结束日收盘价) - 1
```

## 4. 问题所在

### 4.1 时间线图示

```
                    尖峰期间                     尖峰结束后
        |──────────────────────────────|─────────────────────────|
        |                              |                         |
     start_date                   end_date               end_date+5d
     (得分首超阈值)               (得分回落到阈值下)       (事后5d对比日)
        |                              |                         |
        |                         ① 此时卖出?                   |
        |                            (当前代码的隐含假设)         |
        |                                                       |
        |                         ② 实际上策略应该在            |
        |                            start_date 或 peak_date 卖  |
        |                                                       |
     peak_date                                                   |
     (得分峰值)                                                   |
        |                                                        |
        |  ③ 或者在这里卖?                                       |
        |                                                        |
```

### 4.2 问题本质

```mermaid
flowchart LR
    subgraph 当前代码做的事
        A1["尖峰结束日"] --> A2["事后5日"]
        A2 --> A3["收益率 = 事后价 / 结束日价 - 1"]
    end

    subgraph 实际应该做的事
        B1["卖出日<br/>(start_date 或 peak_date)"] --> B2["卖出后5日"]
        B2 --> B3["收益率 = 卖出后5日价 / 卖出日价 - 1"]
    end
```

| 对比维度 | 当前代码 | 应该做的 |
|---------|---------|---------|
| 收益计算基准日 | `end_date`（尖峰已结束） | `start_date` 或 `peak_date`（尖峰进行中） |
| 实际可行性 | ❌ 无法预知 end_date | ✅ 可以在触发时立即卖出 |
| 回答的问题 | "尖峰消退后还会跌吗" | "尖峰触发时卖出能躲掉下跌吗" |
| 问题 | **look-ahead bias**：你只有事后才知道尖峰哪天结束 | 无偏 |

### 4.3 具体示例

以 `2022-02-10 ~ 2022-03-25 豆粕ETF 峰值11.10` 为例：

```
真实时间线:
2022-02-10  start_date  (得分首次 > P90阈值)
    |
    |  ← 策略应该在这附近考虑卖出
    |
2022-02-XX  peak_date   (得分达到最高点 11.10)
    |
    |  ← 或者在这里卖
    |
2022-03-25  end_date    (得分落回阈值下 —— 此时已经跌了32天!)
    |
    |  ← 当前代码从这里开始算收益，毫无意义
    |
2022-04-01  end_date+5d (事后5日收益 -10.33%)
```

**当前代码的 -10.33% 含义**: 从 2022-03-25 到 2022-04-01，又跌了 10.33%

**应该分析的是**: 从 2022-02-10（或 peak_date）卖出后，价格跌了多少？

## 5. 改进方向

### 5.1 应该计算的三个收益基准

```mermaid
flowchart TD
    S[尖峰检测到 start_date] --> P1["方案A: 从 start_date 卖出<br/>计算 start_date → start_date+N 收益"]
    S --> P2["方案B: 从 peak_date 卖出<br/>计算 peak_date → peak_date+N 收益"]
    S --> P3["方案C: 从 start_date + 50%×duration 卖出<br/>计算'半山腰' → 半山腰+N 收益"]
```

### 5.2 需要修改的代码位置

| 函数 | 改动 |
|------|------|
| `detect_spikes()` | 在尖峰记录中增加 `start_close`（start_date 收盘价）和 `peak_close`（peak_date 收盘价） |
| `compute_post_spike_returns()` | 改名为 `compute_sell_returns()`，分别从 start_date、peak_date 开始计算收益 |
| `print_spike_details()` | 打印从 multiple baselines 计算的收益 |
| `plot_spikes()` | 箱线图增加方案A/B的对比 |
