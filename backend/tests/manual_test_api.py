#!/usr/bin/env python3
import requests
import json
import time
import os

# 基础URL
BASE_URL = "http://localhost:5001"

def test_redemption_apis():
    # 检查配置文件是否存在
    if not os.path.exists("test_config.json"):
        print("请先运行 setup_test_data.py 创建测试数据和配置文件")
        return

    # 加载测试配置
    with open("test_config.json", "r") as f:
        config = json.load(f)
    
    token = config["authToken"]
    test_code = config["testRedemptionCode"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 1. 测试生成兑换码
    print("\n===== 测试生成兑换码 =====")
    generate_data = {
        "count": 2,
        "uses_granted": 3
    }
    
    response = requests.post(
        f"{BASE_URL}/api/redemption/generate",
        headers=headers,
        json=generate_data
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    
    if response.status_code == 200:
        generated_codes = response.json()["data"]["codes"]
        if generated_codes and len(generated_codes) > 0:
            new_test_code = generated_codes[0]["code"]
            print(f"新生成的测试兑换码: {new_test_code}")
    
    # 2. 测试兑换码使用
    print("\n===== 测试兑换码使用 =====")
    redeem_data = {
        "code": test_code
    }
    
    response = requests.post(
        f"{BASE_URL}/api/redemption/redeem",
        headers=headers,
        json=redeem_data
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    
    # 3. 测试获取兑换历史
    print("\n===== 测试获取兑换历史 =====")
    time.sleep(1)  # 等待1秒确保历史记录已保存
    
    response = requests.get(
        f"{BASE_URL}/api/redemption/history",
        headers=headers
    )
    
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    # 检查服务器是否启动
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            test_redemption_apis()
        else:
            print(f"服务器状态异常: {response.status_code}")
    except requests.ConnectionError:
        print(f"无法连接到服务器 {BASE_URL}，请确保服务器已启动") 