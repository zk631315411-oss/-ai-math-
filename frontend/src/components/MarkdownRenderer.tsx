import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

// LaTeX 分隔符转换：\( → $, \[ → $$
const formatMath = (text: string | undefined) => {
  if (!text) return '';
  return text.split('\\(').join('$').split('\\)').join('$').split('\\[').join('$$').split('\\]').join('$$');
};

interface Props {
  children: string;
  className?: string;
  applyFormatMath?: boolean;  // 默认 true，ExercisePanel 可传 false
}

export default function MarkdownRenderer({ children, className, applyFormatMath = true }: Props) {
  const content = applyFormatMath ? formatMath(children) : children;
  return (
    <ReactMarkdown
      className={className}
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        code: ({ children }) => <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded text-xs">{children}</code>,
        pre: ({ children }) => <pre className="bg-slate-100 dark:bg-slate-700 p-2 rounded overflow-x-auto text-xs mb-2">{children}</pre>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
