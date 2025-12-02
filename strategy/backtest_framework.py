#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单股票回测框架
支持多种策略切换，计算收益率和夏普比率，可视化结果
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import json
import akshare as ak

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

class Position:
    """持仓信息"""
    def __init__(self):
        self.quantity = 0  # 持股数量
        self.cost_price = 0  # 成本价
        self.total_cost = 0  # 总成本
        
class Signal:
    """交易信号"""
    HOLD = 0
    BUY = 1
    SELL = 2

class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        生成交易信号
        
        Args:
            data: 包含OHLCV数据的DataFrame
            
        Returns:
            pd.Series: 交易信号 (0=持有, 1=买入, 2=卖出)
        """
        pass
        
    def __str__(self):
        return f"{self.name}策略"

class GoldenCrossStrategy(BaseStrategy):
    """金叉策略 - 短期均线向上穿越长期均线时买入"""
    
    def __init__(self, short_window=5, long_window=20):
        super().__init__(f"金叉策略({short_window}/{long_window})")
        self.short_window = short_window
        self.long_window = long_window
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if len(data) < self.long_window:
            return pd.Series([Signal.HOLD] * len(data), index=data.index)
            
        # 计算移动平均线
        short_ma = data['close'].rolling(window=self.short_window).mean()
        long_ma = data['close'].rolling(window=self.long_window).mean()
        
        signals = pd.Series([Signal.HOLD] * len(data), index=data.index)
        
        # 金叉买入：短期均线上穿长期均线
        buy_signals = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
        
        # 死叉卖出：短期均线下穿长期均线
        sell_signals = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))
        
        signals[buy_signals] = Signal.BUY
        signals[sell_signals] = Signal.SELL
        
        return signals

class RSIStrategy(BaseStrategy):
    """RSI策略 - RSI超买超卖策略"""
    
    def __init__(self, rsi_period=14, oversold=30, overbought=70):
        super().__init__(f"RSI策略({rsi_period},{oversold},{overbought})")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if len(data) < self.rsi_period + 1:
            return pd.Series([Signal.HOLD] * len(data), index=data.index)
            
        rsi = self.calculate_rsi(data['close'])
        signals = pd.Series([Signal.HOLD] * len(data), index=data.index)
        
        # RSI超卖区域买入
        buy_signals = (rsi < self.oversold) & (rsi.shift(1) >= self.oversold)
        
        # RSI超买区域卖出
        sell_signals = (rsi > self.overbought) & (rsi.shift(1) <= self.overbought)
        
        signals[buy_signals] = Signal.BUY
        signals[sell_signals] = Signal.SELL
        
        return signals

class DualThrustStrategy(BaseStrategy):
    """Dual Thrust策略 - 基于价格突破的策略"""
    
    def __init__(self, lookback_period=20, k1=0.5, k2=0.5):
        super().__init__(f"Dual Thrust策略({lookback_period},{k1},{k2})")
        self.lookback_period = lookback_period
        self.k1 = k1
        self.k2 = k2
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        if len(data) < self.lookback_period + 1:
            return pd.Series([Signal.HOLD] * len(data), index=data.index)
            
        signals = pd.Series([Signal.HOLD] * len(data), index=data.index)
        
        for i in range(self.lookback_period, len(data)):
            # 获取前N天的数据
            lookback_data = data.iloc[i-self.lookback_period:i]
            
            # 计算最高价、最低价、收盘价的范围
            hh = lookback_data['high'].max()
            ll = lookback_data['low'].min()
            hc = lookback_data['close'].max()
            lc = lookback_data['close'].min()
            
            # 计算买入线和卖出线
            buy_line = max(hh - lc, hc - ll) * self.k1 + data.iloc[i]['open']
            sell_line = min(hc - ll, hh - lc) * self.k2 + data.iloc[i]['open']
            
            # 生成信号
            if data.iloc[i]['close'] > buy_line:
                signals.iloc[i] = Signal.BUY
            elif data.iloc[i]['close'] < sell_line:
                signals.iloc[i] = Signal.SELL
                
        return signals

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital: float = 100000.0, commission_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.reset()
        
    def reset(self):
        """重置回测状态"""
        self.capital = self.initial_capital
        self.position = Position()
        self.trades = []  # 交易记录
        self.portfolio_values = []  # 组合价值历史
        self.returns = []  # 收益率历史
        
    def execute_trade(self, signal: int, price: float, date: str, data: pd.DataFrame):
        """执行交易"""
        if signal == Signal.BUY and self.position.quantity == 0:
            # 买入逻辑
            max_shares = int(self.capital / (price * (1 + self.commission_rate)))
            if max_shares > 0:
                trade_amount = max_shares * price
                commission = trade_amount * self.commission_rate
                
                self.position.quantity = max_shares
                self.position.total_cost = trade_amount + commission
                self.position.cost_price = self.position.total_cost / max_shares
                self.capital -= self.position.total_cost
                
                self.trades.append({
                    'date': date,
                    'action': '买入',
                    'price': price,
                    'quantity': max_shares,
                    'amount': trade_amount,
                    'commission': commission,
                    'capital_after': self.capital
                })
                
        elif signal == Signal.SELL and self.position.quantity > 0:
            # 卖出逻辑
            trade_amount = self.position.quantity * price
            commission = trade_amount * self.commission_rate
            
            self.capital += trade_amount - commission
            profit = trade_amount - commission - self.position.total_cost
            profit_rate = profit / self.position.total_cost if self.position.total_cost > 0 else 0
            
            self.trades.append({
                'date': date,
                'action': '卖出',
                'price': price,
                'quantity': self.position.quantity,
                'amount': trade_amount,
                'commission': commission,
                'profit': profit,
                'profit_rate': profit_rate,
                'capital_after': self.capital
            })
            
            self.position.quantity = 0
            self.position.cost_price = 0
            self.position.total_cost = 0
            
    def run_backtest(self, strategy: BaseStrategy, data: pd.DataFrame) -> Dict:
        """运行回测"""
        self.reset()
        
        # 生成交易信号
        signals = strategy.generate_signals(data)
        
        for i, (date, row) in enumerate(data.iterrows()):
            current_price = row['close']
            signal = signals.iloc[i] if i < len(signals) else Signal.HOLD
            
            # 执行交易
            self.execute_trade(signal, current_price, str(date), data)
            
            # 计算当前组合价值
            position_value = self.position.quantity * current_price
            total_value = self.capital + position_value
            self.portfolio_values.append(total_value)
            
            # 计算收益率
            if i == 0:
                self.returns.append(0)
            else:
                daily_return = (total_value - self.portfolio_values[i-1]) / self.portfolio_values[i-1]
                self.returns.append(daily_return)
        
        # 计算回测结果
        results = self.calculate_results(strategy, data)
        return results
        
    def calculate_results(self, strategy: BaseStrategy, data: pd.DataFrame) -> Dict:
        """计算回测结果"""
        if not self.portfolio_values:
            return {}
            
        final_value = self.portfolio_values[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # 计算年化收益率
        trading_days = len(data)
        years = trading_days / 252  # 假设一年252个交易日
        annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # 计算夏普比率
        if len(self.returns) > 1:
            returns_array = np.array(self.returns)
            annualized_volatility = np.std(returns_array) * np.sqrt(252)
            sharpe_ratio = annual_return / annualized_volatility if annualized_volatility > 0 else 0
        else:
            sharpe_ratio = 0
            
        # 计算最大回撤
        peak = np.maximum.accumulate(self.portfolio_values)
        drawdown = (peak - self.portfolio_values) / peak
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # 胜率统计
        profitable_trades = [t for t in self.trades if 'profit' in t and t['profit'] > 0]
        win_rate = len(profitable_trades) / len(self.trades) if self.trades else 0
        
        return {
            'strategy_name': strategy.name,
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'trades': self.trades,
            'portfolio_values': self.portfolio_values,
            'returns': self.returns,
            'data_index': data.index.tolist()
        }
        
    def plot_results(self, results: Dict, data: pd.DataFrame, save_path: Optional[str] = None):
        """绘制回测结果"""
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
        
        # 图1：价格走势和买卖点
        ax1.plot(data.index, data['close'], label='股价', alpha=0.7, linewidth=1)
        
        # 标记买卖点
        buy_dates = [t['date'] for t in results['trades'] if t['action'] == '买入']
        buy_prices = [t['price'] for t in results['trades'] if t['action'] == '买入']
        
        sell_dates = [t['date'] for t in results['trades'] if t['action'] == '卖出']
        sell_prices = [t['price'] for t in results['trades'] if t['action'] == '卖出']
        
        if buy_dates:
            ax1.scatter(buy_dates, buy_prices, color='red', marker='^', s=100, label='买入', zorder=5)
        if sell_dates:
            ax1.scatter(sell_dates, sell_prices, color='green', marker='v', s=100, label='卖出', zorder=5)
            
        ax1.set_title(f"{results['strategy_name']} - 交易信号", fontsize=14, fontweight='bold')
        ax1.set_ylabel('价格', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 图2：组合价值走势
        ax2.plot(data.index, results['portfolio_values'], label='组合价值', linewidth=2, color='blue')
        ax2.axhline(y=results['initial_capital'], color='red', linestyle='--', alpha=0.5, label='初始资金')
        ax2.set_title("组合价值走势", fontsize=14, fontweight='bold')
        ax2.set_ylabel('组合价值', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 图3：收益率曲线
        cumulative_returns = [(v - results['initial_capital']) / results['initial_capital'] 
                             for v in results['portfolio_values']]
        ax3.plot(data.index, cumulative_returns, label='累计收益率', linewidth=2, color='green')
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax3.set_title("收益率曲线", fontsize=14, fontweight='bold')
        ax3.set_ylabel('收益率', fontsize=12)
        ax3.set_xlabel('时间', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 添加回测结果文本
        info_text = f"""回测结果摘要:
策略: {results['strategy_name']}
总收益率: {results['total_return']:.2%}
年化收益率: {results['annual_return']:.2%}
夏普比率: {results['sharpe_ratio']:.2f}
最大回撤: {results['max_drawdown']:.2%}
交易次数: {results['total_trades']}
胜率: {results['win_rate']:.2%}"""
        
        plt.figtext(0.02, 0.02, info_text, fontsize=10, 
                   bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))
        
        plt.tight_layout()
        
        # 保存图片
        if save_path:
            import os
            os.makedirs(save_path, exist_ok=True)
            filename = f"{save_path}/backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        else:
            filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"回测结果图表已保存为: {filename}")
        
        return filename

def get_akshare_data(stock_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    使用akshare获取真实股票数据
    
    Args:
        stock_code: 股票代码 (如 "600519" 或 "000001")
        start_date: 开始日期 (如 "2020-01-01")
        end_date: 结束日期 (如 "2020-12-31")
    
    Returns:
        pd.DataFrame: 包含OHLCV数据的DataFrame
    """
    try:
        print(f"📊 正在获取股票 {stock_code} 的数据...")
        
        # 转换日期格式
        start_str = start_date.replace("-", "") if start_date else None
        end_str = end_date.replace("-", "") if end_date else None
        
        print(f"   日期范围: {start_str} 到 {end_str}")
        
        # 使用稳定的ak.stock_zh_a_hist函数
        if start_str and end_str:
            data = ak.stock_zh_a_hist(
                symbol=stock_code, 
                period="daily", 
                start_date=start_str, 
                end_date=end_str, 
                adjust="qfq"
            )
        else:
            # 如果没有指定日期，获取最近数据
            data = ak.stock_zh_a_hist(
                symbol=stock_code, 
                period="daily", 
                adjust="qfq"
            )
        
        if data.empty:
            print(f"⚠️  警告: 未获取到股票 {stock_code} 的数据")
            return None
        
        print(f"✅ 获取到数据，列名: {list(data.columns)}")
            
        # ak.stock_zh_a_hist 返回中文列名，直接映射
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close', 
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }
        
        print(f"   原始列名: {list(data.columns)}")
        print(f"   列映射: {column_mapping}")
        
        # 重命名列
        data = data.rename(columns=column_mapping)
        
        # 设置日期索引
        if 'date' in data.columns:
            data['date'] = pd.to_datetime(data['date'])
            data.set_index('date', inplace=True)
        
        # 确保我们有必要的列
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in required_cols if col in data.columns]
        
        if len(available_cols) < len(required_cols):
            print(f"⚠️  警告: 数据缺少必要列")
            print(f"   需要的列: {required_cols}")
            print(f"   可用的列: {list(data.columns)}")
            print(f"   缺少的列: {set(required_cols) - set(available_cols)}")
            return None
        
        # 选择需要的列
        result = data[required_cols].copy()
        
        # 确保数据按日期排序
        result.sort_index(inplace=True)
        
        # 过滤日期范围（如果需要）
        if start_date:
            result = result[result.index >= start_date]
        if end_date:
            result = result[result.index <= end_date]
        
        print(f"✅ 成功处理股票 {stock_code} 数据")
        print(f"   数据期间: {result.index[0].date()} 到 {result.index[-1].date()}")
        print(f"   数据行数: {len(result)}")
        print(f"   价格范围: {result['close'].min():.2f} - {result['close'].max():.2f}")
        
        return result
        
    except Exception as e:
        print(f"❌ 获取股票数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_sample_data(days=252) -> pd.DataFrame:
    """生成示例股票数据 (保留原函数作为备用)"""
    np.random.seed(42)
    
    # 生成随机价格走势
    returns = np.random.normal(0.0008, 0.02, days)  # 日收益率
    prices = [100]  # 初始价格
    
    for r in returns:
        prices.append(prices[-1] * (1 + r))
        
    dates = pd.date_range(start='2023-01-01', periods=days, freq='D')
    
    data = pd.DataFrame({
        'close': prices[1:],
        'open': [p * (1 + np.random.normal(0, 0.005)) for p in prices[1:]],
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices[1:]],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices[1:]],
        'volume': np.random.randint(1000000, 10000000, days)
    }, index=dates)
    
    return data

def demo_real_data(stock_code="600519", start_date="2020-01-01", end_date="2020-12-31"):
    """使用真实股票数据演示回测框架"""
    print("=" * 50)
    print(f"股票回测框架演示 - 真实数据")
    print(f"股票代码: {stock_code}")
    print(f"测试期间: {start_date} 到 {end_date}")
    print("=" * 50)
    
    # 获取真实股票数据
    print(f"获取股票 {stock_code} 的真实数据...")
    data = get_akshare_data(stock_code, start_date, end_date)
    
    if data is None:
        print(f"❌ 无法获取股票 {stock_code} 的数据，切换到模拟数据")
        print("生成示例股票数据...")
        data = generate_sample_data(252)
    else:
        print(f"✅ 成功获取真实股票数据")
        print(f"数据期间: {data.index[0]} 到 {data.index[-1]}")
        print(f"数据行数: {len(data)}")
        print(f"价格范围: {data['close'].min():.2f} - {data['close'].max():.2f}")
    
    # 创建策略列表
    strategies = [
        GoldenCrossStrategy(short_window=5, long_window=20),
        RSIStrategy(rsi_period=14, oversold=30, overbought=70),
        DualThrustStrategy(lookback_period=20, k1=0.5, k2=0.5)
    ]
    
    # 创建回测引擎
    engine = BacktestEngine(initial_capital=100000, commission_rate=0.001)
    
    # 对每个策略进行回测
    results_list = []
    
    for strategy in strategies:
        print(f"\n开始回测: {strategy}")
        results = engine.run_backtest(strategy, data)
        results_list.append(results)
        
        print(f"总收益率: {results['total_return']:.2%}")
        print(f"年化收益率: {results['annual_return']:.2%}")
        print(f"夏普比率: {results['sharpe_ratio']:.2f}")
        print(f"最大回撤: {results['max_drawdown']:.2%}")
        print(f"交易次数: {results['total_trades']}")
        print(f"胜率: {results['win_rate']:.2%}")
        
        # 绘制结果
        engine.plot_results(results, data)
    
    # 策略对比
    print(f"\n{'='*50}")
    print("策略对比")
    print(f"{'='*50}")
    print(f"{'策略名称':<20} {'总收益率':<10} {'年化收益率':<10} {'夏普比率':<10} {'最大回撤':<10} {'胜率':<10}")
    print("-" * 80)
    
    for results in results_list:
        print(f"{results['strategy_name']:<20} "
              f"{results['total_return']:<10.2%} "
              f"{results['annual_return']:<10.2%} "
              f"{results['sharpe_ratio']:<10.2f} "
              f"{results['max_drawdown']:<10.2%} "
              f"{results['win_rate']:<10.2%}")

def demo():
    """演示回测框架 - 使用模拟数据（保留作为备用）"""
    print("=" * 50)
    print("股票回测框架演示 - 模拟数据")
    print("=" * 50)
    
    # 生成示例数据
    print("生成示例股票数据...")
    data = generate_sample_data(252)
    print(f"数据期间: {data.index[0]} 到 {data.index[-1]}")
    print(f"数据行数: {len(data)}")
    
    # 创建策略列表
    strategies = [
        GoldenCrossStrategy(short_window=5, long_window=20),
        RSIStrategy(rsi_period=14, oversold=30, overbought=70),
        DualThrustStrategy(lookback_period=20, k1=0.5, k2=0.5)
    ]
    
    # 创建回测引擎
    engine = BacktestEngine(initial_capital=100000, commission_rate=0.001)
    
    # 对每个策略进行回测
    results_list = []
    
    for strategy in strategies:
        print(f"\n开始回测: {strategy}")
        results = engine.run_backtest(strategy, data)
        results_list.append(results)
        
        print(f"总收益率: {results['total_return']:.2%}")
        print(f"年化收益率: {results['annual_return']:.2%}")
        print(f"夏普比率: {results['sharpe_ratio']:.2f}")
        print(f"最大回撤: {results['max_drawdown']:.2%}")
        print(f"交易次数: {results['total_trades']}")
        print(f"胜率: {results['win_rate']:.2%}")
        
        # 绘制结果
        engine.plot_results(results, data, save_path="backtest_charts")
    
    # 策略对比
    print(f"\n{'='*50}")
    print("策略对比")
    print(f"{'='*50}")
    print(f"{'策略名称':<20} {'总收益率':<10} {'年化收益率':<10} {'夏普比率':<10} {'最大回撤':<10} {'胜率':<10}")
    print("-" * 80)
    
    for results in results_list:
        print(f"{results['strategy_name']:<20} "
              f"{results['total_return']:<10.2%} "
              f"{results['annual_return']:<10.2%} "
              f"{results['sharpe_ratio']:<10.2f} "
              f"{results['max_drawdown']:<10.2%} "
              f"{results['win_rate']:<10.2%}")

if __name__ == "__main__":
    # 默认使用真实数据进行演示
    print("选择演示模式:")
    print("1. 使用真实股票数据 (推荐)")
    print("2. 使用模拟数据")
    
    try:
        choice = input("请输入选择 (1 或 2，默认为1): ").strip()
        if choice == "2":
            demo()
        else:
            demo_real_data()
    except:
        # 如果输入失败，默认使用真实数据
        demo_real_data()