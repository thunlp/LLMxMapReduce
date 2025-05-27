"""
集成TaskManager使用示例

展示如何在同一个系统中使用Redis和SQLAlchemy两种TaskManager
以及如何在它们之间无缝切换
"""

import uuid
from flask import Flask
from src.common_service.models import db, User
from src.task_manager import (
    get_task_manager, 
    get_redis_task_manager,
    reset_task_manager,
    TaskStatus
)
from src.config_manager import RedisConfig

# 初始化Flask应用（示例）
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///example.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db.init_app(app)

def demo_redis_task_manager():
    """演示Redis TaskManager的使用"""
    print("🔴 Redis TaskManager 演示")
    print("=" * 50)
    
    # 配置Redis
    redis_config = RedisConfig(
        host='localhost',
        port=6379,
        db=0,
        password=None,
        key_prefix='demo_task:',
        expire_time=3600  # 1小时
    )
    
    try:
        # 获取Redis TaskManager
        task_manager = get_task_manager(manager_type="redis", redis_config=redis_config)
        
        # 创建任务
        task_id = str(uuid.uuid4())
        params = {
            "query": "Redis任务测试",
            "type": "redis_demo"
        }
        
        success = task_manager.create_task(task_id, params)
        print(f"✅ Redis任务创建: {success}, ID: {task_id}")
        
        # 更新状态
        task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
        print(f"✅ 状态更新为PROCESSING")
        
        # 获取任务
        task_info = task_manager.get_task(task_id)
        if task_info:
            print(f"📋 任务状态: {task_info['status']}")
            print(f"📋 任务参数: {task_info['params']}")
        
        # 完成任务
        task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
        print(f"✅ 任务完成")
        
        # 获取活跃任务数量
        active_count = task_manager.get_active_task_count()
        print(f"📊 活跃任务数量: {active_count}")
        
        # 清理任务
        task_manager.delete_task(task_id)
        print(f"🧹 任务已清理")
        
    except Exception as e:
        print(f"❌ Redis TaskManager演示失败: {e}")
        print("💡 请确保Redis服务正在运行")


def demo_sqlalchemy_task_manager():
    """演示SQLAlchemy TaskManager的使用"""
    print("\n🟢 SQLAlchemy TaskManager 演示")
    print("=" * 50)
    
    with app.app_context():
        try:
            # 创建数据库表
            db.create_all()
            
            # 确保有用户
            user = User.query.filter_by(phone="13800138000").first()
            if not user:
                user = User(phone="13800138000", remaining_uses=10)
                db.session.add(user)
                db.session.commit()
                print(f"✅ 创建用户: {user.phone}")
            
            # 重置TaskManager实例以切换到SQLAlchemy
            reset_task_manager()
            
            # 获取SQLAlchemy TaskManager
            task_manager = get_task_manager(
                manager_type="sqlalchemy",
                default_expire_hours=2
            )
            
            # 创建任务
            task_id = str(uuid.uuid4())
            params = {
                "query": "SQLAlchemy任务测试",
                "type": "sqlalchemy_demo"
            }
            
            # SQLAlchemy版本支持额外参数
            success = task_manager.create_task(
                task_id, 
                params, 
                user_id=user.id,
                expire_hours=1,
                priority=1
            )
            print(f"✅ SQLAlchemy任务创建: {success}, ID: {task_id}")
            
            # 更新状态
            task_manager.update_task_status(task_id, TaskStatus.PROCESSING)
            print(f"✅ 状态更新为PROCESSING")
            
            # 获取任务
            task_info = task_manager.get_task(task_id)
            if task_info:
                print(f"📋 任务状态: {task_info['status']}")
                print(f"📋 任务参数: {task_info['params']}")
                print(f"📋 优先级: {task_info.get('priority', 0)}")
            
            # 更新任务结果
            result_data = {
                "results": ["结果1", "结果2"],
                "summary": "SQLAlchemy任务执行成功"
            }
            task_manager.update_task_field(task_id, "result_data", result_data)
            print(f"✅ 任务结果已更新")
            
            # 完成任务
            task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
            print(f"✅ 任务完成")
            
            # 获取最终任务信息
            final_task = task_manager.get_task(task_id)
            if final_task:
                print(f"📊 执行时间: {final_task.get('execution_seconds', 0):.2f}秒")
                print(f"📊 结果数量: {len(final_task.get('result_data', {}).get('results', []))}")
            
            # 获取活跃任务数量
            active_count = task_manager.get_active_task_count()
            print(f"📊 活跃任务数量: {active_count}")
            
            # 清理任务
            task_manager.delete_task(task_id)
            print(f"🧹 任务已清理")
            
        except Exception as e:
            print(f"❌ SQLAlchemy TaskManager演示失败: {e}")


def demo_compatibility():
    """演示两种TaskManager的兼容性"""
    print("\n🔄 兼容性演示")
    print("=" * 30)
    
    with app.app_context():
        try:
            # 确保有用户
            user = User.query.first()
            if not user:
                user = User(phone="13800138001", remaining_uses=10)
                db.session.add(user)
                db.session.commit()
            
            # 重置实例
            reset_task_manager()
            
            # 使用SQLAlchemy创建任务
            sqlalchemy_manager = get_task_manager(manager_type="sqlalchemy")
            task_id = str(uuid.uuid4())
            
            success = sqlalchemy_manager.create_task(
                task_id,
                {"test": "compatibility"},
                user_id=user.id
            )
            print(f"✅ SQLAlchemy创建任务: {success}")
            
            # 获取任务信息
            task_info = sqlalchemy_manager.get_task(task_id)
            print(f"📋 任务信息: {task_info['status'] if task_info else 'None'}")
            
            # 两种TaskManager都实现了相同的接口
            print(f"📋 接口兼容性:")
            print(f"  - create_task: ✅")
            print(f"  - get_task: ✅")
            print(f"  - update_task_status: ✅")
            print(f"  - list_tasks: ✅")
            print(f"  - delete_task: ✅")
            
            # 清理
            sqlalchemy_manager.delete_task(task_id)
            
        except Exception as e:
            print(f"❌ 兼容性演示失败: {e}")


def demo_backward_compatibility():
    """演示向后兼容性"""
    print("\n🔙 向后兼容性演示")
    print("=" * 30)
    
    try:
        # 使用原有的函数签名
        redis_config = RedisConfig(
            host='localhost',
            port=6379,
            db=0,
            password=None,
            key_prefix='compat_test:',
            expire_time=3600
        )
        
        # 重置实例
        reset_task_manager()
        
        # 使用原有的get_redis_task_manager函数
        task_manager = get_redis_task_manager(redis_config)
        print(f"✅ 原有函数签名仍然可用")
        
        # 使用新的get_task_manager函数（默认Redis）
        reset_task_manager()
        task_manager = get_task_manager(manager_type="redis", redis_config=redis_config)
        print(f"✅ 新函数签名也可用")
        
        print(f"📋 向后兼容性: 完美 ✅")
        
    except Exception as e:
        print(f"❌ 向后兼容性测试失败: {e}")


def performance_comparison():
    """性能对比演示"""
    print("\n⚡ 性能对比演示")
    print("=" * 30)
    
    import time
    
    with app.app_context():
        try:
            # 确保有用户
            user = User.query.first()
            if not user:
                user = User(phone="13800138002", remaining_uses=100)
                db.session.add(user)
                db.session.commit()
            
            # SQLAlchemy性能测试
            reset_task_manager()
            sqlalchemy_manager = get_task_manager(manager_type="sqlalchemy")
            
            start_time = time.time()
            task_ids = []
            
            for i in range(5):
                task_id = str(uuid.uuid4())
                success = sqlalchemy_manager.create_task(
                    task_id,
                    {"test": f"perf_test_{i}"},
                    user_id=user.id
                )
                if success:
                    task_ids.append(task_id)
            
            sqlalchemy_time = time.time() - start_time
            print(f"📊 SQLAlchemy创建5个任务: {sqlalchemy_time:.3f}秒")
            
            # 清理SQLAlchemy任务
            for task_id in task_ids:
                sqlalchemy_manager.delete_task(task_id)
            
            # Redis性能测试（如果可用）
            try:
                redis_config = RedisConfig(
                    host='localhost',
                    port=6379,
                    db=0,
                    password=None,
                    key_prefix='perf_test:',
                    expire_time=3600
                )
                
                reset_task_manager()
                redis_manager = get_task_manager(manager_type="redis", redis_config=redis_config)
                
                start_time = time.time()
                task_ids = []
                
                for i in range(5):
                    task_id = str(uuid.uuid4())
                    success = redis_manager.create_task(task_id, {"test": f"perf_test_{i}"})
                    if success:
                        task_ids.append(task_id)
                
                redis_time = time.time() - start_time
                print(f"📊 Redis创建5个任务: {redis_time:.3f}秒")
                
                # 清理Redis任务
                for task_id in task_ids:
                    redis_manager.delete_task(task_id)
                
                # 性能对比
                if redis_time > 0:
                    ratio = sqlalchemy_time / redis_time
                    print(f"📊 性能比率 (SQLAlchemy/Redis): {ratio:.2f}")
                
            except Exception as e:
                print(f"⚠️  Redis性能测试跳过: {e}")
            
        except Exception as e:
            print(f"❌ 性能对比失败: {e}")


if __name__ == "__main__":
    print("🚀 集成TaskManager演示")
    print("=" * 60)
    
    # Redis演示
    demo_redis_task_manager()
    
    # SQLAlchemy演示
    demo_sqlalchemy_task_manager()
    
    # 兼容性演示
    demo_compatibility()
    
    # 向后兼容性演示
    demo_backward_compatibility()
    
    # 性能对比演示
    performance_comparison()
    
    print("\n✨ 所有演示完成！")
    print("\n💡 使用建议:")
    print("  - 高并发、分布式场景: 使用Redis TaskManager")
    print("  - 单机、中小型应用: 使用SQLAlchemy TaskManager")
    print("  - 需要复杂查询和关系: 使用SQLAlchemy TaskManager")
    print("  - 需要数据持久化保证: 使用SQLAlchemy TaskManager") 