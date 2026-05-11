import axios from 'axios';

const API_BASE = '/api';

export const api = {
  // 获取世界列表
  async getWorlds() {
    const response = await axios.get(`${API_BASE}/worlds`);
    return response.data;
  },

  // 获取世界详情
  async getWorld(worldId: string) {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}`);
    return response.data;
  },

  // 获取事件列表
  async getEvents(worldId: string, limit = 100) {
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
  async getSimulationStatus(worldId: string) {
    const response = await axios.get(`${API_BASE}/simulate/status`, {
      params: { world_id: worldId }
    });
    return response.data;
  },
};
