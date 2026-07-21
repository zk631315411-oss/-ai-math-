import React from 'react';
import { Radar, RadarChart as ReRadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts';

const DIMENSION_LABELS: Record<string, string> = {
  mathematical_thinking: '数学思考',
  logical_reasoning: '逻辑推理',
  symbolic_operation: '符号运算',
  multi_representation: '多重表征',
  problem_solving: '问题解决',
};

const DIMENSION_KEYS = Object.keys(DIMENSION_LABELS);

interface RadarChartProps {
  dimensions: Record<string, { coverage: number; radius: number; technical: number }>;
}

export const RadarChart: React.FC<RadarChartProps> = ({ dimensions }) => {
  const data = DIMENSION_KEYS.map((key) => {
    const scores = dimensions[key];
    const avg = scores
      ? (scores.coverage + scores.radius + scores.technical) / 3
      : 0;
    return {
      dimension: DIMENSION_LABELS[key] || key,
      fullMark: 3,
      score: Math.round(avg * 10) / 10,
    };
  });

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <ReRadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: '#6b7280' }} />
          <PolarRadiusAxis angle={90} domain={[0, 3]} tick={{ fontSize: 10, fill: '#9ca3af' }} />
          <Radar
            name="得分"
            dataKey="score"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.25}
            strokeWidth={2}
          />
          <Tooltip
            formatter={(value) => [`${value}/3`, '平均分']}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e5e7eb' }}
          />
        </ReRadarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default RadarChart;