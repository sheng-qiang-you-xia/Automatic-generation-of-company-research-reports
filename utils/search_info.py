# 示例：搜索中文文本
import requests

def baidu_search(keywords, max_results=10):
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

results2 = baidu_search("百度的行业地位")  # 输入中文查询词
print("搜索结果：")
print(results2)