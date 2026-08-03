import { useEffect, useRef, useState } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from '@tiptap/markdown';
import { Mathematics } from '@tiptap/extension-mathematics';
import { MathfieldElement } from 'mathlive';
import { Calculator, ChevronDown, Grid3X3, LoaderCircle, Plus, Sigma, X } from 'lucide-react';
import MatrixEditor from './MatrixEditor';
import MarkdownRenderer from './MarkdownRenderer';
import { convertFormula } from '../services/api';

type DisplayChoice = 'auto' | 'inline' | 'block';
type FormulaNode = { pos: number; type: 'inline' | 'block' } | null;

interface Props {
  value: string;
  onChange: (value: string) => void;
  token: string;
  placeholder?: string;
  disabled?: boolean;
  compact?: boolean;
  onSubmit?: () => void;
}

const templates = [
  { label: '分数', value: '\\frac{#0}{#?}', glyph: 'a/b' },
  { label: '根式', value: '\\sqrt{#0}', glyph: '√' },
  { label: '上标', value: '^{#0}', glyph: 'x²' },
  { label: '下标', value: '_{#0}', glyph: 'x₂' },
  { label: '极限', value: '\\lim_{#0 \\to #?}', glyph: 'lim' },
  { label: '积分', value: '\\int_{#0}^{#?}', glyph: '∫' },
  { label: '求和', value: '\\sum_{#0}^{#?}', glyph: 'Σ' },
  { label: '向量', value: '\\vec{#0}', glyph: 'v⃗' },
];

const moreTemplates = [
  { label: 'α', value: '\\alpha' }, { label: 'β', value: '\\beta' },
  { label: 'γ', value: '\\gamma' }, { label: 'θ', value: '\\theta' },
  { label: 'λ', value: '\\lambda' }, { label: 'π', value: '\\pi' },
  { label: '∞', value: '\\infty' }, { label: '属于', value: '\\in' },
  { label: '不属于', value: '\\notin' }, { label: '交', value: '\\cap' },
  { label: '并', value: '\\cup' }, { label: '推出', value: '\\Rightarrow' },
];

function MathField({ value, onChange, fieldRef }: {
  value: string;
  onChange: (value: string) => void;
  fieldRef: React.MutableRefObject<MathfieldElement | null>;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const field = new MathfieldElement();
    field.className = 'formula-mathfield';
    field.smartFence = true;
    field.smartMode = false;
    field.value = value;
    const handleInput = () => onChangeRef.current(field.value);
    field.addEventListener('input', handleInput);
    hostRef.current?.appendChild(field);
    fieldRef.current = field;
    requestAnimationFrame(() => field.focus());
    return () => {
      field.removeEventListener('input', handleInput);
      field.remove();
      fieldRef.current = null;
    };
  }, [fieldRef]);

  useEffect(() => {
    if (fieldRef.current && fieldRef.current.value !== value) fieldRef.current.value = value;
  }, [fieldRef, value]);

  return <div ref={hostRef} />;
}

export default function FormulaComposer({
  value, onChange, token, placeholder = '输入文字，或插入数学公式…', disabled, compact, onSubmit,
}: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [description, setDescription] = useState('');
  const [latex, setLatex] = useState('');
  const [displayChoice, setDisplayChoice] = useState<DisplayChoice>('auto');
  const [resolvedDisplay, setResolvedDisplay] = useState<'inline' | 'block'>('inline');
  const [editingNode, setEditingNode] = useState<FormulaNode>(null);
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState('');
  const [showMore, setShowMore] = useState(false);
  const [showMatrix, setShowMatrix] = useState(false);
  const mathFieldRef = useRef<MathfieldElement | null>(null);
  const submitRef = useRef(onSubmit);
  submitRef.current = onSubmit;

  const openNodeEditor = (nodeLatex: string, pos: number, type: 'inline' | 'block') => {
    setEditingNode({ pos, type });
    setLatex(nodeLatex);
    setDescription('');
    setDisplayChoice(type);
    setResolvedDisplay(type);
    setError('');
    setDialogOpen(true);
  };

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: false, blockquote: false, codeBlock: false }),
      Markdown,
      Mathematics.configure({
        katexOptions: { throwOnError: false },
        inlineOptions: { onClick: (node, pos) => openNodeEditor(node.attrs.latex, pos, 'inline') },
        blockOptions: { onClick: (node, pos) => openNodeEditor(node.attrs.latex, pos, 'block') },
      }),
    ],
    content: value,
    contentType: 'markdown',
    editable: !disabled,
    editorProps: {
      attributes: {
        class: `formula-prosemirror ${compact ? 'is-compact' : ''}`,
        role: 'textbox',
        'aria-label': placeholder,
      },
      handleKeyDown: (_view, event) => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && submitRef.current) {
          event.preventDefault();
          submitRef.current();
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor: current }) => onChange(current.getMarkdown()),
  }, []);

  useEffect(() => { editor?.setEditable(!disabled); }, [disabled, editor]);
  useEffect(() => {
    if (!editor || editor.getMarkdown() === value) return;
    editor.commands.setContent(value, { contentType: 'markdown', emitUpdate: false });
  }, [editor, value]);

  const openNewFormula = () => {
    setEditingNode(null);
    setDescription('');
    setLatex('');
    setDisplayChoice('auto');
    setResolvedDisplay('inline');
    setError('');
    setShowMore(false);
    setShowMatrix(false);
    setDialogOpen(true);
  };

  const handleConvert = async () => {
    if (!description.trim() || converting) return;
    setConverting(true);
    setError('');
    try {
      const result = await convertFormula(description.trim(), displayChoice, token);
      setLatex(result.latex);
      setResolvedDisplay(result.display_mode);
    } catch (conversionError) {
      setError(conversionError instanceof Error ? conversionError.message : '转换服务暂时不可用，请手动输入公式');
    } finally {
      setConverting(false);
    }
  };

  const insertTemplate = (template: string) => {
    mathFieldRef.current?.insert(template, { selectionMode: 'placeholder' });
    mathFieldRef.current?.focus();
  };

  const insertFormula = () => {
    const cleanLatex = latex.trim();
    if (!editor || !cleanLatex) return;
    const mode = displayChoice === 'auto' ? resolvedDisplay : displayChoice;
    const type = mode === 'block' ? 'blockMath' : 'inlineMath';
    if (editingNode) {
      const oldNode = editor.state.doc.nodeAt(editingNode.pos);
      if (oldNode) {
        editor.commands.insertContentAt(
          { from: editingNode.pos, to: editingNode.pos + oldNode.nodeSize },
          { type, attrs: { latex: cleanLatex } },
        );
      }
    } else if (mode === 'block') {
      editor.chain().focus().insertBlockMath({ latex: cleanLatex }).run();
    } else {
      editor.chain().focus().insertInlineMath({ latex: cleanLatex }).run();
    }
    setDialogOpen(false);
    setEditingNode(null);
  };

  return (
    <div className="formula-composer relative">
      <div className="formula-editor-shell">
        <div className="relative min-w-0 flex-1">
          {!value && <span className="formula-placeholder">{placeholder}</span>}
          <EditorContent editor={editor} />
        </div>
        <button type="button" onClick={openNewFormula} disabled={disabled}
          className="formula-trigger" title="插入公式" aria-label="插入公式">
          <Calculator size={18} />
        </button>
      </div>

      {dialogOpen && (
        <div className="formula-dialog-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setDialogOpen(false);
        }}>
          <section className="formula-dialog" role="dialog" aria-modal="true" aria-label="公式编辑器">
            <header className="formula-dialog-header">
              <div><h3>{editingNode ? '编辑公式' : '插入公式'}</h3><p>描述转写</p></div>
              <button type="button" onClick={() => setDialogOpen(false)} title="关闭" aria-label="关闭"><X size={18} /></button>
            </header>

            <div className="formula-dialog-body">
              <div className="formula-description-row">
                <input autoFocus value={description} maxLength={500}
                  onChange={(event) => setDescription(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.nativeEvent.isComposing) void handleConvert();
                  }}
                  placeholder="例如：x趋于0时sin x除以x的极限" />
                <button type="button" onClick={() => void handleConvert()}
                  disabled={!description.trim() || converting} className="formula-convert-button">
                  {converting ? <LoaderCircle size={16} className="animate-spin" /> : <Sigma size={16} />}转换
                </button>
              </div>
              {error && <p className="formula-error" role="alert">{error}</p>}

              <div className="formula-preview">
                <span>预览</span>
                {latex ? <MarkdownRenderer applyFormatMath={false}>{resolvedDisplay === 'block' ? `$$\n${latex}\n$$` : `$${latex}$`}</MarkdownRenderer> : <em>等待输入</em>}
              </div>

              <div className="formula-visual-editor"><MathField value={latex} onChange={setLatex} fieldRef={mathFieldRef} /></div>

              <div className="formula-toolbar" aria-label="公式工具栏">
                {templates.map((item) => <button key={item.label} type="button" onClick={() => insertTemplate(item.value)} title={item.label}>{item.glyph}</button>)}
                <button type="button" onClick={() => setShowMatrix((shown) => !shown)} title="矩阵"><Grid3X3 size={16} /></button>
                <button type="button" onClick={() => setShowMore((shown) => !shown)} title="更多符号"><ChevronDown size={16} /></button>
              </div>
              {showMore && <div className="formula-more-symbols">
                {moreTemplates.map((item) => <button key={item.label} type="button" onClick={() => insertTemplate(item.value)}>{item.label}</button>)}
              </div>}
              {showMatrix && <div className="formula-matrix-panel">
                <MatrixEditor onInsert={(matrixLatex) => {
                  insertTemplate(matrixLatex);
                  setResolvedDisplay('block');
                  if (displayChoice === 'auto') setDisplayChoice('block');
                  setShowMatrix(false);
                }} />
              </div>}

              <div className="formula-dialog-footer">
                <div className="formula-display-toggle" aria-label="公式显示方式">
                  {(['auto', 'inline', 'block'] as const).map((choice) => (
                    <button key={choice} type="button" className={displayChoice === choice ? 'is-active' : ''} onClick={() => setDisplayChoice(choice)}>
                      {choice === 'auto' ? '自动' : choice === 'inline' ? '行内' : '独立'}
                    </button>
                  ))}
                </div>
                <button type="button" className="formula-insert-button" disabled={!latex.trim()} onClick={insertFormula}>
                  <Plus size={16} />{editingNode ? '更新' : '插入'}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
