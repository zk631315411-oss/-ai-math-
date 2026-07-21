import { useState, useContext, createContext, useCallback, useRef } from 'react';

// ── 类型定义 ──────────────────────────────────────────────

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration: number;
}

interface ToastContextValue {
  showSuccess: (message: string, duration?: number) => void;
  showError: (message: string, duration?: number) => void;
  showWarning: (message: string, duration?: number) => void;
  showInfo: (message: string, duration?: number) => void;
  dismiss: (id: string) => void;
  toasts: ToastItem[];
}

// ── Context ───────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

// 最多同时显示的 Toast 数量
const MAX_TOASTS = 5;
// 默认自动消失时间（毫秒）
const DEFAULT_DURATION = 3000;

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  // 用 ref 保存定时器，避免组件卸载时泄漏
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    // 清除对应的自动消失定时器
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const addToast = useCallback((type: ToastType, message: string, duration = DEFAULT_DURATION) => {
    const id = String(++nextId);

    setToasts(prev => {
      // 超出上限时移除最早的
      const next = prev.length >= MAX_TOASTS ? prev.slice(1) : prev;
      return [...next, { id, type, message, duration }];
    });

    // 设置自动消失定时器
    const timer = setTimeout(() => dismiss(id), duration);
    timersRef.current.set(id, timer);
  }, [dismiss]);

  const showSuccess = useCallback((msg: string, dur?: number) => addToast('success', msg, dur), [addToast]);
  const showError = useCallback((msg: string, dur?: number) => addToast('error', msg, dur), [addToast]);
  const showWarning = useCallback((msg: string, dur?: number) => addToast('warning', msg, dur), [addToast]);
  const showInfo = useCallback((msg: string, dur?: number) => addToast('info', msg, dur), [addToast]);

  return (
    <ToastContext.Provider value={{ showSuccess, showError, showWarning, showInfo, dismiss, toasts }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast 必须在 ToastProvider 内使用');
  }
  return ctx;
}
