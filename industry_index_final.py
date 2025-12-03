#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终版行业指数数据获取工具
基于实际可用的akshare接口
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import os
import json

class IndustryIndexFinal:
    """最终版行业指数数据获取类"""
    
    def __init__(self):
        self.data_dir = "industry_data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        print("✅ 初始化行业指数工具")
        
    def get_industry_list(self):
        """获取行业板块列表"""
        try:
            print("📊 获取行业板块列表...")
            data = ak.stock_board_industry_name_em()
            print(f"✅ 获取到 {len(data)} 个行业板块")
            
            # 显示前几个行业
            print("前10个行业板块:")
            for i, row in data.head(10).iterrows():
                print(f"  {i+1:2d}. {row['板块代码']:8s} - {row['板块名称']}")
            
            return data
            
        except Exception as e:
            print(f"❌ 获取行业列表失败: {e}")
            return pd.DataFrame()
    
    def get_industry_detail_basic(self, industry_name):
        """获取行业板块基本信息（使用summary接口）"""
        try:
            print(f"📊 获取行业 {industry_name} 基本信息...")
            
            # 尝试不同的接口
            interfaces_to_try = [
                'stock_board_industry_summary_em',
                'stock_board_industry_detail_em'
            ]
            
            for interface in interfaces_to_try:
                if hasattr(ak, interface):
                    try:
                        print(f"   尝试接口: {interface}")
                        data = getattr(ak, interface)(symbol=industry_name)
                        print(f"✅ 获取到 {len(data)} 条数据")
                        return data
                    except Exception as e:
                        print(f"   接口 {interface} 失败: {str(e)[:50]}...")
                        continue
            
            print("⚠️ 所有详细接口都失败，返回空DataFrame")
            return pd.DataFrame()
            
        except Exception as e:
            print(f"❌ 获取行业详情失败: {e}")
            return pd.DataFrame()
    
    def get_concept_list(self):
        """获取概念板块列表"""
        try:
            print("💡 获取概念板块列表...")
            data = ak.stock_board_concept_name_em()
            print(f"✅ 获取到 {len(data)} 个概念板块")
            
            print("前10个概念板块:")
            for i, row in data.head(10).iterrows():
                print(f"  {i+1:2d}. {row['板块代码']:8s} - {row['板块名称']}")
            
            return data
            
        except Exception as e:
            print(f"❌ 获取概念列表失败: {e}")
            return pd.DataFrame()
    
    def get_concept_detail(self, concept_name):
        """获取概念板块详细数据"""
        try:
            print(f"💡 获取概念 {concept_name} 详细数据...")
            data = ak.stock_board_concept_detail_em(symbol=concept_name)
            print(f"✅ 获取到 {len(data)} 条数据")
            return data
            
        except Exception as e:
            print(f"❌ 获取概念详情失败: {e}")
            return pd.DataFrame()
    
    def get_sw_realtime(self, symbol="一级行业"):
        """获取申万指数实时行情"""
        try:
            print(f"📈 获取申万{symbol}实时行情...")
            data = ak.index_realtime_sw(symbol=symbol)
            print(f"✅ 获取到 {len(data)} 个申万指数")
            
            # 显示前10个指数
            print("前10个申万指数:")
            for i, row in data.head(10).iterrows():
                print(f"  {i+1:2d}. {row['指数代码']:8s} - {row['指数名称']:12s}: "
                      f"{row['最新价']:8.2f} ({row['涨跌幅']:+6.2f}%)")
            
            return data
            
        except Exception as e:
            print(f"❌ 获取申万实时行情失败: {e}")
            return pd.DataFrame()
    
    def get_sw_analysis(self, symbol="一级行业", start_date=None, end_date=None, period="日报表"):
        """获取申万指数分析数据"""
        try:
            print(f"📊 获取申万{symbol}分析数据...")
            
            # 设置默认日期
            if not end_date:
                end_date = datetime.now().strftime("%Y%m%d")
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            
            data = ak.index_analysis_sw(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period
            )
            
            print(f"✅ 获取到 {len(data)} 条分析数据")
            return data
            
        except Exception as e:
            print(f"❌ 获取申万分析数据失败: {e}")
            return pd.DataFrame()
    
    def get_sw_components(self, symbol):
        """获取申万指数成分股"""
        try:
            print(f"📋 获取申万指数 {symbol} 成分股...")
            data = ak.index_component_sw(symbol=symbol)
            print(f"✅ 获取到 {len(data)} 只成分股")
            
            # 显示前10只成分股
            print("前10只成分股:")
            for i, row in data.head(10).iterrows():
                stock_code = row.get('证券代码', row.get('代码', 'N/A'))
                stock_name = row.get('证券名称', row.get('名称', 'N/A'))
                print(f"  {i+1:2d}. {stock_code:8s} - {stock_name}")
            
            return data
            
        except Exception as e:
            print(f"❌ 获取申万成分股失败: {e}")
            return pd.DataFrame()
    
    def analyze_industry_performance(self, limit=20):
        """分析行业表现（基于可用数据）"""
        print(f"📊 分析前{limit}个行业的表现...")
        
        # 获取行业列表
        industries = self.get_industry_list()
        if industries.empty:
            return pd.DataFrame()
        
        # 获取行业基本信息
        industry_performance = []
        
        for i, industry in industries.head(limit).iterrows():
            industry_name = industry['板块名称']
            
            # 获取行业基本信息
            detail = self.get_industry_detail_basic(industry_name)
            
            if not detail.empty:
                # 提取关键指标
                avg_change = 0
                total_amount = 0
                company_count = len(detail)
                
                # 查找涨跌幅和成交额列
                change_col = None
                amount_col = None
                
                for col in detail.columns:
                    if '涨跌' in col and '幅' in col:
                        change_col = col
                    elif '成交额' in col or '金额' in col:
                        amount_col = col
                
                if change_col and change_col in detail.columns:
                    avg_change = detail[change_col].mean()
                
                if amount_col and amount_col in detail.columns:
                    total_amount = detail[amount_col].sum()
                
                industry_performance.append({
                    '板块代码': industry['板块代码'],
                    '行业名称': industry_name,
                    '平均涨跌幅': avg_change,
                    '总成交额': total_amount,
                    '公司数量': company_count
                })
                
                print(f"  ✅ {industry_name}: 涨跌幅 {avg_change:+.2f}%, 成交额 {total_amount:.0f}")
        
        if industry_performance:
            performance_df = pd.DataFrame(industry_performance)
            performance_df = performance_df.sort_values('平均涨跌幅', ascending=False)
            print(f"✅ 分析完成 {len(performance_df)} 个行业")
            return performance_df
        else:
            print("❌ 没有获取到任何行业数据")
            return pd.DataFrame()
    
    def get_popular_concepts(self, limit=15):
        """获取热门概念"""
        print(f"🔥 分析前{limit}个热门概念...")
        
        concepts = self.get_concept_list()
        if concepts.empty:
            return pd.DataFrame()
        
        concept_performance = []
        
        for i, concept in concepts.head(limit).iterrows():
            concept_name = concept['板块名称']
            
            # 获取概念详细数据
            detail = self.get_concept_detail(concept_name)
            
            if not detail.empty:
                # 计算表现指标
                avg_change = 0
                company_count = len(detail)
                
                # 查找涨跌幅列
                change_col = None
                for col in detail.columns:
                    if '涨跌' in col and '幅' in col:
                        change_col = col
                        break
                
                if change_col and change_col in detail.columns:
                    avg_change = detail[change_col].mean()
                
                concept_performance.append({
                    '板块代码': concept['板块代码'],
                    '概念名称': concept_name,
                    '平均涨跌幅': avg_change,
                    '成分股数量': company_count
                })
                
                print(f"  ✅ {concept_name}: 涨跌幅 {avg_change:+.2f}%, 成分股 {company_count}只")
        
        if concept_performance:
            concept_df = pd.DataFrame(concept_performance)
            concept_df = concept_df.sort_values('平均涨跌幅', ascending=False)
            print(f"✅ 分析完成 {len(concept_df)} 个概念")
            return concept_df
        else:
            print("❌ 没有获取到任何概念数据")
            return pd.DataFrame()
    
    def save_data(self, data, filename):
        """保存数据"""
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            if filename.endswith('.json'):
                data.to_json(filepath, orient='records', force_ascii=False, indent=2)
            else:
                data.to_csv(filepath, index=False, encoding='utf-8-sig')
                
            print(f"💾 数据已保存到: {filepath}")
            return True
        except Exception as e:
            print(f"❌ 保存数据失败: {e}")
            return False
    
    def generate_industry_report(self):
        """生成行业分析报告"""
        print("=" * 60)
        print("🏢 生成行业分析报告")
        print("=" * 60)
        
        # 1. 申万指数概览
        print("\n1️⃣ 申万指数概览")
        sw_realtime = self.get_sw_realtime(symbol="一级行业")
        if not sw_realtime.empty:
            self.save_data(sw_realtime, "sw_realtime_report.csv")
            
            # 统计涨跌情况
            rising_count = len(sw_realtime[sw_realtime['涨跌幅'] > 0])
            falling_count = len(sw_realtime[sw_realtime['涨跌幅'] < 0])
            flat_count = len(sw_realtime[sw_realtime['涨跌幅'] == 0])
            
            print(f"\n📊 涨跌统计:")
            print(f"  上涨: {rising_count} 个 ({rising_count/len(sw_realtime)*100:.1f}%)")
            print(f"  下跌: {falling_count} 个 ({falling_count/len(sw_realtime)*100:.1f}%)")
            print(f"  平盘: {flat_count} 个 ({flat_count/len(sw_realtime)*100:.1f}%)")
        
        # 2. 行业表现分析
        print(f"\n2️⃣ 行业表现分析")
        industry_performance = self.analyze_industry_performance(limit=15)
        if not industry_performance.empty:
            self.save_data(industry_performance, f"industry_performance_{datetime.now().strftime('%Y%m%d')}.csv")
            
            print(f"\n🏆 表现最佳的5个行业:")
            print("=" * 50)
            for i, (_, ind) in enumerate(industry_performance.head(5).iterrows(), 1):
                print(f"{i:2d}. {ind['行业名称']:15s} "
                      f"{ind['平均涨跌幅']:+6.2f}% "
                      f"成交额:{ind['总成交额']:10.0f}")
            
            print(f"\n📉 表现最差的5个行业:")
            print("=" * 50)
            for i, (_, ind) in enumerate(industry_performance.tail(5).iterrows(), 1):
                rank = len(industry_performance) - 5 + i
                print(f"{rank:2d}. {ind['行业名称']:15s} "
                      f"{ind['平均涨跌幅']:+6.2f}% "
                      f"成交额:{ind['总成交额']:10.0f}")
        
        # 3. 热门概念分析
        print(f"\n3️⃣ 热门概念分析")
        concept_performance = self.get_popular_concepts(limit=10)
        if not concept_performance.empty:
            self.save_data(concept_performance, f"concept_performance_{datetime.now().strftime('%Y%m%d')}.csv")
            
            print(f"\n🔥 涨幅最高的5个概念:")
            print("=" * 50)
            for i, (_, conc) in enumerate(concept_performance.head(5).iterrows(), 1):
                print(f"{i:2d}. {conc['概念名称']:15s} "
                      f"{conc['平均涨跌幅']:+6.2f}% "
                      f"成分股:{conc['成分股数量']:4d}只")
        
        # 4. 具体行业深度分析（银行示例）
        print(f"\n4️⃣ 银行行业深度分析")
        bank_components = self.get_sw_components("801780")  # 银行指数
        if not bank_components.empty:
            self.save_data(bank_components, "bank_index_components.csv")
        
        print(f"\n" + "=" * 60)
        print("✅ 行业分析报告生成完成")
        print("💾 所有数据已保存到 industry_data/ 目录")
        print("=" * 60)

def main():
    """主函数"""
    print("🚀 启动行业指数分析工具...")
    
    try:
        tool = IndustryIndexFinal()
        tool.generate_industry_report()
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()