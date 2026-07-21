import React from 'react';

interface BasicInfoEditorProps {
  grade: string;
  onGradeChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving?: boolean;
}

export const BasicInfoEditor: React.FC<BasicInfoEditorProps> = ({
  grade,
  onGradeChange,
  onSave,
  onCancel,
  saving = false,
}) => {
  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm text-gray-600 mb-1">年级</label>
        <input
          type="text"
          value={grade}
          onChange={(e) => onGradeChange(e.target.value)}
          placeholder="如：大一"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex gap-2">
        <button
          onClick={onSave}
          disabled={saving}
          className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? '保存中...' : '保存'}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200"
        >
          取消
        </button>
      </div>
    </div>
  );
};

export default BasicInfoEditor;
