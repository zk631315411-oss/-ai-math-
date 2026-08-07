import { useState, useEffect } from 'react';
import { getTextbookPreference, saveTextbookPreference } from '../services/api';
import { migrateLegacyTextbookId, TEXTBOOKS, type TextbookId } from '../textbooks';

export const PRESET_PDFS = TEXTBOOKS.map(({ id, name, path }) => ({ name, path, textbookId: id }));

const PDF_PAGE_KEY = 'pdf_viewer_page_v2';
const PREF_KEY = 'textbook_preference';
const MIGRATION_KEY = 'textbook_id_migration_v1';

function migrateStoredTextbookIds(): void {
  if (localStorage.getItem(MIGRATION_KEY) === 'complete') return;
  try {
    const preference = JSON.parse(localStorage.getItem(PREF_KEY) || 'null');
    const textbookId = migrateLegacyTextbookId(preference?.textbookId);
    if (textbookId) localStorage.setItem(PREF_KEY, JSON.stringify({ textbookId }));

    const current = migrateLegacyTextbookId(localStorage.getItem('current_textbook'));
    if (current) localStorage.setItem('current_textbook', current);

    const pages = JSON.parse(localStorage.getItem(PDF_PAGE_KEY) || '{}');
    const migrated: Record<string, number> = {};
    for (const [key, page] of Object.entries(pages)) {
      const canonical = migrateLegacyTextbookId(key);
      if (canonical && typeof page === 'number') migrated[canonical] = page;
    }
    localStorage.setItem(PDF_PAGE_KEY, JSON.stringify(migrated));
    localStorage.setItem(MIGRATION_KEY, 'complete');
  } catch {
    // Leave the marker unset so a future load can retry a malformed value.
  }
}

function getActualPage(textbookId: string): number {
  try {
    const data = JSON.parse(localStorage.getItem(PDF_PAGE_KEY) || '{}');
    return data[textbookId] || 0;
  } catch { return 0; }
}

export function useTextbookPreference(token: string | null) {
  const [selectedPdf, setSelectedPdf] = useState<string>('');
  const [textbookId, setTextbookId] = useState<TextbookId | ''>('');

  // 恢复偏好（云端 + localStorage）
  useEffect(() => {
    migrateStoredTextbookIds();
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
        const tid = migrateLegacyTextbookId(cloudPref.textbook_id || localData?.textbookId);
        if (tid) {
          const matched = PRESET_PDFS.find(p => p.textbookId === tid);
          const finalTid = matched ? matched.textbookId : PRESET_PDFS[0].textbookId;
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
