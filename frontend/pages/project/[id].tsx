import { useRouter } from 'next/router'
import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { projectsApi, episodesApi, subscribeProjectSSE } from '@/lib/api'

interface Project {
  id: string; title: string; genre: string; tone: string
  total_episodes: number; world_config: Record<string, unknown>
  episode_outlines: Array<{ ep: number; outline: string }>
  story_premise?: string
}
interface Episode {
  ep_id: string; ep_number: number; outline: string
  script_version: number; script_locked: boolean
}
interface OutlineItem { ep: number; outline: string }

export default function ProjectPage() {
  const router = useRouter()
  const id = router.query.id as string
  const [proj, setProj] = useState<Project | null>(null)
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [expandedEp, setExpandedEp] = useState<string | null>(null)
  const [newOutline, setNewOutline] = useState('')
  const [creating, setCreating] = useState(false)
  const [batchGenerating, setBatchGenerating] = useState(false)

  // 大纲生成相关
  const [outlinesGenerating, setOutlinesGenerating] = useState(false)
  const [outlineStreamText, setOutlineStreamText] = useState('')
  const [pendingOutlines, setPendingOutlines] = useState<OutlineItem[] | null>(null)
  const [confirming, setConfirming] = useState(false)
  const streamBoxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([
      projectsApi.get(id).then(r => { setProj(r.data); return r.data }),
      episodesApi.list(id).then(r => { setEpisodes(r.data); return r.data }),
    ]).then(([projData, epsData]) => {
      if (projData?.story_premise && epsData.length === 0) {
        setOutlinesGenerating(true)
      }
    }).catch(() => toast.error('加载失败'))

    const es = subscribeProjectSSE(id, (raw: unknown) => {
      const msg = raw as { type: string; delta?: string; count?: number; outlines?: OutlineItem[] }
      if (msg.type === 'outline_chunk' && msg.delta) {
        setOutlineStreamText(prev => prev + msg.delta)
        // 自动滚动到底部
        setTimeout(() => {
          streamBoxRef.current?.scrollTo({ top: streamBoxRef.current.scrollHeight, behavior: 'smooth' })
        }, 10)
      }
      if (msg.type === 'outlines_ready') {
        setOutlinesGenerating(false)
        setOutlineStreamText('')
        setPendingOutlines(msg.outlines ?? [])
      }
    })
    return () => es.close()
  }, [id])

  async function confirmOutlines() {
    if (!pendingOutlines || pendingOutlines.length === 0) return
    setConfirming(true)
    try {
      await episodesApi.batchCreate(id, pendingOutlines)
      const r = await episodesApi.list(id)
      setEpisodes(r.data)
      setPendingOutlines(null)
      toast.success(`已创建 ${r.data.length} 集，可开始生成脚本`)
    } catch {
      toast.error('创建分集失败')
    } finally {
      setConfirming(false)
    }
  }

  async function addEpisode() {
    if (!newOutline.trim()) return toast.error('请填写本集梗概')
    setCreating(true)
    try {
      const r = await episodesApi.create({ project_id: id, ep_number: episodes.length + 1, outline: newOutline })
      setEpisodes([...episodes, r.data])
      setNewOutline('')
      toast.success('分集已创建')
    } catch { toast.error('创建失败') }
    finally { setCreating(false) }
  }

  async function batchGenerateScripts() {
    if (episodes.length === 0) return toast.error('暂无分集')
    setBatchGenerating(true)
    let ok = 0
    try {
      for (const ep of episodes) {
        try { await episodesApi.generateScript(ep.ep_id); ok++ }
        catch { toast.error(`第 ${ep.ep_number} 集脚本生成失败`) }
      }
      toast.success(`已触发 ${ok} 集脚本生成`)
    } finally { setBatchGenerating(false) }
  }

  if (!proj) return <div className="min-h-screen flex items-center justify-center text-gray-500">加载中...</div>

  return (
    <div className="min-h-screen p-8 max-w-5xl mx-auto">
      {/* 顶部导航 */}
      <div className="flex items-center gap-3 mb-8">
        <button className="text-gray-500 hover:text-white text-sm" onClick={() => router.push('/')}>← 返回</button>
        <span className="text-gray-700">/</span>
        <h1 className="text-2xl font-bold">{proj.title}</h1>
        <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">{proj.genre}</span>
      </div>

      {/* 项目信息 */}
      <div className="card mb-6 flex flex-wrap gap-8 text-sm">
        <div><span className="text-gray-500">基调</span><p className="mt-0.5">{proj.tone}</p></div>
        <div><span className="text-gray-500">共</span><p className="mt-0.5">{proj.total_episodes} 集</p></div>
        {proj.story_premise && (
          <div className="flex-1 min-w-0">
            <span className="text-gray-500">故事主线</span>
            <p className="mt-0.5 text-gray-300 truncate">{proj.story_premise}</p>
          </div>
        )}
        <div className="ml-auto flex gap-2 items-start">
          {episodes.length > 0 && (
            <button className="btn-secondary text-sm" disabled={batchGenerating} onClick={batchGenerateScripts}>
              {batchGenerating ? '生成中...' : '⚡ 一键生成全部脚本'}
            </button>
          )}
          <button className="btn-secondary text-sm" onClick={() => router.push(`/characters/${id}`)}>
            👤 角色图库
          </button>
        </div>
      </div>

      {/* ── 大纲流式生成区域 ───────────────────────────────────── */}
      {(outlinesGenerating || outlineStreamText) && (
        <div className="card mb-6 space-y-3">
          <div className="flex items-center gap-2 text-brand-400 text-sm">
            <span className="inline-block w-3 h-3 rounded-full bg-brand-400 animate-pulse" />
            <span>AI 正在生成分集大纲...</span>
          </div>
          <div
            ref={streamBoxRef}
            className="bg-gray-900 rounded-lg p-4 h-48 overflow-y-auto text-sm text-gray-300 whitespace-pre-wrap font-mono leading-relaxed"
          >
            {outlineStreamText || '等待模型输出...'}
          </div>
        </div>
      )}

      {/* ── 大纲确认区域 ────────────────────────────────────────── */}
      {pendingOutlines && (
        <div className="card mb-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-base">AI 已生成 {pendingOutlines.length} 集大纲，请确认</h3>
            <button className="btn-primary text-sm px-5" disabled={confirming} onClick={confirmOutlines}>
              {confirming ? '创建中...' : '✅ 确认，创建分集'}
            </button>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {pendingOutlines.map(item => (
              <div key={item.ep} className="flex gap-3 p-3 bg-gray-900 rounded-lg text-sm">
                <span className="w-8 h-8 rounded-md bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold flex-shrink-0 text-xs">
                  {item.ep}
                </span>
                <p className="text-gray-300 leading-relaxed">{item.outline}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 分集列表 ───────────────────────────────────────────── */}
      {episodes.length > 0 && (
        <>
          <h2 className="text-lg font-semibold mb-3">分集管理</h2>
          <div className="space-y-2 mb-6">
            {episodes.map(ep => (
              <div key={ep.ep_id} className="card transition-colors hover:border-brand-500/60">
                <div
                  className="flex items-center gap-4 cursor-pointer"
                  onClick={() => setExpandedEp(expandedEp === ep.ep_id ? null : ep.ep_id)}
                >
                <div className="w-10 h-10 rounded-lg bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold flex-shrink-0">
                  {ep.ep_number}
                </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm ${expandedEp === ep.ep_id ? 'whitespace-normal' : 'truncate'}`}>{ep.outline}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      脚本版本 v{ep.script_version} {ep.script_locked ? '🔒 已锁定' : ''}
                    </p>
                  </div>
                  <span className="text-gray-500 text-xs flex-shrink-0 select-none">{expandedEp === ep.ep_id ? '▲' : '▼'}</span>
                </div>
                {expandedEp === ep.ep_id && (
                  <div className="mt-3 pt-3 border-t border-gray-800 flex justify-end">
                    <button className="btn-primary text-sm px-5" onClick={() => router.push(`/episode/${ep.ep_id}`)}>进入编辑 →</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── 手动添加分集 ───────────────────────────────────────── */}
      {!outlinesGenerating && !pendingOutlines && (
        <div className="card space-y-3">
          <h3 className="font-medium text-sm text-gray-400">手动添加分集</h3>
          <textarea className="textarea" rows={3}
            placeholder={`第 ${episodes.length + 1} 集梗概，如：林战重返公司，被陈总当众羞辱，决意复仇`}
            value={newOutline} onChange={e => setNewOutline(e.target.value)} />
          <button className="btn-primary w-full" disabled={creating} onClick={addEpisode}>
            {creating ? '创建中...' : `+ 添加第 ${episodes.length + 1} 集`}
          </button>
        </div>
      )}
    </div>
  )
}
