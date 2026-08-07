import textbookRegistry from '../../shared/textbooks.json';

export type TextbookId = 'gaodai_shang' | 'gaodai_xia' | 'gaoshu_shang' | 'gaoshu_xia';

export interface TextbookSpec {
  id: TextbookId;
  name: string;
  path: string;
  subject: 'gaodai' | 'gaoshu';
  volume: 1 | 2;
  pageImage?: { basePath: string; pageCount: number; width: number; height: number };
}

type RegistryRow = {
  id: TextbookId;
  display_name: string;
  web_path: string;
  subject: 'gaodai' | 'gaoshu';
  volume: 1 | 2;
  page_image_base: string;
  page_count: number;
  page_width: number;
  page_height: number;
};

export const TEXTBOOKS: readonly TextbookSpec[] = (textbookRegistry as RegistryRow[]).map((item) => ({
  id: item.id,
  name: item.display_name,
  path: item.web_path,
  subject: item.subject,
  volume: item.volume,
  pageImage: item.page_image_base ? {
    basePath: item.page_image_base,
    pageCount: item.page_count,
    width: item.page_width,
    height: item.page_height,
  } : undefined,
}));

export const TEXTBOOK_IDS = new Set<string>(TEXTBOOKS.map((item) => item.id));

const LEGACY_TEXTBOOK_IDS: Record<string, TextbookId> = {
  '高代上-丘维声': 'gaodai_shang',
  '高代下-丘维声': 'gaodai_xia',
  '高数上-黄立宏': 'gaoshu_shang',
  '高数下-黄立宏': 'gaoshu_xia',
  'gaodai-qiuweisheng-upper': 'gaodai_shang',
  'gaoshu-huang-upper-v2': 'gaoshu_shang',
};

export function migrateLegacyTextbookId(value: unknown): TextbookId | null {
  if (typeof value !== 'string') return null;
  if (TEXTBOOK_IDS.has(value)) return value as TextbookId;
  return LEGACY_TEXTBOOK_IDS[value] || null;
}
