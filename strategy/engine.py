import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import akshare as ak
import matplotlib.pyplot as plt

class StrategyAnalyzer:
    """策略分析器"""
    
    def __init__(self):
        self.results = {}
    
    def add_results(self, results: Dict):
        """添加回测结果"""
        self.results.update(results)
    
    def print_comparison(self):
        """打印策略对比"""
        if not self.results:
            print("无回测结果")
            return
        
        print("\n" + "="*80)
        print("A股策略回测对比结果")
        print("="*80)
        
        comparison_data = []
        for name, result in self.results.items():
            metrics = result['metrics'].copy()
            metrics['策略名称'] = name
            comparison_data.append(metrics)
        
        # 创建对比表格
        comparison_df = pd.DataFrame(comparison_data)
        print(comparison_df.to_string(index=False))
        
        return comparison_df
    
    def plot_results(self, data: pd.DataFrame):
        """绘制策略对比图"""
        if not self.results:
            print("无回测结果可绘制")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. 权益曲线对比
        ax1 = axes[0, 0]
        ax1.plot(data.index, data['close'] / data['close'].iloc[0] * 100000, 
                label='Buy', alpha=0.7, linewidth=1)
        
        for name, result in self.results.items():
            ax1.plot(result['data'].index, result['data']['equity_curve'], 
                    label=name, linewidth=2)
        
        ax1.set_title('compare strategy profit')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_ylabel('profit')
        
        # 2. 持仓情况
        ax2 = axes[0, 1]
        for name, result in self.results.items():
            ax2.plot(result['data'].index, result['data']['position'], 
                    label=name, linewidth=1)
        ax2.set_title('position (1=Hold, 0=Close)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_ylabel('position status')
        
        # 3. 累计收益率
        ax3 = axes[1, 0]
        benchmark_returns = (data['close'] / data['close'].iloc[0] - 1) * 100
        ax3.plot(data.index, benchmark_returns, label='Buy and Hold', linestyle='--')
        
        for name, result in self.results.items():
            strategy_returns = (result['data']['equity_curve'] / 100000 - 1) * 100
            ax3.plot(result['data'].index, strategy_returns, label=name)
        
        ax3.set_title('Cumulative Return (%)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        ax3.set_ylabel('Return (%)')
        
        # 4. 回撤情况
        ax4 = axes[1, 1]
        for name, result in self.results.items():
            equity = result['data']['equity_curve']
            running_max = equity.expanding().max()
            drawdown = (equity - running_max) / running_max * 100
            ax4.plot(result['data'].index, drawdown, label=name)
        
        ax4.set_title('drawdown ratio (%)')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        ax4.set_ylabel('drawdown (%)')
        
        plt.tight_layout()
        plt.show()
    
    def print_trade_analysis(self):
        """打印交易分析"""
        print("\n交易分析")
        print("="*50)
        
        for name, result in self.results.items():
            trades = result['trades']
            if not trades:
                print(f"\n{name}: 无交易记录")
                continue
                
            profitable_trades = [t for t in trades if t['is_profitable']]
            win_rate = len(profitable_trades) / len(trades)
            
            avg_profit = np.mean([t['pnl_pct'] for t in profitable_trades]) if profitable_trades else 0
            losing_trades = [t for t in trades if not t['is_profitable']]
            avg_loss = np.mean([t['pnl_pct'] for t in losing_trades]) if losing_trades else 0
            
            print(f"\n策略: {name}")
            print(f"  总交易次数: {len(trades)}")
            print(f"  盈利交易: {len(profitable_trades)}")
            print(f"  亏损交易: {len(losing_trades)}")
            print(f"  胜率: {win_rate:.1%}")
            print(f"  平均盈利: {avg_profit:.2%}")
            print(f"  平均亏损: {avg_loss:.2%}")
            if avg_loss != 0:
                print(f"  盈亏比: {abs(avg_profit/avg_loss):.2f}")
                
class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, **params):
        self.name = name
        self.params = params
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        pass

    def _validate_signal(self, signal):
        """验证信号符合A股规则"""
        # A股只能做多或空仓，不能做空
        if signal < 0:
            return 0  # 将做空信号转为空仓
        return 1 if signal > 0 else 0  # 只返回0或1

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital=100000, commission = 0.001):
        self.initial_capital = initial_capital
        self.commission = commission
        self.strategies = {}
    
    def add_strategy(self, strategy: BaseStrategy):
        """添加策略"""
        self.strategies[strategy.name] = strategy
    
    def run_single(self, data: pd.DataFrame, strategy_name: str) -> Dict:
        """运行单个策略回测"""
        strategy = self.strategies[strategy_name]
        data_with_signals = strategy.generate_signals(data.copy())
        return self._backtest(data_with_signals, strategy.name)
    
    def run_compare(self, data: pd.DataFrame) -> Dict[str, Dict]:
        """比较所有策略"""
        results = {}
        for name in self.strategies:
            results[name] = self.run_single(data, name)
        return results
    
    def _backtest(self, data: pd.DataFrame, strategy_name: str) -> Dict:
        """执行回测"""
        df = data.copy()
        
        # 验证信号格式
        if 'signal' not in df.columns:
            raise ValueError("数据中缺少signal列")
        
        # 确保信号符合A股规则（只允许0和1）
        df['valid_signal'] = df['signal'].apply(lambda x: 1 if x > 0 else 0)
        
        # 使用前一日信号决定今日持仓（避免未来函数）
        df['position'] = df['valid_signal'].shift(1).fillna(0)
        
        # 计算价格收益率
        df['price_returns'] = df['close'].pct_change()
        
        # 计算策略收益率（A股版：只能做多）
        df['strategy_returns'] = df['position'] * df['price_returns']
        
        # 考虑交易成本（只在开仓和平仓时收取）
        position_changes = df['position'].diff().abs().fillna(0)
        df['commission_cost'] = position_changes * self.commission
        df['net_returns'] = df['strategy_returns'] - df['commission_cost']
        
        # 计算累计收益
        df['cumulative_returns'] = (1 + df['net_returns']).cumprod()
        df['equity_curve'] = self.initial_capital * df['cumulative_returns']
        
        # 计算绩效指标
        metrics = self._calculate_performance_metrics(df)
        
        # 提取交易记录
        trades = self._extract_trades(df)
        
        return {
            'strategy_name': strategy_name,
            'data': df,
            'metrics': metrics,
            'trades': trades,
            'parameters': self.strategies[strategy_name].params
        }
    
    def _calculate_performance_metrics(self, df: pd.DataFrame) -> Dict:
        """计算绩效指标"""
        returns = df['net_returns'].dropna()
        
        if len(returns) == 0:
            return {}
        
        # 基本收益指标
        total_return = df['equity_curve'].iloc[-1] / self.initial_capital - 1
        annual_return = (1 + total_return) ** (252/len(df)) - 1
        
        # 风险指标
        volatility = returns.std() * np.sqrt(252)
        sharpe = annual_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        equity = df['equity_curve']
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # 交易统计
        total_trades = len(df[df['position'].diff().fillna(0) != 0]) // 2  # 开平仓算一次交易
        
        # 持仓统计
        holding_days = len(df[df['position'] == 1])
        empty_days = len(df[df['position'] == 0])
        
        return {
            '策略名称': self.strategies[df.name] if hasattr(df, 'name') else '未知',
            '总收益率': f"{total_return:.2%}",
            '年化收益率': f"{annual_return:.2%}",
            '年化波动率': f"{volatility:.2%}",
            '夏普比率': f"{sharpe:.2f}",
            '最大回撤': f"{max_drawdown:.2%}",
            '总交易次数': total_trades,
            '持仓天数': f"{holding_days}天",
            '空仓天数': f"{empty_days}天",
            '持仓比例': f"{holding_days/len(df)*100:.1f}%"
        }
    
    def _extract_trades(self, df: pd.DataFrame) -> List[Dict]:
        """提取交易记录"""
        trades = []
        in_position = False
        entry_date = None
        entry_price = 0
        
        for i in range(1, len(df)):
            current_position = df['position'].iloc[i]
            prev_position = df['position'].iloc[i-1]
            
            if not in_position and current_position == 1:
                # 开仓
                in_position = True
                entry_date = df.index[i]
                entry_price = df['close'].iloc[i]
                
            elif in_position and current_position == 0:
                # 平仓
                exit_date = df.index[i]
                exit_price = df['close'].iloc[i]
                
                # 计算交易结果
                pnl = exit_price - entry_price
                pnl_pct = pnl / entry_price
                holding_days = (exit_date - entry_date).days
                
                trade = {
                    'entry_date': entry_date,
                    'exit_date': exit_date,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'is_profitable': pnl > 0
                }
                trades.append(trade)
                
                in_position = False
        
        return trades

class DualThrustStrategy(BaseStrategy):
    def generate_signals(self, data):
        n_days = self.params.get('n_days', 20)
        k1 = self.params.get('k1', 0.1)
        k2 = self.params.get('k2', 0.9)
        
        df = data.copy()
        
        # 计算范围
        df['range_high'] = df['high'].rolling(n_days).max()
        df['range_low'] = df['low'].rolling(n_days).min()
        df['close_high'] = df['close'].rolling(n_days).max()
        df['close_low'] = df['close'].rolling(n_days).min()
        
        # Dual Thrust范围计算
        range1 = df['range_high'] - df['close_low'].shift(1)
        range2 = df['close_high'].shift(1) - df['range_low']
        thrust_range = np.maximum(range1, range2)
        
        # 计算通道
        df['upper_band'] = df['open'] + k1 * thrust_range
        df['lower_band'] = df['open'] - k2 * thrust_range
        
        # A股版信号逻辑：突破上轨做多，突破下轨空仓
        df['signal'] = 0
        df.loc[df['high'] > df['upper_band'], 'signal'] = 1  # 突破上轨做多
        df.loc[df['low'] < df['lower_band'], 'signal'] = 0   # 突破下轨空仓
        
        return df

def get_stock_data(symbol, start_date, end_date):
    """获取股票数据"""
    df = ak.stock_zh_a_hist(
        symbol=symbol, period="daily",
        start_date=start_date, end_date=end_date,
        adjust="hfq"
    )
    
    df = df.rename(columns={
        '日期': 'date', '开盘': 'open', '最高': 'high',
        '最低': 'low', '收盘': 'close', '成交量': 'volume'
    })
    
    df['date'] = pd.to_datetime(df['date'])
    return df.set_index('date')[['open', 'high', 'low', 'close', 'volume']]

def run_complete_ashare_backtest():
    """运行完整的A股策略回测"""
    
    print("A股多策略回测框架")
    print("="*50)
    
    # 1. 获取数据
    print("1. 获取A股数据...")
    data = get_stock_data('000001', '20200101', '20201229')  # 平安银行
    if data.empty:
        print("数据获取失败")
        return
    
    print(f"获取到 {len(data)} 个交易日数据")
    print(f"数据期间: {data.index[0]} 到 {data.index[-1]}")
    
    # 2. 初始化回测引擎
    engine = BacktestEngine(initial_capital=100000, commission=0.001)
    
    # 3. 注册策略
    strategies = [
        DualThrustStrategy('dual_thrust', n_days=20, k1=0.5, k2=0.5),
        #MovingAverageStrategy('ma_cross', fast_period=5, slow_period=20),
        #RSIStrategy('rsi', period=14, overbought=70, oversold=30),
        #BreakoutStrategy('breakout', breakout_days=20, stop_loss=0.95)
    ]
    
    for strategy in strategies:
        engine.add_strategy(strategy)
        print(f"注册策略: {strategy.name}")
    
    # 4. 运行回测比较
    print("\n2. 运行策略回测...")
    results = engine.run_compare(data)
    
    # 5. 分析结果
    analyzer = StrategyAnalyzer()
    analyzer.add_results(results)
    
    # 6. 显示结果
    comparison_df = analyzer.print_comparison()
    analyzer.plot_results(data)
    analyzer.print_trade_analysis()
    
    # 7. 基准对比
    bh_return = data['close'].iloc[-1] / data['close'].iloc[0] - 1
    print(f"\n基准（买入持有）收益率: {bh_return:.2%}")
    
    return results, data, analyzer

# 运行完整回测
results, data, analyzer = run_complete_ashare_backtest()