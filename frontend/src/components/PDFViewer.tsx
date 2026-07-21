import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Document, Page, pdfjs, type DocumentProps } from 'react-pdf';

// v5 IIFE worker（esbuild 从 pdfjs-dist@5.4.296 构建），与 react-pdf 的 core 版本一致，兼容旧平板
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.js';

import PageMarker, { type Marker } from './PageMarker';

interface Props {
  pdfUrl: string;
  textbookId: string;
  onPageChange?: (page: number) => void;
  mobile?: boolean;
  markers?: Marker[];
  pdfContainerRef?: React.RefObject<HTMLDivElement | null>;
  onMarkerClick?: (marker: Marker) => void;
  viewerPage?: number;
}

const LS_KEY = 'pdf_viewer_page_v2';
const PDF_LOADING_OPTIONS: DocumentProps['options'] = {
  disableRange: false,
  disableStream: true,
  disableAutoFetch: true,
  rangeChunkSize: 512 * 1024,
};

type PdfLoadProgress = {
  loaded: number;
  total?: number;
};

type PageImageConfig = {
  basePath: string;
  pageCount: number;
  width: number;
  height: number;
};

const PAGE_IMAGE_CONFIGS: Record<string, PageImageConfig> = {
  '高数上-黄立宏': {
    basePath: '/textbook-pages/gaoshu-shang',
    pageCount: 284,
    width: 992,
    height: 1402,
  },
  '高数下-黄立宏': {
    basePath: '/textbook-pages/gaoshu-xia',
    pageCount: 274,
    width: 992,
    height: 1402,
  },
};

function getSavedPage(textbookId: string): number {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (!saved) return 1;
    const data = JSON.parse(saved);
    return data[textbookId] || 1;
  } catch { return 1; }
}

function savePage(textbookId: string, page: number) {
  try {
    const saved = localStorage.getItem(LS_KEY);
    const data = saved ? JSON.parse(saved) : {};
    data[textbookId] = page;
    localStorage.setItem(LS_KEY, JSON.stringify(data));
    // 同时更新 current_textbook（让 App 的 restore effect 能读到当前教材）
    localStorage.setItem('current_textbook', textbookId);
  } catch {}
}

function getCurrentTextbook(): string {
  return localStorage.getItem('current_textbook') || '';
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB';
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function getPageImageUrl(config: PageImageConfig, page: number): string {
  return `${config.basePath}/page-${String(page).padStart(3, '0')}.webp`;
}

function PDFViewerInner({ pdfUrl, textbookId, onPageChange, mobile, markers, pdfContainerRef, onMarkerClick, viewerPage }: Props) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pdfError, setPdfError] = useState<string>('');
  const [pageImageError, setPageImageError] = useState<string>('');
  const [loadProgress, setLoadProgress] = useState<PdfLoadProgress | null>(null);
  const [scale, _setScale] = useState<number>(() => {
    const cached = localStorage.getItem('pdf_zoom');
    return cached ? parseFloat(cached) : 0.4;
  });
  const setScale = useCallback((v: number | ((prev: number) => number)) => {
    _setScale(prev => {
      const next = typeof v === 'function' ? v(prev) : v;
      localStorage.setItem('pdf_zoom', String(next));
      return next;
    });
  }, []);
  const [pageInput, setPageInput] = useState<string>('');
  const prevTextbookId = useRef(textbookId);
  const [toolbarVisible, setToolbarVisible] = useState(true);
  const toolbarTimer = useRef<ReturnType<typeof setTimeout>>();
  const pageInputRef = useRef<HTMLInputElement>(null);
  const [editingPage, setEditingPage] = useState(false);
  const [mobilePageInput, setMobilePageInput] = useState('');
  const [pageContainerHeight, setPageContainerHeight] = useState(0);
  const localContainerRef = useRef<HTMLDivElement | null>(null);
  const pageImageConfig = PAGE_IMAGE_CONFIGS[textbookId];
  const pageImageUrl = pageImageConfig ? getPageImageUrl(pageImageConfig, currentPage) : '';
  const pageImageWidth = pageImageConfig ? pageImageConfig.width * scale : 0;
  const pageImageHeight = pageImageConfig ? pageImageConfig.height * scale : 0;

  // Observe container height and forward to PageMarker
  useEffect(() => {
    const el = localContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setPageContainerHeight(el.offsetHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Merge incoming ref with local ref for container height tracking
  const setContainerRef = useCallback((node: HTMLDivElement | null) => {
    localContainerRef.current = node;
    if (pdfContainerRef) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (pdfContainerRef as any).current = node;
    }
  }, [pdfContainerRef]);

  const resetToolbarTimer = useCallback(() => {
    if (!mobile) return;
    setToolbarVisible(true);
    clearTimeout(toolbarTimer.current);
    toolbarTimer.current = setTimeout(() => setToolbarVisible(false), 30000);
  }, [mobile]);

  useEffect(() => {
    if (mobile) {
      resetToolbarTimer();
      return () => clearTimeout(toolbarTimer.current);
    }
  }, [mobile, resetToolbarTimer]);

  useEffect(() => {
    setPdfError('');
    setPageImageError('');
    setLoadProgress(null);
    setNumPages(0);
  }, [pdfUrl]);

  const commitPageJump = () => {
    const page = parseInt(mobilePageInput, 10);
    if (!isNaN(page) && page >= 1 && page <= numPages) {
      handlePageChange(page);
    }
    setEditingPage(false);
    setMobilePageInput('');
  };

  // textbookId 变化时读取 localStorage 恢复该教材的页码
  // 初始时 textbookId=''，用 getCurrentTextbook() 兜底读取（此时 App restore 可能已完成）
  useEffect(() => {
    const tid = textbookId || getCurrentTextbook();
    console.log('[PDFViewer restore effect] textbookId:', tid, 'will restore page:', getSavedPage(tid));
    if (tid) {
      const savedPage = getSavedPage(tid);
      setCurrentPage(savedPage);
      onPageChange?.(savedPage);
    }
  }, [textbookId]);

  // 用户翻页时直接存 localStorage
  const handlePageChange = (page: number) => {
    console.log('[savePage] saving', { textbookId, page });
    setCurrentPage(page);
    savePage(textbookId, page);
    onPageChange?.(page);
  };

  // textbookId 变化（换教材）→ 查 localStorage 恢复该教材的页码
  useEffect(() => {
    console.log('[PDFViewer textbookId effect]', { prev: prevTextbookId.current, next: textbookId });
    if (prevTextbookId.current !== textbookId && textbookId) {
      prevTextbookId.current = textbookId;
      const saved = getSavedPage(textbookId);
      console.log('[PDFViewer textbookId effect] setCurrentPage:', saved);
      setCurrentPage(saved);
      onPageChange?.(saved);
    }
  }, [textbookId]);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setLoadProgress(null);
    // 如果 saved page > 总页数， clamp 一下
    setCurrentPage(prev => Math.min(prev, numPages));
  };

  const loadingMessage = loadProgress?.total
    ? `加载PDF中... ${Math.min(100, Math.round((loadProgress.loaded / loadProgress.total) * 100))}%`
    : loadProgress?.loaded
      ? `加载PDF中... 已读取 ${formatBytes(loadProgress.loaded)}`
      : '加载PDF中...';

  useEffect(() => {
    setPageImageError('');
  }, [pageImageUrl]);

  useEffect(() => {
    if (!pageImageConfig) return;
    setNumPages(pageImageConfig.pageCount);
    setLoadProgress(null);
    setPageImageError('');
    setCurrentPage(prev => Math.min(Math.max(1, prev), pageImageConfig.pageCount));
  }, [pageImageConfig]);

  const handlePageInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const page = parseInt(pageInput, 10);
      if (!isNaN(page) && page >= 1 && page <= numPages) {
        handlePageChange(page);
      }
      setPageInput('');
    }
  };

  const zoomLevels = [0.4, 0.5, 0.75, 1.0];
  const zoomLabels = [80, 100, 150, 200];

  return (
    <div className="flex h-full">
      {/* 页面导航 — 移动端隐藏 */}
      {!mobile && (
      <div className="w-16 bg-slate-100 dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 flex flex-col items-center py-2 shrink-0">
        {/* 页码显示和跳转 */}
        <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">{currentPage}/{numPages}</div>
        <input
          type="text"
          value={pageInput}
          onChange={(e) => setPageInput(e.target.value)}
          onKeyDown={handlePageInput}
          placeholder="跳转"
          className="w-12 h-6 text-xs text-center border rounded mb-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />

        <button
          onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          className="w-10 h-10 rounded-full bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600 flex items-center justify-center disabled:opacity-30 hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <button
          onClick={() => handlePageChange(Math.min(numPages, currentPage + 1))}
          disabled={currentPage >= numPages}
          className="w-10 h-10 rounded-full bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600 flex items-center justify-center disabled:opacity-30 hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* 缩放控制 */}
        <div className="mt-4 flex flex-col items-center gap-1">
          <button
            onClick={() => setScale(s => Math.min(3, s + 0.25))}
            className="w-10 h-8 rounded bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600 flex items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors"
            title="放大"
          >
            <span className="text-lg font-bold">+</span>
          </button>
          <select
            value={scale}
            onChange={(e) => setScale(parseFloat(e.target.value))}
            className="w-14 h-6 text-xs border border-slate-200 dark:border-slate-600 rounded text-center bg-white dark:bg-slate-700 dark:text-slate-200"
          >
            {zoomLevels.map((z, i) => (
              <option key={z} value={z}>{zoomLabels[i]}%</option>
            ))}
          </select>
          <button
            onClick={() => setScale(s => Math.max(0.25, s - 0.25))}
            className="w-10 h-8 rounded bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600 flex items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors"
            title="缩小"
          >
            <span className="text-lg font-bold">−</span>
          </button>
        </div>
      </div>
      )}

      {/* PDF内容区域 */}
      <div className="flex-1 overflow-auto bg-slate-200 dark:bg-slate-700 p-4 relative"
        onClick={mobile ? resetToolbarTimer : undefined}>
        <div className="flex justify-center">
          <div className="relative inline-block" ref={setContainerRef}>
            {!pageImageConfig && (
              <Document
                file={pdfUrl}
                options={PDF_LOADING_OPTIONS}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadProgress={({ loaded, total }) => setLoadProgress({ loaded, total })}
                loading={<div className="text-gray-500 p-8 text-sm">{loadingMessage}</div>}
                onLoadError={(e: Error) => setPdfError(e.message)}
                error={<div className="text-red-500 p-8 text-sm"><p className="font-bold mb-1">PDF加载失败</p><p className="text-xs opacity-70">{pdfError || '未知错误'}</p></div>}
              >
                <Page
                  pageNumber={currentPage}
                  scale={scale}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  className="shadow-lg"
                />
              </Document>
            )}
            {pageImageConfig && (
              <div
                className="react-pdf__Document"
                style={{ width: pageImageWidth || undefined }}
              >
                <div
                  className="react-pdf__Page shadow-lg bg-white"
                  data-page-number={currentPage}
                  style={{
                    width: pageImageWidth,
                    height: pageImageHeight,
                    position: 'relative',
                  }}
                >
                  {pageImageError ? (
                    <div className="flex h-full items-center justify-center p-8 text-sm text-red-500">
                      {pageImageError}
                    </div>
                  ) : (
                    <img
                      src={pageImageUrl}
                      width={pageImageConfig.width}
                      height={pageImageConfig.height}
                      alt={`第 ${currentPage} 页`}
                      className="block h-full w-full select-none"
                      draggable={false}
                      onError={() => setPageImageError('页面图片加载失败，请重试')}
                    />
                  )}
                </div>
              </div>
            )}
            {markers && onMarkerClick && viewerPage && pdfContainerRef && (
              <PageMarker
                markers={markers}
                currentPage={viewerPage}
                containerRef={pdfContainerRef}
                containerHeight={pageContainerHeight}
                onMarkerClick={onMarkerClick}
              />
            )}
          </div>
        </div>

        {/* 移动端底部工具栏 */}
        {mobile && numPages > 0 && (
          <>
            <div className={`absolute bottom-0 left-0 right-0 z-20 transition-all duration-500 ${toolbarVisible ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
              <div className="h-12 bg-black/50 backdrop-blur flex items-center justify-between px-2">
                <button
                  onClick={(e) => { e.stopPropagation(); handlePageChange(Math.max(1, currentPage - 1)); resetToolbarTimer(); }}
                  disabled={currentPage <= 1}
                  className="w-12 h-12 flex items-center justify-center text-white disabled:opacity-30 active:bg-white/20 rounded-lg transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                </button>

                <div className="flex items-center gap-1">
                  {editingPage ? (
                    <input
                      ref={pageInputRef}
                      type="number"
                      min={1}
                      max={numPages}
                      value={mobilePageInput}
                      onChange={(e) => setMobilePageInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') commitPageJump(); }}
                      onBlur={commitPageJump}
                      onClick={(e) => e.stopPropagation()}
                      className="w-16 h-8 text-sm text-center rounded bg-white/20 text-white border border-white/30 focus:outline-none focus:ring-2 focus:ring-blue-400"
                    />
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingPage(true);
                        setMobilePageInput(String(currentPage));
                        resetToolbarTimer();
                        setTimeout(() => pageInputRef.current?.focus(), 50);
                      }}
                      className="text-white text-sm font-medium px-3 py-1 rounded active:bg-white/20 transition-colors"
                    >
                      {currentPage} / {numPages}
                    </button>
                  )}
                </div>

                <button
                  onClick={(e) => { e.stopPropagation(); handlePageChange(Math.min(numPages, currentPage + 1)); resetToolbarTimer(); }}
                  disabled={currentPage >= numPages}
                  className="w-12 h-12 flex items-center justify-center text-white disabled:opacity-30 active:bg-white/20 rounded-lg transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>

                <div className="flex items-center gap-0.5">
                  <button
                    onClick={(e) => { e.stopPropagation(); setScale(s => Math.max(0.25, s - 0.1)); resetToolbarTimer(); }}
                    className="w-10 h-8 flex items-center justify-center text-white active:bg-white/20 rounded transition-colors"
                  >
                    <span className="text-base font-bold">−</span>
                  </button>
                  <select
                    value={scale}
                    onChange={(e) => { setScale(parseFloat(e.target.value)); resetToolbarTimer(); }}
                    onClick={(e) => e.stopPropagation()}
                    className="h-7 text-xs bg-white/15 text-white border border-white/20 rounded px-1 focus:outline-none"
                  >
                    {[0.4, 0.5, 0.75, 1.0].map(s => (
                      <option key={s} value={s} className="text-black">{Math.round(s / 0.5 * 100)}%</option>
                    ))}
                  </select>
                  <button
                    onClick={(e) => { e.stopPropagation(); setScale(s => Math.min(3, s + 0.1)); resetToolbarTimer(); }}
                    className="w-10 h-8 flex items-center justify-center text-white active:bg-white/20 rounded transition-colors"
                  >
                    <span className="text-base font-bold">+</span>
                  </button>
                </div>
              </div>
            </div>

            <button
              onClick={(e) => { e.stopPropagation(); setToolbarVisible(v => !v); resetToolbarTimer(); }}
              className="absolute bottom-2 right-2 z-30 w-8 h-8 rounded-full bg-black/40 backdrop-blur flex items-center justify-center text-white/70 active:bg-black/60 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default memo(PDFViewerInner);
