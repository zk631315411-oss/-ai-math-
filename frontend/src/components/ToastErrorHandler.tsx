import { useEffect } from 'react';

import { addInterceptor } from '../services/request';
import { ApiError, ErrorType } from '../services/error';
import { useToast } from '../hooks/useToast';

/** 错误类型 → 用户友好提示的映射 */
const ERROR_MESSAGES: Record<ErrorType, string> = {
  [ErrorType.NETWORK]: '网络连接失败，请检查网络',
  [ErrorType.TIMEOUT]: '请求超时，请稍后重试',
  [ErrorType.AUTH]: '登录已过期，请重新登录',
  [ErrorType.VALIDATION]: '',
  [ErrorType.SERVER]: '服务器开小差了，请稍后重试',
  [ErrorType.UNKNOWN]: '',
};

/** 认证相关 URL 前缀，这些路径的 AUTH 错误由组件自行处理，不弹全局 Toast */
const AUTH_URL_PREFIX = '/auth/';

/**
 * 全局错误拦截器组件
 *
 * 在 React 组件树中注册 request 层的错误拦截器，
 * 将 ApiError 自动转为 Toast 提示。
 * 组件卸载时自动注销拦截器，避免内存泄漏。
 */
export default function ToastErrorHandler() {
  const { showError } = useToast();

  useEffect(() => {
    const remove = addInterceptor('error', (error: ApiError, config) => {
      // 认证页面的 AUTH 错误由 AuthModal 自行处理，避免重复提示
      if (error.type === ErrorType.AUTH && config.url.startsWith(AUTH_URL_PREFIX)) {
        return error;
      }

      // 从映射表获取友好提示，VALIDATION 和 UNKNOWN 使用原始 message
      const friendly = ERROR_MESSAGES[error.type];
      showError(friendly || error.message);

      return error;
    });

    return remove;
  }, [showError]);

  return null;
}
