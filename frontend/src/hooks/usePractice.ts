import { useEffect, useRef, useState } from 'react';
import {
  createPracticeDraft, getLearningPreferences,
  getPracticeDraft, getPracticeHint, regeneratePracticeDraft,
  startPracticeDraft, submitPracticeAttempt, updateLearningPreferences,
} from '../services/api';
import type { PracticeDraft, PracticeItem, User } from '../types';

export function usePractice(user: User) {
  const [draft, setDraft] = useState<PracticeDraft | null>(null);
  const [session, setSession] = useState<any>(null);
  const [item, setItem] = useState<PracticeItem | null>(null);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<any>(null);
  const [showPanel, setShowPanel] = useState(false);
  const [autoPrepare, setAutoPrepare] = useState(() => sessionStorage.getItem('auto_prepare_practice') !== 'false');
  const pollRef = useRef<number | null>(null);

  useEffect(() => () => { if (pollRef.current) window.clearTimeout(pollRef.current); }, []);

  useEffect(() => {
    if (!user.token) return;
    getLearningPreferences(user.token)
      .then((value) => {
        setAutoPrepare(value.auto_prepare_practice);
        sessionStorage.setItem('auto_prepare_practice', String(value.auto_prepare_practice));
      })
      .catch(() => undefined);
  }, [user.token]);

  const watchDraft = (incoming: PracticeDraft) => {
    setDraft(incoming);
    if (!user.token || ['ready', 'partial', 'failed', 'stale', 'cancelled'].includes(incoming.status)) return;
    if (pollRef.current) window.clearTimeout(pollRef.current);
    pollRef.current = window.setTimeout(async () => {
      try { watchDraft(await getPracticeDraft(incoming.id, user.token || '') as PracticeDraft); } catch { /* retry on next explicit open */ }
    }, 1200);
  };

  const openDraft = async (incoming: PracticeDraft) => {
    setBusy(true);
    setShowPanel(true);
    try {
      const loaded = await getPracticeDraft(incoming.id, user.token || '') as PracticeDraft;
      watchDraft(loaded);
      if (loaded.status === 'ready' || loaded.status === 'partial') await start(loaded);
    } finally { setBusy(false); }
  };

  const start = async (target: PracticeDraft) => {
    if (!user.token) return;
    setBusy(true);
    try {
      const data = await startPracticeDraft(target.id, user.token);
      setSession(data.session);
      setItem(data.item);
      setResult(data.item ? null : {
        mastery_note: data.selection_reason || '当前没有可用的可信教材题。',
        selection_decision: data.selection_decision,
      });
      setHint(null);
    } finally { setBusy(false); }
  };

  const submit = async (studentAnswer: string) => {
    if (!user.token || !session || !item || !studentAnswer.trim()) return;
    setBusy(true);
    try {
      const data = await submitPracticeAttempt(session.id, { item_id: item.id, student_answer: studentAnswer }, user.token);
      setResult(data);
      setItem(data.next_item || null);
      setSession((prev: any) => prev ? { ...prev, status: data.session_status, completed_count: data.completed_count, current_item_id: data.next_item?.id || null, summary: data.summary || prev.summary, selection_decision: data.selection_decision || prev.selection_decision } : prev);
      setHint(null);
    } finally { setBusy(false); }
  };

  const requestHint = async () => {
    if (!user.token || !session || !item || busy) return;
    setBusy(true);
    try { setHint(await getPracticeHint(session.id, user.token)); } finally { setBusy(false); }
  };

  const regenerate = async (incoming?: PracticeDraft) => {
    const target = incoming || draft;
    if (!user.token || !target) return;
    setBusy(true);
    setDraft(target);
    setShowPanel(true);
    try {
      watchDraft(await regeneratePracticeDraft(target.id, user.token) as PracticeDraft);
      setSession(null);
      setItem(null);
      setResult(null);
      setHint(null);
    } finally { setBusy(false); }
  };

  const requestFromTurn = async (turnId: string, nodeId?: string) => {
    if (!user.token || !turnId) return;
    setBusy(true);
    setShowPanel(true);
    setSession(null);
    setItem(null);
    setResult(null);
    try {
      let current = await createPracticeDraft({ turn_id: turnId, node_id: nodeId || '' }, user.token) as PracticeDraft;
      setDraft(current);
      for (let attempt = 0; attempt < 30 && !['ready', 'partial', 'failed', 'stale', 'cancelled'].includes(current.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        current = await getPracticeDraft(current.id, user.token) as PracticeDraft;
        setDraft(current);
      }
      if (current.status === 'ready' || current.status === 'partial') await start(current);
    } finally {
      setBusy(false);
    }
  };

  const setAuto = (value: boolean) => {
    setAutoPrepare(value);
    sessionStorage.setItem('auto_prepare_practice', String(value));
    if (user.token) updateLearningPreferences(value, user.token).catch(() => undefined);
  };

  return {
    draft, session, item, result, hint, busy, showPanel, autoPrepare,
    openDraft, requestFromTurn, start, submit, requestHint, regenerate, setAuto,
    close: () => { setShowPanel(false); setSession(null); setItem(null); setResult(null); setHint(null); },
  };
}
