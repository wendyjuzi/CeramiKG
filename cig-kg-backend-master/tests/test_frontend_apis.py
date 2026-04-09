#!/usr/bin/env python3
"""
前端API端点测试脚本
测试前端在"图谱构建"页面调用的API端点
"""

import requests
import sys
import json

# 后端服务地址
BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, description, params=None):
    """测试单个API端点"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n测试 {description}")
    print(f"方法: {method.upper()}")
    print(f"URL: {url}")
    if params:
        print(f"参数: {params}")
    
    try:
        if method.lower() == 'get':
            response = requests.get(url, params=params, timeout=10)
        else:
            response = requests.request(method, url, params=params, timeout=10)
            
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 成功")
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"返回列表，包含 {len(data)} 个项目")
                    if len(data) > 0:
                        print(f"第一个项目的键: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
                elif isinstance(data, dict):
                    print(f"返回字典，包含键: {list(data.keys())}")
                else:
                    print(f"返回数据类型: {type(data)}")
            except json.JSONDecodeError:
                print("返回非JSON数据")
                print(f"响应内容: {response.text[:200]}...")
        elif response.status_code == 404:
            print("❌ 404 Not Found - 端点不存在或路由配置错误")
        elif response.status_code == 422:
            print("❌ 422 Unprocessable Entity - 参数验证失败")
            try:
                error_detail = response.json()
                print(f"错误详情: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
            except:
                print(f"错误响应: {response.text}")
        elif response.status_code == 500:
            print("❌ 500 Internal Server Error - 服务器内部错误")
            try:
                error_detail = response.json()
                print(f"错误详情: {error_detail.get('detail', 'Unknown error')}")
            except:
                print(f"错误响应: {response.text}")
        else:
            print(f"❌ 错误状态码: {response.status_code}")
            print(f"响应: {response.text[:200]}...")
            
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败 - 请确保后端服务正在运行")
        print("启动命令: uvicorn app.main:app --reload")
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def main():
    """主测试函数"""
    print("=== 前端API端点测试 ===")
    print(f"测试后端服务: {BASE_URL}")
    
    # 首先测试服务是否运行
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ 后端服务正在运行")
        else:
            print("⚠️ 后端服务状态异常")
    except:
        print("❌ 无法连接到后端服务，请确保服务正在运行")
        print("启动命令: cd cig-kg-backend-master && uvicorn app.main:app --reload")
        return
    
    print("\n" + "="*60)
    print("测试前端'图谱构建'页面调用的API端点")
    print("="*60)
    
    # 测试前端调用的三个主要端点
    test_cases = [
        # DocumentSelector.vue 调用的端点
        {
            "method": "GET",
            "endpoint": "/api/graph/documents",
            "description": "文档列表（默认数据库）",
            "params": {"use_juanyan": False}
        },
        {
            "method": "GET", 
            "endpoint": "/api/graph/documents",
            "description": "文档列表（卷烟知识库）",
            "params": {"use_juanyan": True}
        },
        
        # TermSelector.vue 调用的端点
        {
            "method": "GET",
            "endpoint": "/api/graph/terms",
            "description": "术语列表",
            "params": None
        },
        
        # KnowledgeGraph.vue 调用的端点
        {
            "method": "GET",
            "endpoint": "/api/graph/knowledge-tables",
            "description": "知识表列表",
            "params": None
        }
    ]
    
    for test_case in test_cases:
        test_endpoint(
            test_case["method"],
            test_case["endpoint"], 
            test_case["description"],
            test_case["params"]
        )
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n如果看到 404 错误，说明端点配置有问题")
    print("如果看到 500 错误，说明数据库连接或服务逻辑有问题")
    print("如果看到 422 错误，说明参数格式或验证有问题")

if __name__ == "__main__":
    main()