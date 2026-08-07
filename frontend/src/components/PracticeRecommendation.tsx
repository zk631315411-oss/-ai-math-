import type { PracticeDraft } from '../types';

interface Props {
  draft: PracticeDraft;
  onStart: (draft: PracticeDraft) => void;
  onRegenerate?: (draft: PracticeDraft) => void;
}

export default function PracticeRecommendation({ draft, onStart, onRegenerate }: Props) {
  const ready = draft.status === 'ready' || draft.status === 'partial';
  return (
    <div className="mt-2 w-full rounded-lg border border-blue-200 bg-blue-50/80 p-3 dark:border-blue-800 dark:bg-blue-900/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold text-blue-700 dark:text-blue-300">针对性练习</p>
            <span className="rounded bg-white px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800">教材原题 · 最多 3 题</span>
          </div>
          <p className="mt-1 text-sm font-medium text-slate-700 dark:text-slate-200">{draft.selection_reason || '正在根据本轮卡点准备练习'}</p>
          {draft.concept_names?.length ? <p className="mt-1 text-xs text-blue-700 dark:text-blue-300">目标：{draft.concept_names.slice(0, 3).join('、')}</p> : null}
          {draft.evidence_quote && <p className="mt-1 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">依据：“{draft.evidence_quote}”</p>}
        </div>
        {ready && <span className="shrink-0 rounded bg-emerald-100 px-2 py-1 text-[10px] text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">已审核</span>}
      </div>
      {!ready && draft.status !== 'failed' && <p className="mt-2 text-xs text-slate-500">正在匹配教材题目...</p>}
      {draft.status === 'failed' && <p className="mt-2 text-xs text-red-600">题组准备失败，可稍后重试。</p>}
      <div className="mt-3 flex items-center gap-2">
        <button disabled={!ready} onClick={() => onStart(draft)} className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40">开始练习</button>
        {ready && onRegenerate && <button onClick={() => onRegenerate(draft)} className="rounded-lg border border-blue-200 px-3 py-1.5 text-xs text-blue-700 hover:bg-white dark:border-blue-700 dark:text-blue-300 dark:hover:bg-slate-800">换一组</button>}
      </div>
    </div>
  );
}
