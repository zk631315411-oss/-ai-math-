import React from 'react';

interface DiagnosticHistoryItem {
  assessment_id: string;
  sequence_id: string;
  dimension_deltas: Array<{
    dimension: string;
    delta: { coverage: number; radius: number; technical: number };
    evidence: string;
  }>;
  weak_concepts: string[];
  summary: string;
  created_at: string | null;
}

interface LearningTrajectoryProps {
  history: DiagnosticHistoryItem[];
}

export const LearningTrajectory: React.FC<LearningTrajectoryProps> = ({ history }) => {
  if (!history || history.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-4 text-center">
        暂无学习轨迹记录
      </div>
    );
  }

  const recent = history.slice(0, 5);

  return (
    <div className="space-y-2 max-h-48 overflow-y-auto">
      {recent.map((item, idx) => {
        const deltas = item.dimension_deltas || [];
        const hasRegression = deltas.some(
          (d) => d.delta && (d.delta.coverage < 0 || d.delta.radius < 0 || d.delta.technical < 0)
        );
        const hasImprovement = deltas.some(
          (d) => d.delta && (d.delta.coverage > 0 || d.delta.radius > 0 || d.delta.technical > 0)
        );
        const badge = hasRegression ? '后退' : hasImprovement ? '进步' : '持平';

        return (
          <div key={item.assessment_id || idx} className="text-xs border border-gray-100 rounded-lg p-2">
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-gray-700">{item.sequence_id || '未知章节'}</span>
              <span
                className={`px-1.5 py-0.5 rounded text-white text-xs ${
                  hasRegression ? 'bg-red-400' : hasImprovement ? 'bg-green-400' : 'bg-gray-400'
                }`}
              >
                {badge}
              </span>
            </div>
            <div className="text-gray-500 line-clamp-2">{item.summary || '无评价'}</div>
            {item.weak_concepts && item.weak_concepts.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {item.weak_concepts.slice(0, 3).map((c, i) => (
                  <span key={i} className="px-1 py-0.5 bg-orange-50 text-orange-500 rounded text-xs">
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default LearningTrajectory;