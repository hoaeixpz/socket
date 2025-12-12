#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import math

from stock_data_collector_demo import CustomJSONEncoder

def load_existing_stocks(file = 'industry.json'):
    """加载现有的stock_info.json文件，返回所有股票代码列表"""
    try:
        with open(file, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
        return stocks
    except FileNotFoundError:
        print("错误：找不到{file}文件")
        return {}
    except json.JSONDecodeError as e:
        print(f"错误：JSON文件格式错误 - {e}")
        return {}

def save_industry(industry_dict):
    """保存分析结果"""
    try:
        with open('industry_info.json', 'w', encoding='utf-8') as f:
            json.dump(industry_dict, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        print(f"分析结果已保存到: industry_info.json")
    except Exception as e:
        print(f"保存结果失败: {e}")

def cal_mean_pe(pe_dict):
    try:
        pe_mean_dict = {}
        pe_valid_mean_dict = {}
        for year, pe_list in pe_dict.items():
            #print(year)
            #print(pe_list)
            total = 0
            valid_total = 0
            count = 0
            valid_count = 0
            for value in pe_list:
                if value > 0:
                    valid_total += value
                    valid_count += 1
                count += 1
                total += value
            if count > 0:
                pe_mean_dict[year] = round(total / count, 4)
            else:
                print(f"count == 0 year{year} pe {pe_list}")
            if valid_count > 0:
                pe_valid_mean_dict[year] = round(valid_total / valid_count, 4)
            else:
                print(f"valid count == 0 year{year} pe {pe_list}")
                

        pe_mean_dict = dict(sorted(pe_mean_dict.items(), key=lambda x: int(x[0])))
        pe_valid_mean_dict = dict(sorted(pe_valid_mean_dict.items(), key=lambda x: int(x[0])))
        return pe_mean_dict, pe_valid_mean_dict
    except Exception as e:
        print(f"cal pe fail {e}")

def cal_mean_indicator(roe_dict):
    try:
        roe_mean_dict = {}
        for year, roe_list in roe_dict.items():
            counts = []
            if roe_mean_dict.get(year) is None:
                roe_mean_dict[year] = []
            #print(roe_list)
            for i in range(4):
                #print(f"index {i}")
                total = 0
                valid_count = 0
                for lst in roe_list:
                    value = lst[i]
                    if value is None:
                        continue
                    if not (isinstance(value, float) and math.isnan(value)):
                        total += value
                        valid_count += 1
                roe_mean_dict[year].append(total)
                counts.append(valid_count)
                #print(roe_mean_dict[year])
                #print(counts)

            averages = [total / count if count > 0 else 0 for total,count in zip(roe_mean_dict[year], counts)]
            roe_mean_dict[year] = [round(ava, 4) for ava in averages]
            

        #print(roe_mean_dict)
        return roe_mean_dict
    except Exception as e:
        print(f"calc mean error {e}")
        return None
def main():
    """主函数"""

    industry_map = load_existing_stocks()
    industry_dict = load_existing_stocks("industry_info.json")

    all_stocks = load_existing_stocks("stock_info.json")
    for code, industry in industry_map.items():
        if industry_dict.get(industry) is None:
            industry_dict[industry] = {}
        if industry_dict[industry].get("code") is None:
            industry_dict[industry]["code"] = set()
        if industry_dict[industry].get("kf_roe") is None:
            industry_dict[industry]["kf_roe"] = {}
        if industry_dict[industry].get("roe") is None:
            industry_dict[industry]["roe"] = {}
        if industry_dict[industry].get("pe") is None:
            industry_dict[industry]["pe"] = {}
        if industry_dict[industry].get("valid_pe") is None:
            industry_dict[industry]["valid_pe"] = {}

        industry_dict[industry]["code"] = set(industry_dict[industry]["code"])
        industry_dict[industry]["code"].add(code)

    for industry, industry_info in industry_dict.items():
        #if industry != "文化传媒":
        #    continue
        print(f"industry {industry}")
        industry_dict[industry]["code"] = list(industry_dict[industry]["code"])
        codes = industry_info["code"]
        kf_roe_dict = {}
        roe_dict = {}
        pe_dict = {}
        for code in codes:
            stock_info = all_stocks.get(code)
            if stock_info is None:
                continue

            kf_roe = stock_info['roe_details']['kf_roe']
            ROE = stock_info['roe_details']['roe']
            hist_pe = stock_info['pe_analysis']['historical_pe']
            for year, roe in ROE.items():
                if roe_dict.get(year) is None:
                    roe_dict[year] = []
                roe_dict[year].append(roe)

            for year, roe in kf_roe.items():
                if kf_roe_dict.get(year) is None:
                    kf_roe_dict[year] = []
                kf_roe_dict[year].append(roe)

            for year, pe in hist_pe.items():
                if math.isnan(pe):
                    print(f"code {code} year {year}")
                    continue
                if pe_dict.get(year) is None:
                    pe_dict[year] = []
                pe_dict[year].append(pe)

        #print("cal kf roe")
        kf_roe_mean_dict = cal_mean_indicator(kf_roe_dict)
        #print("cal roe")
        roe_mean_dict = cal_mean_indicator(roe_dict)
        #print("cal pe")
        pe_mean_dict, pe_valid_mean_dict = cal_mean_pe(pe_dict)

        industry_dict[industry]["kf_roe"] = kf_roe_mean_dict
        industry_dict[industry]["roe"] = roe_mean_dict
        industry_dict[industry]["pe"] = pe_mean_dict
        industry_dict[industry]["valid_pe"] = pe_valid_mean_dict
        #print(kf_roe_list)
        #break


    save_industry(industry_dict)

if __name__ == "__main__":
    main()
