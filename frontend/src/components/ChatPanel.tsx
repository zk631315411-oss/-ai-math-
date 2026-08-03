import { useState, useRef, useEffect, memo } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import FormulaComposer from './FormulaComposer';
import type { Message } from '../types';
import CompactTreeRail, { type TreeRailNode } from './CompactTreeRail';

interface Props {
  messages: Message[];
  onSendMessage: (content: string, image?: string) => void;
  onClearMessages: () => void;
  isLoading: boolean;
  pendingImage?: string | null;
  onClearPendingImage?: () => void;
  thinkingStage?: string;
  isThinking?: boolean;
  thinkingExpanded?: boolean;
  setThinkingExpanded?: (v: boolean) => void;
  compact?: boolean;
  onStartExercise?: () => void;
  markerBanner?: { id: string; page: number; question: string } | null;
  onCloseMarkerBanner?: () => void;
  onDeleteMarker?: (id: string) => void;
  onForkMessage?: (message: Message) => void;
  branchAnchor?: { title: string } | null;
  onCancelFork?: () => void;
  treeNodes?: TreeRailNode[];
  activeTreeNodeId?: string | null;
  onSelectTreeNode?: (nodeId: string) => void;
  token?: string;
}

// 防止 KaTeX 长公式溢出：每个公式独立滚动，不强制整个气泡滚动
const katexOverflowCSS = `
  .chat-message .katex-display,
  .chat-message .katex-display > .katex {
    max-width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
  }
  .chat-message .katex {
    max-width: 100%;
    word-break: break-all;
  }
`;

function ChatPanelInner({ messages, onSendMessage, onClearMessages, isLoading, pendingImage, onClearPendingImage, thinkingStage, isThinking, thinkingExpanded: _thinkingExpanded = true, setThinkingExpanded: _setThinkingExpanded, compact, onStartExercise, markerBanner, onCloseMarkerBanner, onDeleteMarker, onForkMessage, branchAnchor, onCancelFork, treeNodes, activeTreeNodeId, onSelectTreeNode, token = '' }: Props) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); };

  useEffect(() => { if (!isLoading) scrollToBottom(); }, [messages, isLoading]);

  const handleSubmit = () => {
    if ((input.trim() || pendingImage) && !isLoading) {
      onSendMessage(input.trim() || '请解答这张图片中的题目', pendingImage || undefined);
      setInput('');
      onClearPendingImage?.();
    }
  };

  return (
    <div className="relative flex flex-col h-full bg-slate-50 dark:bg-slate-900 transition-colors">
      <style>{katexOverflowCSS}</style>
      {/* Header — hide in compact mode (AiBall has its own) */}
      {!compact && (
      <div className="px-4 py-3 border-b border-slate-200/60 dark:border-slate-700/60 bg-white dark:bg-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-500 shadow-sm shadow-blue-300" />
          <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-sm">智能问答</h3>
        </div>
        {onStartExercise && (
          <button onClick={onStartExercise} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
            智能出题
          </button>
        )}
        {messages.length > 0 && (
          <button onClick={onClearMessages} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            清除对话
          </button>
        )}
      </div>
      )}

      {/* Phase 2: 标记上下文横幅 */}
      {markerBanner && (
        <div className="flex items-center justify-between px-4 py-2 bg-amber-50 dark:bg-amber-900/10 border-b border-amber-200 dark:border-amber-800">
          <span className="text-sm font-medium text-amber-800 dark:text-amber-200">
            📌 第{markerBanner.page}页 · {markerBanner.question.slice(0, 30)}...
          </span>
          <div className="flex items-center gap-1">
            {onDeleteMarker && (
              <button
                onClick={() => onDeleteMarker(markerBanner.id)}
                className="text-red-400 hover:text-red-600 dark:hover:text-red-300 text-sm px-1"
                title="删除此标记"
              >
                🗑
              </button>
            )}
            <button
              onClick={onCloseMarkerBanner}
              className="text-amber-500 hover:text-amber-700 dark:hover:text-amber-300 text-lg leading-none"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className={`flex-1 overflow-y-auto p-4 space-y-4 ${treeNodes && treeNodes.length ? 'pr-14' : ''}`}>
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 dark:text-slate-500">
            <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mb-3">
              <svg className="w-8 h-8 text-blue-400 dark:text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-sm font-medium">开始提问</p>
            <p className="text-xs mt-1 opacity-70">框选教材截图或直接输入数学问题</p>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className="flex flex-col items-start max-w-[85%]">
            <div className={`chat-message w-full rounded-2xl px-4 py-3 ${
              msg.role === 'user'
                ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-sm shadow-blue-200 dark:shadow-none rounded-br-md'
                : 'bg-white dark:bg-slate-800 shadow-sm border border-slate-100 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-bl-md'
            }`}>
              {msg.image && (
                <img src={msg.image} alt="用户截图" className="mb-2 max-w-full rounded-lg" style={{ maxHeight: '200px' }} />
              )}

              <MarkdownRenderer className="text-sm leading-relaxed markdown-body">{msg.content}</MarkdownRenderer>

              {msg.sources && msg.sources.length > 0 && (
                <div className={`mt-3 pt-3 border-t ${msg.role === 'user' ? 'border-white/20' : 'border-slate-200 dark:border-slate-700'}`}>
                  <p className="text-xs font-medium mb-2 opacity-70">引用来源</p>
                  <div className="space-y-2">
                    {msg.sources.map((s, i) => (
                      <div key={i} className="text-xs opacity-80">
                        <span className="font-medium">{s.chapter}</span>
                        <p className="mt-1 line-clamp-2">{s.snippet}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {msg.knowledge_points && msg.knowledge_points.length > 0 && (
                <div className={`mt-3 pt-3 border-t ${msg.role === 'user' ? 'border-white/20' : 'border-slate-200 dark:border-slate-700'}`}>
                  <p className="text-xs font-medium mb-2 opacity-70">知识点</p>
                  <div className="flex flex-wrap gap-1">
                    {msg.knowledge_points.map((kp, i) => (
                      <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                        msg.role === 'user' ? 'bg-white/20' : 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                      }`}>{kp}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {msg.role === 'assistant' && msg.content.trim() && msg.treeMessageStatus === 'completed' && msg.treeNodeId && msg.treeMessageId && onForkMessage && (
              <button
                type="button"
                onClick={() => onForkMessage(msg)}
                disabled={isLoading}
                title="从这条回答创建独立分支"
                aria-label="从这条回答创建独立分支"
                className="mt-1.5 ml-1 inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-400 hover:bg-slate-200 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-slate-700 dark:hover:text-blue-400 transition-colors"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 3v12a3 3 0 0 0 3 3h9" /><path d="m15 14 3 4-3 4" /><path d="M6 9h6a3 3 0 0 0 3-3V3" /><path d="m12 6 3-3 3 3" />
                </svg>
              </button>
            )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-slate-800 shadow-sm border border-slate-100 dark:border-slate-700 rounded-2xl rounded-bl-md px-4 py-3 max-w-[85%]">
              {thinkingStage && (
                <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-sm mb-2">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span>{thinkingStage}</span>
                </div>
              )}
              {isThinking && (
                <div className="text-xs text-slate-400 dark:text-slate-500 mt-2">正在思考...</div>
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {treeNodes && treeNodes.length > 0 && onSelectTreeNode && (
        <CompactTreeRail nodes={treeNodes} activeNodeId={activeTreeNodeId} onSelect={onSelectTreeNode} disabled={isLoading} />
      )}

      {branchAnchor && (
        <div className="flex items-center justify-between gap-3 border-t border-blue-200 bg-blue-50 px-4 py-2 text-xs text-blue-700 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300">
          <span className="truncate">正在从“{branchAnchor.title}”创建独立分支</span>
          <button type="button" onClick={onCancelFork} className="shrink-0 text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-100">取消</button>
        </div>
      )}

      {/* Pending image preview */}
      {pendingImage && (
        <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700 bg-blue-50/50 dark:bg-blue-900/10">
          <div className="flex items-start gap-2">
            <img src={pendingImage} alt="待发送截图" className="max-w-[120px] max-h-[100px] rounded-lg shadow-sm border border-blue-200 dark:border-blue-800" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-blue-600 dark:text-blue-400 mb-1 font-medium">截图已捕获</p>
              <button type="button" onClick={onClearPendingImage} className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1 transition-colors">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                删除图片
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 输入区域：小屏输入框 1 行，发送按钮宽度自适应 */}
      <form onSubmit={(event) => { event.preventDefault(); handleSubmit(); }} className="p-3 sm:p-4 border-t border-slate-200/60 dark:border-slate-700/60 bg-white dark:bg-slate-800">
        <div className="flex gap-2">
          <div className="min-w-0 flex-1">
            <FormulaComposer value={input} onChange={setInput} token={token}
              placeholder="输入问题…" compact={compact} disabled={isLoading} onSubmit={handleSubmit} />
          </div>
          <button type="submit" disabled={(!input.trim() && !pendingImage) || isLoading}
            className="px-4 sm:px-6 py-2 sm:py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shadow-blue-200 dark:shadow-none active:scale-95 whitespace-nowrap">
            发送
          </button>
        </div>
      </form>
    </div>
  );
}

export default memo(ChatPanelInner);
