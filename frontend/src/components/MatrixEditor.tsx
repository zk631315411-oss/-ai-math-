import { useState } from 'react';

interface Props {
  rows?: number;
  cols?: number;
  onChange: (latex: string) => void;
}

export default function MatrixEditor({ rows = 2, cols = 2, onChange }: Props) {
  const [grid, setGrid] = useState<string[][]>(
    Array(rows).fill(null).map(() => Array(cols).fill(''))
  );
  const [r, setR] = useState(rows);
  const [c, setC] = useState(cols);

  const update = (nr: number, nc: number, newGrid?: string[][]) => {
    const g = newGrid || grid;
    setGrid(g);
    setR(nr);
    setC(nc);
    // 自动生成 LaTeX
    const latex = '\\\\begin{pmatrix}\n' +
      g.map((row) => row.map((v) => v || '0').join(' & ')).join(' \\\\\\\\\n') +
      '\n\\\\end{pmatrix}';
    onChange(latex);
  };

  const setCell = (ri: number, ci: number, val: string) => {
    const newGrid = grid.map((row, i) =>
      i === ri ? row.map((cell, j) => (j === ci ? val : cell)) : row
    );
    update(r, c, newGrid);
  };

  const addRow = () => update(r + 1, c, [...grid, Array(c).fill('')]);
  const delRow = () => {
    if (r <= 1) return;
    update(r - 1, c, grid.slice(0, -1));
  };
  const addCol = () => update(r, c + 1, grid.map((row) => [...row, '']));
  const delCol = () => {
    if (c <= 1) return;
    update(r, c - 1, grid.map((row) => row.slice(0, -1)));
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-4 mb-1">
        <button onClick={delRow} disabled={r <= 1}
          className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-700 rounded hover:bg-slate-200 disabled:opacity-30">行 -</button>
        <span className="text-xs text-slate-400">{r}×{c}</span>
        <button onClick={addRow}
          className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-700 rounded hover:bg-slate-200">行 +</button>
        <button onClick={delCol} disabled={c <= 1}
          className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-700 rounded hover:bg-slate-200 disabled:opacity-30">列 -</button>
        <button onClick={addCol}
          className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-700 rounded hover:bg-slate-200">列 +</button>
      </div>
      <div className="border-2 border-slate-300 dark:border-slate-500 rounded px-3 py-2">
        {grid.map((row, ri) => (
          <div key={ri} className="flex gap-2 my-1">
            {row.map((cell, ci) => (
              <input
                key={ci}
                value={cell}
                onChange={(e) => setCell(ri, ci, e.target.value)}
                className="w-16 h-8 text-center border border-slate-200 dark:border-slate-600 rounded bg-white dark:bg-slate-800 dark:text-slate-200 text-sm"
                placeholder="0"
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
