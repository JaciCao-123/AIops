import axios from 'axios';
import { message } from 'antd';
import type { 
  Log, LogStats, AgentTask, DiagnoseRequest, DiagnoseResponse, ApiResponse, 
  LoginParams, LoginResult, UserInfo, RegisterParams,
  Alert, ClusteredAlerts, AlertStats, AlertIngestResponse,
  TraceSearchResult, TraceDetail, ServiceDependency, TraceAnalysis,
  RCAReport, MetricsData, SystemHealth, ServiceInfo
} from '../types';

const api = axios.create({
  baseURL: '/aiops/api',
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/aiops/login';
    } else if (error.response?.status === 403) {
      message.error('无权限访问');
    } else if (error.response?.data?.message) {
      message.error(error.response.data.message);
    }
    return Promise.reject(error);
  }
);

export const userApi = {
  login: async (data: LoginParams): Promise<LoginResult> => {
    const formData = new FormData();
    formData.append('username', data.username);
    formData.append('password', data.password);
    const response = await api.post<ApiResponse<LoginResult>>('/auth/login', formData);
    return response.data.data;
  },

  register: async (data: RegisterParams): Promise<UserInfo> => {
    const response = await api.post<ApiResponse<UserInfo>>('/auth/register', data);
    return response.data.data;
  },

  getUserInfo: async (): Promise<UserInfo> => {
    const response = await api.get<ApiResponse<UserInfo>>('/auth/me');
    return response.data.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  getUsers: async (): Promise<UserInfo[]> => {
    const response = await api.get<ApiResponse<UserInfo[]>>('/auth/users');
    return response.data.data;
  },
};

export const logsApi = {
  getLogs: async (params?: { level?: string; is_anomaly?: boolean; limit?: number; offset?: number }): Promise<Log[]> => {
    const response = await api.get('/logs', { params });
    return response.data;
  },

  uploadFile: async (file: File): Promise<{ message: string; filename: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/logs/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  submitFeedback: async (logId: number, feedbackType: boolean): Promise<{ message: string; log_id: number }> => {
    const response = await api.post(`/logs/${logId}/feedback`, { feedback_type: feedbackType });
    return response.data;
  },

  getStats: async (): Promise<LogStats> => {
    const response = await api.get('/logs/stats');
    return response.data;
  },

  ingestLog: async (log: { level: string; content: string; source?: string }): Promise<Log> => {
    const response = await api.post('/logs/ingest', log);
    return response.data;
  },
};

export const agentApi = {
  diagnose: async (request: DiagnoseRequest): Promise<DiagnoseResponse> => {
    const response = await api.post('/agent/diagnose', request);
    return response.data;
  },

  getTaskStatus: async (taskId: string): Promise<AgentTask> => {
    const response = await api.get(`/agent/status/${taskId}`);
    return response.data;
  },

  getHistory: async (limit: number = 10): Promise<{ tasks: Array<{ task_id: string; user_input: string; status: string; created_at: string }> }> => {
    const response = await api.get('/agent/history', { params: { limit } });
    return response.data;
  },
};

export const knowledgeApi = {
  queryKG: async (service?: string, query?: string): Promise<unknown> => {
    const response = await api.get('/knowledge/query', { params: { service, query } });
    return response.data;
  },

  queryRAG: async (query: string, topK: number = 5): Promise<unknown> => {
    const response = await api.post('/knowledge/rag/query', { query, top_k: topK });
    return response.data;
  },

  getTopology: async (service?: string, depth: number = 2): Promise<unknown> => {
    const response = await api.get('/knowledge/topology', { params: { service, depth } });
    return response.data;
  },
};

export interface ChatSession {
  session_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: Array<{ role: string; content: string }>;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  message_count: number;
}

export interface StreamCallbacks {
  onSession?: (sessionId: string) => void;
  onContent?: (content: string) => void;
  onDone?: (sessionId: string, messageCount: number) => void;
  onError?: (error: string) => void;
}

const API_BASE_URL = '';

export const aiChatApi = {
  createSession: async (title?: string): Promise<ChatSession> => {
    const response = await api.post('/ai-chat/sessions', { title });
    return response.data;
  },

  getSessions: async (): Promise<ChatSession[]> => {
    const response = await api.get('/ai-chat/sessions');
    return response.data;
  },

  getSession: async (sessionId: string): Promise<ChatSessionDetail> => {
    const response = await api.get(`/ai-chat/sessions/${sessionId}`);
    return response.data;
  },

  deleteSession: async (sessionId: string): Promise<{ message: string }> => {
    const response = await api.delete(`/ai-chat/sessions/${sessionId}`);
    return response.data;
  },

  updateSessionTitle: async (sessionId: string, title: string): Promise<{ message: string }> => {
    const response = await api.put(`/ai-chat/sessions/${sessionId}/title`, { title });
    return response.data;
  },

  clearSessionMessages: async (sessionId: string): Promise<{ message: string }> => {
    const response = await api.delete(`/ai-chat/sessions/${sessionId}/messages`);
    return response.data;
  },

  chat: async (sessionId: string | null, message: string): Promise<ChatResponse> => {
    const response = await api.post('/ai-chat/chat', { 
      session_id: sessionId, 
      message 
    });
    return response.data;
  },

  chatStream: async (
    sessionId: string | null,
    message: string,
    callbacks: StreamCallbacks
  ): Promise<void> => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/aiops/api/ai-chat/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        session_id: sessionId,
        message: message,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      callbacks.onError?.(error);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError?.('无法读取响应流');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'session':
                  callbacks.onSession?.(data.session_id);
                  break;
                case 'content':
                  callbacks.onContent?.(data.content);
                  break;
                case 'done':
                  callbacks.onDone?.(data.session_id, data.message_count);
                  break;
                case 'error':
                  callbacks.onError?.(data.error);
                  break;
              }
            } catch (e) {
              console.error('解析 SSE 数据失败:', e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  legacyChat: async (messages: Array<{ role: string; content: string }>): Promise<{ response: string }> => {
    const response = await api.post('/ai-chat/chat/legacy', { messages });
    return response.data;
  },

  clearHistory: async (): Promise<{ message: string }> => {
    const response = await api.delete('/ai-chat/history');
    return response.data;
  },

  getStats: async (): Promise<{
    total_sessions: number;
    total_messages: number;
    max_sessions: number;
    max_messages_per_session: number;
  }> => {
    const response = await api.get('/ai-chat/stats');
    return response.data;
  },
};

export const alertsApi = {
  getAlerts: async (params?: { status?: string; severity?: string; limit?: number }): Promise<Alert[]> => {
    const response = await api.get('/alerts', { params });
    return response.data;
  },

  getClusteredAlerts: async (lookback: string = '1h'): Promise<ClusteredAlerts> => {
    const response = await api.get('/alerts/clustered', { params: { lookback } });
    return response.data;
  },

  ingestAlert: async (alert: { level: string; message: string; service?: string; labels?: Record<string, string> }): Promise<AlertIngestResponse> => {
    const response = await api.post('/alerts/ingest', alert);
    return response.data;
  },

  getAlertStats: async (lookback: string = '24h'): Promise<AlertStats> => {
    const response = await api.get('/alerts/stats', { params: { lookback } });
    return response.data;
  },
};

export const traceApi = {
  searchTraces: async (params: { service_name?: string; error_only?: boolean; slow_only?: boolean; lookback?: string; limit?: number }): Promise<TraceSearchResult> => {
    const response = await api.get('/traces/search', { params });
    return response.data;
  },

  getTraceById: async (traceId: string): Promise<TraceDetail> => {
    const response = await api.get(`/traces/${traceId}`);
    return response.data;
  },

  getServiceDependency: async (lookback: string = '24h'): Promise<ServiceDependency> => {
    const response = await api.get('/traces/dependency', { params: { lookback } });
    return response.data;
  },

  analyzeTrace: async (params: { trace_id?: string; service_name?: string; error_only?: boolean; slow_only?: boolean; lookback?: string }): Promise<TraceAnalysis> => {
    const response = await api.post('/traces/analyze', params);
    return response.data;
  },
};

export const rcaApi = {
  analyze: async (params: { service_name?: string; time_window_minutes?: number; include_logs?: boolean; include_traces?: boolean }): Promise<RCAReport> => {
    const response = await api.post('/rca/analyze', params);
    return response.data;
  },

  getReport: async (reportId: string): Promise<RCAReport> => {
    const response = await api.get(`/rca/report/${reportId}`);
    return response.data;
  },

  getHistory: async (limit: number = 10): Promise<{ reports: RCAReport[] }> => {
    const response = await api.get('/rca/history', { params: { limit } });
    return response.data;
  },
};

export const observabilityApi = {
  getMetrics: async (query: string, lookback: string = '1h'): Promise<MetricsData> => {
    const response = await api.get('/observability/metrics', { params: { query, lookback } });
    return response.data;
  },

  getSystemHealth: async (): Promise<SystemHealth> => {
    const response = await api.get('/observability/health');
    return response.data;
  },

  getServiceList: async (): Promise<{ services: ServiceInfo[] }> => {
    const response = await api.get('/observability/services');
    return response.data;
  },
};

export const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/aiops/api/logs/ws/simulate`;
