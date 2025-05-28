#!/usr/bin/env python3
"""
测试PostgreSQL任务管理器

验证PostgreSQLTaskManager的所有功能，包括：
- 任务创建和状态更新
- Flask应用上下文处理
- 多线程安全性
- 数据库事务处理
"""
import sys
import os
import threading
import time
import uuid
from datetime import datetime

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from flask import Flask
from src.common_service.models import db, User
from src.task_manager import get_task_manager, reset_task_manager, TaskStatus


def create_test_app():
    """创建测试Flask应用"""
    app = Flask(__name__)
    
    # 使用SQLite内存数据库进行测试
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_tasks.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # 初始化数据库
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # 创建测试用户
        test_user = User.query.filter_by(phone='test_user').first()
        if not test_user:
            test_user = User(phone='test_user', remaining_uses=100)
            db.session.add(test_user)
            db.session.commit()
            print(f"✓ 创建测试用户: ID={test_user.id}")
    
    return app


def test_basic_operations():
    """测试基本操作"""
    print("\n🔧 测试基本操作")
    print("-" * 40)
    
    app = create_test_app()
    
    # 重置任务管理器以确保使用新的实例
    reset_task_manager()
    
    # 创建PostgreSQL任务管理器
    task_manager = get_task_manager(
        manager_type="postgresql",
        flask_app=app,
        expire_time=3600,
        user_id=1
    )
    
    # 测试健康检查
    if task_manager.health_check():
        print("✓ 健康检查通过")
    else:
        print("✗ 健康检查失败")
        return False
    
    # 测试创建任务
    task_id = str(uuid.uuid4())
    params = {
        "topic": "测试主题",
        "description": "这是一个测试任务",
        "user_id": 1
    }
    
    if task_manager.create_task(task_id, params):
        print(f"✓ 任务创建成功: {task_id}")
    else:
        print("✗ 任务创建失败")
        return False
    
    # 测试获取任务
    task = task_manager.get_task(task_id)
    if task:
        print(f"✓ 任务获取成功: 状态={task['status']}")
        print(f"  参数: {task['params']}")
    else:
        print("✗ 任务获取失败")
        return False
    
    # 测试更新任务状态
    if task_manager.update_task_status(task_id, TaskStatus.PROCESSING):
        print("✓ 任务状态更新成功")
    else:
        print("✗ 任务状态更新失败")
        return False
    
    # 验证状态更新
    updated_task = task_manager.get_task(task_id)
    if updated_task and updated_task['status'] == TaskStatus.PROCESSING.value:
        print("✓ 状态更新验证成功")
    else:
        print("✗ 状态更新验证失败")
        return False
    
    # 测试更新任务字段
    if task_manager.update_task_field(task_id, 'result_data', {'result': 'test_result'}):
        print("✓ 任务字段更新成功")
    else:
        print("✗ 任务字段更新失败")
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
    
    return True


def test_threading_safety():
    """测试多线程安全性"""
    print("\n🧵 测试多线程安全性")
    print("-" * 40)
    
    app = create_test_app()
    
    # 重置任务管理器
    reset_task_manager()
    
    # 创建PostgreSQL任务管理器
    task_manager = get_task_manager(
        manager_type="postgresql",
        flask_app=app,
        expire_time=3600,
        user_id=1
    )
    
    # 用于收集结果的列表
    results = []
    errors = []
    
    def worker_thread(thread_id):
        """工作线程函数"""
        try:
            task_id = f"thread_{thread_id}_{uuid.uuid4()}"
            params = {
                "topic": f"线程{thread_id}测试",
                "thread_id": thread_id,
                "user_id": 1
            }
            
            # 创建任务
            if not task_manager.create_task(task_id, params):
                errors.append(f"线程{thread_id}: 任务创建失败")
                return
            
            # 更新状态
            if not task_manager.update_task_status(task_id, TaskStatus.PROCESSING):
                errors.append(f"线程{thread_id}: 状态更新失败")
                return
            
            # 获取任务
            task = task_manager.get_task(task_id)
            if not task:
                errors.append(f"线程{thread_id}: 任务获取失败")
                return
            
            # 更新结果
            if not task_manager.update_task_field(task_id, 'result_data', {'thread': thread_id}):
                errors.append(f"线程{thread_id}: 字段更新失败")
                return
            
            # 完成任务
            if not task_manager.update_task_status(task_id, TaskStatus.COMPLETED):
                errors.append(f"线程{thread_id}: 完成状态更新失败")
                return
            
            results.append(f"线程{thread_id}: 成功")
            
        except Exception as e:
            errors.append(f"线程{thread_id}: 异常 - {str(e)}")
    
    # 创建并启动多个线程
    threads = []
    thread_count = 5
    
    for i in range(thread_count):
        thread = threading.Thread(target=worker_thread, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 检查结果
    print(f"✓ 成功完成的线程: {len(results)}")
    print(f"✗ 失败的线程: {len(errors)}")
    
    if errors:
        print("错误详情:")
        for error in errors:
            print(f"  - {error}")
    
    return len(errors) == 0


def test_app_context_handling():
    """测试Flask应用上下文处理"""
    print("\n🌐 测试Flask应用上下文处理")
    print("-" * 40)
    
    app = create_test_app()
    
    # 重置任务管理器
    reset_task_manager()
    
    # 创建PostgreSQL任务管理器
    task_manager = get_task_manager(
        manager_type="postgresql",
        flask_app=app,
        expire_time=3600,
        user_id=1
    )
    
    def test_outside_context():
        """在应用上下文外测试"""
        try:
            task_id = f"outside_context_{uuid.uuid4()}"
            params = {"topic": "上下文外测试", "user_id": 1}
            
            # 这应该自动创建应用上下文
            success = task_manager.create_task(task_id, params)
            if success:
                print("✓ 在应用上下文外创建任务成功")
                
                # 获取任务
                task = task_manager.get_task(task_id)
                if task:
                    print("✓ 在应用上下文外获取任务成功")
                    
                    # 清理
                    task_manager.delete_task(task_id)
                    return True
                else:
                    print("✗ 在应用上下文外获取任务失败")
                    return False
            else:
                print("✗ 在应用上下文外创建任务失败")
                return False
                
        except Exception as e:
            print(f"✗ 上下文外测试异常: {str(e)}")
            return False
    
    def test_inside_context():
        """在应用上下文内测试"""
        try:
            with app.app_context():
                task_id = f"inside_context_{uuid.uuid4()}"
                params = {"topic": "上下文内测试", "user_id": 1}
                
                success = task_manager.create_task(task_id, params)
                if success:
                    print("✓ 在应用上下文内创建任务成功")
                    
                    # 获取任务
                    task = task_manager.get_task(task_id)
                    if task:
                        print("✓ 在应用上下文内获取任务成功")
                        
                        # 清理
                        task_manager.delete_task(task_id)
                        return True
                    else:
                        print("✗ 在应用上下文内获取任务失败")
                        return False
                else:
                    print("✗ 在应用上下文内创建任务失败")
                    return False
                    
        except Exception as e:
            print(f"✗ 上下文内测试异常: {str(e)}")
            return False
    
    # 运行测试
    outside_ok = test_outside_context()
    inside_ok = test_inside_context()
    
    return outside_ok and inside_ok


def test_error_handling():
    """测试错误处理"""
    print("\n⚠️  测试错误处理")
    print("-" * 40)
    
    app = create_test_app()
    
    # 重置任务管理器
    reset_task_manager()
    
    # 创建PostgreSQL任务管理器
    task_manager = get_task_manager(
        manager_type="postgresql",
        flask_app=app,
        expire_time=3600,
        user_id=1
    )
    
    # 测试获取不存在的任务
    non_existent_task = task_manager.get_task("non_existent_task_id")
    if non_existent_task is None:
        print("✓ 正确处理不存在的任务")
    else:
        print("✗ 未正确处理不存在的任务")
        return False
    
    # 测试更新不存在任务的状态
    update_result = task_manager.update_task_status("non_existent_task_id", TaskStatus.COMPLETED)
    if not update_result:
        print("✓ 正确处理不存在任务的状态更新")
    else:
        print("✗ 未正确处理不存在任务的状态更新")
        return False
    
    # 测试删除不存在的任务
    delete_result = task_manager.delete_task("non_existent_task_id")
    if not delete_result:
        print("✓ 正确处理不存在任务的删除")
    else:
        print("✗ 未正确处理不存在任务的删除")
        return False
    
    return True


def main():
    """主测试函数"""
    print("🧪 PostgreSQL TaskManager 测试")
    print("=" * 50)
    
    try:
        # 运行所有测试
        tests = [
            ("基本操作", test_basic_operations),
            ("多线程安全性", test_threading_safety),
            ("应用上下文处理", test_app_context_handling),
            ("错误处理", test_error_handling)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    print(f"✅ {test_name}: 通过")
                    passed += 1
                else:
                    print(f"❌ {test_name}: 失败")
            except Exception as e:
                print(f"❌ {test_name}: 异常 - {str(e)}")
        
        print(f"\n📊 测试结果: {passed}/{total} 通过")
        
        if passed == total:
            print("🎉 所有测试通过！PostgreSQL TaskManager 工作正常。")
            return True
        else:
            print("⚠️  部分测试失败，请检查问题。")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {str(e)}")
        return False
    finally:
        # 清理测试数据库文件
        try:
            if os.path.exists("test_tasks.db"):
                os.remove("test_tasks.db")
                print("🧹 测试数据库文件已清理")
        except:
            pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 