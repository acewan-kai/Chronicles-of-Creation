import axios from 'axios';

// API配置 - 开发环境使用代理，生产环境使用实际地址
const API_BASE = import.meta.env.PROD 
  ? 'http://170.106.194.111:8000' 
  : '/api';

// API响应类型
export interface World {
  id: string;
  name: string;
  description: string;
}

export interface Event {
  id: number;
  turn: number;
  actor: string;
  action: string;
  target?: string;
  location?: string;
  type: 'interaction' | 'movement' | 'story' | 'default';
  highlight?: boolean;
  timestamp?: string;
}

export interface Template {
  id: string;
  name: string;
  description: string;
}

export interface SimulationStatus {
  is_running: boolean;
  turn: number;
  event_count: number;
}

export interface HealthCheck {
  status: string;
  version: string;
}

export const api = {
  // 健康检查
  async healthCheck(): Promise<HealthCheck> {
    const response = await axios.get(`${API_BASE}/health`);
    return response.data;
  },

  // 获取API信息
  async getInfo() {
    const response = await axios.get(`${API_BASE}/api/info`);
    return response.data;
  },

  // 获取世界列表
  async getWorlds(): Promise<World[]> {
    const response = await axios.get(`${API_BASE}/api/worlds`);
    return response.data.worlds || [];
  },

  // 获取小说列表
  async getBooks(): Promise<any[]> {
    const response = await axios.get(`${API_BASE}/api/books`);
    return response.data.books || [];
  },

  // 获取模板列表
  async getTemplates(): Promise<Template[]> {
    const response = await axios.get(`${API_BASE}/api/templates`);
    return response.data.templates || [];
  },

  // 获取世界详情
  async getWorld(worldId: string): Promise<World> {
    const response = await axios.get(`${API_BASE}/api/worlds/${worldId}`);
    return response.data;
  },

  // 获取事件列表
  async getEvents(worldId: string, limit = 100): Promise<Event[]> {
    const response = await axios.get(`${API_BASE}/api/worlds/${worldId}/events`, {
      params: { limit }
    });
    return response.data.events || [];
  },

  // 获取指标
  async getMetrics(worldId: string) {
    const response = await axios.get(`${API_BASE}/api/worlds/${worldId}/metrics`);
    return response.data;
  },

  // 开始模拟
  async startSimulation(worldId: string) {
    const response = await axios.post(`${API_BASE}/api/simulate/start`, {
      world_id: worldId
    });
    return response.data;
  },

  // 停止模拟
  async stopSimulation(worldId: string) {
    const response = await axios.post(`${API_BASE}/api/simulate/stop`, {
      world_id: worldId
    });
    return response.data;
  },

  // 获取模拟状态
  async getSimulationStatus(worldId: string): Promise<SimulationStatus> {
    const response = await axios.get(`${API_BASE}/api/simulate/status`, {
      params: { world_id: worldId }
    });
    return response.data;
  },
};
