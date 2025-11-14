#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析有潜力的股票
基于ROE和PE指标进行综合评估
"""

import json
import pandas as pd
from datetime import datetime
import simple_stock_plotter
from simple_stock_plotter import SimpleStockPlotter

class StockAnalyzer:
    """股票分析器"""
    
    def __init__(self):
        self.analysis_criteria = {
            'roe_threshold': 10.0,  # ROE阈值
            'pe_threshold': 20.0,   # PE阈值
            'min_good_years': 3,    # 最少良好年份数
            'max_bad_years': 1      # 最多不良年份数
        }
    
    def load_stock_data(self, file_path='good_stocks.json'):
        """加载股票数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载数据失败: {e}")
            return {}
    
    def analyze_roe_trend(self, roe_details):
        """分析ROE趋势"""
        years = sorted([int(year) for year in roe_details.keys() if year.isdigit()])
        roe_values = [roe_details[str(year)] for year in years]
        
        # 计算趋势
        if len(roe_values) >= 2:
            trend = roe_values[-1] - roe_values[0]
            recent_trend = roe_values[-1] - roe_values[-2] if len(roe_values) >= 2 else 0
        else:
            trend = 0
            recent_trend = 0
        
        return {
            'years': years,
            'roe_values': roe_values,
            'trend': trend,
            'recent_trend': recent_trend,
            'avg_roe': sum(roe_values) / len(roe_values) if roe_values else 0
        }
    
    def analyze_pe_valuation(self, pe_data):
        """分析PE估值，包括历史PE分析"""
        if not pe_data:
            return {'status': 'unknown', 'reason': '无PE数据', 'historical_analysis': {}}
        
        current_pe_list = pe_data.get('current_pe', [])
        historical_pe = pe_data.get('historical_pe', {})
        
        # 获取当前PE（取第一个有效值）
        current_pe = None
        for pe in current_pe_list:
            if pe and pe > 0:
                current_pe = pe
                #break
        
        # 分析历史PE
        historical_analysis = self.analyze_historical_pe(historical_pe)
        
        # 如果当前PE数据缺失，尝试使用历史PE数据
        if current_pe is None and historical_pe:
            # 取最近一年的PE作为当前PE
            years = sorted([int(year) for year in historical_pe.keys() if year.isdigit()], reverse=True)
            if years:
                current_pe = historical_pe.get(str(years[0]))
        
        # 分析估值状态
        if current_pe is None:
            return {
                'status': 'unknown', 
                'reason': '无有效PE数据',
                'historical_analysis': historical_analysis
            }
        
        # 结合历史PE分析当前估值
        valuation_status = self.get_valuation_status(current_pe, historical_analysis)
        
        return {
            'status': valuation_status['status'],
            'reason': valuation_status['reason'],
            'current_pe': current_pe,
            'historical_analysis': historical_analysis
        }
    
    def analyze_historical_pe(self, historical_pe):
        """分析历史PE数据"""
        if not historical_pe:
            return {
                'status': 'no_data',
                'reason': '无历史PE数据',
                'avg_pe': 0,
                'pe_trend': 0,
                'pe_range': (0, 0),
                'years_analyzed': 0
            }
        
        # 提取有效年份和PE值
        years = sorted([int(year) for year in historical_pe.keys() if year.isdigit()])
        pe_values = [historical_pe[str(year)] for year in years if historical_pe[str(year)] and historical_pe[str(year)] > 0]
        
        if not pe_values:
            return {
                'status': 'invalid_data',
                'reason': '历史PE数据无效',
                'avg_pe': 0,
                'pe_trend': 0,
                'pe_range': (0, 0),
                'years_analyzed': 0
            }
        
        # 计算统计指标
        avg_pe = sum(pe_values) / len(pe_values)
        min_pe = min(pe_values)
        max_pe = max(pe_values)
        
        # 计算PE趋势
        if len(pe_values) >= 2:
            pe_trend = pe_values[-1] - pe_values[0]
            recent_trend = pe_values[-1] - pe_values[-2] if len(pe_values) >= 2 else 0
        else:
            pe_trend = 0
            recent_trend = 0
        
        # 分析历史PE状态
        if len(pe_values) >= 3:
            if pe_trend < -5:
                trend_status = '下降明显'
            elif pe_trend < 0:
                trend_status = '温和下降'
            elif pe_trend > 5:
                trend_status = '上升明显'
            elif pe_trend > 0:
                trend_status = '温和上升'
            else:
                trend_status = '基本稳定'
        else:
            trend_status = '数据不足'
        
        return {
            'status': 'valid',
            'reason': f'历史PE分析完成，{trend_status}',
            'avg_pe': avg_pe,
            'pe_trend': pe_trend,
            'recent_trend': recent_trend,
            'min_pe': min_pe,
            'max_pe': max_pe,
            'pe_range': (min_pe, max_pe),
            'years_analyzed': len(pe_values),
            'trend_status': trend_status
        }
    
    def get_valuation_status(self, current_pe, historical_analysis):
        """结合历史PE分析当前估值状态"""
        
        # 基础估值判断
        if current_pe < 0:
            base_status = 'invalid'
            base_reason = f'PE={current_pe:.1f}，估值无效'
        elif current_pe < 10 :
            base_status = 'undervalued'
            base_reason = f'PE={current_pe:.1f}，估值偏低'
        elif current_pe < 20:
            base_status = 'reasonable'
            base_reason = f'PE={current_pe:.1f}，估值合理'
        elif current_pe < 30:
            base_status = 'slightly_overvalued'
            base_reason = f'PE={current_pe:.1f}，估值略高'
        else:
            base_status = 'overvalued'
            base_reason = f'PE={current_pe:.1f}，估值偏高'
        
        # 如果有历史PE数据，进行更精确的分析
        if historical_analysis['status'] == 'valid':
            avg_pe = historical_analysis['avg_pe']
            min_pe = historical_analysis['min_pe']
            max_pe = historical_analysis['max_pe']
            
            # 相对于历史平均水平的估值
            if current_pe < avg_pe * 0.7:
                historical_reason = f'，显著低于历史平均({avg_pe:.1f})'
                if base_status == 'undervalued':
                    base_status = 'deeply_undervalued'
            elif current_pe < avg_pe * 0.9:
                historical_reason = f'，低于历史平均({avg_pe:.1f})'
            elif current_pe > avg_pe * 1.3:
                historical_reason = f'，显著高于历史平均({avg_pe:.1f})'
                if base_status == 'overvalued':
                    base_status = 'deeply_overvalued'
            elif current_pe > avg_pe * 1.1:
                historical_reason = f'，高于历史平均({avg_pe:.1f})'
            else:
                historical_reason = f'，接近历史平均({avg_pe:.1f})'
            
            # 相对于历史区间的估值
            if current_pe < min_pe * 1.1:
                range_reason = f'，接近历史最低({min_pe:.1f})'
            elif current_pe > max_pe * 0.9:
                range_reason = f'，接近历史最高({max_pe:.1f})'
            else:
                range_reason = f'，处于历史区间({min_pe:.1f}-{max_pe:.1f})内'
            
            base_reason += historical_reason + range_reason
        
        return {'status': base_status, 'reason': base_reason}
    
    def calculate_potential_score(self, stock_data):
        """计算潜力分数"""
        score = 0
        reasons = []
        
        # ROE分析（权重40%）
        roe_details = stock_data.get('roe_details', {})
        roe_analysis = self.analyze_roe_trend(roe_details)
        
        # ROE水平评分
        avg_roe = roe_analysis['avg_roe']
        if avg_roe >= 15:
            score += 40
            reasons.append(f"ROE优秀({avg_roe:.1f}%)")
        elif avg_roe >= 10:
            score += 30
            reasons.append(f"ROE良好({avg_roe:.1f}%)")
        elif avg_roe >= 5:
            score += 20
            reasons.append(f"ROE一般({avg_roe:.1f}%)")
        else:
            score += 10
            reasons.append(f"ROE较差({avg_roe:.1f}%)")
        
        # ROE趋势评分（权重20%）
        if roe_analysis['recent_trend'] > 0:
            score += 20
            reasons.append("ROE趋势向上")
        elif roe_analysis['recent_trend'] >= -2:
            score += 15
            reasons.append("ROE趋势稳定")
        else:
            score += 5
            reasons.append("ROE趋势向下")
        
        # PE估值评分（权重30%）
        pe_analysis = self.analyze_pe_valuation(stock_data.get('pe_analysis', {}))
        
        # 根据估值状态和历史分析进行评分
        if pe_analysis['status'] == 'deeply_undervalued':
            score += 35
            reasons.append("深度低估")
        elif pe_analysis['status'] == 'undervalued':
            score += 30
            reasons.append("估值偏低")
        elif pe_analysis['status'] == 'reasonable':
            score += 25
            reasons.append("估值合理")
        elif pe_analysis['status'] == 'slightly_overvalued':
            score += 15
            reasons.append("估值略高")
        elif pe_analysis['status'] == 'overvalued':
            score += 10
            reasons.append("估值偏高")
        elif pe_analysis['status'] == 'deeply_overvalued':
            score += 5
            reasons.append("深度高估")
        else:
            score += 10
            reasons.append("估值未知")
        
        # 如果有历史PE数据，额外加分（权重5%）
        historical_analysis = pe_analysis.get('historical_analysis', {})
        if historical_analysis.get('status') == 'valid':
            score += 5
            reasons.append("有历史PE参考")
            
            # 如果当前PE低于历史平均，额外加分
            current_pe = pe_analysis.get('current_pe', 0)
            avg_pe = historical_analysis.get('avg_pe', 0)
            if current_pe > 0 and avg_pe > 0 and current_pe < avg_pe:
                score += 5
                reasons.append("低于历史平均")
        
        '''
        # 稳定性评分（权重10%）
        years_with_low_roe = stock_data.get('years_with_low_roe', 0)
        if years_with_low_roe == 0:
            score += 10
            reasons.append("ROE稳定")
        elif years_with_low_roe <= 1:
            score += 8
            reasons.append("ROE较稳定")
        else:
            score += 5
            reasons.append("ROE波动较大")
        '''
        
        return {
            'score': score,
            'reasons': reasons,
            'roe_analysis': roe_analysis,
            'pe_analysis': pe_analysis
        }
    
    def analyze_all_stocks(self):
        """分析所有股票"""
        stock_data = self.load_stock_data()
        plottor = simple_stock_plotter.SimpleStockPlotter()
        
        if not stock_data:
            print("没有找到股票数据")
            return {}
        
        analysis_results = {}
        
        for stock_code, stock_info in stock_data.items():
            #print(f"分析股票: {stock_code} {stock_info.get('stock_name', '')}")
            pe_data= stock_info.get('pe_analysis', {})
            current_pe_list = pe_data.get('current_pe', [])
            historical_pe = pe_data.get('historical_pe', {})

            if len(historical_pe) < 2:
                continue

            if len(current_pe_list) == 0:
                continue
            
            years = sorted([int(year) for year in historical_pe.keys() if year.isdigit()])
            #print(f"years {years}")
            pe_values = [historical_pe[str(year)] for year in years if historical_pe[str(year)]]
            print(f"pe_values {pe_values}")

            current_price = stock_info.get('current_price')
            

            trend = True
            for i, pe in enumerate(pe_values):
                if i == len(pe_values) - 1:
                    break
                if pe < 0 or pe_values[i+1] < 0:
                    trend = False
                    break
                if pe_values[i+1] > pe:
                    trend = False
                    break
            
            if trend:
                if current_pe_list[0] < pe_values[-1] or current_pe_list[1] < pe_values[-1] or current_pe_list[2] < pe_values[-1]:
                    print(f"{stock_code} 历史PE趋势向下")
                    #print(f"{stock_code} PE: {pe_values}")
                    #plottor.plot_three_indicators(stock_info, stock_code)
            
            break
            # 计算潜力分数
            #potential_score = self.calculate_potential_score(stock_info)
            
            # analysis_results[stock_code] = {
            #     'stock_name': stock_info.get('stock_name', ''),
            #     'potential_score': potential_score['score'],
            #     'reasons': potential_score['reasons'],
            #     'avg_roe': potential_score['roe_analysis']['avg_roe'],
            #     'roe_trend': potential_score['roe_analysis']['recent_trend'],
            #     'pe_status': potential_score['pe_analysis']['status'],
            #     'pe_reason': potential_score['pe_analysis']['reason'],
            #     'current_pe': potential_score['pe_analysis'].get('current_pe', None),
            #     'historical_analysis': potential_score['pe_analysis'].get('historical_analysis', {}),
            #     'years_with_low_roe': stock_info.get('years_with_low_roe', 0),
            #     'original_status': stock_info.get('status', '')
            # }
        
        return analysis_results
    
    def get_promising_stocks(self, min_score=70):
        """获取有潜力的股票"""
        analysis_results = self.analyze_all_stocks()
        
        # 按潜力分数排序
        sorted_stocks = sorted(
            analysis_results.items(),
            key=lambda x: x[1]['potential_score'],
            reverse=True
        )
        
        # 筛选有潜力的股票
        promising_stocks = {}
        for stock_code, stock_info in sorted_stocks:
            #if stock_info['potential_score'] >= min_score:
            promising_stocks[stock_code] = stock_info
        
        return promising_stocks
    
    def generate_report(self, min_score=70):
        """生成分析报告"""
        promising_stocks = self.get_promising_stocks(min_score)
        
        print("\n" + "="*80)
        print("有潜力的股票分析报告")
        print("="*80)
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"筛选标准: 潜力分数 ≥ {min_score}")
        print(f"发现 {len(promising_stocks)} 只有潜力的股票")
        print("="*80)
        
        if not promising_stocks:
            print("未找到符合标准的股票")
            return
        
        # 打印详细分析
        for i, (stock_code, stock_info) in enumerate(promising_stocks.items(), 1):
            print(f"\n{i}. {stock_code} {stock_info['stock_name']}")
            print(f"   潜力分数: {stock_info['potential_score']}/100")
            print(f"   平均ROE: {stock_info['avg_roe']:.1f}%")
            print(f"   ROE趋势: {stock_info['roe_trend']:+.1f}%")
            print(f"   PE状态: {stock_info['pe_status']} ({stock_info['pe_reason']})")
            print(f"   低ROE年份数: {stock_info['years_with_low_roe']}")
            print(f"   推荐理由: {', '.join(stock_info['reasons'])}")
        
        # 保存结果到文件
        output_file = f"rising_roe_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(promising_stocks, f, ensure_ascii=False, indent=2)
        
        print(f"\n分析结果已保存到: {output_file}")

def main():
    """主函数"""
    analyzer = StockAnalyzer()
    
    # 设置筛选分数阈值
    min_score = 70  # 可以调整这个阈值
    
    # 生成分析报告
    analyzer.generate_report(min_score)

if __name__ == "__main__":
    main()