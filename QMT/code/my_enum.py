from typing import Dict

ORDER_TYPE_MAP: Dict[int, str] = {
    0: "常规",                              # OTP_ORDINARY
    1: "算法交易",                          # OTP_ALGORITHM
    2: "随机量交易",                        # OTP_RANDVOLUME
    3: "算法交易3",                         # OTP_ALGORITHM3
    4: "中信建投算法",                      # OTP_ZXJT
    5: "隔时交易",                          # OTP_ZSGS
    6: "普通交易的触价单笔委托方式",         # OTP_ORDINARY_BASKET_TRIGGER_SINGLE_ORDER
    7: "算法交易的触价单笔委托方式",         # OTP_ALGORITHM_BASKET_TRIGGER_SINGLE_ORDER
    8: "中信证券算法",                      # OTP_ZXZQ
    9: "金纳算法",                          # OTP_GENUS
    10: "爵士算法",                         # OTP_JAZZ
    11: "智能VWAP",                         # OTP_VWAP
    12: "智能TWAP",                         # OTP_TWAP
    13: "智能算法",                         # OTP_XTALGO
    14: "华创算法",                         # OTP_HUACHUANG
    15: "华润算法",                         # OTP_HUARUN
    16: "回转算法",                         # OTP_CUSTOM
    17: "主动算法",                         # OPT_EXTERN
    18: "广发算法"                          # OTP_GUANGFA
}

OPERATION_TYPE_MAP: Dict[int, str] = {
    0: "开多",
    1: "平昨多",           # 黄金用平多表示
    2: "平今多",
    3: "开空",
    4: "平昨空",           # 黄金用平空表示
    5: "平今空",
    6: "平多优先平今",
    7: "平多优先平昨",
    8: "平空优先平今",
    9: "平空优先平昨",
    10: "卖出优先平今",
    11: "卖出优先平昨",
    12: "买入优先平今",
    13: "买入优先平昨",
    14: "平多",
    15: "平空",
    16: "开仓",
    17: "平仓",
    18: "买入",            # 您的例子
    19: "卖出",
    20: "融资买入",
    21: "融券卖出",
    22: "买券还券",
    23: "直接还券",
    24: "卖券还款",
    25: "直接还款"
}

def get_operation_type_str(operation_code: int) -> str:
    """根据操作代码获取中文描述
    
    Args:
        operation_code: 操作代码，如 18
        
    Returns:
        中文描述字符串，如 "买入"
        
    Raises:
        ValueError: 当操作代码不存在时
    """
    if operation_code in OPERATION_TYPE_MAP:
        return OPERATION_TYPE_MAP[operation_code]
    else:
        raise ValueError(f"无效的操作代码: {operation_code}")
