import { useState, useCallback, useEffect } from 'react';
import { getChatHistoryByUser, deleteChatHistory } from '../services/api';
import type { Marker } from '../components/PageMarker';
import type { User } from '../types';

export function useMarkers(user: User, currentPage: number) {
  const [markers, setMarkers] = useState<Marker[]>([]);
  const [activeMarker, setActiveMarker] = useState<Marker | null>(null);
  const [showMarkerPopover, setShowMarkerPopover] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);

  const refreshMarkers = useCallback(async () => {
    if (!user.userId && !user.deviceId) return;
    const uid = user.userId || user.deviceId;
    try {
      const data = await getChatHistoryByUser(uid, currentPage, 50);
      if (Array.isArray(data)) setMarkers(data.map((d: any) => {
        let follow_ups = d.follow_ups || [];
        if (typeof follow_ups === 'string') {
          try { follow_ups = JSON.parse(follow_ups); } catch { follow_ups = []; }
        }
        let crop_bbox = d.crop_bbox || null;
        if (typeof crop_bbox === 'string') {
          try { crop_bbox = JSON.parse(crop_bbox); } catch { crop_bbox = null; }
        }
        return {
          ...d,
          crop_bbox,
          thinking: null,
          follow_ups: follow_ups.map((fu: any) => ({ ...fu, thinking: '' })),
        };
      }));
    } catch {}
  }, [user.userId, user.deviceId, currentPage]);

  // 翻页/登录时刷新标记
  useEffect(() => { refreshMarkers(); }, [currentPage, user.userId, refreshMarkers]);

  const handleMarkerClick = useCallback((marker: Marker) => {
    setActiveThreadId(marker.id);
    setActiveMarker(marker);
    // 桌面端 ChatPanel 展示对话，移动端弹 Popover
    if (window.innerWidth < 1024) {
      setShowMarkerPopover(true);
    }
  }, []);

  const handleDeleteMarker = useCallback(async (markerId: string) => {
    try {
      await deleteChatHistory(markerId);
      setMarkers(prev => prev.filter(m => m.id !== markerId));
      setActiveMarker(prev => prev?.id === markerId ? null : prev);
    } catch {}
  }, []);

  const addMarker = useCallback((marker: Marker) => {
    setMarkers(prev => [...prev, marker]);
  }, []);

  const updateMarker = useCallback((id: string, updater: (m: Marker) => Marker) => {
    setMarkers(prev => prev.map(m => m.id === id ? updater(m) : m));
  }, []);

  const getMarkerById = useCallback((id: string | null): Marker | undefined => {
    if (!id) return undefined;
    return markers.find(m => m.id === id);
  }, [markers]);

  return {
    markers,
    activeMarker,
    showMarkerPopover,
    activeThreadId,
    refreshMarkers,
    handleMarkerClick,
    handleDeleteMarker,
    addMarker,
    updateMarker,
    getMarkerById,
    setActiveThreadId,
    setActiveMarker,
    setShowMarkerPopover,
  };
}
