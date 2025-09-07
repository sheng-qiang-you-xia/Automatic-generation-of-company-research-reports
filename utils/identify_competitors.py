from http import client
import json
import yaml
from typing import Dict, List
import time

import logging  
import openai

from bs4 import BeautifulSoup
import urllib.parse
from sogou_search import sogou_search

logger = logging.getLogger(__name__)

def search_company_by_stock_code(competitors: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    使用sogou搜索验证股票代码对应的公司名称
    
    Args:
        stock_code: 股票代码
        market: 市场类型 (A股/港股)
    
    Returns:
        str: 搜索到的公司名称，如果失败返回None
    """
    valid_competitors = []
    for competitor in competitors:
        if competitor['market'] == "A股":
            search_query = f"A股 股票代码：{competitor['code']}"
        elif competitor['market'] == "港股":
            search_query = f"港股 股票代码：{competitor['code']}"
        else:
            continue        
        # 使用sogou搜索
        results = sogou_search(search_query, num_results=1)
        time.sleep(1) # 等待1秒
        logger.info(f"🤖 搜索结果: {results}")
        if results:
            if competitor['name'] in results[0]['title']:
                logger.info(f"🤖 AI识别的竞争对手: {competitor['name']} 与搜索结果: {results[0]['title']} 一致")
                valid_competitors.append(competitor)
            else:
                logger.warning(f"🤖 AI识别的竞争对手: {competitor['name']} 与搜索结果: {results[0]['title']} 不一致")
        else:
            logger.warning(f"🤖 搜索结果为空: {search_query}")
    return valid_competitors


def identify_competitors_with_ai(api_key,
                                  base_url,
                                  model_name, 
                                  company_name: str, 
                                  ) -> List[Dict[str, str]]:
    """使用AI识别同行竞争对手"""    
    prompt = f"""
      请分析以下公司的竞争对手：
      
      公司名称: {company_name}
      
      请根据以下标准识别该公司的主要竞争对手：
      1. 同行业内的主要上市公司
      2. 业务模式相似的公司
      3. 市值规模相近的公司
      4. 主要业务重叠度高的公司
      
      请返回8-10个主要竞争对手，按竞争程度排序，以YAML格式输出。
      格式要求：包含公司名称、股票代码和上市区域信息。
      
      **股票代码格式要求**：
      - A股：6位数字（如 000001、688327）
      - 港股：5位数字，不足5位前面补0（如 00700、09888）
      - 未上市公司：留空""
      
      **重要说明**：
      1. 只关注A股和港股市场的竞争对手，不包括美股市场
      2. 请确保提供的股票代码是真实存在的
      3. 请确保公司名称与股票代码对应的公司名称一致
      4. 如果不确定某个股票代码，请留空或标注为"未上市"
      
      上市区域包括：A股、港股，如果是未上市公司请标明"未上市"。
      
      请用```yaml包围你的输出内容。输出格式示例：
      ```yaml
      competitors:
        - name: "云从科技"
          code: "688327"
          market: "A股"
        - name: "寒武纪"
          code: "688256"
          market: "A股"
        - name: "百度"
          code: "09888"
          market: "港股"
        - name: "科大讯飞"
          code: "002230"
          market: "A股"
        - name: "某AI初创公司"
          code: ""
          market: "未上市"
      ```
      """
      # 正确的客户端创建方式
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
              {"role": "system", "content": "你是一个专业的金融分析师，擅长识别公司的竞争对手。请严格按照YAML格式返回结果。"},
              {"role": "user", "content": prompt}
          ],
          temperature=0.3  #baseline设置为0.3
        #   temperature= 0
          # temperature=0.7
      )
      #提取模型回答
    competitors_text = response.choices[0].message.content.strip()

      # 使用split方法提取```yaml和```之间的内容
    if '```yaml' in competitors_text:
          competitors_text = competitors_text.split('```yaml')[1].split('```')[0].strip()
    elif '```' in competitors_text:
          competitors_text = competitors_text.split('```')[1].split('```')[0].strip()
      
    try:
          # 解析YAML格式
          data = yaml.safe_load(competitors_text)
          competitors = data.get('competitors', [])
          logger.info(f"🤖 AI识别的竞争对手: {competitors}")
          logger.info(f"🤖 AI生成 {len(competitors)} 个竞争对手")
          # 验证并过滤竞争对手
          valid_competitors = search_company_by_stock_code(competitors)
          logger.info(f"✅ 最终返回 {len(valid_competitors)} 个有效竞争对手")
          logger.info(f"🤖 最终返回的竞争对手: {valid_competitors}")
          return valid_competitors
          
    except yaml.YAMLError:
          # 如果YAML解析失败，返回空列表
          logger.info(f"❌ YAML解析失败")
          return []