import { useState, useEffect, useRef, useCallback } from 'react';
import {
  fetchWithStage, createChatHistory, updateChatHistory,
  getChatTreeByHistory, ensureChatTreeByHistory, getChatNodeContext,
  createChatTree, activateChatNode, createVisualizationAnimation,
  getVisualizationAnimation, getVisualization,
  getPracticeDraft, getTurnInterventions,
} from '../services/api';
import type { Marker } from '../components/PageMarker';
import type { AnimationJob, MathVisualizationArtifact, Message, CropBBox, User, PracticeDraft } from '../types';
import type { TextbookId } from '../textbooks';

function generateId() {
  return Math.random().toString(36).substring(2) + Date.now().toString(36);
}

export interface UseChatParams {
  user: User;
  currentPage: number;
  textbookId: TextbookId | '';
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
  autoPreparePractice?: boolean;
}

export function useChat({
  user, currentPage, textbookId, teachingMode, socraticSubmode,
  markersState, autoPreparePractice = true,
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
  const [branchAnchor, setBranchAnchor] = useState<{ nodeId: string; messageId: string; title: string } | null>(null);
  const [treeNodes, setTreeNodes] = useState<Array<{ id: string; parent_node_id: string | null; title: string; archived_at?: string | null }>>([]);
  const [activeTreeNodeId, setActiveTreeNodeId] = useState<string | null>(null);
  const treeStateRef = useRef<Record<string, { treeId: string; nodeId: string; revision: number }>>({});

  const [hasUnread, setHasUnread] = useState(false);
  const lastMsgCount = useRef(0);
  const wasLoading = useRef(false);

  const hydrateVisualizations = useCallback(async (items: MathVisualizationArtifact[] | undefined) => {
    if (!items?.length || !user.token) return items || [];
    return Promise.all(items.map(async (item) => {
      try {
        return await getVisualization(item.id, user.userId || user.deviceId, user.token!);
      } catch {
        return item;
      }
    }));
  }, [user]);

  const updateVisualization = useCallback((visualizationId: string, update: (item: MathVisualizationArtifact) => MathVisualizationArtifact) => {
    setMessages((current) => current.map((message) => ({
      ...message,
      visualizations: message.visualizations?.map((item) => item.id === visualizationId ? update(item) : item),
    })));
  }, []);

  const generateVisualizationAnimation = useCallback(async (visualizationId: string) => {
    if (!user.token) throw new Error('生成动画需要有效登录状态');
    const userId = user.userId || user.deviceId;
    let job = await createVisualizationAnimation(visualizationId, userId, user.token);
    const applyJob = (next: AnimationJob) => updateVisualization(visualizationId, (item) => ({
      ...item,
      animation_status: next.status,
      animation_job_id: next.id,
      animation: next,
    }));
    applyJob(job);
    for (let attempt = 0; attempt < 60 && (job.status === 'queued' || job.status === 'running'); attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      job = await getVisualizationAnimation(job.id, userId, user.token);
      applyJob(job);
    }
    if (job.status === 'queued' || job.status === 'running') {
      throw new Error('动画仍在后台渲染，请稍后重新打开本对话查看');
    }
  }, [updateVisualization, user]);

  const pollPracticeDraft = useCallback((draft: PracticeDraft, messageId: string, attempt = 0) => {
    setMessages((prev) => prev.map((msg) => msg.id === messageId ? { ...msg, practiceDraft: draft } : msg));
    if (!user.token || ['ready', 'partial', 'failed', 'stale', 'cancelled'].includes(draft.status) || attempt >= 20) return;
    window.setTimeout(async () => {
      try {
        const next = await getPracticeDraft(draft.id, user.token || '');
        pollPracticeDraft(next as PracticeDraft, messageId, attempt + 1);
      } catch {
        // A temporary polling failure should not remove the recommendation.
      }
    }, 1500);
  }, [user.token]);

  const pollInterventions = useCallback((turnId: string, messageId: string, attempt = 0): void => {
    if (!user.token || attempt >= 30) return;
    window.setTimeout(async () => {
      try {
        const result = await getTurnInterventions(turnId, user.token || '');
        const actions = Array.isArray(result.actions) ? result.actions : [];
        const draft = actions.find((action: any) => action.draft)?.draft as PracticeDraft | undefined;
        const offered = actions.some((action: any) => action.action_type === 'offer_practice_entry' && action.status === 'ready');
        setMessages((prev) => prev.map((msg) => msg.id === messageId ? {
          ...msg,
          practiceOffered: offered || msg.practiceOffered,
          practiceDraft: draft || msg.practiceDraft,
        } : msg));
        if (draft) pollPracticeDraft(draft, messageId);
        if (!result.terminal) pollInterventions(turnId, messageId, attempt + 1);
      } catch {
        pollInterventions(turnId, messageId, attempt + 1);
      }
    }, 1500);
  }, [pollPracticeDraft, user.token]);

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
  const loadThreadToChat = async (marker: Marker) => {
    const uid = user.userId || user.deviceId;
    try {
      let tree = await getChatTreeByHistory(marker.id, uid, user.token || undefined);
      if (!tree) {
        tree = await ensureChatTreeByHistory(marker.id, uid, user.token || undefined);
      }
      if (tree) {
        const node = tree.nodes.find(n => n.id === tree.last_active_node_id) || tree.nodes.find(n => !n.parent_node_id) || tree.nodes[0];
        if (node) {
          const context = await getChatNodeContext(node.id, uid, user.token || undefined);
          setTreeNodes(tree.nodes.map(({ id, parent_node_id, title, archived_at }) => ({ id, parent_node_id, title, archived_at })));
          setActiveTreeNodeId(node.id);
          treeStateRef.current[marker.id] = { treeId: tree.id, nodeId: node.id, revision: node.revision };
          const restored = context.filter(m => (
            m.role === 'user' || (m.role === 'assistant' && Boolean(m.content))
          ));
          const hydrated = await Promise.all(restored.map((m) => hydrateVisualizations(m.visualizations)));
          setMessages(restored.map((m, index) => ({
            id: m.id,
            role: m.role === 'assistant' ? 'assistant' : 'user',
            content: m.content,
            image: index === 0 && m.role === 'user' ? (marker.thumbnail || undefined) : undefined,
            treeNodeId: node.id,
            treeMessageId: m.id,
            treeMessageStatus: m.status,
            visualizations: hydrated[index],
            qaTurnId: m.turn_id || undefined,
          })));
          setBranchAnchor(null);
          return;
        }
      }
    } catch {
      // Legacy marker history remains the fallback while a tree is unavailable.
    }
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
    setTreeNodes([]);
    setActiveTreeNodeId(null);
  };

  const selectTreeNode = useCallback(async (nodeId: string) => {
    const markerId = activeThreadId;
    if (!markerId) return;
    const uid = user.userId || user.deviceId;
    try {
      const tree = await getChatTreeByHistory(markerId, uid, user.token || undefined);
      const node = tree?.nodes.find((candidate) => candidate.id === nodeId);
      if (!tree || !node) return;
      await activateChatNode(tree.id, { user_id: uid, node_id: nodeId }, user.token || undefined);
      const context = await getChatNodeContext(nodeId, uid, user.token || undefined);
      treeStateRef.current[markerId] = { treeId: tree.id, nodeId, revision: node.revision };
      setTreeNodes(tree.nodes.map(({ id, parent_node_id, title, archived_at }) => ({ id, parent_node_id, title, archived_at })));
      setActiveTreeNodeId(nodeId);
      const marker = getMarkerById(markerId);
      const restored = context.filter((message) => (
        message.role === 'user' || (message.role === 'assistant' && Boolean(message.content))
      ));
      const hydrated = await Promise.all(restored.map((message) => hydrateVisualizations(message.visualizations)));
      setMessages(restored.map((message, index) => ({
        id: message.id,
        role: message.role === 'assistant' ? 'assistant' : 'user',
        content: message.content,
        image: index === 0 && message.role === 'user' ? (marker?.thumbnail || undefined) : undefined,
        treeNodeId: node.id,
        treeMessageId: message.id,
        treeMessageStatus: message.status,
        visualizations: hydrated[index],
        qaTurnId: message.turn_id || undefined,
      })));
      setBranchAnchor(null);
    } catch {
      setError('无法切换到该分支');
    }
  }, [activeThreadId, getMarkerById, hydrateVisualizations, user]);

  const handleForkMessage = useCallback((message: Message) => {
    if (message.treeNodeId && message.treeMessageId) {
      setBranchAnchor({ nodeId: message.treeNodeId, messageId: message.treeMessageId, title: message.content.replace(/\s+/g, ' ').slice(0, 42) });
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setActiveThreadId(null);
    setActiveMarker(null);
    setBranchAnchor(null);
    setTreeNodes([]);
    setActiveTreeNodeId(null);
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
    let treeNodeId: string | undefined;
    let treeState: { treeId: string; nodeId: string; revision: number } | undefined;
    let collectedAnswer = '';
    let treeTurnStarted = false;
    const requestedBranchAnchor = branchAnchor;
    const clientTurnId = generateId();

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
          try {
            const tree = await createChatTree({ user_id: uid, root_chat_history_id: d.id, question: content, answer: null }, user.token || undefined);
            const root = tree.nodes.find(n => !n.parent_node_id) || tree.nodes[0];
            if (root) {
              setTreeNodes(tree.nodes.map(({ id, parent_node_id, title, archived_at }) => ({ id, parent_node_id, title, archived_at })));
              setActiveTreeNodeId(root.id);
              treeStateRef.current[d.id] = { treeId: tree.id, nodeId: root.id, revision: root.revision };
              const rootQuestion = root.messages.find(m => m.role === 'user');
              if (rootQuestion) {
                setMessages((prev) => prev.map((msg) => msg.id === userMessage.id ? { ...msg, treeNodeId: root.id, treeMessageId: rootQuestion.id } : msg));
              }
            }
          } catch {
            // The legacy marker flow must still work if tree storage is unavailable.
          }
        }
      } catch {}
    } else {
      chatId = activeThreadId;
    }

    treeState = chatId ? treeStateRef.current[chatId] : undefined;
    if (treeState) {
      treeNodeId = requestedBranchAnchor?.nodeId || treeState.nodeId;
      setBranchAnchor(null);
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
        treeState?.treeId,
        treeNodeId,
        requestedBranchAnchor?.messageId,
        treeState ? clientTurnId : undefined,
        (turn) => {
          treeTurnStarted = true;
          treeNodeId = turn.node_id;
          treeState = { treeId: turn.tree_id, nodeId: turn.node_id, revision: turn.node_revision };
          if (chatId) treeStateRef.current[chatId] = treeState;
          setActiveTreeNodeId(turn.node_id);
          setTreeNodes((nodes) => nodes.some((node) => node.id === turn.node_id)
            ? nodes
            : [...nodes, {
                id: turn.node_id,
                parent_node_id: turn.parent_node_id,
                title: turn.title,
                archived_at: null,
              }]);
          setMessages((prev) => prev.map((msg) => {
            if (msg.id === userMessage.id) {
              return { ...msg, treeNodeId: turn.node_id, treeMessageId: turn.user_message.id };
            }
            if (msg.id === assistantMessageId) {
              return { ...msg, treeNodeId: turn.node_id, treeMessageId: turn.assistant_message.id, treeMessageStatus: turn.assistant_message.status };
            }
            return msg;
          }));
        },
        (artifact) => {
          setMessages((prev) => prev.map((msg) => msg.id === assistantMessageId
            ? { ...msg, visualizations: [...(msg.visualizations || []).filter((item) => item.id !== artifact.id), artifact] }
            : msg));
        },
        (draft) => pollPracticeDraft(draft as PracticeDraft, assistantMessageId),
        autoPreparePractice,
      );
      if (answer.tree_turn && chatId) {
        treeState = {
          treeId: answer.tree_turn.tree_id,
          nodeId: answer.tree_turn.node_id,
          revision: answer.tree_turn.node_revision,
        };
        treeStateRef.current[chatId] = treeState;
      }
      setMessages((prev) => prev.map((msg) => msg.id === assistantMessageId ? {
        ...msg,
        content: answer.answer,
        sources: answer.sources || [],
        treeNodeId: answer.tree_turn?.node_id || treeState?.nodeId,
        treeMessageId: answer.tree_turn?.assistant_message.id || msg.treeMessageId,
        treeMessageStatus: answer.tree_turn?.assistant_message.status || msg.treeMessageStatus,
        visualizations: answer.visualizations || msg.visualizations || [],
        degraded: answer.degraded,
        practiceDraft: answer.practice_draft || msg.practiceDraft,
        qaTurnId: answer.qa_turn_id,
      } : msg));
      if (answer.qa_turn_id) pollInterventions(answer.qa_turn_id, assistantMessageId);

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
      setMessages((prev) => prev.filter((msg) => {
        if (msg.role === 'assistant' && msg.content === '') return false;
        if (treeState && !treeTurnStarted && msg.id === userMessage.id) return false;
        return true;
      }));
    } finally {
      setIsLoading(false);
      setThinkingStage('');
      setPendingPageNumber(null);
      setPendingCaptureRatio(null);
      setBranchAnchor(null);
      setTimeout(() => { setIsThinking(false); }, 200);
    }
  };

  return {
    messages, isLoading, error, dismissError,
    pendingImage, pendingCaptureRatio, pendingPageNumber,
    thinkingStage, isThinking, thinkingExpanded, setThinkingExpanded,
    hasUnread, setHasUnread,
    branchAnchor, handleForkMessage, cancelFork: () => setBranchAnchor(null),
    treeNodes, activeTreeNodeId, selectTreeNode,
    handleSendMessage, loadThreadToChat, clearMessages, clearPendingImage,
    handleCapture,
    generateVisualizationAnimation,
  };
}
