import axios from 'axios';

// API配置 - 开发环境使用代理，生产环境使用实际地址
const API_BASE = import.meta.env.PROD 
  ? 'http://170.106.194.111:8000' 
  : '/api';

// API响应类型
export interface Agent {
  agent_id: string;
  name: string;
  config: {
    name: string;
    identity: string;
    personality: string;
    goals: string[];
  };
  current_location: string;
  last_action: string;
  survival_turns: number;
  is_alive: boolean;
  memory_count: number;
  memory_stats?: {
    total: number;
    avg_retention: number;
    total_forgotten: number;
    total_added: number;
    by_type: Record<string, number>;
    retention_distribution: { high: number; medium: number; low: number };
  };
}

export interface Location {
  id: string;
  name: string;
  description: string;
}

export interface World {
  id: string;
  name: string;
  description: string;
  template?: string;
  agents?: Agent[];
  locations?: Location[];
  graph_stats?: {
    node_count: number;
    edge_count: number;
    node_types: Record<string, number>;
    avg_degree: number;
  };
}

export interface Event {
  id: number;
  turn: number;
  actor: string;
  action: string;
  target?: string;
  location?: string;
  action_type: 'normal' | 'interaction' | 'story_moment';
  score?: number;
  timestamp?: string;
  world_mood?: string;
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
    const response = await axios.get(`${API_BASE}/info`);
    return response.data;
  },

  // 创建世界
  async createWorld(name: string, template: string) {
    const response = await axios.post(`${API_BASE}/worlds`, {
      name,
      template
    });
    return response.data;
  },

  // 获取世界列表
  async getWorlds(): Promise<World[]> {
    const response = await axios.get(`${API_BASE}/worlds`);
    return response.data.worlds || [];
  },

  // 获取小说列表
  async getBooks(): Promise<any[]> {
    const response = await axios.get(`${API_BASE}/books`);
    return response.data.books || [];
  },

  // 获取模板列表
  async getTemplates(): Promise<Template[]> {
    const response = await axios.get(`${API_BASE}/templates`);
    return response.data.templates || [];
  },

  // 获取世界详情
  async getWorld(worldId: string): Promise<World> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}`);
    return response.data;
  },

  // 获取事件列表
  async getEvents(worldId: string, limit = 100): Promise<Event[]> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/events`, {
      params: { limit }
    });
    return response.data.events || [];
  },

  // 获取指标
  async getMetrics(worldId: string) {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/metrics`);
    return response.data;
  },

  // 开始模拟
  async startSimulation(worldId: string) {
    const response = await axios.post(`${API_BASE}/simulate/start`, {
      world_id: worldId
    });
    return response.data;
  },

  // 停止模拟
  async stopSimulation(worldId: string) {
    const response = await axios.post(`${API_BASE}/simulate/stop`, {
      world_id: worldId
    });
    return response.data;
  },

  // 获取模拟状态
  async getSimulationStatus(worldId: string): Promise<SimulationStatus> {
    const response = await axios.get(`${API_BASE}/simulate/status`, {
      params: { world_id: worldId }
    });
    return response.data;
  },
};
