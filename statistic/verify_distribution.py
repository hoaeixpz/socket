#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# 分析股价每日涨跌幅度是否符合正态分布

from datetime import datetime
import time

import matplotlib.pyplot as plt  # 由于 Backtrader 的问题，此处要求 pip install matplotlib==3.2.2
import akshare as ak  # 升级到最新版
import pandas as pd
import json
import math
import numpy as np
import scipy.stats as stats

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

import sys
sys.path.append("..")
from stock_price_cache import StockPriceCache

stock_price = StockPriceCache()

def get_cz1000_price():
	data = stock_price.get_index_price("000852")
	data.index = pd.to_datetime(data['date'])
	print("000852")
	print(data[0:5])
	return data

def get_hs300_price():
	data = stock_price.get_index_price("399300")
	data.index = pd.to_datetime(data['date'])
	print("399300")
	print(data[0:5])
	return data

def verify_distribution():
    hs300 = get_hs300_price()
    log_price = np.log(hs300['close'])
    #log_price = log_price[-600:-500]
    log_returns = np.diff(log_price) # r_t = ln(P_t) - ln(P_{t-1})

    # 3. 正态性检验（使用Jarque-Bera检验，适合金融数据
    jb_stat, jb_pvalue = stats.jarque_bera(log_returns)
    is_normal = jb_pvalue > 0.05 # 如果p值大于0.05，则在5%显著性水平下无法拒绝正态分布的原假设
    
    print("对数收益率统计摘要:")
    print(f"  样本数: {len(log_returns)}")
    print(f"  均值: {log_returns.mean():.6f}")
    print(f"  标准差: {log_returns.std():.6f}")
    print(f"  偏度: {stats.skew(log_returns):.4f}")
    print(f"  峰度: {stats.kurtosis(log_returns):.4f}") # 注意：这是超额峰度，正态分布为0
    print(f"\nJarque-Bera正态性检验:")
    print(f"  统计量: {jb_stat:.4f}, P值: {jb_pvalue:.6f}")
    print(f"  是否符合正态分布 (p>0.05)? {'是' if is_normal else '否'}")
    
    # 4. 绘制直方图与拟合的正态分布曲线
    plt.figure(figsize=(12, 6))
    
    # 绘制直方图（密度归一化）
    n, bins, patches = plt.hist(log_returns, bins=50, density=True, 
                                alpha=0.7, color='steelblue', edgecolor='black', 
                                label='对数收益率分布')
    
    # 计算并绘制拟合的正态分布曲线
    mu, sigma = log_returns.mean(), log_returns.std() # 正态分布的参数（均值，标准差）
    # 在直方图的X轴范围内生成一系列点
    x = np.linspace(log_returns.min(), log_returns.max(), 1000)
    # 计算这些点对应的正态分布概率密度
    normal_curve = (1/(sigma * np.sqrt(2*np.pi))) * np.exp(-0.5 * ((x - mu)/sigma)**2)
    plt.plot(x, normal_curve, 'r-', linewidth=3, label=f'拟合正态曲线\n(μ={mu:.4f}, σ={sigma:.4f})')
    
    # 添加图形标注和美化
    plt.title('对数收益率分布与正态分布拟合', fontsize=15, fontweight='bold', pad=15)
    plt.xlabel('对数收益率', fontsize=12)
    plt.ylabel('概率密度', fontsize=12)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # 在图上添加正态性检验结果文本
    textstr = '\n'.join((
        f'Jarque-Bera检验:',
        f'  统计量 = {jb_stat:.4f}',
        f'  P值 = {jb_pvalue:.4f}',
        f'  正态性: {"接受" if is_normal else "拒绝"}'))
    plt.text(0.02, 0.98, textstr, transform=plt.gca().transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.show()
    
    # 5. 输出最终结论
    print("\n" + "="*50)
    print("分析结论:")
    if is_normal:
        print(f"  在5%的显著性水平下，无法拒绝对数收益率服从正态分布的原假设。")
        print(f"  分布特征接近正态，但实际金融数据中完全符合的情况较少。")
    else:
        print(f"  在5%的显著性水平下，拒绝对数收益率服从正态分布的原假设。")
        print(f"  典型的金融数据特征：")
        print(f"    • 偏度 = {stats.skew(log_returns):.4f} (正态为0)")
        print(f"    • 超额峰度 = {stats.kurtosis(log_returns):.4f} (正态为0)")
        if stats.kurtosis(log_returns) > 0:
            print(f"    → 具有'尖峰厚尾'特征，极端值概率高于正态分布预测")
    
verify_distribution()
