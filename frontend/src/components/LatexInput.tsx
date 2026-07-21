import { useState } from 'react';

interface Props {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
}

// 常用数学符号快速插入
const SYMBOLS = [
  ['\\\\frac{}{}', '分数'],
  ['\\\\sqrt{}', '根号'],
  ['\\\\begin{pmatrix} & \\\\\\\\ & \\\\end{pmatrix}', '矩阵'],
  ['\\\\int_{}^{}', '积分'],
  ['\\\\sum_{}^{}', '求和'],
  ['\\\\alpha', 'α'],
  ['\\\\beta', 'β'],
  ['\\\\lambda', 'λ'],
  ['\\\\pi', 'π'],
  ['\\\\infty', '∞'],
  ['\\\\cdot', '·'],
  ['\\\\times', '×'],
  ['\\\\Rightarrow', '⇒'],
  ['\\\\Leftrightarrow', '⇔'],
];

export default function LatexInput({ value, onChange, placeholder }: Props) {
  const [preview, setPreview] = useState('');

  const handleChange = (text: string) => {
    onChange(text);
    setPreview(text);
  };

  const insertSymbol = (latex: string) => {
    onChange(value + ' ' + latex + ' ');
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1">
        {SYMBOLS.map(([latex, label]) => (
          <button
            key={latex}
            onClick={() => insertSymbol(latex)}
            className="px-2 py-1 text-xs bg-slate-100 dark:bg-slate-700 rounded hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
            title={label}
          >
            {label}
          </button>
        ))}
      </div>
      <textarea
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder || '输入 LaTeX 公式...'}
        className="w-full min-h-[80px] p-3 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm resize-y"
      />
      {preview && (
        <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg text-sm text-slate-500 dark:text-slate-400">
          <span className="text-xs font-medium">预览：</span>
          <span className="katex-preview">{preview}</span>
        </div>
      )}
    </div>
  );
}
