import { useState } from 'react';
import { getExercisesByPage, generateExercise, getExerciseList } from '../services/api';
import type { User } from '../types';

export function useExercise(user: User, currentPage: number, textbookId: string) {
  const [showExercisePanel, setShowExercisePanel] = useState(false);
  const [exerciseList, setExerciseList] = useState<any[]>([]);
  const [generationStatus, setGenerationStatus] = useState('');
  const [exerciseKey, setExerciseKey] = useState(0);

  const startExercise = async () => {
    setGenerationStatus('正在匹配章节...');
    setExerciseList([]);
    setShowExercisePanel(true);

    const uid = user.userId || user.deviceId;
    const exercises = await getExercisesByPage(currentPage, uid, textbookId || '高代上-丘维声');

    if (exercises.length > 0) {
      setExerciseKey(k => k + 1);
      setGenerationStatus('');
      setExerciseList(exercises);
    } else {
      setGenerationStatus('当前页无教材例题，正在用 AI 生成...');
      const genRes = await generateExercise({
        user_id: uid, token: user.token || undefined,
        textbook_id: textbookId || undefined, page_number: currentPage,
      });
      const reader = genRes.body?.getReader();
      if (!reader) { setGenerationStatus('生成失败'); return; }
      const decoder = new TextDecoder();
      let buffer = '', exerciseId = '', errMsg = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6));
              if (d.status) setGenerationStatus(d.text || d.status);
              if (d.error) errMsg = d.error;
              if (d.done) exerciseId = d.exercise_id;
            } catch {}
          }
        }
      }
      if (exerciseId) {
        setExerciseKey(k => k + 1);
        setGenerationStatus('');
        const exercises = await getExerciseList(uid, 5);
        setExerciseList(exercises);
      } else {
        setGenerationStatus(errMsg || '生成失败，请重试');
      }
    }
  };

  const closeExercise = () => {
    setShowExercisePanel(false);
    setGenerationStatus('');
  };

  return {
    showExercisePanel, exerciseList, generationStatus, exerciseKey,
    startExercise, closeExercise,
  };
}
