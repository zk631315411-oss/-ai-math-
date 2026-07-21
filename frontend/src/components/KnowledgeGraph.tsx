import React, { useEffect, useState } from 'react';
import { getKnowledgeGraph } from '../services/api';

interface ConceptNode {
  name: string;
  stage: number | null;
  stage_label: string;
}

interface WeakConcept {
  name: string;
  stage: number | null;
  stage_label: string;
  prerequisites: ConceptNode[];
  dependents: ConceptNode[];
}

interface KnowledgeGraphProps {
  token: string;
}

function stageColor(stage: number | null): string {
  if (stage === null) return 'bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-gray-400';
  if (stage <= 1) return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-300 dark:border-red-700';
  if (stage <= 3) return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-700';
  return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-300 dark:border-green-700';
}

function stageBg(stage: number | null): string {
  if (stage === null) return 'bg-gray-50 dark:bg-gray-800';
  if (stage <= 1) return 'bg-red-50 dark:bg-red-950/20';
  if (stage <= 3) return 'bg-amber-50 dark:bg-amber-950/20';
  return 'bg-green-50 dark:bg-green-950/20';
}

function NodeCard({ node, isWeak }: { node: ConceptNode; isWeak?: boolean }) {
  return (
    <div
      className={`
        px-2.5 py-1.5 rounded-lg border text-xs text-center min-w-[64px] max-w-[120px]
        ${stageColor(node.stage)}
        ${isWeak ? 'ring-2 ring-offset-1 ring-blue-400 dark:ring-blue-500 font-semibold' : ''}
      `}
      title={`${node.name}: ${node.stage_label} (stage ${node.stage ?? '?'})`}
    >
      <div className="truncate">{node.name}</div>
      <div className="text-[10px] opacity-70 mt-0.5">{node.stage_label}</div>
    </div>
  );
}

function ConceptGroup({ weak }: { weak: WeakConcept }) {
  return (
    <div className={`p-3 rounded-xl border ${stageBg(weak.stage)} border-slate-200 dark:border-slate-700`}>
      {/* Support knowledge row */}
      {weak.prerequisites.length > 0 && (
        <div className="flex flex-wrap gap-1.5 justify-center mb-3">
          {weak.prerequisites.map((p) => (
            <NodeCard key={p.name} node={p} />
          ))}
        </div>
      )}

      {/* Connector to weak concept */}
      {weak.prerequisites.length > 0 && (
        <div className="flex justify-center mb-1">
          <div className="flex gap-4 text-slate-300 dark:text-slate-600 text-lg leading-none">
            {weak.prerequisites.slice(0, 3).map((_, i) => (
              <span key={i}>↓</span>
            ))}
          </div>
        </div>
      )}

      {/* Weak concept (center, highlighted) */}
      <div className="flex justify-center mb-1">
        <NodeCard node={weak} isWeak />
      </div>

      {/* Connector to related extension knowledge */}
      {weak.dependents.length > 0 && (
        <div className="flex justify-center mb-1">
          <div className="flex gap-4 text-slate-300 dark:text-slate-600 text-lg leading-none">
            {weak.dependents.slice(0, 3).map((_, i) => (
              <span key={i}>↓</span>
            ))}
          </div>
        </div>
      )}

      {/* Related extension row */}
      {weak.dependents.length > 0 && (
        <div className="flex flex-wrap gap-1.5 justify-center mt-1">
          {weak.dependents.map((d) => (
            <NodeCard key={d.name} node={d} />
          ))}
        </div>
      )}
    </div>
  );
}

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({ token }) => {
  const [data, setData] = useState<{ weak_concepts: WeakConcept[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const json = await getKnowledgeGraph(token);
        setData(json);
      } catch (e) {
        setError('加载失败');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token]);

  if (loading) {
    return <div className="text-center text-gray-400 py-8 text-sm">加载中...</div>;
  }

  if (error) {
    return <div className="text-center text-gray-400 py-8 text-sm">{error}</div>;
  }

  const concepts = data?.weak_concepts || [];

  if (concepts.length === 0) {
    return (
      <div className="text-center text-gray-400 py-6 text-sm space-y-2">
        <p>暂无薄弱概念</p>
        <p className="text-xs text-gray-300 dark:text-gray-600">完成更多问答后，诊断系统会自动识别薄弱点</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex gap-3 text-[10px] text-gray-500 justify-center">
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-red-400" /> 入门
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> 理解/应用
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-green-400" /> 分析/综合
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-gray-300" /> 未知
        </span>
      </div>

      {concepts.map((wc) => (
        <ConceptGroup key={wc.name} weak={wc} />
      ))}

      <p className="text-[10px] text-gray-400 text-center">
        蓝色边框 = 薄弱概念 · 上方 = 支撑知识 · 下方 = 相关延伸
      </p>
    </div>
  );
};

export default KnowledgeGraph;
