import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { episodesApi } from '@/lib/api'

interface Episode {
  ep_id: string; ep_number: number
  script_text: string; script_version: number; script_locked: boolean
}

export default function ScriptEditor({ ep, onSaved }: { ep: Episode; onSaved: () => void }) {
  const [text, setText] = useState(ep.script_text || '')
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  useEffect(() => {
    setText(ep.script_text || '')
    setDirty(false)
  }, [ep.script_text])

  function handleChange(val: string) {
    setText(val)
    setDirty(val !== ep.script_text)
  }

  async function handleSave() {
    // 如果已有版本，弹出确认"是否重新分镜"
    if (ep.script_version > 0) {
      setShowConfirm(true)
    } else {
      await doSave()
    }
  }

  async function doSave() {
    setShowConfirm(false)
    setSaving(true)
    try {
      await episodesApi.editScript(ep.ep_id, text)
      toast.success(`剧本已保存（v${ep.script_version + 1}）`)
      setDirty(false)
      onSaved()
    } catch { toast.error('保存失败') }
    finally { setSaving(false) }
  }

  if (ep.script_locked) {
    return (
      <div className="card text-center py-12 text-gray-500">
        🔒 剧本已锁定（所有分镜均已完成）
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">剧本编辑</h2>
          <span className="text-xs text-gray-500">v{ep.script_version}</span>
          {dirty && <span className="text-xs text-yellow-500">● 有未保存修改</span>}
        </div>
        <button className="btn-primary text-sm" disabled={!dirty || saving} onClick={handleSave}>
          {saving ? '保存中...' : '保存'}
        </button>
      </div>

      <textarea
        className="textarea font-mono text-sm leading-relaxed"
        rows={30}
        placeholder={"剧本内容会在「生成脚本+分镜」后自动填入。\n你也可以直接粘贴自己的剧本文字。"}
        value={text}
        onChange={e => handleChange(e.target.value)}
      />

      <p className="text-xs text-gray-600">
        💡 修改剧本后保存，系统将自动分析 diff，只对有变动的幕重新生成分镜，不影响已通过的片段。
      </p>

      {/* 确认弹窗 */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="card w-full max-w-sm space-y-4">
            <h3 className="font-semibold">剧本已更改</h3>
            <p className="text-sm text-gray-400">是否重新分析 diff，并对变动幕重新生成分镜？</p>
            <div className="flex gap-2">
              <button className="btn-secondary flex-1"
                onClick={async () => { setShowConfirm(false); await doSave() }}>
                否，只保存文字
              </button>
              <button className="btn-primary flex-1" onClick={doSave}>
                是，重新分镜
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
