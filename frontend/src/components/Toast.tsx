import { useToast } from '../hooks/useToast';

// ── 类型与颜色映射 ────────────────────────────────────────

type ToastType = 'success' | 'error' | 'warning' | 'info';

/** 每种类型对应的图标、边框颜色和背景色 */
const TYPE_STYLES: Record<ToastType, {
  icon: string;
  border: string;
  bg: string;
  text: string;
}> = {
  success: {
    icon: '✓',
    border: 'border-green-400 dark:border-green-600',
    bg: 'bg-green-50 dark:bg-green-900/20',
    text: 'text-green-600 dark:text-green-400',
  },
  error: {
    icon: '✕',
    border: 'border-red-400 dark:border-red-600',
    bg: 'bg-red-50 dark:bg-red-900/20',
    text: 'text-red-600 dark:text-red-400',
  },
  warning: {
    icon: '⚠',
    border: 'border-yellow-400 dark:border-yellow-600',
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    text: 'text-yellow-600 dark:text-yellow-400',
  },
  info: {
    icon: 'ℹ',
    border: 'border-blue-400 dark:border-blue-600',
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-600 dark:text-blue-400',
  },
};

// ── 单个 Toast 条目 ───────────────────────────────────────

function ToastItem({ id, type, message, onDismiss }: {
  id: string;
  type: ToastType;
  message: string;
  onDismiss: (id: string) => void;
}) {
  const style = TYPE_STYLES[type];

  return (
    <div
      className={`
        flex items-start gap-2 px-4 py-3 rounded-lg border shadow-lg
        ${style.bg} ${style.border}
        animate-slide-in
        max-w-sm w-full
      `}
      role="alert"
    >
      {/* 图标 */}
      <span className={`mt-0.5 text-base font-bold shrink-0 ${style.text}`}>
        {style.icon}
      </span>

      {/* 消息文本 */}
      <p className="flex-1 text-sm text-slate-700 dark:text-slate-300 leading-5">
        {message}
      </p>

      {/* 关闭按钮 */}
      <button
        onClick={() => onDismiss(id)}
        className="shrink-0 mt-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors leading-none"
        aria-label="关闭提示"
      >
        ✕
      </button>
    </div>
  );
}

// ── Toast 容器 ────────────────────────────────────────────

export default function ToastContainer() {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
      {toasts.map(toast => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem
            id={toast.id}
            type={toast.type}
            message={toast.message}
            onDismiss={dismiss}
          />
        </div>
      ))}
    </div>
  );
}