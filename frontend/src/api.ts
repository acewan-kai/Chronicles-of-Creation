import axios from 'axios';

// API配置 - 开发环境使用代理，生产环境使用实际地址
const API_BASE = import.meta.env.PROD
  ? 'http://170.106.194.111:8000'
  : '/api';

// WebSocket URL - 开发用Vite代理，生产直连
const WS_BASE = import.meta.env.PROD
  ? 'ws://170.106.194.111:8000'
  : `ws://${window.location.host}`;

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
  planner?: {
    active_plans: number;
    completed_plans: number;
    failed_plans: number;
    current_goal: string | null;
    current_plan: {
      plan_id: string;
      title: string;
      steps: { id: string; description: string; target: string | null }[];
      current_step: number;
      progress_pct: number;
      status: string;
      created_turn: number;
    } | null;
  };
  reflector?: {
    reflection_count: number;
    last_reflection_turn: number;
    recent_insights: string[];
    latest_summary: string | null;
  };
}

export interface Location {
  id: string;
  name: string;
  description: string;
  lat?: number;
  lng?: number;
}

export interface NpcPosition {
  agent_id: string;
  agent_name: string;
  identity?: string;
  location_id: string;
  location_name: string;
  lat: number;
  lng: number;
  is_alive: boolean;
}

export interface Snapshot {
  id: string;
  world_id: string;
  turn: number;
  day: number;
  time_of_day: string;
  world_mood: string;
  event_summary: string;
  npc_positions: NpcPosition[];
  created_at: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;  // "knows", "friend", "enemy"
  weight: number;
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
  graph_edges?: GraphEdge[];
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

// WebSocket 消息类型
export type WsEventType = 'NEW_EVENT' | 'TURN_COMPLETE' | 'STATUS_CHANGE' | 'DISTURBANCE' | 'STAGNATION_ALERT' | 'NPC_POSITION';

export interface WsMessage {
  type: WsEventType;
  data: any;
}

export type WsHandler = (msg: WsMessage) => void;

// WebSocket 连接工厂
export function connectWebSocket(worldId: string, onMessage: WsHandler): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/${worldId}`);

  ws.onopen = () => {
    console.log(`[WS] 已连接到世界 ${worldId}`);
  };

  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data);
      onMessage(msg);
    } catch {
      console.warn('[WS] 无法解析消息:', event.data);
    }
  };

  ws.onerror = (err) => {
    console.error('[WS] 连接错误:', err);
  };

  ws.onclose = (e) => {
    console.log(`[WS] 连接关闭 (code=${e.code})`);
  };

  return ws;
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

  // F02: 获取NPC位置（含坐标）
  async getNpcLocations(worldId: string): Promise<NpcPosition[]> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/npc-locations`);
    return response.data.npcs || [];
  },

  // F03: 保存快照
  async saveSnapshot(worldId: string): Promise<Snapshot> {
    const response = await axios.post(`${API_BASE}/worlds/${worldId}/snapshots`);
    return response.data.snapshot;
  },

  // F03: 获取快照列表
  async getSnapshots(worldId: string, limit = 20): Promise<Snapshot[]> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/snapshots`, {
      params: { limit }
    });
    return response.data.snapshots || [];
  },

  // F03: 获取单个快照
  async getSnapshot(worldId: string, snapshotId: string): Promise<Snapshot> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/snapshots/${snapshotId}`);
    return response.data.snapshot;
  },

  // G04: 获取风格预设列表
  async getStylePresets(): Promise<any[]> {
    const response = await axios.get(`${API_BASE}/style/presets`);
    return response.data.presets || [];
  },

  // G04: 生成风格化章节
  async generateStyledChapter(worldId: string, styleName: string, intensity: number): Promise<any> {
    const response = await axios.post(`${API_BASE}/style/generate`, {
      world_id: worldId,
      style_name: styleName,
      intensity,
    });
    return response.data;
  },

  // C02: 获取一致性守护状态
  async getConsistencyGuardian(worldId: string): Promise<any> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/consistency/guardian`);
    return response.data;
  },

  // F04: 降临到NPC
  async descendToAgent(worldId: string, agentId: string): Promise<any> {
    const response = await axios.post(`${API_BASE}/worlds/${worldId}/agents/${agentId}/descend`);
    return response.data;
  },

  // F04: 退出降临
  async exitDescend(worldId: string, agentId: string): Promise<any> {
    const response = await axios.delete(`${API_BASE}/worlds/${worldId}/agents/${agentId}/descend`);
    return response.data;
  },

  // F04: 降临行动
  async descendAct(worldId: string, agentId: string, actionType: string, content: string, target?: string): Promise<any> {
    const response = await axios.post(`${API_BASE}/worlds/${worldId}/agents/${agentId}/descend/act`, {
      action_type: actionType,
      content,
      target,
    });
    return response.data;
  },

  // F04: 获取降临状态
  async getDescendStatus(worldId: string, agentId: string): Promise<any> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/agents/${agentId}/descend/status`);
    return response.data;
  },

  // F04: 生成降临选项
  async getDescendOptions(worldId: string, agentId: string, situation?: string): Promise<any> {
    const response = await axios.post(`${API_BASE}/worlds/${worldId}/agents/${agentId}/descend/options`, {
      situation: situation || '',
    });
    return response.data;
  },

  // F04: 获取降临日志
  async getDescendLogs(worldId: string, limit?: number): Promise<any> {
    const response = await axios.get(`${API_BASE}/worlds/${worldId}/descend/logs`, {
      params: { limit: limit || 10 }
    });
    return response.data;
  },
};
