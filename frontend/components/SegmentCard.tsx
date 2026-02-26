import { useState } from 'react'
import toast from 'react-hot-toast'
import { segmentsApi } from '@/lib/api'
import type { Segment } from '@/pages/episode/[id]'

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  prompt_ready:   { label: 'Prompt 就绪', color: 'bg-gray-700 text-gray-300' },
  draft_pending:  { label: '队列中',     color: 'bg-yellow-900 text-yellow-300' },
  drafting:       { label: '生成中',     color: 'bg-blue-900 text-blue-300' },
  draft_review:   { label: '待审核',     color: 'bg-purple-900 text-purple-300' },
  done:           { label: '✓ 完成',     color: 'bg-green-900 text-green-300' },
  failed:         { label: '✗ 失败',     color: 'bg-red-900 text-red-300' },
  skipped:        { label: '已跳过',     color: 'bg-gray-800 text-gray-500' },
}

const ACT_NAMES = ['', '开场钩子', '冲突升级', '转折爽点', '连锁反应', '集尾钩子']

export default function SegmentCard({ seg, onUpdate }: { seg: Segment; onUpdate: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [prompt, setPrompt] = useState(seg.prompt)
  const [saving, setSaving] = useState(false)

  const statusInfo = STATUS_LABELS[seg.status] ?? { label: seg.status, color: 'bg-gray-800 text-gray-400' }

  async function savePrompt() {
    setSaving(true)
    try {
      await segmentsApi.update(seg.id, { prompt })
      toast.success('Prompt 已保存')
      setEditing(false)
      onUpdate()
    } catch { toast.error('保存失败') }
    finally { setSaving(false) }
  }

  async function handleApprove() {
    try { await segmentsApi.approveDraft(seg.id); onUpdate(); toast.success('草稿已通过') }
    catch (e: unknown) { toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '操作失败') }
  }

  async function handleReject() {
    try { await segmentsApi.rejectDraft(seg.id); onUpdate(); toast.success('草稿已退回') }
    catch (e: unknown) { toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '操作失败') }
  }

  async function handleSkip() {
    try { await segmentsApi.skip(seg.id); onUpdate(); toast.success('已跳过') }
    catch { toast.error('操作失败') }
  }

  async function handleSingleDraft() {
    try {
      await segmentsApi.submitSingleDraft(seg.id)
      onUpdate()
      toast.success('生成已提交')
    } catch (e: unknown) {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '提交失败')
    }
  }

  return (
    <div className={`card transition-all ${seg.prompt_dirty ? 'border-yellow-600/60' : ''}`}>
      {/* 卡片头 */}
      <div className="flex items-center gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="w-7 h-7 rounded bg-gray-800 text-gray-400 text-xs flex items-center justify-center flex-shrink-0">
          {seg.order}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">{ACT_NAMES[seg.act] ?? `第${seg.act}幕`}</span>
            <span className="text-sm truncate">{seg.scene_desc}</span>
          </div>
          {seg.dialogue && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">💬 {seg.dialogue}</p>
          )}
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${statusInfo.color}`}>
          {statusInfo.label}
        </span>
        {seg.prompt_dirty && (
          <span className="text-xs text-yellow-500 flex-shrink-0">Prompt 已改</span>
        )}
        <span className="text-gray-600 text-xs">{expanded ? '▲' : '▽'}</span>
      </div>

      {/* 展开内容 */}
      {expanded && (
        <div className="mt-4 space-y-3 border-t border-gray-800 pt-4">
          {/* 出场角色 */}
          {seg.characters?.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {seg.characters.map(c => (
                <span key={c} className="text-xs bg-brand-500/20 text-brand-300 px-2 py-0.5 rounded-full">{c}</span>
              ))}
            </div>
          )}

          {/* Prompt 编辑 */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500">视频 Prompt</span>
              {!editing && (
                <button className="text-xs text-brand-400 hover:text-brand-300"
                  onClick={() => setEditing(true)}>编辑</button>
              )}
            </div>
            {editing ? (
              <div className="space-y-2">
                <textarea className="textarea text-xs" rows={5} value={prompt}
                  onChange={e => setPrompt(e.target.value)} />
                <div className="flex gap-2">
                  <button className="btn-primary text-xs py-1 px-3" disabled={saving} onClick={savePrompt}>
                    {saving ? '保存中...' : '保存'}
                  </button>
                  <button className="btn-secondary text-xs py-1 px-3"
                    onClick={() => { setEditing(false); setPrompt(seg.prompt) }}>取消</button>
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-400 bg-gray-800/50 rounded p-2 leading-relaxed">{prompt}</p>
            )}
          </div>

          {/* prompt_ready：单独生成 */}
          {seg.status === 'prompt_ready' && (
            <button className="btn-primary text-xs py-1.5 w-full"
              onClick={handleSingleDraft}>
              ▶ 单独生成视频
            </button>
          )}

          {/* 视频 */}
          {seg.draft_video_url && (
            <div>
              <p className="text-xs text-gray-500 mb-1">视频</p>
              <video src={seg.draft_video_url} controls className="w-full rounded-lg max-h-48" />
              {seg.status === 'draft_review' && (
                <div className="flex gap-2 mt-2">
                  <button className="btn-primary text-xs py-1 flex-1" onClick={handleApprove}>✓ 通过</button>
                  <button className="btn-danger text-xs py-1 flex-1" onClick={handleReject}>✗ 重做</button>
                </div>
              )}
            </div>
          )}

          {/* 失败：错误信息 + 重试 */}
          {seg.status === 'failed' && (
            <div className="bg-red-950/50 border border-red-900/50 rounded p-2 space-y-2">
              {seg.last_error && (
                <p className="text-xs text-red-400 break-all">{seg.last_error}</p>
              )}
              <button className="text-xs text-red-400 hover:text-red-300 underline"
                onClick={async () => {
                  try { await segmentsApi.rejectDraft(seg.id); onUpdate(); toast.success('已重置，可重新提交') }
                  catch { toast.error('重置失败') }
                }}>
                ↺ 重置并重试
              </button>
            </div>
          )}

          {/* 跳过按钮 */}
          {!['done', 'skipped'].includes(seg.status) && (
            <button className="text-xs text-gray-600 hover:text-gray-400 mt-1" onClick={handleSkip}>
              跳过此分镜
            </button>
          )}
        </div>
      )}
    </div>
  )
}
