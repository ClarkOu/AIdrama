import { useRouter } from 'next/router'
import { useEffect, useState, useCallback, useRef } from 'react'
import toast from 'react-hot-toast'
import { episodesApi, segmentsApi, subscribeEpisodeSSE } from '@/lib/api'
import SegmentCard from '@/components/SegmentCard'
import ScriptEditor from '@/components/ScriptEditor'
import EpisodeTimeline from '@/components/EpisodeTimeline'

interface Episode {
  ep_id: string; ep_number: number; outline: string
  script_text: string; script_version: number; script_locked: boolean
  project_id: string
}
export interface Segment {
  id: string; order: number; act: number
  scene_desc: string; characters: string[]; dialogue: string
  prompt: string; prompt_dirty: boolean; status: string
  draft_video_url: string | null
  last_error: string | null
}

function SpinIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  )
}

export default function EpisodePage() {
  const router = useRouter()
  const epId = router.query.id as string

  const [ep, setEp] = useState<Episode | null>(null)
  const [segments, setSegments] = useState<Segment[]>([])
  const [view, setView] = useState<'segments' | 'script'>('segments')

  // 独立 loading 状态
  const [generatingScript, setGeneratingScript] = useState(false)
  const [submittingDrafts, setSubmittingDrafts] = useState(false)
  const [composing, setComposing] = useState(false)
  const [composedUrl, setComposedUrl] = useState<string | null>(null)
  const [streamingText, setStreamingText] = useState('')    // 流式输出累积文本
  const streamEndTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null) // 流结束防抖
  const streamBoxRef = useRef<HTMLDivElement>(null)           // 滚动容器

  // 草稿批量进度（used by SSE）
  const draftProgressRef = useRef({ done: 0, total: 0 })
  const [draftProgress, setDraftProgress] = useState({ done: 0, total: 0 })

  const loadData = useCallback(async () => {
    if (!epId) return
    const [epR, segsR] = await Promise.all([
      episodesApi.get(epId),
      segmentsApi.list(epId),
    ])
    setEp(epR.data)
    setSegments(segsR.data)
  }, [epId])

  useEffect(() => { loadData() }, [loadData])

  // ── SSE 实时推送 ──────────────────────────────────────────────
  useEffect(() => {
    if (!epId) return
    const es = subscribeEpisodeSSE(epId, (raw: unknown) => {
      const msg = raw as {
        type: string; seg_id?: string; status?: string
        segment_count?: number; output_path?: string; output_url?: string; delta?: string
        draft_video_url?: string | null; last_error?: string | null
      }

      // LLM 流式 chunk：直接追加 delta，打字机效果
      if (msg.type === 'script_chunk' && msg.delta) {
        setStreamingText(prev => {
          const next = prev + msg.delta
          // 让滚动容器跟到最底
          requestAnimationFrame(() => {
            if (streamBoxRef.current) {
              streamBoxRef.current.scrollTop = streamBoxRef.current.scrollHeight
            }
          })
          return next
        })
        // 最后一个 chunk 后 1.5s 判定流结束
        if (streamEndTimerRef.current) clearTimeout(streamEndTimerRef.current)
        streamEndTimerRef.current = setTimeout(() => {
          setGeneratingScript(false)
          setStreamingText('')
          toast.success('✨ 脚本生成完成！', { duration: 5000 })
          loadData()
          setView('segments')
        }, 1500)
      }

      // 分镜状态变更
      if (msg.type === 'segment_status' && msg.seg_id) {
        const newStatus = msg.status ?? ''
        setSegments(prev => prev.map(s => {
          if (s.id !== msg.seg_id) return s
          return {
            ...s,
            status: newStatus,
            ...(msg.draft_video_url !== undefined && { draft_video_url: msg.draft_video_url as string }),
            ...(msg.last_error !== undefined && { last_error: msg.last_error as string | null }),
          }
        }))
        if (['draft_review', 'failed', 'skipped'].includes(newStatus)) {
          const p = draftProgressRef.current
          p.done += 1
          setDraftProgress({ ...p })
        }
        if (newStatus === 'failed') {
          toast.error(`分镜生成失败 #${msg.seg_id?.split('-').pop()}`)
        }
        if (newStatus === 'done') {
          toast.success('✅ 正式视频生成完成', { duration: 2500 })
        }
      }

      // 脚本+分镜生成完成（备用触发，debounce 先到就已处理）
      if (msg.type === 'script_ready') {
        if (streamEndTimerRef.current) clearTimeout(streamEndTimerRef.current)
        setGeneratingScript(false)
        setStreamingText('')
        toast.success(`✨ 脚本生成完成！共 ${msg.segment_count ?? 0} 个分镜`, { duration: 5000 })
        loadData()
        setView('segments')
      }

      // 整集合成完成
      if (msg.type === 'compose_done') {
        setComposing(false)
        if (msg.output_url) setComposedUrl(msg.output_url)
        toast.success('🎬 整集合成完成！', { duration: 6000 })
        loadData()
      }
    })
    return () => {
      es.close()
      if (streamEndTimerRef.current) clearTimeout(streamEndTimerRef.current)
    }
  }, [epId, loadData])

  // ── 操作处理 ─────────────────────────────────────────────────
  async function handleGenerateScript() {
    if (!ep) return
    if (segments.length > 0) {
      if (!window.confirm('将清空当前所有分镜并重新生成脚本，确定继续？')) return
    }
    if (ep.script_locked) {
      toast.error('剧本已锁定，请先解锁后再重新生成')
      return
    }
    setGeneratingScript(true)
    setStreamingText('')
    setView('script')   // 自动切到剧本编辑tab
    try {
      await episodesApi.generateScript(epId)
      toast('正在生成脚本+分镜，请稍候...', { icon: '⏳', duration: 3000 })
    } catch {
      setGeneratingScript(false)
      toast.error('生成请求失败，请重试')
    }
  }

  async function handleSubmitDrafts() {
    const readyCount = segments.filter(s => s.status === 'prompt_ready').length
    if (readyCount === 0) {
      toast.error('没有状态为「Prompt就绪」的分镜')
      return
    }
    draftProgressRef.current = { done: 0, total: readyCount }
    setDraftProgress({ done: 0, total: readyCount })
    setSubmittingDrafts(true)
    try {
      await segmentsApi.submitDrafts(epId)
      toast.success(`已提交 ${readyCount} 个分镜，草稿生成中...`, { duration: 3000 })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '提交失败'
      toast.error(detail)
    } finally {
      setSubmittingDrafts(false)
    }
  }

  async function handleCompose() {
    setComposing(true)
    try {
      await segmentsApi.compose(epId)
      toast('合成任务已提交...', { icon: '🎬', duration: 3000 })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '合成失败'
      toast.error(detail)
      setComposing(false)
    }
  }

  // ── 统计 ──────────────────────────────────────────────────────
  const doneCount    = segments.filter(s => s.status === 'done').length
  const reviewCount  = segments.filter(s => s.status === 'draft_review').length
  const draftingNow  = segments.some(s => ['drafting', 'draft_pending'].includes(s.status))
  const allDone      = segments.length > 0 && segments.every(s => ['done', 'skipped'].includes(s.status))

  if (!ep) return (
    <div className="min-h-screen flex items-center justify-center text-gray-500">
      <SpinIcon className="w-5 h-5 mr-2" />加载中...
    </div>
  )

  return (
    <div className="min-h-screen flex flex-col">
      {/* 顶部栏 */}
      <header className="border-b border-gray-800 px-6 py-3 flex items-center gap-3 flex-wrap">
        <button className="text-gray-500 hover:text-white text-sm"
          onClick={() => router.push(`/project/${ep.project_id}`)}>← 返回项目</button>
        <span className="text-gray-700">/</span>
        <h1 className="font-semibold">第 {ep.ep_number} 集</h1>
        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">v{ep.script_version}</span>

        <div className="ml-auto flex items-center gap-2 flex-wrap">
          {/* 草稿生成实时进度标签 */}
          {(draftingNow || (submittingDrafts && draftProgress.total > 0)) && (
            <span className="flex items-center gap-1.5 text-xs text-yellow-300 bg-yellow-900/30 px-2.5 py-1 rounded-full">
              <SpinIcon />草稿 {draftProgress.done}/{draftProgress.total}
            </span>
          )}

          {/* 待审核数 */}
          {reviewCount > 0 && (
            <span className="text-xs text-purple-300 bg-purple-900/30 px-2.5 py-1 rounded-full">
              {reviewCount} 待审核
            </span>
          )}

          {segments.length === 0 ? (
            <button className="btn-primary text-sm flex items-center gap-1.5"
              disabled={generatingScript} onClick={handleGenerateScript}>
              {generatingScript ? <><SpinIcon /><span>生成中...</span></> : '✨ 生成脚本+分镜'}
            </button>
          ) : (
            <button className="btn-secondary text-sm flex items-center gap-1.5 text-orange-300 border-orange-800 hover:border-orange-600"
              disabled={generatingScript || submittingDrafts || draftingNow} onClick={handleGenerateScript}>
              {generatingScript ? <><SpinIcon /><span>重新生成中...</span></> : '↺ 重新生成脚本'}
            </button>
          )}

          {/* 草稿批量生成按钮 */}
          {segments.length > 0 && !allDone && (
            <button className="btn-secondary text-sm flex items-center gap-1.5"
              disabled={submittingDrafts || draftingNow} onClick={handleSubmitDrafts}>
              {(submittingDrafts || draftingNow)
                ? <><SpinIcon /><span>草稿生成中...</span></>
                : '📽 批量生成草稿'}
            </button>
          )}

          {/* 合成按钮 */}
          {allDone && (
            <button className="btn-primary text-sm flex items-center gap-1.5"
              disabled={composing} onClick={handleCompose}>
              {composing ? <><SpinIcon /><span>合成中...</span></> : '🎬 合成整集'}
            </button>
          )}

          {/* 合成完成下载链接 */}
          {composedUrl && (
            <a
              href={composedUrl}
              download
              target="_blank"
              rel="noreferrer"
              className="btn-secondary text-sm flex items-center gap-1.5 text-green-300 border-green-800 hover:border-green-600"
            >
              ⬇ 下载整集
            </a>
          )}
        </div>
      </header>

      {/* 本集梗概 */}
      <div className="bg-gray-900/60 border-b border-gray-800 px-6 py-2.5 flex items-start gap-2.5 text-sm">
        <span className="text-gray-500 flex-shrink-0 pt-px">本集梗概</span>
        <p className="text-gray-300 leading-relaxed">{ep.outline}</p>
      </div>

      {/* 视图切换 */}
      <div className="border-b border-gray-800 px-6 flex gap-4">
        {(['segments', 'script'] as const).map(v => (
          <button key={v}
            className={`py-2.5 text-sm border-b-2 transition-colors ${view === v
              ? 'border-brand-500 text-white'
              : 'border-transparent text-gray-500 hover:text-gray-300'}`}
            onClick={() => setView(v)}>
            {v === 'segments'
              ? `分镜 (${doneCount}/${segments.length} 完成)`
              : generatingScript ? '剧本编辑 ●' : '剧本编辑'}
          </button>
        ))}
      </div>


      {/* 主内容 */}
      <div className="flex-1 overflow-y-auto p-6">
        {view === 'segments' && (
          <div className="space-y-3 max-w-3xl mx-auto">
            {segments.length > 0 && <EpisodeTimeline segments={segments} />}

            {segments.length === 0 && !generatingScript && (
              <div className="text-center py-24 text-gray-600">
                <p className="text-lg">还没有分镜</p>
                <p className="text-sm mt-2">点击右上角「✨ 生成脚本+分镜」开始</p>
              </div>
            )}

            {segments.map(seg => (
              <SegmentCard key={seg.id} seg={seg} onUpdate={loadData} />
            ))}
          </div>
        )}
        {view === 'script' && (
          <div className="max-w-3xl mx-auto">
            {generatingScript ? (
              // 生成中：打字机效果
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm text-brand-300">
                  <SpinIcon /><span>AI 正在写剧本...</span>
                </div>
                <div
                  ref={streamBoxRef}
                  className="h-[calc(100vh-260px)] min-h-[300px] overflow-y-auto rounded-lg bg-gray-900 border border-gray-700 p-4 text-sm text-gray-200 whitespace-pre-wrap leading-relaxed font-mono"
                >
                  {streamingText
                    ? <>{streamingText}<span className="inline-block w-[2px] h-[1em] align-text-bottom bg-brand-400 animate-pulse ml-0.5" /></>
                    : <span className="text-gray-600 animate-pulse">等待模型响应...</span>
                  }
                </div>
              </div>
            ) : (
              <ScriptEditor ep={ep} onSaved={loadData} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
