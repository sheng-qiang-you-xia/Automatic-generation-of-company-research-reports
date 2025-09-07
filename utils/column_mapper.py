import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from utils.column_mapper import standardize_dataframe, get_available_columns

# 设置matplotlib使用宋体显示中文
matplotlib.use('Agg')
plt.rcParams['font.sans-serif'] = ['SimSun', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def get_column_mapping(df, market_type="HK"):
    """
    获取列名映射，将标准列名映射到实际数据文件中的列名
    
    Args:
        df: DataFrame对象
        market_type: 市场类型，"HK"为港股，"A"为A股
    
    Returns:
        dict: 列名映射字典
    """
    columns = df.columns.tolist()
    mapping = {}
    
    if market_type == "HK":
        # 港股列名映射
        if "营业额" in columns:
            mapping["REVENUE"] = "营业额"
        elif "营运收入" in columns:
            mapping["REVENUE"] = "营运收入"
            
        if "股东应占溢利" in columns:
            mapping["NET_PROFIT"] = "股东应占溢利"
        elif "除税后溢利" in columns:
            mapping["NET_PROFIT"] = "除税后溢利"
            
        if "经营活动现金流量净额" in columns:
            mapping["OPERATING_CASH_FLOW"] = "经营活动现金流量净额"
        elif "经营活动现金净额" in columns:
            mapping["OPERATING_CASH_FLOW"] = "经营活动现金净额"
            
        if "报告期" in columns:
            mapping["YEAR"] = "报告期"
        elif "REPORT_DATE" in columns:
            mapping["YEAR"] = "REPORT_DATE"
            
    elif market_type == "A":
        # A股列名映射
        if "TOTAL_OPERATE_INCOME" in columns:
            mapping["REVENUE"] = "TOTAL_OPERATE_INCOME"
        elif "OPERATE_INCOME" in columns:
            mapping["REVENUE"] = "OPERATE_INCOME"
            
        if "PARENT_NETPROFIT" in columns:
            mapping["NET_PROFIT"] = "PARENT_NETPROFIT"
        elif "NETPROFIT" in columns:
            mapping["NET_PROFIT"] = "NETPROFIT"
            
        if "NET_OPERATE_CASH_FLOW" in columns:
            mapping["OPERATING_CASH_FLOW"] = "NET_OPERATE_CASH_FLOW"
        elif "OPERATE_CASH_FLOW" in columns:
            mapping["OPERATING_CASH_FLOW"] = "OPERATE_CASH_FLOW"
            
        if "REPORT_DATE" in columns:
            mapping["YEAR"] = "REPORT_DATE"
    
    return mapping

def standardize_dataframe(df, market_type="HK"):
    """
    标准化DataFrame的列名
    
    Args:
        df: 原始DataFrame
        market_type: 市场类型
    
    Returns:
        DataFrame: 标准化后的DataFrame
    """
    mapping = get_column_mapping(df, market_type)
    
    # 创建新的DataFrame，使用标准列名
    standardized_df = df.copy()
    
    # 重命名列
    for standard_name, actual_name in mapping.items():
        if actual_name in df.columns:
            standardized_df[standard_name] = df[actual_name]
    
    return standardized_df

def get_available_columns(df):
    """
    获取DataFrame中可用的列名
    
    Args:
        df: DataFrame对象
    
    Returns:
        list: 列名列表
    """
    return df.columns.tolist()

# 在读取数据后，标准化DataFrame
# 假设你已经有了merged_df，并且知道是港股还是A股数据
market_type = "HK"  # 或者 "A"，根据你的数据来源
merged_df = standardize_dataframe(merged_df, market_type)

# 现在你可以安全地使用标准列名了
plt.plot(merged_df['YEAR'], merged_df['REVENUE'], label='营业收入')
plt.plot(merged_df['YEAR'], merged_df['NET_PROFIT'], label='净利润')
plt.plot(merged_df['YEAR'], merged_df['OPERATING_CASH_FLOW'], label='经营活动现金流') 