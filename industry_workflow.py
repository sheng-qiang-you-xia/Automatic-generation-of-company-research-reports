# -*- coding: utf-8 -*-
"""
行业研究工作流
"""

import os
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# 导入pocketflow相关模块
try:
    from pocketflow import Node, Workflow
except ImportError:
    print("pocketflow未安装，使用简化版本")
    # 简化版本的Node和Workflow类
    class Node:
        def __init__(self, name):
            self.name = name
        
        def prep(self, shared):
            return None
        
        def exec(self, *args):
            return None
        
        def post(self, shared, prep_res, exec_res):
            return None
    
    class Workflow:
        def __init__(self):
            self.nodes = {}
        
        def add_node(self, node):
            self.nodes[node.name] = node
        
        def run(self, shared):
            for node_name, node in self.nodes.items():
                print(f"执行节点: {node_name}")
                prep_res = node.prep(shared)
                exec_res = node.exec(prep_res) if prep_res is not None else node.exec()
                next_node = node.post(shared, prep_res, exec_res)
                if next_node and next_node in self.nodes:
                    continue
                break

class SearchInfo(Node):  # 信息搜索节点
    def prep(self, shared):
        return shared.get("search_terms", [])

    def exec(self, search_terms):
        all_results = []
        total = len(search_terms)
        for i, term in enumerate(search_terms, 1):
            print(f"\n搜索关键词 ({i}/{total}): {term}")
            results = baidu_search(term)
            print(f"找到 {len(results)} 条相关信息")
            all_results.append({"term": term, "results": results})
            time.sleep(15)  # 避免请求过快
        return all_results

    def post(self, shared, prep_res, exec_res):
        context_list = shared.get("context", [])
        context_list.extend(exec_res)
        shared["context"] = context_list
        print("\n信息搜索完成，返回决策节点...")
        return "search_done"

class DecisionMaker(Node):  # 决策节点
    def prep(self, shared):
        return shared.get("context", [])

    def exec(self, context):
        print("\n分析搜索结果，制定决策...")
        # 这里可以添加更复杂的决策逻辑
        decisions = []
        for item in context:
            term = item.get("term", "")
            results = item.get("results", [])
            if results:
                decisions.append(f"关键词 '{term}' 找到 {len(results)} 条相关信息")
            else:
                decisions.append(f"关键词 '{term}' 未找到相关信息")
        return decisions

    def post(self, shared, prep_res, exec_res):
        shared["decisions"] = exec_res
        print("决策制定完成")
        return None

class ReportGenerator(Node):  # 报告生成节点
    def prep(self, shared):
        return {
            "context": shared.get("context", []),
            "decisions": shared.get("decisions", [])
        }

    def exec(self, data):
        print("\n生成行业研究报告...")
        context = data.get("context", [])
        decisions = data.get("decisions", [])
        
        report = "行业研究报告\n"
        report += "=" * 50 + "\n"
        report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        report += "搜索结果摘要:\n"
        for decision in decisions:
            report += f"- {decision}\n"
        
        report += "\n详细信息:\n"
        for item in context:
            term = item.get("term", "")
            results = item.get("results", [])
            report += f"\n关键词: {term}\n"
            for i, result in enumerate(results[:3], 1):  # 只显示前3个结果
                report += f"  {i}. {result.get('title', '无标题')}\n"
                report += f"     链接: {result.get('href', '无链接')}\n"
                report += f"     摘要: {result.get('body', '无摘要')[:100]}...\n"
        
        return report

    def post(self, shared, prep_res, exec_res):
        # 保存报告到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"行业研究报告_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(exec_res)
        
        print(f"报告已保存到: {filename}")
        shared["report"] = exec_res
        return None

def baidu_search(keywords, max_results=20):
    """百度搜索实现"""
    try:
        import urllib.parse
        search_url = "https://www.baidu.com/s"
        params = {
            'wd': keywords,
            'rn': max_results
        }           
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # 简单解析HTML结果
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.find_all('h3', class_='t', limit=max_results):
                link = result.find('a')
                if link:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    # 获取摘要
                    summary_elem = result.find_next_sibling('div', class_='c-abstract')
                    summary = summary_elem.get_text(strip=True) if summary_elem else f"关于 {keywords} 的搜索结果"
                    
                    results.append({
                        "title": title,
                        "href": href,
                        "body": summary
                    })
            
            return results
        else:
            print(f"百度搜索HTTP错误: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"百度搜索失败: {e}")
        return []

def run_industry_research(search_terms):
    """运行行业研究工作流"""
    print("="*60)
    print("行业研究工作流启动")
    print("="*60)
    
    # 创建工作流
    workflow = Workflow()
    
    # 添加节点
    workflow.add_node(SearchInfo("search_info"))
    workflow.add_node(DecisionMaker("decision_maker"))
    workflow.add_node(ReportGenerator("report_generator"))
    
    # 准备共享数据
    shared_data = {
        "search_terms": search_terms,
        "context": [],
        "decisions": []
    }
    
    # 运行工作流
    workflow.run(shared_data)
    
    print("\n" + "="*60)
    print("行业研究工作流完成")
    print("="*60)
    
    return shared_data.get("report", "")

if __name__ == "__main__":
    # 示例搜索词
    search_terms = [
        "人工智能行业发展趋势",
        "AI技术应用前景",
        "机器学习市场分析"
    ]
    
    report = run_industry_research(search_terms)
    print("\n生成的报告:")
    print(report)
