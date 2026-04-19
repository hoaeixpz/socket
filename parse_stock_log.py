#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析股票持仓日志文件，提取每周持仓记录（含股价）
根据"当日(周几)持仓市值:"关键字识别，优先取周2的数据
"""

import re
import os
from collections import defaultdict
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False

# 日期范围设置 (格式: 'YYYY-MM-DD')
DATE_START = '2022-08-19'
DATE_END = '2022-10-31'

# 图片输出目录
OUTPUT_DIR = rf'C:\socket\stock_charts_{DATE_START.replace("-", "")}_{DATE_END.replace("-", "")}'

def parse_weekly_holdings(filepath):
    """
    解析日志文件，提取每周持仓记录（含当天卖出的股票）
    根据"当日(周几)持仓市值:"关键字识别，每周只取最早出现的那条记录
    同时收集当天10:00前卖出的股票
    """
    from datetime import datetime, timedelta
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 存储每周的持仓数据，格式: {周一日期: {'date': 实际日期, 'weekday': 周几, 'stocks': [...]}}
    weekly_data = {}
    
    current_date = None
    
    # 收集所有15:30的持仓行
    all_holdings = []
    
    # 收集所有卖出记录 {(date, stock_name): {'quantity': int, 'price': float, 'sell_type': str}}
    sell_records = {}  # sell_type: '10点' 或 '涨停'
    
    for i, line in enumerate(lines):
        # 匹配日期
        date_match = re.search(r'^(\d{4}-\d{2}-\d{2})', line)
        if date_match:
            current_date = date_match.group(1)
        
        # 匹配持仓行 (15:30)
        holding_match = re.search(r'✅持仓:\s*([^ (（]+)\(([^)]+)\).*?数量[：:]\s*(\d+).*?市值[：:]\s*([\d.]+)元', line)
        if holding_match and '15:30' in line:
            stock_name = holding_match.group(1).strip()
            stock_code = holding_match.group(2).strip()
            quantity = int(holding_match.group(3))
            market_value = float(holding_match.group(4))
            
            if stock_code.endswith('.XSHE'):
                all_holdings.append({
                    'date': current_date,
                    'name': stock_name,
                    'code': stock_code,
                    'quantity': quantity,
                    'market_value': market_value
                })
        
        # 匹配10:00卖出行
        sell_match = re.search(r'✅卖出:\s*([^ (（]+)', line)
        if sell_match and '10:' in line:
            stock_name = sell_match.group(1).strip()
            # 查找下一行的卖出价格
            if i + 1 < len(lines):
                price_line = lines[i + 1]
                price_match = re.search(r'卖出\s*(\d+)股\s*\*\s*([\d.]+)元', price_line)
                if price_match:
                    quantity = int(price_match.group(1))
                    price = float(price_match.group(2))
                    key = (current_date, stock_name)
                    if key not in sell_records:  # 只记录第一次卖出
                        sell_records[key] = {
                            'quantity': quantity,
                            'price': price,
                            'sell_type': '10点卖出'
                        }
        
        # 匹配涨停卖出行 (14:00)
        if '涨停卖出' in line and '14:00' in line:
            # 查找下一行，获取涨停卖出的股票
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # 格式: 股票名称 股票代码
                limit_up_match = re.search(r'([^\s]+)\s+([0-9]{6}\.XSHE)', next_line)
                if limit_up_match:
                    stock_name = limit_up_match.group(1).strip()
                    stock_code = limit_up_match.group(2).strip()
                    # 在持仓记录中查找该股票的买入价作为参考
                    price = 0
                    for h in all_holdings:
                        if h['code'] == stock_code:
                            price = round(h['market_value'] / h['quantity'], 2) if h['quantity'] > 0 else 0
                            break
                    key = (current_date, stock_name)
                    if key not in sell_records:
                        sell_records[key] = {
                            'quantity': 0,
                            'price': price,
                            'sell_type': '涨停卖出'
                        }
    
    # 找出所有"当日持仓市值"行
    daily_holdings_dates = []
    
    for i, line in enumerate(lines):
        if '当日(周' in line and '持仓市值' in line and '15:30' in line:
            date_match = re.search(r'^(\d{4}-\d{2}-\d{2})', line)
            if date_match:
                date = date_match.group(1)
                daily_holdings_dates.append((i, date, line))
    
    # 按周分组，优先选择周2
    week_records = {}  # {monday_str: (date, weekday, line)}
    
    for idx, (line_num, date, line) in enumerate(daily_holdings_dates):
        weekday_match = re.search(r'当日\((周\d+)\)', line)
        if not weekday_match:
            continue
        weekday = weekday_match.group(1)
        
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        weekday_num = date_obj.weekday()
        monday_of_week = date_obj - timedelta(days=weekday_num)
        monday_str = monday_of_week.strftime('%Y-%m-%d')
        
        if monday_str not in week_records or weekday == '周2':
            week_records[monday_str] = (date, weekday, line)
    
    # 处理每周选中的记录
    for monday_str, (date, weekday, line) in week_records.items():
        stocks_with_price = []
        existing_codes = set()  # 记录已添加的股票代码
        
        # 先添加当天15:30的持仓
        for h in all_holdings:
            if h['date'] == date and h['quantity'] > 0:
                stocks_with_price.append({
                    'name': h['name'],
                    'code': h['code'],
                    'quantity': h['quantity'],
                    'market_value': h['market_value'],
                    'price': round(h['market_value'] / h['quantity'], 2),
                    'sold': False
                })
                existing_codes.add(h['code'])
        
        # 添加当天卖出的股票（从持仓列表中查找代码）
        for (sell_date, sell_name), sell_info in sell_records.items():
            if sell_date == date:
                # 在持仓记录中查找对应的股票代码
                for h in all_holdings:
                    if h['name'] == sell_name:
                        code = h['code']
                        # 如果该股票不在当前持仓中，添加为已卖出状态
                        if code not in existing_codes:
                            stocks_with_price.append({
                                'name': sell_name,
                                'code': code,
                                'quantity': 0,
                                'market_value': 0,
                                'price': sell_info['price'],
                                'sold': True,
                                'sell_type': sell_info['sell_type']
                            })
                            existing_codes.add(code)
                        break
        
        weekly_data[monday_str] = {
            'date': date,
            'weekday': weekday,
            'stocks': stocks_with_price
        }
    
    return weekly_data

def filter_by_date_range(weekly_data, start_date=None, end_date=None):
    """
    按日期范围过滤数据
    
    参数:
        weekly_data: 原始数据
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
    
    返回:
        过滤后的数据
    """
    from datetime import datetime
    
    result = {}
    for k, v in weekly_data.items():
        date = v['date']
        if start_date and date < start_date:
            continue
        if end_date and date > end_date:
            continue
        result[k] = v
    return result

def count_stock_holdings(weekly_data):
    """统计每只股票的持仓周数，返回 {代码: {'name': 名称, 'weeks': 周数}}"""
    stock_info = defaultdict(lambda: {'name': '', 'weeks': 0, 'weekdays': []})
    
    # 按实际日期排序
    sorted_keys = sorted(weekly_data.keys(), key=lambda x: weekly_data[x]['date'])
    
    for key in sorted_keys:
        record = weekly_data[key]
        for stock in record['stocks']:
            code = stock['code']
            stock_info[code]['name'] = stock['name']
            stock_info[code]['weeks'] += 1
            stock_info[code]['weekdays'].append((record['date'], record.get('weekday', '')))
    
    return stock_info

def plot_histogram(stock_info):
    """绘制持仓周数直方图"""
    # 按持仓周数排序
    sorted_data = sorted(stock_info.items(), key=lambda x: x[1]['weeks'], reverse=True)
    labels = [f"{info['name']} ({code})" for code, info in sorted_data]
    weeks = [info['weeks'] for _, info in sorted_data]
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(18, 14))
    
    # 绘制水平条形图
    bars = ax.barh(range(len(labels)), weeks, color='steelblue', edgecolor='white')
    
    # 设置y轴标签
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    
    # 在条形上添加数值标签
    for bar, week in zip(bars, weeks):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2, 
                str(week), va='center', fontsize=9)
    
    ax.set_xlabel('持仓周数 (Holding Weeks)', fontsize=12)
    ax.set_ylabel('股票名称 (Stock)', fontsize=12)
    ax.set_title('2022年各股票持仓周数统计', fontsize=14, fontweight='bold')
    
    # 反转y轴，使周数最多的在上面
    ax.invert_yaxis()
    
    # 设置x轴范围，留出标签空间
    ax.set_xlim(0, max(weeks) + 10)
    
    plt.tight_layout()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(OUTPUT_DIR, 'stock_holdings_histogram.png'), dpi=150, bbox_inches='tight')
    plt.show()
    print(f"\n直方图已保存到: {os.path.join(OUTPUT_DIR, 'stock_holdings_histogram.png')}")


def plot_stock_trend(weekly_data, stock_code, show_price=True, show_value=True):
    """
    绘制指定股票的持仓走势图
    
    参数:
        weekly_data: parse_weekly_holdings 返回的每周持仓数据
        stock_code: 股票代码 (如 "002633.XSHE")
        show_price: 是否显示股价走势
        show_value: 是否显示持仓市值走势
    
    返回:
        包含日期、股价、市值的列表
    """
    from datetime import datetime
    
    dates = []
    prices = []
    values = []
    quantities = []
    
    # 按实际日期排序
    sorted_keys = sorted(weekly_data.keys(), key=lambda x: weekly_data[x]['date'])
    
    for key in sorted_keys:
        record = weekly_data[key]
        actual_date = record['date']
        
        for stock in record['stocks']:
            # 根据代码匹配
            if stock['code'] == stock_code:
                dates.append(datetime.strptime(actual_date, '%Y-%m-%d'))
                prices.append(stock['price'])
                values.append(stock['market_value'])
                quantities.append(stock['quantity'])
                break
    
    if not dates:
        print(f"未找到股票: {stock_code}")
        return None
    
    # 从数据中获取股票名称
    stock_label = None
    for key in weekly_data:
        for stock in weekly_data[key]['stocks']:
            if stock['code'] == stock_code:
                stock_label = stock['name']
                break
        if stock_label:
            break
    stock_label = stock_label or stock_code
    
    # 确定子图数量
    n_subplots = sum([show_price, show_value])
    if n_subplots == 0:
        n_subplots = 1
    
    fig, axes = plt.subplots(n_subplots, 1, figsize=(12, 5 * n_subplots), sharex=True)
    if n_subplots == 1:
        axes = [axes]
    
    idx = 0
    
    if show_price:
        ax = axes[idx]
        
        # 按日期排序
        sorted_data = sorted(zip(dates, prices), key=lambda x: x[0])
        sorted_dates = [d[0] for d in sorted_data]
        sorted_prices = [d[1] for d in sorted_data]
        
        # 只对连续持仓的区间进行连线
        # 先找出连续持仓的区间
        i = 0
        while i < len(sorted_dates):
            # 找连续区间起点
            segment_dates = [sorted_dates[i]]
            segment_prices = [sorted_prices[i]]
            
            # 往后找连续的周
            j = i + 1
            while j < len(sorted_dates):
                # 计算间隔天数
                days_diff = (sorted_dates[j] - sorted_dates[j-1]).days
                if days_diff <= 10:  # 连续（1-2周内）
                    segment_dates.append(sorted_dates[j])
                    segment_prices.append(sorted_prices[j])
                    j += 1
                else:
                    break
            
            # 绘制这段连续区间
            if len(segment_dates) >= 2:
                ax.plot(segment_dates, segment_prices, 'b-o', linewidth=2, markersize=6)
            else:
                # 单点用散点图
                ax.scatter(segment_dates, segment_prices, color='blue', s=50, zorder=5)
            
            ax.fill_between(segment_dates, segment_prices, alpha=0.2)
            
            i = j  # 移动到下一段
        
        ax.set_ylabel('股价 (元)', fontsize=11)
        ax.set_title(f'{stock_label} 股价走势', fontsize=13, fontweight='bold')
        ax.legend(['连续持仓区间'], loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # 标注最高最低点
        max_idx = prices.index(max(prices))
        min_idx = prices.index(min(prices))
        ax.annotate(f'最高: {prices[max_idx]:.2f}', 
                    xy=(dates[max_idx], prices[max_idx]),
                    xytext=(10, 5), textcoords='offset points', fontsize=9, color='red')
        ax.annotate(f'最低: {prices[min_idx]:.2f}', 
                    xy=(dates[min_idx], prices[min_idx]),
                    xytext=(10, -15), textcoords='offset points', fontsize=9, color='green')
        ax.set_xlabel('日期', fontsize=11)
        idx += 1
    
    if show_value:
        ax = axes[idx]
        ax.bar(dates, values, width=3, color='steelblue', alpha=0.7, label='持仓市值')
        ax.set_xlabel('日期', fontsize=11)
        ax.set_ylabel('持仓市值 (元)', fontsize=11)
        ax.set_title(f'{stock_label} 持仓市值变化', fontsize=13, fontweight='bold')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3, axis='y')
    
    # 设置x轴日期格式 - 每个子图都设置
    import matplotlib.dates as mdates
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.set_xticks(dates)
        ax.set_xticklabels([d.strftime('%m-%d') for d in dates], rotation=45, fontsize=8)
    
    plt.tight_layout()
    
    # 确保目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 清理文件名中的特殊字符
    safe_label = stock_label.replace('*', 'ST').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '').replace('STST', 'ST')
    
    # 保存图片
    save_path = os.path.join(OUTPUT_DIR, f'{safe_label}_持仓走势图.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"走势图已保存到: {save_path}")
    plt.close()  # 显示图片
    
    # 打印统计信息
    print(f"\n=== {stock_label} 统计信息 ===")
    print(f"持仓周数: {len(dates)}")
    if show_price:
        print(f"最高价: {max(prices):.2f} 元 (日期: {dates[max_idx].strftime('%Y-%m-%d')})")
        print(f"最低价: {min(prices):.2f} 元 (日期: {dates[min_idx].strftime('%Y-%m-%d')})")
        print(f"平均价: {sum(prices)/len(prices):.2f} 元")
        print(f"价格波动: {(max(prices)-min(prices))/min(prices)*100:.1f}%")
    
    return [{'date': d.strftime('%Y-%m-%d'), 'price': p, 'value': v, 'quantity': q} 
            for d, p, v, q in zip(dates, prices, values, quantities)]


def main():
    filepath = 'C:/socket/1'
    weekly_data = parse_weekly_holdings(filepath)
    
    # 按日期范围过滤数据
    filtered_data = filter_by_date_range(weekly_data, DATE_START, DATE_END)
    
    # 按实际日期排序输出
    sorted_dates = sorted(filtered_data.keys(), key=lambda x: filtered_data[x]['date'])
    
    print(f"总共找到 {len(weekly_data)} 周的持仓记录")
    print(f"日期范围 {DATE_START} 至 {DATE_END} 内有 {len(filtered_data)} 周的持仓记录\n")
    
    # 输出每周持仓（含股价）
    print("=" * 90)
    print("每周持仓股票列表（含股价）")
    print("=" * 90)
    
    for i, key in enumerate(sorted_dates, 1):
        record = filtered_data[key]
        date = record['date']  # 实际日期
        weekday = record['weekday']
        stocks = record['stocks']
        
        print(f"第 {i} 周 ({date} {weekday}):")
        print(f"{'股票名称':<14}{'股票代码':<16}{'数量':<10}{'市值(元)':<14}{'股价(元)':<10}")
        print("-" * 70)
        
        for stock in stocks:
            print(f"{stock['name']:<14}{stock['code']:<16}{stock['quantity']:<10}"
                  f"{stock['market_value']:<14.2f}{stock['price']:<10.2f}")
        print()
    
    # 统计持仓周数
    print("=" * 70)
    print("各股票持仓周数统计表")
    print("=" * 70)
    stock_info = count_stock_holdings(filtered_data)
    
    # 按持仓周数降序排序
    sorted_stocks = sorted(stock_info.items(), key=lambda x: x[1]['weeks'], reverse=True)
    
    print(f"{'排名':<6}{'股票名称':<14}{'股票代码':<16}{'持仓周数':<10}")
    print("-" * 50)
    for i, (code, info) in enumerate(sorted_stocks, 1):
        print(f"{i:<6}{info['name']:<14}{code:<16}{info['weeks']:<10}")
    
    print(f"\n共有 {len(sorted_stocks)} 只不同的股票被持仓")
    
    # 绘制直方图
    plot_histogram(stock_info)
    
    return filtered_data, stock_info


def demo_stock_trend(weekly_data):
    """绘制所有股票的持仓走势图"""
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"输出目录: {OUTPUT_DIR}")
    
    # 获取所有股票代码
    stock_codes = set()
    for record in weekly_data.values():
        for stock in record['stocks']:
            stock_codes.add(stock['code'])
    
    print("\n" + "=" * 60)
    print(f"日期范围: {DATE_START} 至 {DATE_END}")
    print(f"开始绘制所有股票走势图 (共 {len(stock_codes)} 只)...")
    print("=" * 60)
    
    for i, stock_code in enumerate(sorted(stock_codes), 1):
        print(f"[{i}/{len(stock_codes)}] 正在绘制 {stock_code}...")
        plot_stock_trend(weekly_data, stock_code=stock_code)
    
    print(f"\n所有走势图已保存到: {OUTPUT_DIR}")


if __name__ == '__main__':
    # 运行主分析
    weekly_2022, stock_info = main()
    
    # 演示：绘制申科股份走势图
    demo_stock_trend(weekly_2022)
