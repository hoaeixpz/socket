#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单股票指标绘图器
专门绘制PE、ROE、PEG三个指标在一张图中
"""

import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import json

class SimpleStockPlotter:
    """简单股票指标绘图器 - 专门绘制PE、ROE、PEG"""
    
    def __init__(self, figsize=(15, 10)):
        """初始化绘图器"""
        self.figsize = figsize
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False
        
    def plot_three_indicators(self, stock_data, stock_code, save_path=None):
        """
        在一张图中绘制PE、ROE、PEG三个指标，直接保存为图片
        
        Args:
            stock_data: 股票数据字典（参考test_stocks.json格式）
            stock_code: 股票代码
            save_path: 保存路径，如果为None则保存在当前目录
        """
        # 创建图表
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=self.figsize)
        fig.suptitle(f'{stock_code} {stock_data.get("stock_name", "")} - PE/ROE/PEG分析', fontsize=16, fontweight='bold')
        
        # 提取数据
        roe_details = stock_data.get('roe_details', {})
        pe_analysis = stock_data.get('pe_analysis', {})
        
        # 1. 绘制ROE图
        self._plot_roe_simple(ax1, roe_details, stock_code)
        
        # 2. 绘制PE图
        self._plot_pe_simple(ax2, pe_analysis, stock_code)
        
        # 3. 绘制PEG图
        self._plot_peg_simple(ax3, pe_analysis, stock_code)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.93)
        
        # 保存图片（不显示）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if save_path:
            import os
            os.makedirs(save_path, exist_ok=True)
            filename = os.path.join(save_path, f"{stock_code}_three_indicators_{timestamp}.png")
        else:
            filename = f"{stock_code}_three_indicators_{timestamp}.png"
        
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close(fig)  # 关闭图形以释放内存
        print(f"图表已保存为: {filename}")
        return filename
    
    def _plot_roe_simple(self, ax, roe_details, stock_code):
        """绘制简单的ROE趋势图"""
        if not roe_details:
            ax.text(0.5, 0.5, '无ROE数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('ROE趋势', fontsize=14)
            return
        
        # 提取年份和ROE值
        years = sorted([int(year) for year in roe_details.keys() if year.isdigit()])
        print(f"years: {years}")
        roe_values = [roe_details[str(year)] for year in years]
        print(f"roe_values: {roe_values}")
        
        # 绘制折线图
        ax.plot(years, roe_values, 'o-', color='#2E86AB', linewidth=3, markersize=8, markerfacecolor='white', markeredgewidth=2)
        ax.set_title('ROE趋势 (%)', fontsize=14, fontweight='bold')
        ax.set_xlabel('年份', fontsize=12)
        ax.set_ylabel('ROE (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # 设置Y轴范围，确保包含0
        y_min = min(0, min(roe_values)) - 5
        y_max = max(roe_values) + 5
        ax.set_ylim(y_min, y_max)
        print(f"y_min: {y_min}, y_max: {y_max}")
        
        # 添加水平参考线
        ax.axhline(y=10, color='green', linestyle='--', alpha=0.5, label='优秀线(10%)')
        ax.axhline(y=5, color='orange', linestyle='--', alpha=0.5, label='及格线(5%)')
        ax.axhline(y=0, color='red', linestyle='-', alpha=0.3)
        
        # 添加数据标签
        # for i, (year, roe) in enumerate(zip(years, roe_values)):
        #     color = 'green' if roe >= 10 else 'orange' if roe >= 5 else 'red'
        #     ax.annotate(f'{roe:.1f}%', (year, roe), textcoords="offset points", 
        #                xytext=(0,10), ha='center', fontsize=10, color=color, fontweight='bold')
        
        # ax.legend()
    
    def _plot_pe_simple(self, ax, pe_analysis, stock_code):
        """绘制简单的PE估值图"""
        if not pe_analysis:
            ax.text(0.5, 0.5, '无PE数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('PE估值', fontsize=14)
            return
        
        historical_pe = pe_analysis.get('historical_pe', {})
        current_pe_list = pe_analysis.get('current_pe', [])
        
        
        if historical_pe:
            # 提取历史PE数据
            # 处理年份格式（可能包含季度信息）
            years_data = {}
            for date_str, pe_value in historical_pe.items():
                year = int(date_str[:4])  # 取前4位作为年份
                if year not in years_data or date_str > max(years_data.keys(), key=lambda x: x[:4]):
                    years_data[year] = pe_value
            
            years = sorted(years_data.keys())
            pe_values = [years_data[year] for year in years]
            
            # valid_data = [(year, pe) for year, pe in zip(years, pe_values) if pe]
            # if valid_data:
            #     years, pe_values = zip(*valid_data)
            #     years, pe_values = list(years), list(pe_values)
            # else:
            #     ax.text(0.5, 0.5, '无有效PE数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
            #     ax.set_title('PE估值', fontsize=14)
            #     return
            
            # 绘制历史PE
            ax.plot(years, pe_values, 's-', color='#A23B72', linewidth=2, markersize=6, label='历史PE')
            
            # 添加当前PE点
            dong_pe = current_pe_list[0]
            jing_pe = current_pe_list[1]
            TTM_pe = current_pe_list[2]
            latest_year = max(years) if years else datetime.now().year
            ax.plot(latest_year, dong_pe, 'ro', markersize=10, label=f'动态PE ({dong_pe:.1f})')
            ax.plot(latest_year, jing_pe, 'bo', markersize=10, label=f'静态PE ({jing_pe:.1f})')
            ax.plot(latest_year, TTM_pe, 'go', markersize=10, label=f'TTM PE ({TTM_pe:.1f})')
            
            ax.set_title('PE估值趋势', fontsize=14, fontweight='bold')
            ax.set_xlabel('年份', fontsize=12)
            ax.set_ylabel('PE Ratio', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # 添加估值区间参考线
            ax.axhline(y=15, color='green', linestyle='--', alpha=0.5, label='合理区间(15)')
            ax.axhline(y=30, color='red', linestyle='--', alpha=0.5, label='高估警戒(30)')
            
            ax.legend()
        else:
            # 只显示当前PE
            if current_pe and current_pe > 0:
                ax.bar(['当前PE'], [current_pe], color=['#F18F01'], alpha=0.7)
                ax.set_title(f'当前PE: {current_pe:.1f}', fontsize=14, fontweight='bold')
                ax.set_ylabel('PE Ratio', fontsize=12)
                
                # 添加估值区间参考线
                ax.axhline(y=15, color='green', linestyle='--', alpha=0.5, label='合理区间')
                ax.axhline(y=30, color='red', linestyle='--', alpha=0.5, label='高估警戒')
                ax.legend()
            else:
                ax.text(0.5, 0.5, '无有效PE数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
    
    def _plot_peg_simple(self, ax, pe_analysis, stock_code):
        """绘制简单的PEG图"""
        if not pe_analysis:
            ax.text(0.5, 0.5, '无PEG数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('PEG指标', fontsize=14)
            return
        
        historical_peg = pe_analysis.get('historical_peg', {})
        
        if historical_peg:
            # 提取年份和PEG值
            years = sorted([int(year) for year in historical_peg.keys() if year.isdigit()])
            peg_values = [historical_peg[str(year)] for year in years]
            
            # 过滤有效PEG值（排除极端值）
            valid_peg = []
            valid_years = []
            for year, peg in zip(years, peg_values):
                if peg is not None and abs(peg) < 100:  # 排除极端值
                    valid_peg.append(peg)
                    valid_years.append(year)
            
            if not valid_peg:
                ax.text(0.5, 0.5, '无有效PEG数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
                ax.set_title('PEG指标', fontsize=14)
                return
            
            # 绘制PEG图
            colors = ['green' if 0 < peg <= 1 else 'orange' if peg <= 2 else 'red' for peg in valid_peg]
            bars = ax.bar(valid_years, valid_peg, color=colors, alpha=0.7)
            
            ax.set_title('PEG指标分析', fontsize=14, fontweight='bold')
            ax.set_xlabel('年份', fontsize=12)
            ax.set_ylabel('PEG Ratio', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # 添加PEG参考线
            #ax.axhline(y=1, color='blue', linestyle='--', alpha=0.7, label='PEG=1 (合理)')
            #ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            
            # 添加数据标签
            for bar, peg in zip(bars, valid_peg):
                height = bar.get_height()
                va = 'bottom' if height >= 0 else 'top'
                y_offset = 3 if height >= 0 else -3
                ax.text(bar.get_x() + bar.get_width()/2, height, 
                       f'{peg:.2f}', ha='center', va=va, fontsize=9, fontweight='bold')
            
            # 添加图例说明
            ax.legend()
            
            # 添加PEG说明文本
            ax.text(0.02, 0.98, 'PEG说明:\n• PEG<1: 可能被低估\n• PEG=1: 合理估值\n• PEG>1: 可能被高估', 
                   transform=ax.transAxes, fontsize=10, va='top', ha='left',
                   bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.5))
        else:
            ax.text(0.5, 0.5, '无PEG数据', ha='center', va='center', transform=ax.transAxes, fontsize=12)
    
    def plot_for_stock(self, json_file_path, stock_code, save_path=None):
        """
        从JSON文件中读取特定股票数据并绘图，直接保存为图片
        
        Args:
            json_file_path: JSON文件路径
            stock_code: 股票代码
            save_path: 保存路径，如果为None则保存在当前目录
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                all_stocks_data = json.load(f)
            
            if stock_code in all_stocks_data:
                stock_data = all_stocks_data[stock_code]
                filename = self.plot_three_indicators(stock_data, stock_code, save_path)
                return filename
            else:
                print(f"在文件 {json_file_path} 中未找到股票代码 {stock_code}")
                return None
        except Exception as e:
            print(f"读取文件失败: {e}")
            return None


def demo():
    """演示如何使用简单绘图器"""
    # 示例数据（基于test_stocks.json格式）
    sample_data = {
        "stock_name": "深物业A",
        "roe_details": {
            "2024": -28.0,
            "2023": 10.26,
            "2022": 12.36,
            "2021": 24.49,
            "2020": 23.47
        },
        "pe_analysis": {
            "current_pe": [142.79, -5.51, -5.65],
            "historical_pe": {
                "20241231": -4.67,
                "20231231": 10.94,
                "20221231": 11.89,
                "20211231": 5.94,
                "20201231": 7.71
            },
            "historical_peg": {
                "2024": 0.01,
                "2023": -0.73,
                "2022": -0.25,
                "2021": 0.16,
                "2020": -5.30
            }
        }
    }
    
    # 创建绘图器并绘图
    plotter = SimpleStockPlotter()
    plotter.plot_three_indicators(sample_data, "000011")


def demo_from_file():
    """从test_stocks.json文件中演示"""
    plotter = SimpleStockPlotter()
    
    # 绘制test_stocks.json中的第一只股票
    plotter.plot_for_stock('test_stocks.json', '002749')


if __name__ == "__main__":
    # 运行演示
    #demo()
    # 或者从文件演示
    demo_from_file()