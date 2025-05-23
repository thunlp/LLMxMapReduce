#!/usr/bin/env python3
"""
测试脚本：验证修改后的pipeline任务隔离功能

这个脚本模拟发送多个并发请求，验证：
1. 每个任务是否有唯一的综述标题
2. 任务结果是否正确隔离
3. 基于内容的检测是否正常工作
"""

import requests
import json
import time
import concurrent.futures
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置
BASE_URL = "http://localhost:5000"
TEST_TOPICS = [
    "深度学习在自然语言处理中的应用",
    "区块链技术在金融领域的发展",
    "人工智能在医疗诊断中的运用"
]

def submit_task(topic):
    """提交一个任务"""
    try:
        url = f"{BASE_URL}/api/start_pipeline"
        data = {
            "topic": topic,
            "description": f"关于{topic}的综合调研",
            "block_count": 0,
            "top_n": 50
        }
        
        logger.info(f"提交任务: {topic}")
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get('success'):
            task_id = result['task_id']
            unique_title = result['unique_survey_title']
            logger.info(f"任务提交成功: {task_id}, 唯一标题: {unique_title}")
            return {
                'task_id': task_id,
                'topic': topic,
                'unique_title': unique_title,
                'output_file': result['output_file']
            }
        else:
            logger.error(f"任务提交失败: {result}")
            return None
            
    except Exception as e:
        logger.error(f"提交任务 '{topic}' 时发生错误: {str(e)}")
        return None

def check_task_status(task_id):
    """检查任务状态"""
    try:
        url = f"{BASE_URL}/api/task/{task_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('success'):
            task = result['task']
            return task['status']
        else:
            logger.error(f"获取任务状态失败: {result}")
            return None
            
    except Exception as e:
        logger.error(f"检查任务状态时发生错误: {str(e)}")
        return None

def wait_for_completion(task_info, timeout=1800):  # 30分钟超时
    """等待任务完成"""
    task_id = task_info['task_id']
    topic = task_info['topic']
    start_time = time.time()
    
    logger.info(f"开始监控任务 {task_id} ({topic})")
    
    while time.time() - start_time < timeout:
        status = check_task_status(task_id)
        if status is None:
            logger.warning(f"无法获取任务 {task_id} 的状态")
            time.sleep(30)
            continue
            
        if status == 'completed':
            logger.info(f"任务 {task_id} ({topic}) 已完成")
            return True
        elif status == 'failed':
            logger.error(f"任务 {task_id} ({topic}) 执行失败")
            return False
        else:
            logger.info(f"任务 {task_id} ({topic}) 状态: {status}")
            time.sleep(30)
    
    logger.error(f"任务 {task_id} ({topic}) 超时")
    return False

def verify_output_isolation(task_infos):
    """验证输出隔离是否正确"""
    logger.info("开始验证输出隔离...")
    
    for task_info in task_infos:
        task_id = task_info['task_id']
        unique_title = task_info['unique_title']
        output_file = task_info['output_file']
        
        try:
            if not os.path.exists(output_file):
                logger.error(f"输出文件不存在: {output_file}")
                continue
                
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    logger.error(f"输出文件为空: {output_file}")
                    continue
                    
                # 检查是否包含正确的标题
                lines = content.strip().split('\n')
                found_correct_title = False
                
                for line in lines:
                    try:
                        data = json.loads(line)
                        if data.get('title') == unique_title:
                            found_correct_title = True
                            logger.info(f"✓ 任务 {task_id} 输出正确，包含唯一标题: {unique_title}")
                            break
                    except json.JSONDecodeError:
                        continue
                
                if not found_correct_title:
                    logger.error(f"✗ 任务 {task_id} 输出不正确，未找到唯一标题: {unique_title}")
                    
        except Exception as e:
            logger.error(f"验证任务 {task_id} 输出时发生错误: {str(e)}")

def main():
    """主测试函数"""
    logger.info("开始pipeline任务隔离测试")
    
    # 1. 提交多个任务
    logger.info("=== 阶段1: 提交多个任务 ===")
    submitted_tasks = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_topic = {executor.submit(submit_task, topic): topic for topic in TEST_TOPICS}
        
        for future in concurrent.futures.as_completed(future_to_topic):
            topic = future_to_topic[future]
            try:
                task_info = future.result()
                if task_info:
                    submitted_tasks.append(task_info)
                else:
                    logger.error(f"提交任务 '{topic}' 失败")
            except Exception as e:
                logger.error(f"提交任务 '{topic}' 时发生异常: {str(e)}")
    
    if not submitted_tasks:
        logger.error("没有成功提交任何任务，测试终止")
        return
    
    logger.info(f"成功提交 {len(submitted_tasks)} 个任务")
    
    # 2. 等待任务完成
    logger.info("=== 阶段2: 等待任务完成 ===")
    completed_tasks = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(submitted_tasks)) as executor:
        future_to_task = {executor.submit(wait_for_completion, task): task for task in submitted_tasks}
        
        for future in concurrent.futures.as_completed(future_to_task):
            task_info = future_to_task[future]
            try:
                success = future.result()
                if success:
                    completed_tasks.append(task_info)
                    logger.info(f"任务 {task_info['task_id']} 成功完成")
                else:
                    logger.error(f"任务 {task_info['task_id']} 失败")
            except Exception as e:
                logger.error(f"等待任务 {task_info['task_id']} 完成时发生异常: {str(e)}")
    
    # 3. 验证输出隔离
    logger.info("=== 阶段3: 验证输出隔离 ===")
    if completed_tasks:
        # 等待一点时间确保文件写入完成
        time.sleep(10)
        verify_output_isolation(completed_tasks)
    else:
        logger.error("没有任务成功完成，无法验证输出隔离")
    
    # 4. 生成测试报告
    logger.info("=== 测试结果汇总 ===")
    logger.info(f"提交任务数: {len(submitted_tasks)}")
    logger.info(f"完成任务数: {len(completed_tasks)}")
    logger.info(f"成功率: {len(completed_tasks)/len(submitted_tasks)*100:.1f}%")
    
    logger.info("测试完成")

if __name__ == "__main__":
    import os
    main() 