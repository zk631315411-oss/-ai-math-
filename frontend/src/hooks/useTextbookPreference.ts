import { useState, useEffect } from 'react';
import { getTextbookPreference, saveTextbookPreference } from '../services/api';

export const PRESET_PDFS = [
  { name: '高等代数（上册）丘维声', path: '/gaodai_vol1.pdf', textbookId: '高代上-丘维声' },
  { name: '高等代数（下册）丘维声', path: '/高等代数下册_丘维声.pdf', textbookId: '高代下-丘维声' },
  { name: '高等数学（上册）黄立宏', path: '/高等数学第二版上册黄立宏主编.pdf', textbookId: '高数上-黄立宏' },
  { name: '高等数学（下册）黄立宏', path: '/高等数学第二版下册黄立宏主编.pdf', textbookId: '高数下-黄立宏' },
];

const PDF_PAGE_KEY = 'pdf_viewer_page_v2';
const PREF_KEY = 'textbook_preference';

function getActualPage(textbookId: string): number {
  try {
    const data = JSON.parse(localStorage.getItem(PDF_PAGE_KEY) || '{}');
    return data[textbookId] || 0;
  } catch { return 0; }
}

export function useTextbookPreference(token: string | null) {
  const [selectedPdf, setSelectedPdf] = useState<string>('');
  const [textbookId, setTextbookId] = useState<string>('');

  // 恢复偏好（云端 + localStorage）
  useEffect(() => {
    const localPref = localStorage.getItem(PREF_KEY);
    const localData = localPref ? JSON.parse(localPref) : null;

    if (!token) {
      // 匿名：仅从 localStorage 恢复
      if (localData?.textbookId) {
        localStorage.setItem('current_textbook', localData.textbookId);
        setTextbookId(localData.textbookId);
        const preset = PRESET_PDFS.find(p => p.textbookId === localData.textbookId);
        if (preset) setSelectedPdf(window.location.origin + encodeURI(preset.path));
      }
    } else {
      // 登录：云端优先，localStorage 兜底
      getTextbookPreference(token).then(cloudPref => {
        const tid = cloudPref.textbook_id || localData?.textbookId;
        if (tid) {
          const matched = PRESET_PDFS.find(p => p.textbookId === tid);
          const finalTid = matched ? matched.textbookId : (PRESET_PDFS[0]?.textbookId || tid);
          localStorage.setItem('current_textbook', finalTid);

          const url = matched
            ? window.location.origin + encodeURI(matched.path)
            : (PRESET_PDFS[0] ? window.location.origin + encodeURI(PRESET_PDFS[0].path) : '');
          setTextbookId(finalTid);
          setSelectedPdf(url);

          // 云端页码兜底：如果本地无记录，用云端 page_number 初始化
          if (cloudPref.page_number && !getActualPage(finalTid)) {
            try {
              const pageData = JSON.parse(localStorage.getItem(PDF_PAGE_KEY) || '{}');
              pageData[finalTid] = cloudPref.page_number;
              localStorage.setItem(PDF_PAGE_KEY, JSON.stringify(pageData));
            } catch {}
          }

          // 同步本地 preference
          if (cloudPref.textbook_id && localData?.textbookId !== cloudPref.textbook_id) {
            localStorage.setItem(PREF_KEY, JSON.stringify({ textbookId: cloudPref.textbook_id }));
          }
        }
      });
    }
  }, [token]);

  // 保存偏好（textbookId 变化时同步到 localStorage + 云端）
  useEffect(() => {
    if (!textbookId) return;
    const isValid = PRESET_PDFS.some(p => p.textbookId === textbookId);
    if (!isValid) return;

    localStorage.setItem(PREF_KEY, JSON.stringify({ textbookId }));
    localStorage.setItem('current_textbook', textbookId);

    if (token) {
      const realPage = getActualPage(textbookId) || 1;
      saveTextbookPreference(token, textbookId, realPage).catch(() => {});
    }
  }, [textbookId, token]);

  return { selectedPdf, setSelectedPdf, textbookId, setTextbookId };
}
