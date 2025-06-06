interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data: T;
}

interface LoginResponse {
  token: string;
  user: {
    id: number;
    phone: string;
    remaining_uses: number;
  };
}

// 新增：用户信息响应接口
interface UserInfoResponse {
  id: number;
  phone: string;
  remaining_uses: number;
  created_at: string;
}

// 新增：任务提交响应接口
interface TaskSubmitResponse {
  task_id: string;
  output_file: string;
  original_topic: string;
  unique_survey_title: string;
}

// 新增：兑换码使用响应接口
interface RedemptionResponse {
  remaining_uses: number;
  added_uses: number;
}

// 新增：兑换历史响应接口
interface RedemptionHistory {
  history: Array<{
    id: number;
    code: string;
    uses_granted: number;
    redeemed_at: string;
  }>;
}

// 新增：用户任务列表响应接口
interface UserTask {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  params: {
    topic: string;
    user_id: number;
  };
  execution_seconds?: number;
  start_time?: string;
  end_time?: string;
}

// 实际API返回的格式（直接包含success字段）
interface UserTasksResponse {
  success: boolean;
  tasks: UserTask[];
  count: number;
  user_id: number;
  message?: string;
}

const API_BASE_URL = 'http://localhost:5000';

// 发送验证码
export async function sendVerificationCode(phone: string): Promise<ApiResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/send_code`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phone }),
  });

  if (!response.ok) {
    throw new Error('发送验证码失败');
  }

  return response.json();
}

// 登录
export async function login(phone: string, code: string): Promise<ApiResponse<LoginResponse>> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phone, code }),
  });

  if (!response.ok) {
    throw new Error('登录失败');
  }

  return response.json();
}

// 获取用户信息
export async function getUserInfo(token: string): Promise<ApiResponse<UserInfoResponse>> {
  const response = await fetch(`${API_BASE_URL}/auth/user_info`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('获取用户信息失败');
  }

  return response.json();
}

// 提交任务
export async function submitTask(token: string, topic: string, description?: string): Promise<ApiResponse<TaskSubmitResponse>> {
  const response = await fetch(`${API_BASE_URL}/api/task/submit`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      topic,
      description
    }),
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || '提交任务失败');
  }

  return response.json();
}

// 使用兑换码
export async function redeemCode(token: string, code: string): Promise<ApiResponse<RedemptionResponse>> {
  const response = await fetch(`${API_BASE_URL}/redemption/redeem`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code }),
  });

  if (!response.ok) {
    try {
      const errorData = await response.json();
      // 优先使用后端返回的具体错误信息
      throw new Error(errorData.message || '兑换失败');
    } catch (parseError) {
      // 如果无法解析错误响应，根据状态码给出提示
      if (response.status === 400) {
        throw new Error('兑换码无效或已被使用');
      } else if (response.status === 404) {
        throw new Error('用户不存在');
      } else {
        throw new Error('兑换失败，请稍后重试');
      }
    }
  }

  return response.json();
}

// 获取兑换历史
export async function getRedemptionHistory(token: string): Promise<ApiResponse<RedemptionHistory>> {
  const response = await fetch(`${API_BASE_URL}/redemption/history`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('获取兑换历史失败');
  }

  return response.json();
}

// 获取用户任务列表
export async function getUserTasks(
  token: string, 
  status?: string, 
  limit: number = 100
): Promise<UserTasksResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  params.append('limit', limit.toString());

  const response = await fetch(`${API_BASE_URL}/api/user/tasks?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('获取任务列表失败');
  }

  return response.json();
}
