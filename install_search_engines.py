#!/usr/bin/env python3
"""
搜索引擎依赖安装脚本
"""

import subprocess
import sys

def install_package(package_name, description=""):
    """安装Python包"""
    print(f"正在安装 {package_name}...")
    if description:
        print(f"描述: {description}")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"✅ {package_name} 安装成功")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ {package_name} 安装失败")
        return False

def main():
    print("="*60)
    print("搜索引擎依赖安装工具")
    print("="*60)
    
    print("\n可用的搜索引擎及其依赖:")
    print("1. 百度搜索 - 免费，无需API密钥，中文支持好（已包含在requirements.txt中）")
    print("2. Google (googlesearch-python) - 免费，但可能被限制")
    print("3. SerpAPI (google-search-results) - 付费，需要API密钥")
    print("4. 模拟搜索 - 无需安装，用于测试")
    
    print("\n推荐安装顺序:")
    print("1. 百度搜索已默认可用（无需额外安装）")
    print("2. 如果百度搜索不可用，尝试Google")
    print("3. 如果需要更稳定的服务，使用SerpAPI")
    
    choice = input("\n请选择要安装的搜索引擎 (2-3，或输入 'all' 安装所有): ").strip().lower()
    
    if choice == "2" or choice == "all":
        install_package("googlesearch-python", "Google搜索引擎，免费但可能被限制")
    
    if choice == "3" or choice == "all":
        install_package("google-search-results", "SerpAPI，付费服务，需要API密钥")
        print("\n⚠️  SerpAPI需要API密钥，请访问 https://serpapi.com/ 注册获取")
        print("   然后在 .env 文件中添加: SERPAPI_KEY=your_api_key")
    
    print("\n" + "="*60)
    print("安装完成！")
    print("现在可以运行 research_report_generator.py 来选择搜索引擎")
    print("默认使用百度搜索，无需额外配置")
    print("="*60)

if __name__ == "__main__":
    main() 