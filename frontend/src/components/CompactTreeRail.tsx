import { useState } from 'react';

export interface TreeRailNode {
  id: string;
  parent_node_id: string | null;
  title: string;
  archived_at?: string | null;
}

interface Props {
  nodes: TreeRailNode[];
  activeNodeId?: string | null;
  onSelect: (nodeId: string) => void;
  disabled?: boolean;
}

/** Desktop tree navigation: narrow by default, expandable for larger trees. */
export default function CompactTreeRail({ nodes, activeNodeId, onSelect, disabled = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (!nodes.length) return null;
  const visibleNodes = nodes.filter((node) => !node.archived_at);

  return (
    <aside className={`absolute right-0 top-14 bottom-16 z-10 border-l border-slate-200/80 bg-white/90 shadow-sm backdrop-blur dark:border-slate-700/80 dark:bg-slate-800/90 ${expanded ? 'w-44' : 'w-10'} transition-[width]`}>
      <div className="flex h-full flex-col items-center gap-2 overflow-y-auto py-3">
        {visibleNodes.map((node) => {
          const depth = (() => {
            let value = 0;
            let current = node;
            while (current.parent_node_id && value < 8) {
              value += 1;
              current = visibleNodes.find((candidate) => candidate.id === current.parent_node_id) || current;
              if (current.id === node.id) break;
            }
            return value;
          })();
          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelect(node.id)}
              disabled={disabled}
              title={node.title}
              aria-label={node.title}
              className={`flex min-h-7 w-full items-center gap-2 px-2 text-left text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${node.id === activeNodeId ? 'text-blue-700 dark:text-blue-300' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'}`}
              style={{ paddingLeft: expanded ? `${8 + depth * 12}px` : undefined }}
            >
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full border-2 ${node.id === activeNodeId ? 'border-blue-600 bg-blue-500' : 'border-slate-400 bg-transparent dark:border-slate-500'}`} />
              {expanded && <span className="truncate">{node.title || '未命名追问'}</span>}
            </button>
          );
        })}
        {visibleNodes.length > 2 && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            title={expanded ? '收起分支' : '展开全部分支'}
            aria-label={expanded ? '收起分支' : '展开全部分支'}
            className="mt-auto flex h-7 w-7 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-blue-600 dark:hover:bg-slate-700 dark:hover:text-blue-400"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              {expanded ? <path d="m15 18-6-6 6-6" /> : <path d="m9 18 6-6-6-6" />}
            </svg>
          </button>
        )}
      </div>
    </aside>
  );
}
