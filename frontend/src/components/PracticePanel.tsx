import { useEffect, useState } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import LatexInput from './LatexInput';
import type { PracticeDraft, PracticeItem } from '../types';

const GOAL_LABELS: Record<string, string> = {
  definition: '定义理解',
  application: '方法应用',
  proof: '独立证明',
  counterexample: '反例辨析',
  transfer: '迁移应用',
};

const VERDICT_LABELS: Record<string, string> = {
  correct: '正确',
  partial: '部分正确',
  incorrect: '错误',
  ungradable: '证据不足',
};

interface Props {
  draft: PracticeDraft;
  item: PracticeItem | null;
  session: any;
  result: any;
  hint: any;
  busy: boolean;
  onStart: () => void;
  onSubmit: (answer: string) => void;
  onHint: () => void;
  onClose: () => void;
}

export default function PracticePanel({ draft, item, session, result, hint, busy, onStart, onSubmit, onHint, onClose }: Props) {
  const [answer, setAnswer] = useState('');
  useEffect(() => setAnswer(''), [item?.id]);

  const completed = session?.status === 'completed' || session?.status === 'inconclusive' || (!item && result);
  const inconclusive = session?.status === 'inconclusive';
  const counts = session?.summary?.verdict_counts || {};
  const showReason = import.meta.env.VITE_PRACTICE_SHOW_REASON === 'true';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-2xl dark:bg-slate-800">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-700">
          <div>
            <p className="text-sm font-bold text-slate-800 dark:text-slate-100">针对性练习</p>
            <p className="text-xs text-slate-500">教材原题 · 每轮最多三题</p>
          </div>
          <button onClick={onClose} className="text-xl text-slate-400 hover:text-slate-700" aria-label="Close">x</button>
        </div>

        <div className="overflow-y-auto p-5">
          {completed ? (
            <div className="py-8 text-center">
              <p className="text-lg font-bold text-slate-800 dark:text-slate-100">
                {inconclusive ? '本轮证据不足' : '本轮练习完成'}
              </p>
              <div className="mx-auto mt-5 grid max-w-md grid-cols-4 gap-2 text-xs">
                <div className="rounded-lg bg-green-50 p-3 text-green-700">正确<br /><strong>{counts.correct || 0}</strong></div>
                <div className="rounded-lg bg-amber-50 p-3 text-amber-700">部分正确<br /><strong>{counts.partial || 0}</strong></div>
                <div className="rounded-lg bg-red-50 p-3 text-red-700">错误<br /><strong>{counts.incorrect || 0}</strong></div>
                <div className="rounded-lg bg-slate-100 p-3 text-slate-600">使用提示<br /><strong>{session?.summary?.hints_used || 0}</strong></div>
              </div>
              <p className="mx-auto mt-5 max-w-md text-sm text-slate-500">
                {result?.mastery_note || session?.selection_decision?.reason || '本轮作答已作为诊断证据保存，长期掌握状态仍需继续积累证据。'}
              </p>
              <button onClick={onClose} className="mt-5 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white">返回对话</button>
            </div>
          ) : !item ? (
            <div className="py-10 text-center text-sm text-slate-500">
              {draft.status === 'failed' ? (
                <p className="text-red-500">暂时没有匹配到可信教材题。</p>
              ) : draft.status === 'ready' || draft.status === 'partial' ? (
                <>
                  <p>针对性题组已准备完成。</p>
                  <button onClick={onStart} disabled={busy} className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
                    {busy ? '正在开始...' : '开始练习'}
                  </button>
                </>
              ) : (
                <p>正在匹配教材题目...</p>
              )}
            </div>
          ) : (
            <>
              <div className="mb-4 flex items-center justify-between gap-4 text-xs text-slate-500">
                <span>第 {(session?.completed_count || 0) + 1} / 3 题</span>
                <span className="text-right">教材第 {item.source_page || '-'} 页 · 题号 {item.source_problem_no || '-'}{item.source_subitem_no ? `（${item.source_subitem_no}）` : ''}</span>
              </div>
              <div className="mb-3 text-xs text-slate-500">
                {item.primary_concept_name || item.concept_names?.[0] || item.concept_ids?.[0] || '当前知识点'} · {GOAL_LABELS[item.diagnostic_goal] || '针对性练习'}
              </div>
              <div className="rounded-lg bg-blue-50 p-4 text-sm leading-7 text-slate-800 dark:bg-blue-900/20 dark:text-slate-100">
                <MarkdownRenderer applyFormatMath={false}>{item.question}</MarkdownRenderer>
              </div>
              <div className="mt-4"><LatexInput value={answer} onChange={setAnswer} placeholder="写下答案、计算过程或证明步骤" /></div>
              {hint && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
                  <p className="mb-1 font-medium text-amber-700">提示 {hint.hint_level}/3</p>
                  <MarkdownRenderer>{hint.hint}</MarkdownRenderer>
                  {hint.worked_example && (
                    <div className="mt-3 border-t border-amber-200 pt-3 dark:border-amber-800">
                      <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">
                        教材例题 · 第 {hint.worked_example.source_page || '-'} 页 · {hint.worked_example.source_problem_no || '例题'}
                      </p>
                      <div className="mt-2"><MarkdownRenderer>{hint.worked_example.question}</MarkdownRenderer></div>
                      <div className="mt-2 text-slate-600 dark:text-slate-300"><MarkdownRenderer>{hint.worked_example.explanation}</MarkdownRenderer></div>
                    </div>
                  )}
                </div>
              )}
              {result && (
                <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900">
                  <p className="font-semibold">上题结果：{VERDICT_LABELS[result.verdict] || result.verdict}</p>
                  <p className="mt-1 text-sm">{result.feedback}</p>
                  {result.evidence_quotes?.length > 0 && <p className="mt-2 text-xs text-slate-500">作答依据：{result.evidence_quotes.join('；')}</p>}
                  {result.error_analysis && Object.keys(result.error_analysis).length > 0 && <p className="mt-2 text-xs text-slate-500">错因：{result.error_analysis.category || '需要继续核对解题过程'}</p>}
                  <p className="mt-2 text-xs text-slate-500">下一步：{result.next_reason}</p>
                  {showReason && result.selection_decision?.reason && <p className="mt-2 text-xs text-slate-500">内部选题理由：{result.selection_decision.reason}</p>}
                </div>
              )}
              <div className="mt-4 flex items-center gap-2">
                <button onClick={onHint} disabled={busy || hint?.exhausted} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 disabled:opacity-40 dark:border-slate-600 dark:text-slate-300">查看提示</button>
                <button onClick={() => onSubmit(answer)} disabled={busy || !answer.trim()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">{busy ? '正在批改...' : '提交答案'}</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
