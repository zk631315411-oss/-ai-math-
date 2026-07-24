import React from 'react';

interface RuleCase {
  name: string;
  owner: string;
  applies_to: string[];
  condition_logic: string;
  conditions: string[];
  outcomes: string[];
}

interface DiagnosticCardProps {
  conceptName: string;
  stage: number;
  confidence: number;
  evidenceQuote: string;
  diagnosis: string;
  evidenceCount: number;
  lastUpdated: string;
  sourceDisplay?: string;
  textbookName?: string;
  evidenceSpan?: string;
  ruleCases?: RuleCase[];
}

/** 认知阶段标签映射 */
const STAGE_LABELS: Record<number, string> = {
  0: '未接触',
  1: '入门',
  2: '理解',
};

/** 认知阶段颜色映射 */
const STAGE_COLORS: Record<number, string> = {
  0: 'text-red-600 bg-red-50',
  1: 'text-orange-600 bg-orange-50',
  2: 'text-yellow-600 bg-yellow-50',
};

export function DiagnosticCard({
  conceptName,
  stage,
  confidence,
  evidenceQuote,
  diagnosis,
  evidenceCount,
  lastUpdated,
  sourceDisplay,
  textbookName,
  evidenceSpan,
  ruleCases,
}: DiagnosticCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-3">
      {/* 标题行：概念名 + 阶段标签 */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-base font-semibold text-gray-900">{conceptName}</h3>
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${
            STAGE_COLORS[stage] || 'text-gray-600 bg-gray-50'
          }`}
        >
          Stage {stage} · {STAGE_LABELS[stage] || '未知'}
        </span>
      </div>

      {/* 判断依据 */}
      {evidenceQuote && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-0.5">判断依据</p>
          <p className="text-sm text-gray-700 bg-gray-50 rounded p-2 italic">
            "{evidenceQuote}"
          </p>
        </div>
      )}

      {/* 教材出处 */}
      {sourceDisplay && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-0.5">教材出处</p>
          <p className="text-sm text-blue-700 bg-blue-50 rounded p-2">{sourceDisplay}</p>
        </div>
      )}

      {/* 教材原文 */}
      {evidenceSpan && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-0.5">教材原文</p>
          <p className="text-sm text-gray-700 bg-gray-50 rounded p-2">{evidenceSpan}</p>
        </div>
      )}

      {/* 诊断结论 */}
      {diagnosis && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-0.5">诊断结论</p>
          <p className="text-sm text-gray-700">{diagnosis}</p>
        </div>
      )}

      {/* 规则案例 */}
      {ruleCases && ruleCases.length > 0 && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-0.5">规则案例</p>
          {ruleCases.map((rc, i) => (
            <div key={i} className="text-sm text-gray-700 bg-green-50 rounded p-2 mb-1">
              <p className="font-medium">{rc.owner} / {rc.name}</p>
              <p className="text-xs text-gray-500 mt-1">
                适用对象：{rc.applies_to?.join('、') || '未指定'}
              </p>
              <p className="text-xs text-gray-500">
                {rc.condition_logic || '条件'}：{rc.conditions?.join('；') || '未列出'}
              </p>
              <p className="text-xs text-gray-500">
                结论：{rc.outcomes?.join('；') || '未列出'}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* 底部：置信度 / 证据条数 / 更新时间 */}
      <div className="flex items-center justify-between text-xs text-gray-400 mt-2 pt-2 border-t border-gray-100">
        <span>置信度: {(confidence * 100).toFixed(0)}%</span>
        <span>{evidenceCount} 条证据</span>
        <span>{lastUpdated ? new Date(lastUpdated).toLocaleDateString('zh-CN') : ''}</span>
      </div>
    </div>
  );
}
