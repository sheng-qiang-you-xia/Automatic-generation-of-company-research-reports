"""
金融研报生成器
整合财务分析、股权分析、估值模型和行业信息，生成完整的金融研报
"""

import os
import glob
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
import importlib

from data_analysis_agent import quick_analysis
from data_analysis_agent.config.llm_config import LLMConfig
from data_analysis_agent.utils.llm_helper import LLMHelper
from utils.get_shareholder_info import get_shareholder_info, get_table_content
from utils.get_financial_statements import get_all_financial_statements, save_financial_statements_to_csv
from utils.identify_competitors import identify_competitors_with_ai
from utils.get_stock_intro import get_stock_intro, save_stock_intro_to_txt
import logging


#配置日志记录
os.makedirs("logs",exist_ok=True)
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    filename = f"logs/research_report.log",
    filemode = "w",
    encoding = "utf-8"
)
logger = logging.getLogger(__name__)#创建日志记录器

def open_debug_mode():
    import debugpy
    try:
        # 5678 is the default attach port in the VS Code debug configurations. Unless a host and port are specified, host defaults to 127.0.0.1
        debugpy.listen(("localhost", 5678))
        print("Waiting for debugger attach")
        debugpy.wait_for_client()
    except Exception as e:
        pass

open_debug_mode()

class SearchEngine:
    """搜索引擎类 - 使用百度搜索"""
    def __init__(self, engine_type="baidu"):
        self.engine_type = engine_type
    def search(self, keywords, max_results=10):
        """执行搜索 - 使用百度搜索"""
        return self._baidu_search(keywords, max_results)
    def _baidu_search(self, keywords, max_results):
        """百度搜索（使用requests直接调用）"""
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
                logging.error(f"百度搜索HTTP错误: {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"百度搜索失败: {e}")
            return []


def robust_search_with_retry(keywords, search_engine, max_retries=3):
    """
    健壮的搜索函数，包含重试机制
    
    Args:
        keywords: 搜索关键词
        search_engine: SearchEngine实例
        max_retries: 最大重试次数
    
    Returns:
        list: 搜索结果列表，失败时返回空列表
    """
    for attempt in range(max_retries):
        try:
            logging.info(f"尝试搜索 '{keywords}' (第{attempt + 1}次)")
            results = search_engine.search(keywords, max_results=10)
            if results:
                logging.info(f"成功获取 {len(results)} 条搜索结果")
                return results
            else:
                logging.info("搜索结果为空")
                return []
        except Exception as e:
            logging.error(f"搜索失败 (第{attempt + 1}次): {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10  # 递增等待时间
                logging.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logging.error(f"搜索 '{keywords}' 最终失败，跳过")
                return []

# ========== 环境变量与全局配置 ==========
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
model = os.getenv("OPENAI_MODEL", "gpt-4")

# 新增：通过环境变量控制是否跳过搜索
SKIP_SEARCH = os.getenv("SKIP_SEARCH", "false").lower() == "true"

target_company = "商汤科技"
target_company_code = "00020"
target_company_market = "HK"
data_dir = "./download_financial_statement_files"  #存放公司三大表
os.makedirs(data_dir, exist_ok=True)  #创建目录

company_info_dir = "./company_info"
os.makedirs(company_info_dir, exist_ok=True)

llm_config = LLMConfig(   #模型配置初始化
    api_key=api_key,
    base_url=base_url,
    model=model,
    temperature=0.7,
    max_tokens=8192,  # 修复：从16384改为8192，符合API限制,qwen-plus
)
llm = LLMHelper(llm_config)

# ========== 1. 获取目标公司及竞争对手的财务数据 ==========
# 获取竞争对手列表
other_companies = identify_competitors_with_ai(api_key=api_key,
                                               base_url=base_url,
                                               model_name=model,
                                               company_name=target_company)

#过滤掉未上市的公司----竞争对手中仅关注未上市公司
listed_companies = [company for company in other_companies if company.get('market') != "未上市"]

# 获取目标公司财务数据  --------从akshare中获取三大表，输出是一个字典，包含三个键值对，分别是资产负债表、利润表、现金流量表
print("\n" + "="*80)
print(f"获取目标公司 {target_company}({target_company_market}:{target_company_code}) 的财务数据")
target_financials = get_all_financial_statements(
    stock_code=target_company_code,
    market=target_company_market,
    period="年度",
    verbose=False
)

save_financial_statements_to_csv(
    financial_statements=target_financials,
    stock_code=target_company_code,
    market=target_company_market,
    company_name=target_company,
    period="年度",
    save_dir=data_dir
)

# 获取竞争对手的财务数据
print("\n" + "="*80)
print("获取竞争对手的财务数据")
competitors_financials = {}
for company in listed_companies:
    company_name = company.get('name')
    company_code = company.get('code')
    market_str = company.get('market', '')
    if "A" in market_str:
        market = "A"
        if not (company_code.startswith('SH') or company_code.startswith('SZ')):
            if company_code.startswith('6'):
                company_code = f"SH{company_code}"
            else:
                company_code = f"SZ{company_code}"
    elif "港" in market_str:
        market = "HK"
    print(f"\n获取竞争对手 {company_name}({market}:{company_code}) 的财务数据")
    try:
        company_financials = get_all_financial_statements(
            stock_code=company_code,
            market=market,
            period="年度",
            verbose=False
        )
        save_financial_statements_to_csv(
            financial_statements=company_financials,
            stock_code=company_code,
            market=market,
            company_name=company_name,
            period="年度",
            save_dir=data_dir
        )
        competitors_financials[company_name] = company_financials
        time.sleep(2)
    except Exception as e:
        print(f"获取 {company_name} 财务数据失败: {e}")
print("\n" + "="*80)
print("财务数据获取完成")
print(f"目标公司: {target_company}")
print(f"竞争对手数量: {len(competitors_financials)}")
print("="*80)

# ========== 1.1 获取所有公司基础信息并保存 ==========
print("="*80)
print("开始获取公司基础信息")
print("="*80)

# 统一收集目标公司、竞争对手、特定公司（如百度）
all_base_info_targets = [(target_company, target_company_code, target_company_market)]
for company in listed_companies:
    company_name = company.get('name')
    company_code = company.get('code')
    market_str = company.get('market', '')
    if "A" in market_str:
        market = "A"
        if not (company_code.startswith('SH') or company_code.startswith('SZ')):
            if company_code.startswith('6'):
                company_code = f"SH{company_code}"
            else:
                company_code = f"SZ{company_code}"
    elif "港" in market_str:
        market = "HK"
    all_base_info_targets.append((company_name, company_code, market))
# 特定公司如百度
all_base_info_targets.append(("百度", "09888", "HK"))

for company_name, company_code, market in all_base_info_targets:
    logging.info(f"\n获取公司 {company_name}({market}:{company_code}) 的基础信息")
    company_info = get_stock_intro(company_code, market=market)
    if company_info:
        logging.info(company_info)
        save_path = os.path.join(company_info_dir, f"{company_name}_{market}_{company_code}_info.txt")
        save_stock_intro_to_txt(company_code, market, save_path)
        logging.info(f"公司信息已保存到: {save_path}")
    else:
        logging.error(f"未能获取到 {company_name} 的基础信息")
    time.sleep(1)

# ========== 1.x 搜索行业信息并保存 ==========
industry_info_dir = "./industry_info"
os.makedirs(industry_info_dir, exist_ok=True)

logging.info("="*80)
logging.info("开始搜索行业信息")
logging.info("="*80)

all_search_results = {}

# 检查是否跳过搜索（如果网络有问题）
if SKIP_SEARCH:
    skip_search = True
    logging.info("检测到环境变量 SKIP_SEARCH=true，跳过网络搜索")
else:
    # skip_search = input("是否跳过网络搜索？(y/n，默认n): ").lower().strip() == 'y'?
    skip_search = False

if not skip_search:
    # 直接使用百度搜索引擎
    search_engine = SearchEngine("baidu")
    logging.info("使用搜索引擎: 百度搜索")
    
    # 1. 搜索目标公司行业信息
    logging.info(f"\n搜索目标公司 {target_company} 的行业信息")
    target_search_keywords = f"{target_company} 行业地位 市场份额 竞争分析 业务模式"
    all_search_results[target_company] = robust_search_with_retry(target_search_keywords, search_engine)

    # 2. 搜索竞争对手行业信息
    logging.info(f"\n搜索竞争对手的行业信息")
    for company in listed_companies:
        company_name = company.get('name')
        search_keywords = f"{company_name} 行业地位 市场份额 业务模式 发展战略"
        all_search_results[company_name] = robust_search_with_retry(search_keywords, search_engine)
        time.sleep(5)  # 短暂等待，避免请求过于频繁
else:
    logging.info("跳过网络搜索，使用空的搜索结果...")
    all_search_results = {}

# 保存所有搜索结果的JSON文件
search_results_file = os.path.join(industry_info_dir, "all_search_results.json")
with open(search_results_file, 'w', encoding='utf-8') as f:
    json.dump(all_search_results, f, ensure_ascii=False, indent=2)

# ========== 2. 公司信息整理 ==========
#将从akshare中匹配到的公司基础信息串起来
def get_company_infos(data_dir:str="./company_info"):
    all_files = os.listdir(data_dir)
    company_infos = ""
    for file in all_files:
        if file.endswith(".txt"):
            company_name = file.split(".")[0]
            with open(os.path.join(data_dir, file), 'r', encoding='utf-8') as f:
                content = f.read()
            company_infos += f"【公司信息开始】\n公司名称: {company_name}\n{content}\n【公司信息结束】\n\n"
    return company_infos

company_infos = get_company_infos(company_info_dir)
logger.info(f"公司信息:{company_infos}")

company_infos = llm.call(
    f"请整理以下公司信息内容，确保格式清晰易读，并保留关键信息：\n{company_infos}",
    system_prompt="你是一个专业的公司信息整理师。",
    max_tokens=8192,  
    temperature=0.7
)
logger.info(f"整理后的公司信息:{company_infos}")

# ========== 3. 股权信息整理 ==========
info = get_shareholder_info()
shangtang_shareholder_info = info.get("tables")
table_content = get_table_content(shangtang_shareholder_info)
shareholder_analysis = llm.call(
    "请分析以下股东信息表格内容：\n" + table_content,
    system_prompt="你是一个专业的股东信息分析师。",
    max_tokens=8192,  # 修复：从16384改为8192
    temperature=0.5
)

# ========== 4. 行业信息搜索结果整理 ==========
with open(search_results_file, 'r', encoding='utf-8') as f:
    all_search_results = json.load(f)
search_res = ""
for company, results in all_search_results.items():
    search_res += f"【{company}搜索信息开始】\n"
    for result in results:
        search_res += f"标题: {result.get('title', '无标题')}\n"
        search_res += f"链接: {result.get('href', '无链接')}\n"
        search_res += f"摘要: {result.get('body', '无摘要')}\n"
        search_res += "----\n"
    search_res += f"【{company}搜索信息结束】\n\n"

# ========== 5. 财务数据分析与对比分析 ==========
def get_company_files(data_dir):
    all_files = glob.glob(f"{data_dir}/*.csv")
    companies = {}
    for file in all_files:
        filename = os.path.basename(file)
        company_name = filename.split("_")[0]
        companies.setdefault(company_name, []).append(file)
    return companies

def analyze_individual_company(company_name, files, llm_config, query=None, verbose=True):
    if query is None:
        query = "基于表格的数据，分析有价值的内容，并绘制相关图表。最后生成汇报给我。"
    report = quick_analysis(
        query=query, files=files, llm_config=llm_config, 
        absolute_path=True, max_rounds=20
    )
    return report

def format_final_reports(all_reports):
    formatted_output = []
    for company_name, report in all_reports.items():
        formatted_output.append(f"【{company_name}财务数据分析结果开始】")
        final_report = report.get("final_report", "未生成报告")
        formatted_output.append(final_report)
        formatted_output.append(f"【{company_name}财务数据分析结果结束】")
        formatted_output.append("")
    return "\n".join(formatted_output)

# 该函数用于批量分析指定目录下所有公司的财务数据文件。
# 它首先通过 get_company_files(data_directory) 获取目录下每个公司的所有CSV文件，
# 然后对每个公司调用 analyze_individual_company 进行分析，生成分析报告。
# 最终返回一个字典，键为公司名，值为对应的分析报告。
def analyze_companies_in_directory(data_directory, llm_config, query="基于表格的数据，分析有价值的内容，并绘制相关图表。最后生成汇报给我。"):
    company_files = get_company_files(data_directory)
    all_reports = {}
    for company_name, files in company_files.items():
        report = analyze_individual_company(company_name, files, llm_config, query, verbose=False)
        if report:
            all_reports[company_name] = report
    return all_reports

def compare_two_companies(company1_name, company1_files, company2_name, company2_files, llm_config):
    query = "基于两个公司的表格的数据，分析有共同点的部分，绘制对比分析的表格，并绘制相关图表。最后生成汇报给我。"
    all_files = company1_files + company2_files
    report = quick_analysis(
        query=query,
        files=all_files,
        llm_config=llm_config,
        absolute_path=True,
        max_rounds=20
    )
    return report

def run_comparison_analysis(data_directory, target_company_name, llm_config):
    company_files = get_company_files(data_directory)
    if not company_files or target_company_name not in company_files:
        return {}
    competitors = [company for company in company_files.keys() if company != target_company_name]
    comparison_reports = {}
    for competitor in competitors:
        comparison_key = f"{target_company_name}_vs_{competitor}"
        report = compare_two_companies(
            target_company_name, company_files[target_company_name],
            competitor, company_files[competitor],
            llm_config
        )
        if report:
            comparison_reports[comparison_key] = {
                'company1': target_company_name,
                'company2': competitor,
                'report': report
            }
    return comparison_reports

def merge_reports(individual_reports, comparison_reports):
    merged = {}
    for company, report in individual_reports.items():
        merged[company] = report
    for comp_key, comp_data in comparison_reports.items():
        merged[comp_key] = comp_data['report']
    return merged

# ========== 5.1 商汤科技估值与预测分析 ==========
def get_sensetime_files(data_dir):
    """获取商汤科技的财务数据文件"""
    all_files = glob.glob(f"{data_dir}/*.csv")
    sensetime_files = []
    for file in all_files:
        filename = os.path.basename(file)
        company_name = filename.split("_")[0]
        if "商汤" in company_name or "SenseTime" in company_name:
            sensetime_files.append(file)
    return sensetime_files

def analyze_sensetime_valuation(files, llm_config):
    """分析商汤科技的估值与预测"""
    query = "基于三大表的数据，构建估值与预测模型，模拟关键变量变化对财务结果的影响,并绘制相关图表。最后生成汇报给我。"
    report = quick_analysis(
        query=query, files=files, llm_config=llm_config, absolute_path=True, max_rounds=20
    )
    return report

# ========== 6. 主程序入口 ==========
if __name__ == "__main__":
    # 当前可用的主要数据说明：
    print("\n========== 数据说明 ==========")
    print("1. 公司基础信息（整理后）：company_infos\n   用法示例：print(company_infos[:500])  # 打印前500字\n")
    print("2. 股权信息分析（整理后）：shareholder_analysis\n   用法示例：print(shareholder_analysis[:500])\n")
    print("3. 行业信息搜索结果（整理后）：search_res\n   用法示例：print(search_res[:500])\n")
    print("4. 单公司财务分析与两两对比分析结果：merged_results\n   用法示例：print(format_final_reports(merged_results)[:500])\n")
    print("5. 商汤科技估值与预测分析：sensetime_valuation_report\n   用法示例：print(sensetime_valuation_report['final_report'][:500])\n")
    print("============================\n")

    # 运行公司分析
    results = analyze_companies_in_directory(
        data_directory=data_dir, 
        llm_config=llm_config
    )
    # 运行两两对比分析（以商汤科技为目标公司）
    comparison_results = run_comparison_analysis(
        data_directory=data_dir,
        target_company_name=target_company,
        llm_config=llm_config
    )
    # 合并所有报告
    merged_results = merge_reports(results, comparison_results)

    # 商汤科技估值与预测分析
    sensetime_files = get_sensetime_files(data_dir)
    sensetime_valuation_report = None
    if sensetime_files:
        sensetime_valuation_report = analyze_sensetime_valuation(sensetime_files, llm_config)

    # 格式化并输出最终报告
    if merged_results:
        print("\n" + "="*80)
        print("📋 格式化财务数据分析报告（含两两对比）")
        print("="*80)
        formatted_report = format_final_reports(merged_results)
        print(formatted_report)
        output_file = f"财务分析汇总报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_report)
        print(f"\n📁 报告已保存到: {output_file}")
        # 输出估值分析报告主要内容
        if sensetime_valuation_report and isinstance(sensetime_valuation_report, dict):
            print("\n" + "="*80)
            print("📊 商汤科技估值与预测分析报告主要内容：")
            print("="*80)
            print(sensetime_valuation_report.get('final_report', '未生成报告'))
        # 统一保存为markdown
        md_output_file = f"财务研报汇总_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(md_output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 公司基础信息\n\n## 整理后公司信息\n\n{company_infos}\n\n")
            f.write(f"# 股权信息分析\n\n{shareholder_analysis}\n\n")
            f.write(f"# 行业信息搜索结果\n\n{search_res}\n\n")
            f.write(f"# 财务数据分析与两两对比\n\n{formatted_report}\n\n")
            if sensetime_valuation_report and isinstance(sensetime_valuation_report, dict):
                f.write(f"# 商汤科技估值与预测分析\n\n{sensetime_valuation_report.get('final_report', '未生成报告')}\n\n")
        print(f"\n📁 Markdown版报告已保存到: {md_output_file}")
    else:
        print("\n❌ 没有成功分析的公司数据")

