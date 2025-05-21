from flask import Blueprint, request
from datetime import datetime, timezone
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, Task
from app.utils.helpers import api_response, jwt_required_custom

task_bp = Blueprint('task', __name__)

@task_bp.route('/create', methods=['POST'])
@jwt_required_custom
def create_task():
    """创建新任务"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return api_response(message="用户不存在", status=404)
    
    # 检查用户剩余使用次数
    if user.remaining_uses <= 0:
        return api_response(message="使用次数不足，请兑换后再试", status=403)
    
    # 创建新任务
    task = Task(
        user_id=user_id,
        status="准备"
    )
    
    # 减少用户使用次数
    user.remaining_uses -= 1
    
    db.session.add(task)
    db.session.commit()
    
    return api_response(
        data={"task_id": task.id},
        message="任务创建成功"
    )

@task_bp.route('/update_status', methods=['POST'])
@jwt_required_custom
def update_task_status():
    """更新任务状态"""
    data = request.get_json()
    
    if not data or 'task_id' not in data or 'status' not in data:
        return api_response(message="请提供任务ID和状态", status=400)
    
    task_id = data['task_id']
    status = data['status']
    
    # 验证状态值
    valid_statuses = ["准备", "处理中", "完成"]
    if status not in valid_statuses:
        return api_response(message="无效的任务状态", status=400)
    
    # 查找任务
    task = Task.query.get(task_id)
    
    if not task:
        return api_response(message="任务不存在", status=404)
    
    # 更新任务状态
    task.status = status
    
    # 根据状态更新相关字段
    now = datetime.now(timezone.utc)
    
    if status == "处理中" and not task.start_time:
        task.start_time = now
    
    if status == "完成" and not task.end_time:
        task.end_time = now
        if task.start_time:
            # 计算执行时间（秒）
            delta = task.end_time - task.start_time
            task.execution_time = delta.total_seconds()
    
    # 更新其他可选字段
    if 'error' in data:
        task.error = data['error']
    
    if 'output_file_path' in data:
        task.output_file_path = data['output_file_path']
    
    db.session.commit()
    
    return api_response(
        data={"task_id": task.id, "status": task.status},
        message="任务状态更新成功"
    )

@task_bp.route('/list', methods=['GET'])
@jwt_required_custom
def get_task_list():
    """获取用户任务列表"""
    user_id = get_jwt_identity()
    
    # 分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 状态过滤
    status = request.args.get('status')
    
    # 构建查询
    query = Task.query.filter_by(user_id=user_id)
    
    if status:
        query = query.filter_by(status=status)
    
    # 按创建时间倒序排列
    tasks = query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    task_list = [{
        "id": task.id,
        "status": task.status,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "execution_time": task.execution_time,
        "created_at": task.created_at.isoformat(),
        "output_file_path": task.output_file_path
    } for task in tasks.items]
    
    return api_response(
        data={
            "tasks": task_list,
            "pagination": {
                "total": tasks.total,
                "pages": tasks.pages,
                "current_page": page,
                "per_page": per_page
            }
        },
        message="获取任务列表成功"
    )

@task_bp.route('/detail/<int:task_id>', methods=['GET'])
@jwt_required_custom
def get_task_detail(task_id):
    """获取任务详情"""
    user_id = get_jwt_identity()
    
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    
    if not task:
        return api_response(message="任务不存在或无权访问", status=404)
    
    task_detail = {
        "id": task.id,
        "status": task.status,
        "start_time": task.start_time.isoformat() if task.start_time else None,
        "end_time": task.end_time.isoformat() if task.end_time else None,
        "execution_time": task.execution_time,
        "error": task.error,
        "output_file_path": task.output_file_path,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat()
    }
    
    return api_response(
        data={"task": task_detail},
        message="获取任务详情成功"
    )
