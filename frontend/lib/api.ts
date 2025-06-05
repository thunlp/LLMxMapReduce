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

// 新增：任务提交响应接口
interface TaskSubmitResponse {
  task_id: string;
  output_file: string;
  original_topic: string;
  unique_survey_title: string;
}

const API_BASE_URL = 'http://localhost:5000/';

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
export async function getUserInfo(token: string): Promise<ApiResponse> {
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
  const response = await fetch(`${API_BASE_URL}/task/submit`, {
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
