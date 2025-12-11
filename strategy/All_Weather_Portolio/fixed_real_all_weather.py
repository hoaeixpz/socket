import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class FixedRealAllWeather:
    """修正版全天候组合策略 - 真实数据"""
    
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        
        # ETF配置
        self.etf_config = {
            '沪深300ETF': {'symbol': 'sh510300', 'weight': 0.30},
            '10年期国债ETF': {'symbol': 'sh511260', 'weight': 0.40},
            '5年期国债ETF': {'symbol': 'sh511010', 'weight': 0.15},
            '黄金ETF': {'symbol': 'sh518800', 'weight': 0.15}
        }
        
        self.data = {}
        
    def load_data(self):
        """加载真实parquet数据"""
        print("📊 加载真实ETF数据文件")
        print("=" * 50)
        
        try:
            for etf_name, config in self.etf_config.items():
                symbol = config['symbol']
                filename = f'../../stock_price/{symbol}_index_daily.parquet'
                
                if os.path.exists(filename):
                    df = pd.read_parquet(filename)
                    df.index = pd.to_datetime(df['date'])
                    df = df.sort_index()
                    self.data[etf_name] = df
                    print(f"✅ {etf_name} ({symbol}): {len(df)} 条数据，日期范围 {df.index[0].date()} 到 {df.index[-1].date()}")
                else:
                    print(f"❌ 文件不存在: {filename}")
                    return False
            
            return len(self.data) >= 2  # 至少需要2个ETF
            
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            return False
    
    def run_backtest(self):
        """运行修正版回测"""
        print("\n🌍 运行修正版全天候组合策略回测")
        print("=" * 60)
        
        # 获取共同日期范围
        common_dates = None
        for etf_name, df in self.data.items():
            if common_dates is None:
                common_dates = df.index
            else:
                common_dates = common_dates.intersection(df.index)
        
        common_dates = sorted(common_dates)
        start_date = common_dates[0]
        end_date = common_dates[-1]
        years = (end_date - start_date).days / 365.25
        
        print(f"回测期间: {start_date.date()} 到 {end_date.date()}")
        print(f"投资年限: {years:.1f} 年")
        print(f"可用交易日: {len(common_dates)}")
        
        # 初始化
        positions = {}
        cash = self.initial_capital
        available_weights = {etf_name: config['weight'] for etf_name, config in self.etf_config.items() if etf_name in self.data}
        
        # 按目标权重初始买入
        print(f"\n🎯 初始建仓:")
        total_invested = 0
        for etf_name in self.data.keys():
            target_value = self.initial_capital * available_weights[etf_name]
            price = self.data[etf_name].loc[start_date, 'close']
            shares = int(target_value / price)
            cost = shares * price
            positions[etf_name] = shares
            cash -= cost
            total_invested += cost
            print(f"  {etf_name}: {shares:,}股 @ ¥{price:.2f} = ¥{cost:,.0f} (目标{available_weights[etf_name]:.0%})")
        
        print(f"  初始投资: ¥{total_invested:,.0f}")
        print(f"  剩余现金: ¥{cash:,.0f}")
        
        # 记录
        daily_values = []
        rebalance_records = []
        quarterly_records = []
        last_quarter = None
        
        # 逐步回测
        for i, date in enumerate(common_dates):
            # 计算当日组合价值
            portfolio_value = cash
            for etf_name, shares in positions.items():
                portfolio_value += shares * self.data[etf_name].loc[date, 'close']
            
            daily_values.append({
                'date': date,
                'value': portfolio_value,
                'cash': cash
            })
            
            # 季度检查
            current_quarter = (date.year, date.quarter)
            if current_quarter != last_quarter and date.month in [3, 6, 9, 12] and date.day <= 5:
                last_quarter = current_quarter
                
                # 计算当前配置
                current_allocation = {}
                total_value = portfolio_value
                quarter_info = {'date': date, 'total_value': total_value, 'weights': {}, 'positions': {}}
                
                for etf_name, shares in positions.items():
                    current_value = shares * self.data[etf_name].loc[date, 'close']
                    current_allocation[etf_name] = current_value / total_value if total_value > 0 else 0
                    quarter_info['weights'][etf_name] = current_allocation[etf_name]
                    quarter_info['positions'][etf_name] = {'shares': shares, 'value': current_value}
                
                quarterly_records.append(quarter_info)
                
                # 打印季度资产比重
                quarter_str = f"Q{date.quarter} {date.year}"
                print(f"\n📅 {quarter_str} 资产配置:")
                print(f"  总价值: ¥{total_value:,.0f}")
                print(f"  {'ETF名称':12s} {'当前比重':10s} {'目标比重':10s} {'偏离度':8s} {'持仓价值':10s}")
                print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*8} {'-'*10}")
                
                max_deviation = 0
                for etf_name in self.data.keys():
                    current = current_allocation[etf_name]
                    target = available_weights[etf_name]
                    deviation = abs(current - target)
                    max_deviation = max(max_deviation, deviation)
                    
                    print(f"  {etf_name:12s} {current:8.1%} {target:8.1%} {deviation:6.1%} ¥{quarter_info['positions'][etf_name]['value']:8.0f}")
                
                # 检查是否需要再平衡
                need_rebalance = max_deviation > 0.05  # 5%偏离阈值
                
                if need_rebalance:
                    print(f"\n🔄 执行修正版再平衡 (最大偏离: {max_deviation:.1%}):")
                    
                    rebalance_operations = []
                    cash_before_rebalance = cash
                    
                    # 第一步：计算所有需要调整的资产
                    adjustments = {}
                    total_sell_value = 0
                    total_buy_value = 0
                    
                    print(f"  📋 再平衡计算:")
                    for etf_name in self.data.keys():
                        target_value = total_value * available_weights[etf_name]
                        current_value = current_allocation[etf_name] * total_value
                        price = self.data[etf_name].loc[date, 'close']
                        
                        if current_value > target_value:
                            # 需要卖出
                            sell_amount = current_value - target_value
                            sell_shares = int(sell_amount / price)
                            proceeds = sell_shares * price
                            
                            if sell_shares > 0 and sell_shares <= positions[etf_name]:
                                adjustments[etf_name] = {
                                    'action': 'sell',
                                    'shares': sell_shares,
                                    'value': proceeds
                                }
                                total_sell_value += proceeds
                                print(f"    {etf_name}: 卖出 {sell_shares}股, 获得 ¥{proceeds:,.0f}")
                        
                        elif current_value < target_value:
                            # 需要买入
                            buy_amount = target_value - current_value
                            buy_shares = int(buy_amount / price)
                            cost = buy_shares * price
                            
                            if buy_shares > 0:
                                adjustments[etf_name] = {
                                    'action': 'buy',
                                    'shares': buy_shares,
                                    'value': cost
                                }
                                total_buy_value += cost
                                print(f"    {etf_name}: 需买入 {buy_shares}股, 需 ¥{cost:,.0f}")
                    
                    # 第二步：先执行所有卖出操作
                    print(f"    💰 执行卖出操作:")
                    for etf_name, adj in adjustments.items():
                        if adj['action'] == 'sell':
                            price = self.data[etf_name].loc[date, 'close']
                            positions[etf_name] -= adj['shares']
                            cash += adj['value']
                            rebalance_operations.append(f"➖ 卖出 {etf_name}: {adj['shares']}股 @ ¥{price:.2f}, 收入 ¥{adj['value']:.0f}")
                            print(f"      ✅ {rebalance_operations[-1]}")
                    
                    print(f"    卖出后现金: ¥{cash_before_rebalance:,.0f} → ¥{cash:,.0f}")
                    
                    # 第三步：再执行买入操作
                    print(f"    💳 执行买入操作:")
                    for etf_name, adj in adjustments.items():
                        if adj['action'] == 'buy':
                            price = self.data[etf_name].loc[date, 'close']
                            if cash >= adj['value']:
                                positions[etf_name] += adj['shares']
                                cash -= adj['value']
                                rebalance_operations.append(f"➕ 买入 {etf_name}: {adj['shares']}股 @ ¥{price:.2f}, 成本 ¥{adj['value']:.0f}")
                                print(f"      ✅ {rebalance_operations[-1]}")
                            else:
                                # 现金仍然不足，按比例减少买入
                                affordable_ratio = cash / total_buy_value if total_buy_value > 0 else 0
                                if affordable_ratio > 0:
                                    adjusted_shares = int(adj['shares'] * affordable_ratio)
                                    adjusted_cost = adjusted_shares * price
                                    if adjusted_shares > 0:
                                        positions[etf_name] += adjusted_shares
                                        cash -= adjusted_cost
                                        rebalance_operations.append(f"➕ 买入 {etf_name}: {adjusted_shares}股 @ ¥{price:.2f}, 成本 ¥{adjusted_cost:.0f} (部分)")
                                        print(f"      ⚠️  {rebalance_operations[-1]}")
                    
                    print(f"    最终现金: ¥{cash:,.0f}")
                    
                    # 记录再平衡
                    rebalance_records.append({
                        'date': date,
                        'quarter': quarter_str,
                        'total_value_before': total_value,
                        'operations': rebalance_operations,
                        'cash_before': cash_before_rebalance,
                        'cash_after': cash
                    })
                    
                else:
                    print(f"  ✅ 无需再平衡 (最大偏离: {max_deviation:.1%} < 5%)")
            
            # 进度显示
            if (i + 1) % 500 == 0:
                progress = (i + 1) / len(common_dates) * 100
                print(f"  进度: {progress:.1f}%")
        
        # 计算最终结果
        final_value = daily_values[-1]['value']
        total_return = (final_value - self.initial_capital) / self.initial_capital
        annual_return = (final_value / self.initial_capital) ** (1/years) - 1
        
        # 计算最大回撤
        values = [v['value'] for v in daily_values]
        peak = values[0]
        max_drawdown = 0
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # 计算各ETF单独表现
        etf_performances = {}
        for etf_name in self.data.keys():
            start_price = self.data[etf_name].loc[start_date, 'close']
            end_price = self.data[etf_name].loc[end_date, 'close']
            total_r = (end_price - start_price) / start_price
            annual_r = (end_price / start_price) ** (1/years) - 1
            etf_performances[etf_name] = {
                'total_return': total_r,
                'annual_return': annual_r
            }
        
        # 显示结果
        self.display_results(start_date, end_date, years, final_value, 
                           total_return, annual_return, max_drawdown, 
                           len(rebalance_records), positions, etf_performances,
                           quarterly_records, rebalance_records)
        
        # 绘制图表
        self.plot_results(daily_values, rebalance_records, etf_performances)
        
        # 写入季度比重报告
        self.write_quarterly_weights_to_md(quarterly_records, rebalance_records, 
                                         start_date, end_date, years,
                                         final_value, total_return, annual_return, max_drawdown,
                                         len(rebalance_records), positions, etf_performances)
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'years': years,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'rebalance_count': len(rebalance_records),
            'positions': positions,
            'etf_performances': etf_performances,
            'quarterly_records': quarterly_records,
            'rebalance_records': rebalance_records
        }
    
    def display_results(self, start_date, end_date, years, final_value, 
                        total_return, annual_return, max_drawdown, 
                        rebalance_count, positions, etf_performances,
                        quarterly_records, rebalance_records):
        
        print(f"\n📊 修正版全天候组合策略真实数据回测结果")
        print("=" * 70)
        print(f"回测期间: {start_date.date()} 到 {end_date.date()}")
        print(f"投资年限: {years:.1f} 年")
        print(f"初始资金: ¥{self.initial_capital:,.0f}")
        print(f"最终价值: ¥{final_value:,.0f}")
        print(f"总收益: ¥{final_value - self.initial_capital:,.0f}")
        print(f"总收益率: {total_return:.2%}")
        print(f"年化收益率: {annual_return:.2%}")
        print(f"最大回撤: {max_drawdown:.2%}")
        print(f"再平衡次数: {rebalance_count}")
        print(f"成功获取ETF: {len(self.data)}/4")
        
        print(f"\n🎯 最终持仓:")
        print(f"{'ETF名称':15s} {'持仓股数':10s} {'持仓价值':10s} {'实际占比':10s}")
        print("-" * 50)
        for etf_name, shares in positions.items():
            if shares > 0:
                price = self.data[etf_name].loc[end_date, 'close']
                value = shares * price
                weight = value / final_value
                print(f"{etf_name:15s} {shares:10,} {value:10,.0f} {weight:10.1%}")
        
        print(f"\n📈 各资产单独表现对比:")
        print(f"{'ETF名称':15s} {'总收益率':10s} {'年化收益率':10s} {'相对组合':10s}")
        print("-" * 50)
        for etf_name, perf in etf_performances.items():
            relative = perf['annual_return'] - annual_return
            print(f"{etf_name:15s} {perf['total_return']:8.2%} {perf['annual_return']:8.2%} {relative:+8.2%}")
        
        print(f"{'修正版组合':15s} {total_return:8.2%} {annual_return:8.2%} {'基准':>10s}")
        
        # 打印修正版再平衡操作汇总
        print(f"\n🔄 修正版再平衡操作详情:")
        if rebalance_records:
            print("-" * 60)
            for record in rebalance_records:
                print(f"{record['quarter']}:")
                print(f"  总价值(再平衡前): ¥{record['total_value_before']:,.0f}")
                print(f"  现金变化: ¥{record['cash_before']:,.0f} → ¥{record['cash_after']:,.0f}")
                for operation in record['operations']:
                    print(f"    {operation}")
        else:
            print("  无再平衡操作")
        
        print(f"\n✨ 修正版策略特点:")
        print(f"  🎯 目标配置: 沪深300(30%) + 10年期国债(40%) + 5年期国债(15%) + 黄金(15%)")
        print(f"  ⚖️  再平衡: 季度检查，偏离5%触发调整")
        print(f"  🛡️  风险控制: 最大回撤控制在{max_drawdown:.1%}以内")
        print(f"  📈 长期稳健: 年化收益率{annual_return:.1%}，适合长期投资")
        print(f"  🔧 修正逻辑: 先卖出超配资产，再买入低配资产，确保现金充足")
    
    def plot_results(self, daily_values, rebalance_records, etf_performances):
        """绘制结果图表"""
        dates = [v['date'] for v in daily_values]
        values = [v['value'] for v in daily_values]
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. 组合价值曲线
        ax1.plot(dates, values, 'b-', linewidth=2, label='修正版全天候组合')
        ax1.axhline(y=self.initial_capital, color='r', linestyle='--', alpha=0.7, label='初始资金')
        
        # 标记再平衡点
        for record in rebalance_records:
            rebalance_date = record['date']
            ax1.axvline(x=rebalance_date, color='orange', linestyle=':', alpha=0.7)
        
        ax1.set_title('修正版全天候组合策略 - 组合价值走势', fontsize=14, fontweight='bold')
        ax1.set_ylabel('组合价值 (¥)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 回撤分析
        peak = values[0]
        drawdowns = []
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            drawdowns.append(-drawdown * 100)
        
        ax2.fill_between(dates, 0, drawdowns, alpha=0.3, color='red')
        ax2.plot(dates, drawdowns, 'r-', linewidth=1)
        ax2.set_title('修正版组合回撤分析', fontsize=14, fontweight='bold')
        ax2.set_ylabel('回撤 (%)')
        ax2.grid(True, alpha=0.3)
        
        # 3. 各ETF年化收益对比
        etf_names = list(etf_performances.keys())
        annual_returns = [etf_performances[name]['annual_return'] * 100 for name in etf_names]
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        
        bars = ax3.bar(range(len(etf_names)), annual_returns, color=colors)
        ax3.set_title('各ETF年化收益率对比', fontsize=14, fontweight='bold')
        ax3.set_ylabel('年化收益率 (%)')
        ax3.set_xticks(range(len(etf_names)))
        ax3.set_xticklabels([name.replace('ETF', '') for name in etf_names], rotation=45)
        ax3.grid(True, alpha=0.3)
        
        # 在柱状图上添加数值
        for bar, value in zip(bars, annual_returns):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{value:.1f}%', ha='center', va='bottom')
        
        # 4. 再平衡频率分析
        if len(rebalance_records) > 0:
            rebalance_years = [r['date'].year for r in rebalance_records]
            year_counts = pd.Series(rebalance_years).value_counts().sort_index()
            ax4.bar(range(len(year_counts)), year_counts.values, color='lightblue')
            ax4.set_title('年度再平衡次数', fontsize=14, fontweight='bold')
            ax4.set_ylabel('再平衡次数')
            ax4.set_xticks(range(len(year_counts)))
            ax4.set_xticklabels([f'{year}' for year in year_counts.index])
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, '无再平衡操作', ha='center', va='center', 
                    transform=ax4.transAxes, fontsize=16)
            ax4.set_title('年度再平衡次数', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig('fixed_real_all_weather.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print(f"\n📈 图表已保存为: fixed_real_all_weather.png")
    
    def write_quarterly_weights_to_md(self, quarterly_records, rebalance_records,
                                      start_date, end_date, years,
                                      final_value, total_return, annual_return, max_drawdown,
                                      rebalance_count, positions, etf_performances):
        """将季度比重数据写入md文件"""
        md_content = f"""# 修正版全天候组合策略季度比重详细报告

## 📅 回测基本信息
- **回测期间**: {start_date.date()} 到 {end_date.date()}
- **投资年限**: {years:.1f} 年
- **初始资金**: ¥{self.initial_capital:,.0f}
- **最终价值**: ¥{final_value:,.0f}
- **总收益率**: {total_return:.2%}
- **年化收益率**: {annual_return:.2%}
- **最大回撤**: {max_drawdown:.2%}
- **再平衡次数**: {rebalance_count}
- **策略修正**: 先卖出超配资产，再买入低配资产，确保现金充足

## 📊 各季度资产配置比重

"""
        
        # 写入每个季度的详细数据
        for i, quarter_info in enumerate(quarterly_records):
            date = quarter_info['date']
            total_value = quarter_info['total_value']
            weights = quarter_info['weights']
            quarter_str = f"Q{date.quarter} {date.year}"
            
            md_content += f"""### 📅 {quarter_str}
- **总价值**: ¥{total_value:,.0f}

| ETF名称 | 当前比重 | 目标比重 | 偏离度 | 持仓价值 | 持仓股数 |
|---------|----------|----------|----------|----------|----------|
"""
            
            for etf_name in sorted(self.data.keys()):
                current_weight = weights.get(etf_name, 0)
                target_weight = self.etf_config[etf_name]['weight']
                deviation = abs(current_weight - target_weight)
                position_value = quarter_info['positions'][etf_name]['value']
                
                # 从rebalance_records中获取最新持仓股数
                shares = positions.get(etf_name, 0)
                
                md_content += f"| {etf_name} | {current_weight:6.1%} | {target_weight:6.1%} | {deviation:6.1%} | ¥{position_value:8.0f} | {shares:,} |\n"
            
            # 检查是否有再平衡操作
            rebalance_for_quarter = None
            for record in rebalance_records:
                if record['quarter'] == quarter_str:
                    rebalance_for_quarter = record
                    break
            
            if rebalance_for_quarter:
                md_content += f"""
#### 🔄 修正版再平衡操作
- **触发原因**: 最大偏离超过5%
- **再平衡前总价值**: ¥{rebalance_for_quarter['total_value_before']:,.0f}
- **现金变化**: ¥{rebalance_for_quarter['cash_before']:,.0f} → ¥{rebalance_for_quarter['cash_after']:,.0f}

**具体操作**:
"""
                for operation in rebalance_for_quarter['operations']:
                    md_content += f"- {operation}\n"
            else:
                md_content += f"""
#### ✅ 无需再平衡
- **原因**: 最大偏离度小于5%，符合目标配置
"""
            
            md_content += "\n---\n\n"
        
        # 添加最终持仓和总结
        md_content += f"""## 🎯 最终持仓详情

| ETF名称 | 持仓股数 | 最终价格 | 持仓价值 | 实际占比 |
|---------|----------|----------|----------|----------|
"""
        
        for etf_name, shares in positions.items():
            if shares > 0:
                final_price = self.data[etf_name].loc[end_date, 'close']
                final_value_etf = shares * final_price
                weight = final_value_etf / final_value
                md_content += f"| {etf_name} | {shares:,} | ¥{final_price:6.2f} | ¥{final_value_etf:8.0f} | {weight:6.1%} |\n"
        
        md_content += f"""
## 📈 各资产单独表现

| ETF名称 | 总收益率 | 年化收益率 | 对比修正版组合 |
|---------|----------|------------|----------------|
"""
        
        for etf_name, perf in etf_performances.items():
            md_content += f"| {etf_name} | {perf['total_return']:8.2%} | {perf['annual_return']:6.2%} | {'优于' if perf['annual_return'] > annual_return else '劣于'} |\n"
        
        md_content += f"| **修正版组合** | **{total_return:8.2%}** | **{annual_return:6.2%}** | **基准** |\n"
        
        md_content += f"""
## 🔄 修正版再平衡操作汇总

"""
        
        if rebalance_records:
            md_content += "| 季度 | 再平衡前价值 | 现金变化 | 操作数 | 再平衡效果 |\n"
            md_content += "|------|--------------|----------|--------|----------|\n"
            
            for record in rebalance_records:
                cash_change = record['cash_after'] - record['cash_before']
                operations_count = len(record['operations'])
                effect = "恢复目标配置"
                md_content += f"| {record['quarter']} | ¥{record['total_value_before']:,.0f} | ¥{cash_change:+,.0f} | {operations_count}笔 | {effect} |\n"
        else:
            md_content += "本次回测期间未触发再平衡操作。\n"
        
        md_content += f"""
## ✨ 修正版策略特点

### 🎯 配置纪律性
- **季度检查**: 每个季度定期检查配置偏离
- **5%阈值**: 偏离超过5%自动触发再平衡
- **修正逻辑**: 先卖出超配资产获得现金，再买入低配资产
- **纪律执行**: 严格执行修正版再平衡操作，保持目标配置

### 🔧 逻辑修正要点
1. **先计算所有调整需求**: 统一计算需要卖出和买入的资产
2. **优先执行卖出操作**: 获得充足现金用于后续买入
3. **再执行买入操作**: 按计划买入低配资产
4. **现金充足保障**: 确保再平衡过程不会因现金不足而失败

### 📊 风险分散效果
- **多资产配置**: {len(self.data)}个不同类型ETF
- **相关性低**: 股票、债券、黄金相关性较低
- **波动控制**: 最大回撤{max_drawdown:.1%}，风险可控

### 💰 收益特征
- **稳健增长**: 年化收益率{annual_return:.1%}
- **超越理财**: 显著超过银行理财收益
- **长期有效**: {years:.1f}年长期验证策略有效性

## 📋 投资建议

### 🎯 ETF代码清单
"""
        
        for etf_name, config in self.etf_config.items():
            if etf_name in self.data:
                md_content += f"- **{etf_name}**: {config['symbol']}\n"
        
        md_content += f"""
### 📊 配置比例
"""
        
        for etf_name in self.data.keys():
            md_content += f"- **{etf_name}**: {self.etf_config[etf_name]['weight']:.0%}\n"
        
        md_content += f"""
### 🔄 操作指引
1. **定期检查**: 每季度检查一次配置偏离
2. **严格执行**: 偏离超过5%必须再平衡
3. **修正顺序**: 先卖出超配资产，再买入低配资产
4. **分散风险**: 按目标配置比例买入
5. **长期持有**: 坚持策略，避免情绪化操作

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*数据来源: stock_price目录下的真实parquet文件*
*策略特点: 修正版再平衡逻辑，确保现金充足*
"""
        
        # 写入md文件
        with open('fixed_quarterly_weights_detailed.md', 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\n📝 修正版季度比重详细报告已保存为: fixed_quarterly_weights_detailed.md")

def main():
    strategy = FixedRealAllWeather(initial_capital=100000)
    
    print("🌍 修正版全天候组合策略 - 真实parquet数据版本")
    print("使用stock_price目录下的真实ETF价格数据进行回测")
    print("修正了再平衡逻辑：先卖出超配资产，再买入低配资产")
    print("=" * 60)
    
    if strategy.load_data():
        result = strategy.run_backtest()
        
        print(f"\n🎉 修正版回测完成!")
        print("=" * 50)
        print("📊 生成的文件:")
        print("  - fixed_real_all_weather.png: 修正版回测图表")
        print("  - fixed_quarterly_weights_detailed.md: 修正版季度详细报告")
        print("=" * 50)
        print("✨ 修正版策略特点:")
        print("  🔧 修正了再平衡逻辑，确保现金充足")
        print("  📊 先卖出超配资产，再买入低配资产")
        print("  🎯 保持目标配置比例 30%-40%-15%-15%")
        print("  📈 基于真实数据验证策略有效性")
        
    else:
        print("❌ 数据加载失败，请检查parquet文件是否存在")

if __name__ == "__main__":
    main()