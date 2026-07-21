import { useState } from 'react';
import MarkdownRenderer from './MarkdownRenderer';
import LatexInput from './LatexInput';
import MatrixEditor from './MatrixEditor';
import { getExerciseHint, submitExercise, getExerciseList, reportExerciseError } from '../services/api';

interface Exercise {
  id: string;
  topic: string;
  difficulty: string;
  question: string;
  hints: string[];
  hint_level: number;
  is_answered: boolean;
  is_correct?: boolean;
  error_analysis?: Record<string, string>;
}

interface Props {
  exercises: Exercise[];
  token: string;
  userId: string;
  onClose: () => void;
  isGenerating?: boolean;
  generationStatus?: string;
}

const HINT_LABELS = ['请求提示', '再给一点提示 (2/3)', '就差最后一步了 (3/3)'];

const DIFFICULTY_COLORS: Record<string, string> = {
  basic: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  variation: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  comprehensive: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const DIFFICULTY_LABELS: Record<string, string> = {
  basic: '基础',
  variation: '变式',
  comprehensive: '综合',
};

export default function ExercisePanel({ exercises, token: _token, userId, onClose, isGenerating, generationStatus }: Props) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [studentAnswers, setStudentAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [feedbacks, setFeedbacks] = useState<Record<string, { is_correct: boolean; grading_feedback: string; error_analysis?: Record<string, string> }>>({});
  const [hintTexts, setHintTexts] = useState<Record<string, { text: string; level: number; exhausted: boolean }>>({});
  const [submittingStatus, setSubmittingStatus] = useState<string>('');
  const [exList, setExList] = useState(exercises);

  const STATUS_MESSAGES = ['正在核对计算步骤…', '正在验证最终结果…', '正在生成反馈…'];

  const ex = exList[currentIdx];

  // Generation in progress or empty after attempted generation
  if (isGenerating) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg m-4 p-8 text-center">
          <div className="animate-pulse text-slate-400 text-lg mb-2">⏳</div>
          <p className="text-slate-600 dark:text-slate-400">{generationStatus || '正在生成...'}</p>
          <button
            onClick={onClose}
            className="mt-4 text-xs text-slate-400 hover:text-slate-600 transition-colors"
          >
            取消
          </button>
        </div>
      </div>
    );
  }

  // Error state: generation finished but nothing to show
  if ((!exList || exList.length === 0) && !isGenerating && generationStatus) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg m-4 p-8 text-center">
          <p className="text-red-500 dark:text-red-400 text-lg mb-1">生成失败</p>
          <p className="text-slate-500 dark:text-slate-400 text-sm">{generationStatus}</p>
          <button
            onClick={onClose}
            className="mt-4 px-4 py-2 text-sm bg-slate-100 dark:bg-slate-700 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  if (!ex) return null;

  const feedback = feedbacks[ex.id];
  const hintState = hintTexts[ex.id] || { text: ex.hints?.[0] || '', level: 0, exhausted: false };

  const requestHint = async () => {
    if (hintState.exhausted) return;
    const data = await getExerciseHint(ex.id);
    setHintTexts((prev) => ({ ...prev, [ex.id]: data }));
  };

  const submitAnswer = async () => {
    const answer = studentAnswers[ex.id] || '';
    if (!answer.trim()) return;
    setSubmitting(ex.id);
    setSubmittingStatus(STATUS_MESSAGES[0]);

    // Rotating status messages
    const timer = setInterval(() => {
      setSubmittingStatus((prev) => {
        const idx = STATUS_MESSAGES.indexOf(prev);
        return STATUS_MESSAGES[(idx + 1) % STATUS_MESSAGES.length];
      });
    }, 1500);

    const data = await submitExercise(ex.id, { student_answer: answer });
    clearInterval(timer);
    setSubmitting(null);
    setSubmittingStatus('');
    setFeedbacks((prev) => ({ ...prev, [ex.id]: data }));

    // Poll for async error analysis if answer is wrong
    if (!data.is_correct && !data.error_analysis) {
      pollErrorAnalysis(ex.id);
    }
  };

  const pollErrorAnalysis = async (exerciseId: string) => {
    for (let i = 0; i < 15; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      const exercises = await getExerciseList(userId, 50);
      const found = exercises.find((e: Exercise) => e.id === exerciseId);
      if (found?.error_analysis) {
        setFeedbacks((prev) => ({
          ...prev,
          [exerciseId]: { ...(prev[exerciseId] || { is_correct: false, grading_feedback: '' }), error_analysis: found.error_analysis },
        }));
        // Update in exList
        setExList((prev) => prev.map((e) => (e.id === exerciseId ? { ...e, error_analysis: found.error_analysis } : e)));
        return;
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto m-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-lg text-slate-800 dark:text-slate-200">智能练习</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${DIFFICULTY_COLORS[ex.difficulty] || ''}`}>
              {DIFFICULTY_LABELS[ex.difficulty] || ex.difficulty}
            </span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 text-xl">&times;</button>
        </div>

        <div className="p-6">
          {/* Navigation */}
          {exList.length > 1 && (
            <div className="flex gap-2 mb-4">
              {exList.map((e, i) => (
                <button
                  key={e.id}
                  onClick={() => setCurrentIdx(i)}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${i === currentIdx ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'}`}
                >
                  {DIFFICULTY_LABELS[e.difficulty] || ''} #{i + 1}
                </button>
              ))}
            </div>
          )}

          {/* Question */}
          <div className="prose dark:prose-invert max-w-none mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl text-sm leading-relaxed">
            <MarkdownRenderer applyFormatMath={false}>{ex.question}</MarkdownRenderer>
          </div>

          {/* Input area */}
          <div className="mb-4">
            <LatexInput
              value={studentAnswers[ex.id] || ''}
              onChange={(v) => setStudentAnswers((prev) => ({ ...prev, [ex.id]: v }))}
              placeholder="输入你的答案（支持 LaTeX）..."
            />
            <p className="text-xs text-slate-400 mt-1">
              输入矩阵也可以用矩阵编辑器：
            </p>
            <MatrixEditor onChange={(latex) => {
              setStudentAnswers((prev) => ({
                ...prev,
                [ex.id]: (prev[ex.id] || '') + '\n' + latex,
              }));
            }} />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={requestHint}
              disabled={hintState.exhausted || submitting === ex.id}
              className="px-4 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-40 transition-colors"
            >
              {HINT_LABELS[hintState.level] || '请求提示'}
            </button>
            <button
              onClick={submitAnswer}
              disabled={submitting === ex.id || !(studentAnswers[ex.id] || '').trim()}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 transition-colors font-medium"
            >
              {submitting === ex.id ? submittingStatus : '提交答案'}
            </button>
            <button
              onClick={() => reportExerciseError(ex.id)}
              className="px-3 py-2 text-xs text-slate-400 hover:text-red-500 transition-colors"
            >
              题目有误
            </button>
          </div>

          {/* Hint display */}
          {hintState.text && hintState.level > 0 && (
            <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-lg text-sm">
              💡 提示：{hintState.text}
            </div>
          )}

          {/* Feedback */}
          {feedback && (
            <div className={`mt-4 p-4 rounded-lg border ${feedback.is_correct ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800'}`}>
              <p className={`font-bold ${feedback.is_correct ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                {feedback.is_correct ? '✅ 回答正确！' : '❌ 回答不正确'}
              </p>
              <div className="text-sm mt-1 text-slate-600 dark:text-slate-400">
                <MarkdownRenderer applyFormatMath={false}>{feedback.grading_feedback}</MarkdownRenderer>
              </div>
              {feedback.error_analysis && (
                <div className="mt-3 p-3 bg-white dark:bg-slate-800 rounded-lg text-sm">
                  <p className="font-medium">📊 错因分析</p>
                  <p>类别：{feedback.error_analysis.error_category} — {feedback.error_analysis.error_subtype}</p>
                  <p>问题：{feedback.error_analysis.specific_error}</p>
                  <p>💡 {feedback.error_analysis.remediation}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
