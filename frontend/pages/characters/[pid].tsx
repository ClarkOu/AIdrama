import { useRouter } from 'next/router'
import { useEffect, useState, useCallback } from 'react'
import toast from 'react-hot-toast'
import { charactersApi, subscribeProjectSSE } from '@/lib/api'
import CharacterCard from '@/components/CharacterCard'
import ImageGenPanel from '@/components/ImageGenPanel'

interface Character {
  id: string; name: string; fixed_desc: string
  aliases: string[]; ref_images: Array<{ url: string; source: string; is_primary: boolean }>
}

export default function CharactersPage() {
  const router = useRouter()
  const pid = router.query.pid as string
  const [chars, setChars] = useState<Character[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [showGen, setShowGen] = useState<string | null>(null)  // char_id
  const [form, setForm] = useState({ name: '', fixed_desc: '', aliases: '' })
  // 正在生成图片的角色 id 集合
  const [generatingChars, setGeneratingChars] = useState<Set<string>>(new Set())

  const load = useCallback(() => {
    if (!pid) return
    charactersApi.list(pid).then(r => setChars(r.data)).catch(() => toast.error('加载失败'))
  }, [pid])

  useEffect(() => { load() }, [load])

  // ── 项目级 SSE：监听图片生成完成 ────────────────────────────
  useEffect(() => {
    if (!pid) return
    const es = subscribeProjectSSE(pid, (raw: unknown) => {
      const msg = raw as { type: string; char_id?: string; char_name?: string }
      if (msg.type === 'image_done') {
        const charId = msg.char_id ?? ''
        setGeneratingChars(prev => {
          const next = new Set(prev)
          next.delete(charId)
          return next
        })
        toast.success(`🎨 ${msg.char_name || '角色'}图片生成完成！`, { duration: 4000 })
        load()
      }
    })
    return () => es.close()
  }, [pid, load])

  async function handleCreate() {
    if (!form.name.trim() || !form.fixed_desc.trim()) return toast.error('姓名和形象描述为必填')
    try {
      await charactersApi.create({
        project_id: pid,
        name: form.name,
        fixed_desc: form.fixed_desc,
        aliases: form.aliases.split('，').filter(Boolean),
      })
      setForm({ name: '', fixed_desc: '', aliases: '' })
      setShowCreate(false)
      load()
      toast.success('角色已创建')
    } catch { toast.error('创建失败') }
  }

  // 点击「生成」时把该角色加入进行中集合
  function handleGenImage(charId: string) {
    setShowGen(charId)
  }

  function handleGenPanelClose(submitted: boolean, charId: string) {
    setShowGen(null)
    if (submitted) {
      setGeneratingChars(prev => { const next = new Set(prev); next.add(charId); return next })
      toast('图片生成中，完成后自动刷新...', { icon: '🎨', duration: 3000 })
    }
    load()
  }

  return (
    <div className="min-h-screen p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <button className="text-gray-500 hover:text-white text-sm"
          onClick={() => router.push(`/project/${pid}`)}>← 返回项目</button>
        <span className="text-gray-700">/</span>
        <h1 className="text-2xl font-bold">角色图库</h1>
      </div>

      <div className="flex justify-end mb-4">
        <button className="btn-primary" onClick={() => setShowCreate(true)}>+ 添加角色</button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {chars.map(c => (
          <CharacterCard
            key={c.id}
            char={c}
            isGenerating={generatingChars.has(c.id)}
            onGenImage={() => handleGenImage(c.id)}
            onRefresh={load}
          />
        ))}
        {chars.length === 0 && (
          <div className="col-span-3 text-center py-20 text-gray-600">
            还没有角色，先添加角色再生成图片
          </div>
        )}
      </div>

      {/* 创建弹窗 */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="card w-full max-w-md space-y-3">
            <h2 className="text-lg font-semibold">添加角色</h2>
            <input className="input" placeholder="角色姓名（全局唯一 Key）" value={form.name}
              onChange={e => setForm({ ...form, name: e.target.value })} />
            <textarea className="textarea" rows={3}
              placeholder="形象描述，如：25岁黑发男，方形下颌，深色西装，眼神冷静"
              value={form.fixed_desc} onChange={e => setForm({ ...form, fixed_desc: e.target.value })} />
            <input className="input" placeholder="别名（用中文顿号分隔，如：男主、主角）"
              value={form.aliases} onChange={e => setForm({ ...form, aliases: e.target.value })} />
            <div className="flex gap-2 justify-end">
              <button className="btn-secondary" onClick={() => setShowCreate(false)}>取消</button>
              <button className="btn-primary" onClick={handleCreate}>创建</button>
            </div>
          </div>
        </div>
      )}

      {/* AI 生图面板 */}
      {showGen && (
        <ImageGenPanel
          charId={showGen}
          onClose={(submitted?: boolean) => handleGenPanelClose(!!submitted, showGen)}
        />
      )}
    </div>
  )
}
