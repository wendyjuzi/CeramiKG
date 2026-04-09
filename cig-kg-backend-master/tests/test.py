import json
import os
import re
from typing import Dict, Any, List
from dotenv import load_dotenv
from fastapi import Depends
from openai import OpenAI
from app.services.kg_build_service import save_kg_data

prompt = """

你是一名知识图谱构建助手，请根据用户提供的规范从文本中提取结构化信息。请遵循以下步骤：  

1. 实体与关系定义：  
【实体类型定义】  
- 类型名称：[机组]
  属性列表：[实体名]
  示例：[PROTOS70 卷接机组]
  定义：点检的对象
  标签：Machine
- 类型名称：[点检项目]
  属性列表：[实体名]
  示例：[SE 盘纸接头 检测]
  定义：机组检测需要进行的检测项目
  标签：Project
- 类型名称：[判定标准]
  属性列表：[实体名]
  示例：[以上两项任有一项未满足，则判定该检测不正常]
  定义：如何判定某项检测是否正常
  标签：Standard
- 类型名称：[点检方法]
  属性列表：[实体名]
  示例：[①操作工用双层盘纸测试，检测器状态应有变化]
  定义：点检项目包含的点检步骤
  标签：Method  

【关系类型定义】  
- 关系名称：[包含]
  起点类型：[机组]
  终点类型：[点检项目]
  定义：检测机组时，可能需要进行多个点检项目
  标签：INCLUDE
- 关系名称：[拥有]
  起点类型：[点检项目]
  终点类型：[判定标准]
  定义：点检项目判定是否通过的标准
  标签：HAS_STANDARD
- 关系名称：[包含]
  起点类型：[点检项目]
  终点类型：[点检方法]
  定义：点检项目包含点检方法
  标签：INCLUDE  


2. 处理规则：  
a. 逐句分析文本，识别符合定义的实体及属性  
b. 根据上下文推断实体间符合定义的关系  
c. 为每个实体分配唯一数字ID（从1001开始自增）  
d. 遇到无法明确判断的情况时保持谨慎，宁可忽略不记录  

3. 输出要求：  
{  
  "nodes": [  
    {"id": 1001, "type": "类型1", "properties": {"属性a":"值","属性b":"值"}},  
    ...  
  ],  
  "relationships": [  
    {"type": "关系X", "from": 1001, "to": 1002},  
    ...  
  ]  
}  

4. 特别说明：  
- 输出必须为纯JSON格式，不需要解释文本  
- 确保所有节点ID唯一且关系端点有效  
- 属性值为空时使用null  
- 严格遵循用户定义的实体/关系类型体系  


    """


def extract_kg_elements(text: str, prompt: str) -> Dict[str, Any]:

    """从文本中提取知识图谱元素"""
    system_prompt = """你是一个文档处理专家并擅长构建知识图谱"""
    user_prompt = f"{prompt}\n\n5. 待处理的文本如下：\n{text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        response_format={'type': 'json_object'},
        max_tokens=3000
    )

    result = json.loads(response.choices[0].message.content)
    return result

load_dotenv()
client = OpenAI(
            api_key=os.getenv("API_KEY", "API_KEY"),
            base_url=os.getenv("BASE_URL", "BASE_URL")
        )
preprocessed_path = "F:\毕设\Code\cig-kg-backend\doc_preprocessed\卷包（成型）在线质量检测装置_20250416_144853.txt"
chunks = split_text_by_chars(preprocessed_path, max_chars=3200)

for index, chunk in enumerate(chunks):
    print(f"{index}----------------------\n")
    print(chunk)

    kg_data = extract_kg_elements(text=chunk, prompt=prompt)
    with open(f"../kg_output/test/{index}.json", "w", encoding="utf-8") as f:
        json.dump(kg_data, f, ensure_ascii=False, indent=2)


