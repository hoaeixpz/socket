import numpy as np
from typing import Tuple
import random
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


def simple_linear_regression(y: list[float]) -> Tuple[float, float, float]:
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

#test_fun2()