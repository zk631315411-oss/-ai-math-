import { useState, useLayoutEffect, useEffect, useRef } from 'react';

import { ErrorBoundary } from './components/ErrorBoundary';
import ChatPanel from './components/ChatPanel';
import ScreenCapture from './components/ScreenCapture';
import PDFViewer from './components/PDFViewer';
import ProfilePanel from './components/ProfilePanel';
import AuthModal from './components/AuthModal';
import AiBall from './components/AiBall';
import ExercisePanel from './components/ExercisePanel';
import MobileChatPanel from './components/MobileChatPanel';
import { type Marker } from './components/PageMarker';
import MarkerPopover from './components/MarkerPopover';
import ToastErrorHandler from './components/ToastErrorHandler';
import { useAuth } from './hooks/useAuth';
import { useTextbookPreference, PRESET_PDFS } from './hooks/useTextbookPreference';
import { useFeedback } from './hooks/useFeedback';
import { useExercise } from './hooks/useExercise';
import { useMarkers } from './hooks/useMarkers';
import { useChat } from './hooks/useChat';
import type { CropBBox } from './types';

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    if (saved !== null) return saved === 'true';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  useLayoutEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('darkMode', String(dark));
  }, [dark]);
  return [dark, () => setDark(!dark)] as const;
}

export default function App() {
  const [darkMode, toggleDark] = useDarkMode();

  const {
    user, showAuthModal, setShowAuthModal,
    authMode, setAuthMode, authUsername, setAuthUsername,
    authPassword, setAuthPassword, authError, handleAuthSubmit, handleLogout,
  } = useAuth();

  const { selectedPdf, setSelectedPdf, textbookId, setTextbookId } = useTextbookPreference(user.token);

  const [isCapturing, setIsCapturing] = useState(false);
  const [teachingMode, setTeachingMode] = useState<string>(() => localStorage.getItem('teaching_mode') || 'socratic');
  const [socraticSubmode, setSocraticSubmode] = useState<string>(() => localStorage.getItem('socratic_submode') || 'unclassified');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 1024);
  const [showMobileChat, setShowMobileChat] = useState(false);
  const pdfContainerRef = useRef<HTMLDivElement>(null);

  const exercise = useExercise(user, currentPage, textbookId || '');
  const feedback = useFeedback();

  const markers = useMarkers(user, currentPage);
  const chat = useChat({
    user, currentPage, textbookId: textbookId || '',
    teachingMode, socraticSubmode,
    markersState: markers,
  });

  const handleMarkerClick = (marker: Marker) => {
    markers.handleMarkerClick(marker);
    chat.loadThreadToChat(marker);
  };

  const handleCapture = (imageData: string, pageRatioX: number, pageRatioY: number, cropBBox: CropBBox) => {
    setIsCapturing(false);
    chat.handleCapture(imageData, pageRatioX, pageRatioY, cropBBox);
  };

  useEffect(() => {
    const onResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const selectClass = "text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors";

  return (
    <ErrorBoundary>
    <ToastErrorHandler />
    <div className="h-screen flex flex-col bg-slate-50 dark:bg-slate-900 transition-colors">
      {/* Header — glass morphism */}
      <header className="px-6 py-3 bg-white/85 dark:bg-slate-800/85 backdrop-blur border-b border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between shrink-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white text-sm font-bold shadow-sm">
            Z
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-blue-600 to-blue-500 bg-clip-text text-transparent">学数有道</h1>
            <p className="text-xs text-slate-400 dark:text-slate-500">面向大学数学的AI私教</p>
          </div>
        </div>

        {/* 响应式工具栏：小屏隐藏非必要元素，教材选择宽度自适应 */}
        <div className="flex items-center gap-2 sm:gap-3">
          <select className={`${selectClass} w-24 sm:w-auto`} value={selectedPdf} onChange={(e) => {
            const selected = PRESET_PDFS.find((pdf) => (window.location.origin + encodeURI(pdf.path)) === e.target.value);
            setSelectedPdf(e.target.value);
            setTextbookId(selected ? selected.textbookId : '');
          }}>
            <option value="">选择教材...</option>
            {PRESET_PDFS.map((pdf) => (
              <option key={pdf.path} value={window.location.origin + encodeURI(pdf.path)}>{pdf.name}</option>
            ))}
          </select>

          {/* 小屏隐藏教学模式选择，通过 AiBall 内聊天面板仍可使用 */}
          <select className={`${selectClass} hidden sm:block`} value={teachingMode} onChange={(e) => { const v = e.target.value; setTeachingMode(v); localStorage.setItem('teaching_mode', v); }}>
            <option value="socratic">苏格拉底式</option>
            <option value="direct">直接讲解</option>
          </select>

          {teachingMode === 'socratic' && (
            <select className={`${selectClass} hidden md:block`} value={socraticSubmode} onChange={(e) => { const v = e.target.value; setSocraticSubmode(v); localStorage.setItem('socratic_submode', v); }}>
              <option value="unclassified">无分类</option>
              <option value="preview">预习</option>
              <option value="exam_review">考试复习</option>
              <option value="connected_review">串联复习</option>
            </select>
          )}

          {/* 框选提问：小屏只显示图标，中屏以上显示文字 */}
          <button onClick={() => setIsCapturing(true)} disabled={!selectedPdf}
            className="flex items-center gap-1.5 px-2 sm:px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed shadow-sm shadow-blue-200 dark:shadow-none">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="hidden sm:inline">框选提问</span>
          </button>

          {/* 深色模式切换：所有屏幕尺寸均可见 */}
          <button onClick={toggleDark}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            title={darkMode ? '切换亮色模式' : '切换暗色模式'}>
            {darkMode ? (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
            )}
          </button>

          {/* 用户区域：小屏隐藏用户名和画像，只保留退出/登录 */}
          {user.token ? (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-200 dark:border-slate-600">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300 hidden sm:inline">{user.username}</span>
              <button onClick={() => setShowProfileModal(true)} className="text-xs text-blue-600 dark:text-blue-400 hover:underline hidden sm:inline">画像</button>
              <button onClick={handleLogout} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">退出</button>
              {user.profile?.grade && <span className="text-xs px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded hidden sm:inline">{user.profile.grade}</span>}
            </div>
          ) : (
            <div className="flex items-center gap-1 pl-2 border-l border-slate-200 dark:border-slate-600">
              <button onClick={() => { setAuthMode('login'); setShowAuthModal(true); }} className="text-sm text-blue-600 dark:text-blue-400 hover:underline">登录</button>
              <span className="text-slate-300 dark:text-slate-600 hidden sm:inline">|</span>
              <button onClick={() => { setAuthMode('register'); setShowAuthModal(true); }} className="text-sm text-slate-500 dark:text-slate-400 hover:underline hidden sm:inline">注册</button>
            </div>
          )}
        </div>
      </header>

      {/* Feedback bar */}
      <div className="bg-slate-100 dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-1.5 flex items-center justify-between shrink-0">
        {feedback.feedbackSent ? (
          <span className="text-xs text-green-600">已发送，谢谢反馈！</span>
        ) : feedback.feedbackOpen ? (
          <div className="flex items-center gap-2 w-full">
            <input
              value={feedback.feedbackText}
              onChange={(e) => feedback.setFeedbackText(e.target.value)}
              placeholder="写下你的建议或遇到的问题..."
              className="flex-1 text-xs border border-slate-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-300 outline-none focus:ring-1 focus:ring-blue-500"
              maxLength={2000}
            />
            <button
              onClick={feedback.submit}
              className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
            >发送</button>
            <button onClick={feedback.cancel} className="text-xs text-slate-400 hover:text-slate-600">取消</button>
          </div>
        ) : (
          <button
            onClick={feedback.open}
            className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
          >💬 反馈建议</button>
        )}
        {!feedback.feedbackOpen && (
          <button onClick={() => {}} className="text-xs text-slate-300 opacity-0">×</button>
        )}
      </div>

      {chat.error && (
        <div className="bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800 px-6 py-2 text-sm text-red-600 dark:text-red-400 flex items-center justify-between">
          <span>{chat.error}</span>
          <button onClick={chat.dismissError} className="hover:opacity-70">✕</button>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden p-3 gap-3">
        {/* Desktop: PDF + Chat side by side */}
        {isDesktop && <div className="flex flex-1 gap-3 overflow-hidden">
          <div className="flex-1 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200/60 dark:border-slate-700/60 overflow-hidden transition-colors">
            {selectedPdf ? (
              <PDFViewer pdfUrl={selectedPdf} textbookId={textbookId} onPageChange={setCurrentPage}
                markers={markers.markers} pdfContainerRef={pdfContainerRef} onMarkerClick={handleMarkerClick} viewerPage={currentPage} />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-500">
                <div className="w-20 h-20 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mb-4">
                  <svg className="w-10 h-10 text-blue-400 dark:text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </div>
                <p className="text-sm font-medium">请选择教材开始学习</p>
                <p className="text-xs mt-1 opacity-70">选择后可使用"框选提问"截图答疑</p>
              </div>
            )}
          </div>
          <div className="w-[420px] bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200/60 dark:border-slate-700/60 overflow-hidden shrink-0 transition-colors">
            <ChatPanel
              messages={chat.messages}
              onSendMessage={chat.handleSendMessage}
              onClearMessages={chat.clearMessages} isLoading={chat.isLoading}
              pendingImage={chat.pendingImage} onClearPendingImage={chat.clearPendingImage}
              thinkingStage={chat.thinkingStage}
              isThinking={chat.isThinking} thinkingExpanded={chat.thinkingExpanded}
              setThinkingExpanded={chat.setThinkingExpanded}
              onStartExercise={exercise.startExercise}
              markerBanner={markers.activeMarker ? { id: markers.activeMarker.id, page: markers.activeMarker.page_number, question: markers.activeMarker.question } : null}
              onCloseMarkerBanner={() => markers.setActiveMarker(null)}
              onDeleteMarker={markers.handleDeleteMarker}
            />
          </div>
        </div>}

        {/* 移动端：PDF 全屏，AiBall 浮动球 + 临时聊天面板 */}
        {!isDesktop && <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200/60 dark:border-slate-700/60 overflow-hidden">
            {selectedPdf ? (
              <PDFViewer pdfUrl={selectedPdf} textbookId={textbookId} onPageChange={setCurrentPage} mobile
                markers={markers.markers} pdfContainerRef={pdfContainerRef} onMarkerClick={handleMarkerClick} viewerPage={currentPage} />
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-500">
                <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mb-3">
                  <svg className="w-8 h-8 text-blue-400 dark:text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </div>
                <p className="text-sm font-medium">请选择教材</p>
              </div>
            )}
          </div>

          {/* 移动端浮动聊天按钮：与 AiBall 配合，点击临时展开全屏聊天面板 */}
          {selectedPdf && !showMobileChat && (
            <button
              onClick={() => setShowMobileChat(true)}
              className="fixed bottom-6 left-4 z-30 w-12 h-12 rounded-full bg-blue-600 text-white shadow-lg flex items-center justify-center hover:bg-blue-700 active:scale-95 transition-all"
              title="打开聊天"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </button>
          )}

          {/* 移动端临时全屏聊天面板 */}
          {showMobileChat && (
            <MobileChatPanel
              messages={chat.messages} onSendMessage={chat.handleSendMessage}
              onClearMessages={chat.clearMessages} isLoading={chat.isLoading}
              pendingImage={chat.pendingImage} onClearPendingImage={chat.clearPendingImage}
              thinkingStage={chat.thinkingStage}
              isThinking={chat.isThinking} thinkingExpanded={chat.thinkingExpanded}
              setThinkingExpanded={chat.setThinkingExpanded}
              onStartExercise={exercise.startExercise}
              markerBanner={markers.activeMarker ? { id: markers.activeMarker.id, page: markers.activeMarker.page_number, question: markers.activeMarker.question } : null}
              onCloseMarkerBanner={() => markers.setActiveMarker(null)}
              onDeleteMarker={markers.handleDeleteMarker}
              onClose={() => setShowMobileChat(false)}
            />
          )}

          {selectedPdf && (
            <AiBall
              messages={chat.messages} onSendMessage={chat.handleSendMessage}
              onClearMessages={chat.clearMessages} isLoading={chat.isLoading}
              pendingImage={chat.pendingImage} onClearPendingImage={chat.clearPendingImage}
              thinkingStage={chat.thinkingStage}
              isThinking={chat.isThinking} thinkingExpanded={chat.thinkingExpanded}
              setThinkingExpanded={chat.setThinkingExpanded}
              hasUnread={chat.hasUnread}
              onRead={() => chat.setHasUnread(false)}
            />
          )}
        </div>}
      </div>

      <ScreenCapture isActive={isCapturing} currentPage={currentPage} onCapture={handleCapture} onCancel={() => setIsCapturing(false)} />

      {showAuthModal && (
        <AuthModal mode={authMode} username={authUsername} password={authPassword} error={authError}
          onUsernameChange={setAuthUsername} onPasswordChange={setAuthPassword}
          onSubmit={handleAuthSubmit}
          onModeSwitch={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
          onClose={() => setShowAuthModal(false)} />
      )}

      {showProfileModal && user.token && (
        <ProfilePanel token={user.token} username={user.username} onClose={() => setShowProfileModal(false)} />
      )}

      {exercise.showExercisePanel && (
        <ExercisePanel
          key={exercise.exerciseKey}
          exercises={exercise.exerciseList}
          token={user.token || ''}
          userId={user.userId || user.deviceId}
          onClose={exercise.closeExercise}
          isGenerating={!!exercise.generationStatus}
          generationStatus={exercise.generationStatus}
        />
      )}

      {markers.showMarkerPopover && markers.activeMarker && (
        <MarkerPopover
          marker={markers.activeMarker}
          onClose={() => markers.setShowMarkerPopover(false)}
          onDelete={markers.handleDeleteMarker}
        />
      )}
    </div>
    </ErrorBoundary>
  );
}
