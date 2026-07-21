import { useState, useEffect, useRef, useCallback } from 'react';
import { fetchWithStage, createChatHistory, updateChatHistory } from '../services/api';
import type { Marker } from '../components/PageMarker';
import type { Message, CropBBox, User } from '../types';

function generateId() {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

export interface UseChatParams {
  user: User;
  currentPage: number;
  textbookId: string;
  teachingMode: string;
  socraticSubmode: string;
  markersState: {
    markers: Marker[];
    activeThreadId: string | null;
    addMarker: (marker: Marker) => void;
    updateMarker: (id: string, updater: (m: Marker) => Marker) => void;
    getMarkerById: (id: string | null) => Marker | undefined;
    setActiveThreadId: (id: string | null) => void;
    setActiveMarker: (marker: Marker | null | ((prev: Marker | null) => Marker | null)) => void;
    refreshMarkers: () => Promise<void>;
  };
}

export function useChat({
  user, currentPage, textbookId, teachingMode, socraticSubmode,
  markersState,
}: UseChatParams) {
  const {
    markers,
    activeThreadId,
    addMarker,
    updateMarker,
    getMarkerById,
    setActiveThreadId,
    setActiveMarker,
    refreshMarkers,
  } = markersState;

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [pendingCaptureRatio, setPendingCaptureRatio] = useState<{ rx: number; ry: number; bbox?: CropBBox } | null>(null);
  const [thinkingStage, setThinkingStage] = useState<string>('');
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [thinkingExpanded, setThinkingExpanded] = useState<boolean>(true);
  const [pendingPageNumber, setPendingPageNumber] = useState<number | null>(null);

  const [hasUnread, setHasUnread] = useState(false);
  const lastMsgCount = useRef(0);
  const wasLoading = useRef(false);

  useEffect(() => {
    // 刚收到 assistant 回复时（isLoading true→false），标记未读
    if (wasLoading.current && !isLoading) {
      const last = messages[messages.length - 1];
      if (last?.role === 'assistant' && messages.length > lastMsgCount.current) {
        setHasUnread(true);
      }
    }
    lastMsgCount.current = messages.length;
    wasLoading.current = isLoading;
  }, [messages, isLoading]);

  // 从 marker 加载对话历史到聊天面板
  const loadThreadToChat = (marker: Marker) => {
    const msgs: Message[] = [];
    const threadImage = marker.marker_type === 'screenshot' ? marker.thumbnail || undefined : undefined;
    msgs.push({ id: generateId(), role: 'user', content: marker.question, image: threadImage });
    if (marker.answer) {
      msgs.push({ id: generateId(), role: 'assistant', content: marker.answer });
    }
    (marker.follow_ups || []).forEach((fu: any) => {
      msgs.push({ id: generateId(), role: 'user', content: fu.question, image: fu.image || undefined });
      if (fu.answer) {
        msgs.push({ id: generateId(), role: 'assistant', content: fu.answer });
      }
    });
    setMessages(msgs);
  };

  const clearMessages = useCallback(() => {
    setMessages([]);
    setActiveThreadId(null);
    setActiveMarker(null);
  }, [setActiveThreadId, setActiveMarker]);

  const clearPendingImage = useCallback(() => {
    setPendingImage(null);
    setPendingPageNumber(null);
    setPendingCaptureRatio(null);
  }, []);

  const dismissError = useCallback(() => setError(null), []);

  const handleCapture = (imageData: string, pageRatioX: number, pageRatioY: number, cropBBox: CropBBox) => {
    setPendingImage(imageData);
    setPendingPageNumber(currentPage);
    setPendingCaptureRatio({ rx: pageRatioX, ry: pageRatioY, bbox: cropBBox });
  };

  const handleSendMessage = async (content: string, image?: string) => {
    const userMessage: Message = { id: generateId(), role: 'user', content, image };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);
    setThinkingStage('思考中...');

    const uid = user.userId || user.deviceId;
    const pageNum = pendingPageNumber || currentPage;
    const isNewThread = activeThreadId === null;
    const activeThread = activeThreadId ? getMarkerById(activeThreadId) : undefined;
    const inheritedThreadImage = !image && !isNewThread && activeThread?.thumbnail
      ? activeThread.thumbnail || undefined
      : undefined;
    const requestImage = image || inheritedThreadImage;
    const requestCropBBox = image
      ? pendingCaptureRatio?.bbox || null
      : activeThread?.crop_bbox && typeof activeThread.crop_bbox !== 'string'
        ? activeThread.crop_bbox
        : null;
    const requestScreenshotContextId = !isNewThread && activeThread?.screenshot_context_id
      ? activeThread.screenshot_context_id
      : null;
    let chatId: string | undefined;
    let collectedAnswer = '';

    // 新线程：创建 marker
    if (isNewThread) {
      const markerType = image ? 'screenshot' : 'text';
      let markerYRatio: number | undefined;
      if (image && pendingCaptureRatio) {
        markerYRatio = Math.max(5, Math.min(95, pendingCaptureRatio.ry * 100));
      } else if (image) {
        markerYRatio = 50;
      } else {
        const existingText = markers.filter(m => m.page_number === pageNum && m.marker_type === 'text');
        markerYRatio = Math.min(10 + existingText.length * 10, 90);
      }
      try {
        const d = await createChatHistory({
          user_id: uid,
          question: content,
          answer: null,
          page_number: pageNum,
          marker_y_ratio: markerYRatio,
          marker_type: markerType,
          thumbnail: image || undefined,
          crop_bbox: pendingCaptureRatio?.bbox ? JSON.stringify(pendingCaptureRatio.bbox) : undefined,
        });
        if (d.id) {
          chatId = d.id;
          setActiveThreadId(d.id);
          addMarker({
            id: d.id, page_number: pageNum, marker_y_ratio: markerYRatio ?? 50,
            marker_type: markerType, thumbnail: image || null,
            crop_bbox: pendingCaptureRatio?.bbox || null, question: content,
            answer: null, thinking: null, follow_ups: [],
          });
        }
      } catch {}
    } else {
      chatId = activeThreadId;
    }

    try {
      const assistantMessageId = generateId();
      setMessages((prev) => [...prev, { id: assistantMessageId, role: 'assistant', content: '', sources: [], knowledge_points: [] }]);
      // 构建对话历史（追问时传给 AI 作为上下文）
      const historyPairs: Array<{user: string, assistant: string}> = [];
      for (let i = 0; i < messages.length; i++) {
        if (messages[i].role === 'user') {
          const next = messages[i + 1];
          historyPairs.push({ user: messages[i].content, assistant: (next && next.role === 'assistant') ? next.content : '' });
        }
      }
      const answer = await fetchWithStage(
        uid, content,
        (_stage, text) => { setThinkingStage(text); },
        requestImage || undefined, teachingMode,
        undefined,
        textbookId || undefined,
        historyPairs.length > 0 ? historyPairs : undefined,
        (thinking) => { setIsThinking(thinking); },
        (text) => { collectedAnswer += text; setMessages((prev) => prev.map((msg) => msg.id === assistantMessageId ? { ...msg, content: collectedAnswer } : msg)); },
        user.token || undefined,
        pendingPageNumber || (activeThreadId ? getMarkerById(activeThreadId)?.page_number : undefined) || currentPage,
        teachingMode === 'socratic' ? socraticSubmode : undefined,
        isNewThread ? chatId : undefined,
        chatId || activeThreadId || undefined,
        requestCropBBox,
        requestScreenshotContextId,
      );
      setMessages((prev) => prev.map((msg) => msg.id === assistantMessageId ? { ...msg, content: answer.answer, sources: answer.sources || [] } : msg));

      // 落库
      if (chatId) {
        const finalAnswer = answer.answer || collectedAnswer;
        const finalThinking = "";

        if (isNewThread) {
          updateMarker(chatId, m => ({ ...m, answer: finalAnswer, thinking: finalThinking, screenshot_context_id: answer.screenshot_context_id || m.screenshot_context_id || null }));
          setActiveMarker(prev => prev && prev.id === chatId ? { ...prev, answer: finalAnswer, thinking: finalThinking, screenshot_context_id: answer.screenshot_context_id || prev.screenshot_context_id || null } : prev);
          await updateChatHistory(chatId, { answer: finalAnswer, thinking: finalThinking, screenshot_context_id: answer.screenshot_context_id || undefined });
        } else {
          // 直接从 markers 计算 follow_ups（不用 setState 回调，避免异步导致空数组）
          const target = getMarkerById(chatId);
          if (target) {
            const nextCropBBox = image && pendingCaptureRatio?.bbox
              ? pendingCaptureRatio.bbox
              : target.crop_bbox || null;
            const nextThumbnail = image || target.thumbnail || null;
            const nextScreenshotContextId = answer.screenshot_context_id || target.screenshot_context_id || null;
            const followUp = {
              question: content,
              answer: finalAnswer,
              thinking: finalThinking,
              image: image || null,
              crop_bbox: image && pendingCaptureRatio?.bbox ? pendingCaptureRatio.bbox : null,
              screenshot_context_id: answer.screenshot_context_id || null,
            };
            const updatedFollowUps = [...(target.follow_ups || []), followUp];
            updateMarker(chatId, m => ({ ...m, follow_ups: updatedFollowUps, thumbnail: nextThumbnail, crop_bbox: nextCropBBox, screenshot_context_id: nextScreenshotContextId }));
            setActiveMarker(prev => prev && prev.id === chatId ? { ...prev, follow_ups: updatedFollowUps, thumbnail: nextThumbnail, crop_bbox: nextCropBBox, screenshot_context_id: nextScreenshotContextId } : prev);
            await updateChatHistory(chatId, {
              follow_ups: JSON.stringify(updatedFollowUps),
              screenshot_context_id: nextScreenshotContextId || undefined,
              thumbnail: nextThumbnail || undefined,
              crop_bbox: nextCropBBox ? JSON.stringify(nextCropBBox) : undefined,
            });
          }
        }
        refreshMarkers();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '提问失败');
      setMessages((prev) => prev.filter((msg) => msg.role !== 'assistant' || msg.content !== ''));
    } finally {
      setIsLoading(false);
      setThinkingStage('');
      setPendingPageNumber(null);
      setPendingCaptureRatio(null);
      setTimeout(() => { setIsThinking(false); }, 200);
    }
  };

  return {
    messages, isLoading, error, dismissError,
    pendingImage, pendingCaptureRatio, pendingPageNumber,
    thinkingStage, isThinking, thinkingExpanded, setThinkingExpanded,
    hasUnread, setHasUnread,
    handleSendMessage, loadThreadToChat, clearMessages, clearPendingImage,
    handleCapture,
  };
}
