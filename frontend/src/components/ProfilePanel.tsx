import React, { useEffect, useState } from 'react';
import { RadarChart } from './RadarChart';
import { LearningTrajectory } from './LearningTrajectory';
import { WeakPointGraph } from './WeakPointGraph';
import { KnowledgeGraph } from './KnowledgeGraph';
import { BasicInfoEditor } from './BasicInfoEditor';
import { DiagnosticCard } from './DiagnosticCard';
import { getMathProfile, getKnowledgeStats, getDiagnosticHistory, updateMathProfile, getInsight, regenerateInsight, MathProfile } from '../services/api';

interface ProfilePanelProps {
  token: string;
  username: string;
  onClose: () => void;
}

type Tab = 'radar' | 'trajectory' | 'weak' | 'graph' | 'insight' | 'diagnostic';

export const ProfilePanel: React.FC<ProfilePanelProps> = ({ token, username, onClose }) => {
  const [activeTab, setActiveTab] = useState<Tab>('radar');
  const [mathProfile, setMathProfile] = useState<MathProfile | null>(null);
  const [knowledgeStats, setKnowledgeStats] = useState<any[]>([]);
  const [diagnosticHistory, setDiagnosticHistory] = useState<any[]>([]);
  const [insight, setInsight] = useState<any>(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  // BasicInfoEditor state
  const [editGrade, setEditGrade] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [mp, ks, dh] = await Promise.all([
          getMathProfile(token),
          getKnowledgeStats(token),
          getDiagnosticHistory(token),
        ]);
        setMathProfile(mp);
        setKnowledgeStats(ks.stats || []);
        setDiagnosticHistory(dh.history || []);
        setEditGrade(mp.grade || '');
      } catch (e) {
        console.error('加载画像失败', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // 发送 grade + 保留现有 weak_points，防止清空诊断数据
      const currentWeak = mathProfile?.weak_points || [];
      await updateMathProfile(token, { grade: editGrade, weak_points: currentWeak });
      if (mathProfile) {
        setMathProfile({ ...mathProfile, grade: editGrade });
      }
      setEditing(false);
    } catch (e) {
      console.error('保存失败', e);
    } finally {
      setSaving(false);
    }
  };

  const fetchInsight = async () => {
    setInsightLoading(true);
    try {
      const data = await getInsight(token);
      setInsight(data.insight);
    } catch (e) {
      console.error('加载洞察失败', e);
    } finally {
      setInsightLoading(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'radar', label: '五维雷达' },
    { key: 'trajectory', label: '学习轨迹' },
    { key: 'weak', label: '薄弱点' },
    { key: 'graph', label: '知识图谱' },
    { key: 'insight', label: '学习洞察' },
    { key: 'diagnostic', label: '诊断卡片' },
  ];

  return (
    <div className="fixed inset-0 bg-black/40 dark:bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl w-[420px] max-h-[85vh] flex flex-col border border-slate-200/60 dark:border-slate-700/60">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200">学习画像</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-xs text-slate-400 dark:text-slate-500">{username}</p>
              {!editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="text-xs text-slate-400 hover:text-blue-500 transition-colors"
                >
                  编辑资料
                </button>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 text-xl leading-none transition-colors"
          >
            ×
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-gray-100 px-6">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === t.key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="text-center text-gray-400 py-8">加载中...</div>
          ) : (
            <>
              {/* Basic Info Editor - only shown when editing */}
              {editing && (
                <div className="mb-4 p-3 bg-gray-50 dark:bg-slate-800/50 rounded-lg border border-gray-100 dark:border-slate-700">
                  <BasicInfoEditor
                    grade={editGrade}
                    onGradeChange={setEditGrade}
                    onSave={handleSave}
                    onCancel={() => {
                      setEditing(false);
                      setEditGrade(mathProfile?.grade || '');
                    }}
                    saving={saving}
                  />
                </div>
              )}

              <div className={editing ? 'border-t border-gray-100 pt-4' : ''}>
                {activeTab === 'radar' && (
                  <div>
                    <p className="text-xs text-gray-400 mb-2 text-center">
                      综合平均分：{mathProfile?.overall_average?.toFixed(2) ?? '0'}/3
                    </p>
                    <RadarChart dimensions={mathProfile?.dimensions || {}} />
                  </div>
                )}

                {activeTab === 'trajectory' && (
                  <LearningTrajectory history={diagnosticHistory} />
                )}

                {activeTab === 'weak' && (
                  <WeakPointGraph
                    weakPoints={mathProfile?.weak_points || []}
                    knowledgeStats={knowledgeStats}
                  />
                )}

                {activeTab === 'graph' && (
                  <KnowledgeGraph token={token} />
                )}

                {activeTab === 'insight' && (
                  <div>
                    {!insight && !insightLoading && (
                      <div className="text-center py-4">
                        <button
                          onClick={fetchInsight}
                          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
                        >
                          生成学习洞察
                        </button>
                      </div>
                    )}
                    {insightLoading && (
                      <div className="text-center text-gray-400 py-8">正在分析学习数据...</div>
                    )}
                    {insight && (
                      <div className="space-y-4 text-sm">
                        <div className="p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg">
                          <p className="text-slate-700 dark:text-slate-300">{insight.overall_assessment}</p>
                        </div>
                        {insight.strengths?.length > 0 && (
                          <div>
                            <p className="font-medium text-green-600 dark:text-green-400 mb-2">优势</p>
                            {insight.strengths.map((s: any, i: number) => (
                              <p key={i} className="text-slate-600 dark:text-slate-400 text-xs ml-2 mb-1">
                                {s.dimension}：{s.evidence}
                              </p>
                            ))}
                          </div>
                        )}
                        {insight.weaknesses?.length > 0 && (
                          <div>
                            <p className="font-medium text-amber-600 dark:text-amber-400 mb-2">待提升</p>
                            {insight.weaknesses.map((w: any, i: number) => (
                              <p key={i} className="text-slate-600 dark:text-slate-400 text-xs ml-2 mb-1">
                                {w.dimension}：{w.suggestion}
                              </p>
                            ))}
                          </div>
                        )}
                        {insight.recommended_focus?.length > 0 && (
                          <div>
                            <p className="font-medium text-blue-600 dark:text-blue-400 mb-1">建议重点</p>
                            <div className="flex flex-wrap gap-1">
                              {insight.recommended_focus.map((f: string, i: number) => (
                                <span key={i} className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-xs">{f}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {insight.motivation_message && (
                          <div className="p-3 bg-green-50 dark:bg-green-900/10 rounded-lg text-center italic text-slate-500 dark:text-slate-400">
                            "{insight.motivation_message}"
                          </div>
                        )}
                        <button
                          onClick={async () => {
                            await regenerateInsight(token);
                            fetchInsight();
                          }}
                          className="text-xs text-slate-400 hover:text-blue-500 underline w-full text-center"
                        >
                          刷新报告
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'diagnostic' && (
                  <DiagnosticCardsView userId={username} />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfilePanel;

/** 诊断卡片列表视图——从后端获取数据并渲染卡片列表 */
function DiagnosticCardsView({ userId }: { userId: string }) {
  const [cards, setCards] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) return;
    fetch(`/api/auth/diagnostic-cards?user_id=${encodeURIComponent(userId)}&limit=20`, {
      headers: { 'Content-Type': 'application/json' },
    })
      .then(r => r.json())
      .then(data => setCards(data.cards || []))
      .catch(() => setCards([]))
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading) return <div className="p-4 text-gray-500">加载中...</div>;
  if (cards.length === 0) return <div className="p-4 text-gray-500">暂无诊断卡片</div>;

  return (
    <div className="p-4">
      <p className="text-sm text-gray-500 mb-3">以下知识点认知阶段较低（Stage ≤ 2），建议优先复习：</p>
      {cards.map((card, i) => (
        <DiagnosticCard key={i} {...card} />
      ))}
    </div>
  );
}