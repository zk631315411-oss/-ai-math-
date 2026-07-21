import React from 'react';

interface KnowledgeStats {
  topic: string;
  total_asks: number;
}

interface WeakPointGraphProps {
  weakPoints: string[];
  knowledgeStats: KnowledgeStats[];
}

export const WeakPointGraph: React.FC<WeakPointGraphProps> = ({ weakPoints, knowledgeStats }) => {
  const hasWeak = weakPoints.length > 0;
  const topFreq = knowledgeStats
    .filter((s) => s.total_asks > 0)
    .sort((a, b) => b.total_asks - a.total_asks)
    .slice(0, 5);
  const hasFreq = topFreq.length > 0;

  // --- Empty state ---
  if (!hasWeak && !hasFreq) {
    return (
      <div className="text-center text-gray-400 py-6 text-sm space-y-1">
        <p>还没有足够数据判断薄弱点。</p>
        <p className="text-xs text-gray-300 dark:text-gray-600">
          完成几次问答或练习后，这里会自动生成待提升清单。
        </p>
      </div>
    );
  }

  // --- Summary ---
  const summary = hasWeak
    ? `系统根据你的问答和练习，识别出 ${weakPoints.length} 个需要优先补强的概念。`
    : hasFreq
      ? '暂未识别出明确薄弱点，但发现了一些近期高频关注内容。'
      : null;

  return (
    <div className="space-y-4 text-sm">
      {summary && (
        <p className="text-slate-600 dark:text-slate-400 leading-relaxed">{summary}</p>
      )}

      {/* 块一：系统识别的薄弱概念 */}
      {hasWeak && (
        <div>
          <h3 className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            需要优先补强
          </h3>
          <div className="space-y-2">
            {weakPoints.map((wp) => (
              <div
                key={wp}
                className="p-3 rounded-lg border border-red-100 dark:border-red-900/30 bg-red-50/50 dark:bg-red-950/10"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-slate-800 dark:text-slate-200">{wp}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">
                    待补强
                  </span>
                </div>
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  由最近问答与诊断结果识别
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  建议回到教材相关小节复习定义、例题，再完成针对练习。
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 块二：最近高频提问 */}
      {hasFreq && (
        <div>
          <h3 className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            近期高频关注
          </h3>
          <p className="text-xs text-slate-400 dark:text-slate-500 mb-2">
            你最近反复关注这些概念，可能是当前学习重点。
          </p>
          <div className="space-y-1.5">
            {topFreq.map((s) => (
              <div
                key={s.topic}
                className="flex items-center justify-between px-3 py-2 rounded-lg border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800/50"
              >
                <span className="text-slate-700 dark:text-slate-300">{s.topic}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">{s.total_asks} 次提问</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
                    关注中
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default WeakPointGraph;
