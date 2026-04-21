#!/usr/bin/env python3
"""
IT日志文本预处理模块
实现IT领域特殊的正则分词规则，这是模型效果好坏的生命线

核心功能：
1. 去除动态变量（IP地址、纯数字、时间戳）
2. 分隔符切分（空格、/、-、_、.）
3. 驼峰命名拆分（OutOfMemoryError -> Out Of Memory Error）
4. 去除停用词
5. 全小写化
"""
import logging
import re
from typing import List, Set

from config import IT_STOPWORDS, MIN_WORD_LENGTH

logger = logging.getLogger(__name__)

IP_PATTERN = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
)

PORT_PATTERN = re.compile(r':\d{1,5}\b')

TIMESTAMP_PATTERNS = [
    re.compile(r'\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'),
    re.compile(r'\b\d{2}:\d{2}:\d{2}\.\d+\b'),
    re.compile(r'\b\d{13,}\b'),
    re.compile(r'\b\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2}\b'),
]

PURE_NUMBER_PATTERN = re.compile(r'\b\d+\.?\d*\b')

HEX_PATTERN = re.compile(r'\b0x[0-9a-fA-F]+\b')

UUID_PATTERN = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.IGNORECASE)

CAMEL_CASE_PATTERN = re.compile(r'([a-z])([A-Z])')

NUM_LETTER_PATTERN = re.compile(r'(\d)([a-zA-Z])')
LETTER_NUM_PATTERN = re.compile(r'([a-zA-Z])(\d)')

SEPARATOR_PATTERN = re.compile(r'[\s/\-_.:]+')

STOPWORDS_SET: Set[str] = set(IT_STOPWORDS)


def remove_dynamic_variables(text: str) -> str:
    """
    去除动态变量：IP地址、端口、时间戳、纯数字、十六进制、UUID
    防止模型学习无意义的数字规律
    """
    result = text
    result = IP_PATTERN.sub(' ', result)
    result = PORT_PATTERN.sub(' ', result)
    for pattern in TIMESTAMP_PATTERNS:
        result = pattern.sub(' ', result)
    result = HEX_PATTERN.sub(' ', result)
    result = UUID_PATTERN.sub(' ', result)
    result = PURE_NUMBER_PATTERN.sub(' ', result)
    return result


def split_camel_case(text: str) -> str:
    """
    拆分驼峰命名
    例如：OutOfMemoryError -> Out Of Memory Error
         redisCluster -> redis Cluster
         APIGateway -> API Gateway
         HTTP2Protocol -> HTTP 2 Protocol
    """
    result = CAMEL_CASE_PATTERN.sub(r'\1 \2', text)
    result = NUM_LETTER_PATTERN.sub(r'\1 \2', result)
    result = LETTER_NUM_PATTERN.sub(r'\1 \2', result)
    return result


def tokenize_it_text(text: str) -> List[str]:
    """
    IT日志正则分词主函数
    
    输入：一行原始日志文本
    输出：分词后的词列表 ['word1', 'word2', ...]
    
    处理流程：
    1. 去除动态变量（IP、数字、时间戳等）
    2. 拆分驼峰命名
    3. 按分隔符切分
    4. 过滤停用词和短词
    5. 全小写化
    """
    if not text or not isinstance(text, str):
        return []
    
    cleaned = remove_dynamic_variables(text)
    
    cleaned = split_camel_case(cleaned)
    
    tokens = SEPARATOR_PATTERN.split(cleaned)
    
    result = []
    for token in tokens:
        token = token.lower().strip()
        if len(token) < MIN_WORD_LENGTH:
            continue
        if token in STOPWORDS_SET:
            continue
        if token.isnumeric():
            continue
        if all(c in '._-' for c in token):
            continue
        result.append(token)
    
    return result


def preprocess_for_drain(text: str) -> str:
    """
    为Drain算法预处理文本
    将IP、端口等替换为占位符，保留模板结构
    """
    result = text
    result = IP_PATTERN.sub('<IP>', result)
    result = PORT_PATTERN.sub(':<PORT>', result)
    for pattern in TIMESTAMP_PATTERNS:
        result = pattern.sub('<TIMESTAMP>', result)
    result = HEX_PATTERN.sub('<HEX>', result)
    result = UUID_PATTERN.sub('<UUID>', result)
    result = PURE_NUMBER_PATTERN.sub('<NUM>', result)
    return result


def batch_tokenize(texts: List[str]) -> List[List[str]]:
    """
    批量分词
    """
    return [tokenize_it_text(text) for text in texts]
