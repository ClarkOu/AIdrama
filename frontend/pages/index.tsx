import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import toast from 'react-hot-toast'
import { projectsApi } from '@/lib/api'

interface Project {
  id: string
  title: string
  genre: string
  tone: string
  total_episodes: number
  created_at: string
}

export default function Home() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ title: '', genre: '', tone: '', story_premise: '', total_episodes: 6 })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    projectsApi.list().then(r => setProjects(r.data)).catch(() => toast.error('加载项目失败'))
  }, [])

  async function handleCreate() {
    if (!form.title.trim()) return toast.error('请填写剧名')
    setLoading(true)
    try {
      const r = await projectsApi.create(form)
      router.push(`/project/${r.data.id}`)
    } catch {
      toast.error('创建失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-10">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">🎬 AIdrama</h1>
          <p className="text-gray-400 mt-1">AI 短剧自动生成工具</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          + 新建项目
        </button>
      </div>

      {/* 项目列表 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map(p => (
          <div
            key={p.id}
            className="card cursor-pointer hover:border-brand-500 transition-colors"
            onClick={() => router.push(`/project/${p.id}`)}
          >
            <div className="flex items-start justify-between">
              <h2 className="font-semibold text-lg">{p.title}</h2>
              <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">{p.genre}</span>
            </div>
            <p className="text-gray-400 text-sm mt-2 line-clamp-2">{p.tone}</p>
            <div className="flex items-center justify-between mt-4 text-xs text-gray-500">
              <span>共 {p.total_episodes} 集</span>
              <span>{p.created_at?.slice(0, 10)}</span>
            </div>
          </div>
        ))}

        {projects.length === 0 && (
          <div className="col-span-3 text-center py-24 text-gray-600">
            还没有项目，点击「新建项目」开始创作
          </div>
        )}
      </div>

      {/* 新建弹窗 */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="card w-full max-w-md space-y-4">
            <h2 className="text-xl font-semibold">新建项目</h2>
            <div className="space-y-3">
              <input className="input" placeholder="剧名（必填）" value={form.title}
                onChange={e => setForm({ ...form, title: e.target.value })} />
              <input className="input" placeholder="类型，如：都市爽文" value={form.genre}
                onChange={e => setForm({ ...form, genre: e.target.value })} />
              <input className="input" placeholder="基调，如：压抑→反转→爽感" value={form.tone}
                onChange={e => setForm({ ...form, tone: e.target.value })} />
              <textarea className="textarea" rows={3}
                placeholder="故事主线（选填）：填写后自动生成所有集梗概，如：林战被前公司陷害入狱3年，出狱后携带神秘系统复仇，最终成为商界传奇"
                value={form.story_premise}
                onChange={e => setForm({ ...form, story_premise: e.target.value })} />
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-400 whitespace-nowrap">共几集</label>
                <input className="input" type="number" min={1} max={100} value={form.total_episodes}
                  onChange={e => setForm({ ...form, total_episodes: Number(e.target.value) })} />
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <button className="btn-secondary" onClick={() => setShowCreate(false)}>取消</button>
              <button className="btn-primary" disabled={loading} onClick={handleCreate}>
                {loading ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
