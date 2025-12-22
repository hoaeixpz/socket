import numpy as np
from typing import Tuple
import random
import math
import matplotlib.pyplot as plt

def linear_regression_least_squares(y: list[float], x: list[float] = None) -> Tuple[float, float]:
    """
    最小二乘法线性回归（输入为list）
    
    参数:
    y: 因变量列表
    x: 自变量列表，如果为None，则使用等间距时间点 [1, 2, ..., len(y)]
    
    返回:
    slope: 斜率 β1
    intercept: 截距 β0
    """
    n = len(y)
    
    # 如果x未提供，使用等间距时间点
    if x is None:
        x = list(range(1, n + 1))
    
    # 转换为numpy数组便于计算
    y_arr = np.array(y, dtype=float)
    x_arr = np.array(x, dtype=float)
    
    # 计算x和y的均值
    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)
    
    # 计算分子和分母
    numerator = np.sum((x_arr - x_mean) * (y_arr - y_mean))
    denominator = np.sum((x_arr - x_mean) ** 2)
    
    # 防止除零错误
    if abs(denominator) < 1e-10:
        return 0.0, float(y_mean), None
    
    # 计算斜率和截距
    slope = numerator / denominator
    intercept = float(y_mean - slope * x_mean)

    residuals = y_arr - (x_arr * slope + intercept)
    # 计算残差标准差
    se = np.std(residuals, ddof=2)
    
    return float(slope), intercept, se


def simple_linear_regression(y: list[float], ddof = 2) -> Tuple[float, float, float]:
    """
    简化的最小二乘法（适用于等间距x，输入为list）
    
    参数:
    y: 因变量列表
    
    返回:
    slope: 斜率 β1
    intercept: 截距 β0
    """
    n = len(y)
    y_arr = np.array(y, dtype=float)
    
    # 使用简化公式
    sum_x = n * (n + 1) / 2
    sum_x2 = n * (n + 1) * (2 * n + 1) / 6
    sum_y = np.sum(y_arr)
    
    # 计算 Σ(i * y_i)
    i_values = np.arange(1, n + 1)
    sum_xy = np.sum(i_values * y_arr)
    
    # 计算斜率和截距
    denominator = n * sum_x2 - sum_x * sum_x
    if abs(denominator) < 1e-10:
        slope = 0.0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator
    
    intercept = (sum_y - slope * sum_x) / n

    residuals = y_arr - (i_values * slope + intercept)

    # 计算残差标准差
    sorted_res = np.sort(residuals)
    residuals = sorted_res[1:-1]
    se = np.std(residuals, ddof=2)
    '''
    X = list(range(0, n))
    x_min, x_max = min(X), max(X)
    x_line = np.linspace(x_min, x_max, 100)
    y_line = intercept + slope * x_line

    plt.plot(x_line, y_line, 'r-', linewidth=2)
    plt.scatter(X, y_arr, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    plt.show()
    '''
    

    #斜率 截距 波动标准差
    return float(slope), float(intercept), float(se)

def calc_R_squared(y: list[float]):
    """
    根据简化的最小二乘法，计算R2
    
    参数:
    y: 因变量列表

    R2 = 1 - SSE / SST
    SSE = 拟合数据 与 原始数据 相差 的平方和
    SST = 原始数据                 的方差

    如果SSE = 0， 说明拟合数据与原始数据完全相等，原始数据没有任何波动，此时R2 = 1
    如果SSE = SST,说明拟合数据与原始数据的均值完全相等，拟合结果为斜率为0的直线，
                    原始数据上下波动幅度相等，拟合结果不惧任何解释性， 此时R2 = 0
    
    返回:
    R2 拟合优度
    """
    n = len(y)
    y_arr = np.array(y, dtype=float)
    
    # 使用简化公式
    sum_x = n * (n + 1) / 2
    sum_x2 = n * (n + 1) * (2 * n + 1) / 6
    sum_y = np.sum(y_arr)
    
    # 计算 Σ(i * y_i)
    i_values = np.arange(1, n + 1)
    sum_xy = np.sum(i_values * y_arr)
    
    # 计算斜率和截距
    denominator = n * sum_x2 - sum_x * sum_x
    if abs(denominator) < 1e-10:
        slope = 0.0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator
    
    intercept = (sum_y - slope * sum_x) / n

    residuals = y_arr - (i_values * slope + intercept)

    SSE = np.sum(residuals ** 2)
    SST = np.sum((y_arr - sum_y / n) ** 2)
    #print("SSE ", SSE)
    #print("SST ", SST)
    #print("SSE / SST ", SSE/SST)
    if SST == 0:
        return 1
    R2 = 1 - SSE / SST

    return R2

def test_fun():
    x = [1,2,3,4]
    y = [6,5,7,10]
    #k,b = linear_regression_least_squares(y, x)
    k, b = simple_linear_regression(y)
    print(f"y = {k} x + {b}")

    plt.scatter(x, y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)

    x_min, x_max = min(x), max(x)
    x_line = np.linspace(x_min, x_max, 100)
    y_line = b + k * x_line
    plt.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {b:.2f} + {k:.2f}x')

    plt.show()

def test_fun2():
    K = 2
    B = 100
    X = list(range(1, 50))
    Y = list(x * K + B + random.uniform(-40, 40) for x in X)

    k, b, se= simple_linear_regression(Y)
    print(f"y = {k} x + {b} + {se}")


    x_min, x_max = min(X), max(X)
    x_line = np.linspace(x_min, x_max, 100)
    y_line = b + k * x_line

    plt.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {b:.2f} + {k:.2f}x')
    plt.scatter(X, Y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    plt.show()

def test_fun3():
    #X = [1,2,3,4,5]
    #Y = [6,7,8,9,10]
    #Y = [1,3,1,3,0]

    K = 0.6
    B = 10
    X = list(range(1, 50))
    Y = list(math.log(x * K + B + random.uniform(-1, 1)) for x in X)
    #Y = list(x * K + B + random.uniform(-4, 4) for x in X)
    #Y = list(100 / (x + 10) + random.uniform(-1, 1) for x in X)


    #k,b = linear_regression_least_squares(y, x)
    k, b, se = simple_linear_regression(Y)
    R2   = calc_R_squared(Y)
    #pct = Y[-1] / Y[0] - 1
    pct = k * 252
    print(f"y = {k:.2f} x + {b:.2f} + E({se:.2f})  R2 = {R2:.3f}, pct = {pct:.3f}, {R2 * pct:.3f}")

    plt.scatter(X, Y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)

    x_min, x_max = min(X), max(X)
    x_line = np.linspace(x_min, x_max, 10)
    y_line = b + k * x_line
    plt.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {b:.2f} + {k:.2f}x + E{se:.2f}  R2 = {R2}')
    plt.legend()
    plt.show()

def test_fun4():
    Y0 = 100
    r = 1.05
    #X = list(range(1, 10))
    #Y = list(math.log(Y0 * (r ** x)) for x in X)
    #print(Y)

    K = 0.9
    B = 10
    #origin_Y = list(x * K + B for x in X)
    origin_Y = [0.624, 0.627, 0.628, 0.64, 0.641, 0.64, 0.639, 0.637, 0.633, 0.635, 0.637, 0.629, 0.63, 0.633, 0.631, 0.633, 0.638, 0.638, 0.635, 0.636, 0.63, 0.63, 0.628, 0.632, 0.643]
    #origin_Y = [2.581, 2.591, 2.58, 2.554, 2.576, 2.579, 2.581, 2.574, 2.621, 2.625, 2.646, 2.724, 2.717, 2.73, 2.777, 2.715, 2.717, 2.712, 2.675, 2.681, 2.805, 2.828, 2.817, 2.83, 2.818]
    Y  =  list(math.log(y) for y in origin_Y)
    X = list(range(1, len(Y) + 1))

    k, b, se = simple_linear_regression(Y)
    R2   = calc_R_squared(Y)
    pct = k * 100

    print(f"y = {k:.3f} x + {b:.3f} + E({se:.3f})  R2 = {R2:.3f}, pct = {pct:.3f}%, {R2 * pct:.3f}")

    plt.scatter(X, Y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    plt.scatter(X, origin_Y, alpha=0.6, s=50, c='red', edgecolors='black', linewidth=0.5)

    x_min, x_max = min(X), max(X)
    x_line = np.linspace(x_min, x_max, 10)
    y_line = b + k * x_line
    plt.plot(x_line, y_line, 'r-', linewidth=2, label=f'y = {b:.2f} + {k:.2f}x + E{se:.2f}  R2 = {R2}')
    plt.legend()
    plt.show()

def test_fun5():
    K = 0.6
    B = 100
    X = list(range(1, 200))

    R2_list = []
    pct_list = []
    noise_list = []
    for noise in range(1,200):
        n = noise / 10
        Y = list(math.log(x * K + B + random.uniform(-n, n)) for x in X)
        k, b, se = simple_linear_regression(Y)
        R2   = calc_R_squared(Y)
        pct = k * 252

        R2_list.append(R2)
        pct_list.append(pct * R2)
        noise_list.append(n)
        if False and (n > 9.8 or n < 0.2):
            print(f"y = {k} * x + {b:.2f} + E({se:.2f})  R2 = {R2:.3f}, pct = {pct:.3f}, {R2 * pct:.3f}")
            plt.scatter(X, Y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
            plt.show()


    plt.scatter(noise_list, pct_list, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    plt.show()

def test_fun6():
    n = 3
    B = 100
    X = list(range(1, 200))

    R2_list = []
    pct_list = []
    k_list = []
    for slope in range(1,100):
        K = slope / 100
        Y = list(math.log(x * K + B + random.uniform(-n, n)) for x in X)
        k, b, se = simple_linear_regression(Y)
        R2   = calc_R_squared(Y)
        pct = k * 252

        R2_list.append(R2)
        pct_list.append(pct * R2)
        k_list.append(K)
        if K > 0.98 or K < 0.02:
            print(f"y = {k} * x + {b:.2f} + E({se:.2f})  R2 = {R2:.3f}, pct = {pct:.3f}, {R2 * pct:.3f}")
            plt.scatter(X, Y, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
            plt.show()


    plt.scatter(k_list, R2_list, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5)
    plt.show()

#test_fun3()
#test_fun6()