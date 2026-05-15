import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, LayersControl, useMap } from 'react-leaflet';
import L from 'leaflet';
import { api, NpcPosition, Event, Location } from '../api';
import 'leaflet/dist/leaflet.css';

// 修复 Leaflet 默认图标在 webpack/vite 下的问题
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconShadowUrl from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl,
  shadowUrl: iconShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

// NPC 图标工厂（按身份/状态着色）
const npcIcon = (isAlive: boolean, isFocused: boolean) => {
  const color = isAlive ? (isFocused ? '#e74c3c' : '#3498db') : '#95a5a6';
  return L.divIcon({
    className: 'npc-map-icon',
    html: `<div style="
      width: 14px; height: 14px;
      background: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      ${isFocused ? 'transform: scale(1.4); transition: transform 0.2s;' : ''}
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  });
};

// 地点图标
const locationIcon = L.divIcon({
  className: 'location-map-icon',
  html: '<div style="width: 20px; height: 20px; background: #2ecc71; border: 2px solid white; border-radius: 4px; transform: rotate(45deg); box-shadow: 0 1px 3px rgba(0,0,0,0.3);"></div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

// 热力图层组件（基于事件密度）
const EventHeatLayer: React.FC<{ locations: Location[]; events: Event[] }> = ({ locations, events }) => {
  const map = useMap();

  const heatData = useMemo(() => {
    return locations.map(loc => {
      const count = events.filter(e => e.location === loc.name).length;
      return { ...loc, density: count };
    });
  }, [locations, events]);

  useEffect(() => {
    if (heatData.length === 0) return;
    const maxDensity = Math.max(...heatData.map(d => d.density), 1);
    const circles = heatData.map(d => {
      const radius = Math.max(5, (d.density / maxDensity) * 30);
      const opacity = Math.min(0.6, d.density / Math.max(maxDensity, 1));
      const color = d.density > maxDensity * 0.7 ? '#e74c3c'
        : d.density > maxDensity * 0.3 ? '#f39c12'
        : '#2ecc71';
      return L.circleMarker([d.lat ?? 0, d.lng ?? 0], {
        radius,
        fillColor: color,
        color: '#fff',
        weight: 1,
        opacity: 0.8,
        fillOpacity: opacity,
      }).addTo(map);
    });
    return () => circles.forEach(c => c.remove());
  }, [heatData, map]);

  return null;
};

// 自动适应地图范围
const FitBounds: React.FC<{ markers: { lat: number; lng: number }[] }> = ({ markers }) => {
  const map = useMap();
  useEffect(() => {
    if (markers.length === 0) return;
    const bounds = L.latLngBounds(markers.map(m => [m.lat, m.lng]));
    map.fitBounds(bounds, { padding: [50, 50] });
  }, [markers, map]);
  return null;
};

interface WorldMapProps {
  worldId: string;
  locations: Location[];
  events: Event[];
  isSimulating: boolean;
  npcPositions?: NpcPosition[];
}

type MapLayer = 'geography' | 'faction' | 'heat';

export const WorldMap: React.FC<WorldMapProps> = ({ worldId, locations, events, isSimulating, npcPositions }) => {
  const [npcs, setNpcs] = useState<NpcPosition[]>([]);
  const [activeLayer, setActiveLayer] = useState<MapLayer>('geography');
  const [selectedNpc, setSelectedNpc] = useState<NpcPosition | null>(null);

  // 加载NPC位置（初始加载用HTTP，后续WebSocket实时更新）
  const loadNpcs = useCallback(async () => {
    try {
      const data = await api.getNpcLocations(worldId);
      setNpcs(data);
    } catch { /* ignore */ }
  }, [worldId]);

  useEffect(() => { loadNpcs(); }, [loadNpcs]);

  // WebSocket实时更新优先；无WebSocket数据时轮询兜底
  useEffect(() => {
    if (npcPositions && npcPositions.length > 0) {
      setNpcs(npcPositions);
      return;
    }
    if (!isSimulating) return;
    const interval = setInterval(loadNpcs, 5000);
    return () => clearInterval(interval);
  }, [isSimulating, npcPositions, loadNpcs]);

  // 合并所有标记点（地点 + NPC）
  const allMarkers = useMemo(() => {
    const markers: { lat: number; lng: number }[] = [];
    locations.forEach(l => {
      if (l.lat && l.lng) markers.push({ lat: l.lat, lng: l.lng });
    });
    npcs.forEach(n => {
      if (n.lat && n.lng) markers.push({ lat: n.lat, lng: n.lng });
    });
    return markers;
  }, [locations, npcs]);

  return (
    <div className="world-map-container">
      {/* 图层切换 */}
      <div className="map-layer-controls">
        <button
          className={`btn btn-xs ${activeLayer === 'geography' ? 'btn-active' : ''}`}
          onClick={() => setActiveLayer('geography')}
        >
          🗺 地理
        </button>
        <button
          className={`btn btn-xs ${activeLayer === 'faction' ? 'btn-active' : ''}`}
          onClick={() => setActiveLayer('faction')}
        >
          ⚔ 势力
        </button>
        <button
          className={`btn btn-xs ${activeLayer === 'heat' ? 'btn-active' : ''}`}
          onClick={() => setActiveLayer('heat')}
        >
          🔥 热力
        </button>
        <span className="map-npc-count">NPC: {npcs.length}</span>
      </div>

      {/* Leaflet 地图 */}
      <MapContainer
        center={[34.05, 118.24]}
        zoom={8}
        className="leaflet-map"
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* 地点标记 */}
        <LayersControl position="topright">
          <LayersControl.Overlay checked name="地点">
            <div />
          </LayersControl.Overlay>
          <LayersControl.Overlay checked name="NPC位置">
            <div />
          </LayersControl.Overlay>
        </LayersControl>

        {locations.filter(l => l.lat && l.lng).map(loc => (
          <Marker
            key={loc.id}
            position={[loc.lat!, loc.lng!]}
            icon={locationIcon}
          >
            <Popup>
              <div className="map-popup">
                <strong>{loc.name}</strong>
                <p>{loc.description}</p>
              </div>
            </Popup>
          </Marker>
        ))}

        {npcs.filter(n => n.lat && n.lng).map(npc => (
          <Marker
            key={npc.agent_id}
            position={[npc.lat, npc.lng]}
            icon={npcIcon(npc.is_alive, selectedNpc?.agent_id === npc.agent_id)}
            eventHandlers={{
              click: () => setSelectedNpc(npc),
            }}
          >
            <Popup>
              <div className="map-popup">
                <strong>{npc.agent_name}</strong>
                <p className="npc-identity">{npc.identity || ''}</p>
                <p className="npc-location">📍 {npc.location_name}</p>
                <p className={`npc-status ${npc.is_alive ? 'alive' : 'dead'}`}>
                  {npc.is_alive ? '存活' : '已死亡'}
                </p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* 热力图层 */}
        {activeLayer === 'heat' && (
          <EventHeatLayer locations={locations} events={events} />
        )}

        <FitBounds markers={allMarkers} />
      </MapContainer>

      {/* NPC详情侧栏 */}
      {selectedNpc && (
        <div className="npc-detail-sidebar">
          <div className="npc-detail-header">
            <strong>{selectedNpc.agent_name}</strong>
            <button className="btn btn-xs" onClick={() => setSelectedNpc(null)}>✕</button>
          </div>
          <p className="npc-detail-identity">{selectedNpc.identity || '身份未知'}</p>
          <p>📍 {selectedNpc.location_name}</p>
          <p className={`npc-status ${selectedNpc.is_alive ? 'alive' : 'dead'}`}>
            {selectedNpc.is_alive ? '存活' : '已死亡'}
          </p>
        </div>
      )}
    </div>
  );
};
