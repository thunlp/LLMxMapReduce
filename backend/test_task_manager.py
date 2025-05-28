#!/usr/bin/env python3
"""
测试SQLAlchemy任务管理器
"""
import sys
import os

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.task_manager import get_task_manager, TaskStatus

def test_sqlalchemy_task_manager():
    """测试SQLAlchemy任务管理器"""
    print("开始测试SQLAlchemy任务管理器...")
    
    try:
        # 创建任务管理器实例
        task_manager = get_task_manager(
            manager_type="sqlalchemy",
            database_url="sqlite:///test_tasks.db"
        )
        print("✓ 任务管理器创建成功")
        
        # 测试健康检查
        if task_manager.health_check():
            print("✓ 健康检查通过")
        else:
            print("✗ 健康检查失败")
            return False
        
        # 测试创建任务
        task_id = "test_task_001"
        params = {"query": "测试查询", "type": "test"}
        
        if task_manager.create_task(task_id, params):
            print("✓ 任务创建成功")
        else:
            print("✗ 任务创建失败")
            return False
        
        # 测试获取任务
        task = task_manager.get_task(task_id)
        if task:
            print(f"✓ 任务获取成功: {task['status']}")
            print(f"  任务参数: {task['params']}")
        else:
            print("✗ 任务获取失败")
            return False
        
        # 测试更新任务状态
        if task_manager.update_task_status(task_id, TaskStatus.PROCESSING):
            print("✓ 任务状态更新成功")
        else:
            print("✗ 任务状态更新失败")
            return False
        
        # 测试获取任务列表
        tasks = task_manager.list_tasks()
        print(f"✓ 获取任务列表成功，共 {len(tasks)} 个任务")
        
        # 测试获取活跃任务数量
        active_count = task_manager.get_active_task_count()
        print(f"✓ 活跃任务数量: {active_count}")
        
        # 测试删除任务
        if task_manager.delete_task(task_id):
            print("✓ 任务删除成功")
        else:
            print("✗ 任务删除失败")
            return False
        
        print("\n所有测试通过！SQLAlchemy任务管理器工作正常。")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sqlalchemy_task_manager()
    
    # 清理测试文件
    try:
        if os.path.exists("test_tasks.db"):
            os.remove("test_tasks.db")
            print("测试数据库文件已清理")
    except:
        pass
    
    sys.exit(0 if success else 1) 