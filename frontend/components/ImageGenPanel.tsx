import { useState } from 'react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { charactersApi } from '@/lib/api'

interface Props {
  charId: string
  onClose: (submitted?: boolean) => void
}

export default function ImageGenPanel({ charId, onClose }: Props) {
  const [mode, setMode] = useState<'t2i' | 'i2i' | 'upload'>('t2i')
  const [prompt, setPrompt] = useState('')
  const [refFile, setRefFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'image/*': [] },
    maxFiles: 1,
    onDrop: files => setRefFile(files[0] ?? null),
  })

  async function handleUpload() {
    if (!refFile) return toast.error('请先选择图片')
    setUploading(true)
    try {
      await charactersApi.uploadImage(charId, refFile)
      toast.success('图片上传成功')
      onClose(false)
    } catch { toast.error('上传失败') }
    finally { setUploading(false) }
  }

  async function handleGenerate() {
    if (mode === 't2i' && !prompt.trim()) return toast.error('请填写角色外貌描述')
    if (mode === 'i2i' && !refFile) return toast.error('请上传参考图')
    setGenerating(true)
    try {
      if (mode === 'i2i' && refFile) {
        // 先上传参考图获取路径，再生图
        const uploadResp = await charactersApi.uploadImage(charId, refFile)
        await charactersApi.generateImage(charId, {
          mode: 'i2i',
          prompt,
          ref_image_path: uploadResp.data.url,
        })
      } else {
        await charactersApi.generateImage(charId, { mode: 't2i', prompt })
      }
      toast.success('生图任务已提交，完成后自动刷新页面')
      onClose(true)
    } catch { toast.error('生图失败') }
    finally { setGenerating(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="card w-full max-w-md space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">添加角色图片</h2>
          <button className="text-gray-500 hover:text-white" onClick={() => onClose(false)}>✕</button>
        </div>

        {/* 方式选择 */}
        <div className="flex gap-2">
          {([
            { key: 't2i',   label: '文生图' },
            { key: 'i2i',   label: '图生图' },
            { key: 'upload', label: '本地上传' },
          ] as const).map(o => (
            <button key={o.key}
              className={`flex-1 py-1.5 text-sm rounded-lg border transition-colors ${mode === o.key ? 'border-brand-500 bg-brand-500/20 text-brand-300' : 'border-gray-700 text-gray-400 hover:border-gray-600'}`}
              onClick={() => setMode(o.key)}>
              {o.label}
            </button>
          ))}
        </div>

        {/* 上传/参考图区域 */}
        {(mode === 'upload' || mode === 'i2i') && (
          <div {...getRootProps()} className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${isDragActive ? 'border-brand-500 bg-brand-500/10' : 'border-gray-700 hover:border-gray-500'}`}>
            <input {...getInputProps()} />
            {refFile ? (
              <p className="text-sm text-green-400">✓ {refFile.name}</p>
            ) : (
              <p className="text-sm text-gray-500">拖拽图片到此，或点击选择</p>
            )}
          </div>
        )}

        {/* Prompt 输入（文生图 / 图生图辅助描述） */}
        {mode !== 'upload' && (
          <textarea className="textarea" rows={4}
            placeholder={mode === 't2i'
              ? '描述角色外貌，如：25岁中国男性，黑发，方形下颌，深色西装，眼神冷静，纯白背景'
              : '（可选）额外描述风格迁移方向，如：统一动漫写实风，保持服装一致'}
            value={prompt} onChange={e => setPrompt(e.target.value)} />
        )}

        {/* 建议文字 */}
        <p className="text-xs text-gray-600">💡 建议纯白背景，Seedance API 识别更准确</p>

        {/* 操作按钮 */}
        <div className="flex gap-2">
          <button className="btn-secondary flex-1" onClick={() => onClose(false)}>取消</button>
          {mode === 'upload' ? (
            <button className="btn-primary flex-1" disabled={uploading} onClick={handleUpload}>
              {uploading ? '上传中...' : '上传'}
            </button>
          ) : (
            <button className="btn-primary flex-1" disabled={generating} onClick={handleGenerate}>
              {generating ? '生图中...' : '生成'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
