import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── 项目 ────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get('/projects'),
  get:  (id: string) => api.get(`/projects/${id}`),
  create: (data: object) => api.post('/projects', data),
  update: (id: string, data: object) => api.patch(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
}

// ── 角色 ────────────────────────────────────────────────────────
export const charactersApi = {
  list:    (projectId: string) => api.get(`/characters/project/${projectId}`),
  get:     (id: string) => api.get(`/characters/${id}`),
  create:  (data: object) => api.post('/characters', data),
  update:  (id: string, data: object) => api.patch(`/characters/${id}`, data),
  delete:  (id: string) => api.delete(`/characters/${id}`),
  uploadImage: (charId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/characters/${charId}/upload-image`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  generateImage: (charId: string, data: { mode: string; prompt?: string; ref_image_path?: string }) =>
    api.post(`/characters/${charId}/generate-image`, data),
  setPrimaryImage: (charId: string, index: number) =>
    api.post(`/characters/${charId}/images/${index}/set-primary`),
  deleteImage: (charId: string, index: number) =>
    api.delete(`/characters/${charId}/images/${index}`),
}

// ── 分集 ────────────────────────────────────────────────────────
export const episodesApi = {
  list:           (projectId: string) => api.get(`/episodes/project/${projectId}`),
  get:            (id: string) => api.get(`/episodes/${id}`),
  create:         (data: object) => api.post('/episodes', data),
  batchCreate:    (projectId: string, outlines: Array<{ep: number; outline: string}>) =>
    api.post(`/episodes/project/${projectId}/batch`, { outlines }),
  generateScript: (epId: string) => api.post(`/episodes/${epId}/generate-script`),
  editScript:     (epId: string, newText: string) =>
    api.patch(`/episodes/${epId}/script`, { new_script_text: newText }),
}

// ── 分镜 ────────────────────────────────────────────────────────
export const segmentsApi = {
  list:          (epId: string) => api.get(`/segments/episode/${epId}`),
  get:           (id: string) => api.get(`/segments/${id}`),
  update:        (id: string, data: object) => api.patch(`/segments/${id}`, data),
  reorder:       (epId: string, orderedIds: string[]) =>
    api.post(`/segments/episode/${epId}/reorder`, { ordered_ids: orderedIds }),
  submitDrafts:      (epId: string)  => api.post(`/segments/episode/${epId}/submit-drafts`),
  submitSingleDraft: (segId: string) => api.post(`/segments/${segId}/submit-draft`),
  approveDraft:      (segId: string) => api.post(`/segments/${segId}/approve-draft`),
  rejectDraft:   (segId: string) => api.post(`/segments/${segId}/reject-draft`),
  skip:          (segId: string) => api.post(`/segments/${segId}/skip`),
  compose:       (epId: string) => api.post(`/segments/episode/${epId}/compose`),
}

// ── SSE 辅助 ─────────────────────────────────────────────────────
// Next.js rewrites 会缓冲 streaming 响应，SSE 必须直连后端
const SSE_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'

export function subscribeEpisodeSSE(epId: string, onMessage: (data: object) => void) {
  const es = new EventSource(`${SSE_BASE}/api/sse/${epId}`)
  es.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch { /* ignore heartbeat */ }
  }
  return es
}

export function subscribeProjectSSE(projId: string, onMessage: (data: object) => void) {
  const es = new EventSource(`${SSE_BASE}/api/sse/project/${projId}`)
  es.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch { /* ignore heartbeat */ }
  }
  return es
}
