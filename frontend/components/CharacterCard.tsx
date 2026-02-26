import Image from 'next/image'
import { useState } from 'react'
import toast from 'react-hot-toast'
import { charactersApi } from '@/lib/api'

interface RefImage { url: string; source: string; is_primary: boolean }
interface Character {
  id: string; name: string; fixed_desc: string
  aliases: string[]; ref_images: RefImage[]
}

export default function CharacterCard({
  char,
  onGenImage,
  onRefresh,
  isGenerating = false,
}: {
  char: Character
  onGenImage: () => void
  onRefresh: () => void
  isGenerating?: boolean
}) {
  const [deleting, setDeleting] = useState(false)
  const [imgWorking, setImgWorking] = useState<number | null>(null)
  const primaryImg = char.ref_images?.find(i => i.is_primary) ?? char.ref_images?.[0]

  async function handleDelete() {
    if (!confirm(`确定删除角色「${char.name}」？`)) return
    setDeleting(true)
    try {
      await charactersApi.delete(char.id)
      toast.success('已删除')
      onRefresh()
    } catch { toast.error('删除失败') }
    finally { setDeleting(false) }
  }

  async function handleSetPrimary(index: number) {
    setImgWorking(index)
    try {
      await charactersApi.setPrimaryImage(char.id, index)
      onRefresh()
    } catch { toast.error('操作失败') }
    finally { setImgWorking(null) }
  }

  async function handleDeleteImage(index: number) {
    setImgWorking(index)
    try {
      await charactersApi.deleteImage(char.id, index)
      onRefresh()
    } catch { toast.error('删除失败') }
    finally { setImgWorking(null) }
  }

  return (
    <div className="card space-y-3">
      {/* 主图 */}
      <div className="aspect-[3/4] bg-gray-800 rounded-lg overflow-hidden relative">
        {isGenerating && (
          <div className="absolute inset-0 z-10 bg-black/60 flex flex-col items-center justify-center gap-2">
            <svg className="animate-spin w-8 h-8 text-brand-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span className="text-xs text-gray-300">图片生成中...</span>
          </div>
        )}
        {primaryImg ? (
          <Image
            src={primaryImg.url}
            alt={char.name}
            fill
            className="object-cover"
            unoptimized={primaryImg.url.startsWith('http://localhost')}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600 gap-2">
            <span className="text-4xl">👤</span>
            <p className="text-xs">暂无图片</p>
          </div>
        )}
        {char.ref_images?.length > 0 && (
          <span className="absolute bottom-2 right-2 text-xs bg-black/70 text-gray-300 px-1.5 py-0.5 rounded">
            {char.ref_images.length} 张
          </span>
        )}
      </div>

      {/* 多图缩略条 */}
      {char.ref_images?.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {char.ref_images.map((img, idx) => (
            <div key={idx} className="relative flex-shrink-0 w-12 h-16 bg-gray-800 rounded overflow-hidden group">
              <Image
                src={img.url}
                alt={`img-${idx}`}
                fill
                className="object-cover"
                unoptimized={img.url.startsWith('http://localhost')}
              />
              {/* 主图标记 */}
              {img.is_primary && (
                <span className="absolute top-0.5 left-0.5 text-xs leading-none">⭐</span>
              )}
              {/* 操作按钮 */}
              {imgWorking === idx ? (
                <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                  <span className="text-xs text-gray-300">...</span>
                </div>
              ) : (
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition flex flex-col items-center justify-center gap-0.5 opacity-0 group-hover:opacity-100">
                  {!img.is_primary && (
                    <button
                      onClick={() => handleSetPrimary(idx)}
                      title="设为主图"
                      className="text-xs bg-yellow-500/80 hover:bg-yellow-400 text-black px-1 py-0.5 rounded leading-none"
                    >
                      主图
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteImage(idx)}
                    title="删除此图"
                    className="text-xs bg-red-600/80 hover:bg-red-500 text-white px-1 py-0.5 rounded leading-none"
                  >
                    删除
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 信息 */}
      <div>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">{char.name}</h3>
          {char.aliases?.length > 0 && (
            <span className="text-xs text-gray-500">{char.aliases.join(' / ')}</span>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{char.fixed_desc}</p>
      </div>

      {/* 操作 */}
      <div className="flex gap-2">
        <button className="btn-secondary text-xs flex-1 py-1.5" onClick={onGenImage} disabled={isGenerating}>
          {isGenerating ? '生成中...' : '+ 添加图片'}
        </button>
        <button className="text-xs text-red-600 hover:text-red-400 px-2" disabled={deleting}
          onClick={handleDelete}>
          {deleting ? '...' : '删除'}
        </button>
      </div>
    </div>
  )
}
