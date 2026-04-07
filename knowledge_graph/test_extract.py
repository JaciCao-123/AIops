#!/usr/bin/env python3
"""
测试LLM提取功能
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.dirname(__file__))

import openai
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

client = openai.OpenAI(
    api_key=os.getenv('QWEN_API_KEY'),
    base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
)

prompt_template = """你是一个医疗知识图谱专家。请从以下文本中提取实体、属性和关系。

实体类型定义：
- 药物：具有治疗作用的物质
- 疾病：疾病名称
- 症状：疾病表现
- 药物类别：药物的分类

关系类型：
- 治疗：药物用于治疗疾病
- 属于：药物属于某类别
- 常用于：药物通常用于某种情况
- 引发：疾病引发症状

请以JSON格式返回，格式如下：
{
    "entities": [
        {
            "name": "实体名称",
            "type": "实体类型",
            "properties": {
                "description": "描述"
            }
        }
    ],
    "relations": [
        {
            "source": "头实体名称",
            "relation": "关系类型",
            "target": "尾实体名称"
        }
    ]
}

文本内容：
{text}

请直接返回JSON，不要包含其他内容。"""

def clean_json(text):
    """清理JSON字符串"""
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    return text

text = '阿司匹林主要用于治疗头痛和发热。它属于非甾体抗炎药。布洛芬也属于非甾体抗炎药，常用于缓解疼痛。'

print('测试文本:', text)
print()

response = client.chat.completions.create(
    model='qwen-plus',
    messages=[
        {'role': 'user', 'content': prompt_template.format(text=text)}
    ],
    temperature=0.1
)

content = response.choices[0].message.content
print('='*60)
print('原始响应:')
print('='*60)
print(content)
print()

cleaned = clean_json(content)
print('='*60)
print('清理后:')
print('='*60)
print(cleaned)
print()

try:
    data = json.loads(cleaned)
    print('='*60)
    print('解析成功!')
    print('='*60)
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    print('='*60)
    print(f'解析失败: {e}')
    print('='*60)
