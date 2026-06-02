const API_BASE = ''

export type HttpInit = RequestInit & {
  timeoutMs?: number
  maxAttempts?: number
}

export class HttpError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
}

function stripMarkupBlocks(text: string): string {
  return String(text || '')
    .replace(/<system-reminder\b[^>]*>[\s\S]*?<\/system-reminder>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function mapHttpError(status: number, rawText: string): string {
  const cleaned = stripMarkupBlocks(rawText)
  const low = cleaned.toLowerCase()
  if (status === 401) return '登录状态已失效，请重新登录'
  if (status === 403) return '当前操作无权限执行'
  if (status === 404) return '请求的资源不存在'
  if (status === 405) return '当前操作暂不支持，请稍后重试'
  if (status === 408) return '请求超时，请稍后重试'
  if (status === 429) return '请求过于频繁，请稍后重试'
   if (status >= 500) {
     if (cleaned) return cleaned
     return '服务暂时不可用，请稍后重试'
   }
  if (low === 'method not allowed') return '当前操作暂不支持，请稍后重试'
  return cleaned || `HTTP ${status}`
}

async function readApiError(res: Response): Promise<string> {
  const ct = String(res.headers.get('content-type') || '').toLowerCase()
  if (ct.includes('application/json')) {
    try {
      const j: any = await res.json()
      if (typeof j?.detail === 'string') return mapHttpError(res.status, j.detail)
      const s = JSON.stringify(j)
      if (s && s !== '{}') return mapHttpError(res.status, s)
    } catch {
      // fall through
    }
  }
  const txt = await res.text().catch(() => '')
  const t = String(txt || '').trim()
  if (t) {
    try {
      const j: any = JSON.parse(t)
      if (typeof j?.detail === 'string') return mapHttpError(res.status, j.detail)
      return mapHttpError(res.status, JSON.stringify(j))
    } catch {
      return mapHttpError(res.status, t)
    }
  }
  return `HTTP ${res.status}`
}

async function assertOk(res: Response): Promise<void> {
  if (!res.ok) {
    if (res.status === 401) notifyAuthRequired()
    throw new HttpError(res.status, await readApiError(res))
  }
}

async function readSuccessBody<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T
  const ct = String(res.headers.get('content-type') || '').toLowerCase()
  if (ct.includes('application/json')) {
    return (await res.json()) as T
  }
  const txt = await res.text()
  if (!txt.trim()) return undefined as T
  return txt as T
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function notifyAuthRequired() {
  try {
    window.dispatchEvent(new CustomEvent('chengpian-auth-required'))
  } catch {
    // Ignore auth redirect event failures.
  }
}

export async function http<T>(path: string, init?: HttpInit): Promise<T> {
  const method = String(init?.method || 'GET').toUpperCase()
  const maxAttempts = Math.max(1, init?.maxAttempts ?? (method === 'GET' ? 3 : 1))
  const timeoutMs = Math.max(1000, init?.timeoutMs ?? (method === 'GET' ? 25000 : 15000))

  const headers: Record<string, string> = {}
  if (init?.headers) {
    for (const [k, v] of Object.entries(init.headers as Record<string, string>)) headers[k] = v
  }
  if (init?.body && !(init.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json'
  }

  let lastError: Error | null = null
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        credentials: 'include',
        headers,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!res.ok) {
        if (res.status === 401) notifyAuthRequired()
        const err = new HttpError(res.status, await readApiError(res))
        // 标记 4xx 错误，用于后续判断是否重试
        if (res.status >= 400 && res.status < 500) {
          (err as any).__is4xx = true
        }
        throw err
      }
      return await readSuccessBody<T>(res)
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error) {
        lastError = error.name === 'AbortError' ? new Error('请求超时，请检查网络连接后重试') : error
      } else {
        lastError = new Error('网络请求失败，请稍后重试')
      }
      // 4xx 错误不重试
      if ((error as any)?.__is4xx) {
        throw lastError
      }
      if (attempt < maxAttempts) {
        await delay(250 * attempt)
        continue
      }
    }
  }
  throw lastError || new Error('网络请求失败，请稍后重试')
}

export async function uploadForm<T>(path: string, formData: FormData, timeoutMs = 120000): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
      signal: controller.signal,
    })
    await assertOk(res)
    return await readSuccessBody<T>(res)
  } finally {
    clearTimeout(timer)
  }
}
