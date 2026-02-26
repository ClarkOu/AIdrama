import type { Segment } from '@/pages/episode/[id]'

const STATUS_COLOR: Record<string, string> = {
  prompt_ready:  'bg-gray-700',
  draft_pending: 'bg-yellow-600',
  drafting:      'bg-blue-600 animate-pulse',
  draft_review:  'bg-purple-600',
  final_pending: 'bg-orange-500',
  generating:    'bg-cyan-600 animate-pulse',
  done:          'bg-green-500',
  failed:        'bg-red-600',
  skipped:       'bg-gray-800',
}

const ACT_LABELS = ['', '开场', '冲突', '反转', '连锁', '钩子']

export default function EpisodeTimeline({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) return null

  const doneCount    = segments.filter(s => s.status === 'done').length
  const skippedCount = segments.filter(s => s.status === 'skipped').length
  const pct = segments.length ? Math.round(((doneCount + skippedCount) / segments.length) * 100) : 0

  // 按幕分组
  const actGroups: Record<number, Segment[]> = {}
  for (const seg of segments) {
    if (!actGroups[seg.act]) actGroups[seg.act] = []
    actGroups[seg.act].push(seg)
  }

  return (
    <div className="card mb-4 space-y-3">
      {/* 整体进度 */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-400">整体进度</span>
        <span className="text-gray-300 font-medium">{doneCount + skippedCount} / {segments.length}</span>
      </div>
      <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full bg-green-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }} />
      </div>

      {/* 幕结构时间轴 */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {Object.entries(actGroups).map(([act, segs]) => (
          <div key={act} className="flex-shrink-0">
            <p className="text-xs text-gray-600 mb-1 text-center">{ACT_LABELS[Number(act)] || `第${act}幕`}</p>
            <div className="flex gap-1">
              {segs.map(seg => (
                <div
                  key={seg.id}
                  title={`#${seg.order} ${seg.scene_desc}`}
                  className={`w-5 h-5 rounded-sm ${STATUS_COLOR[seg.status] ?? 'bg-gray-700'}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
