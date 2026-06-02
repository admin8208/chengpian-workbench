import { createApp } from 'vue'
import './style.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'animate.css'
import App from './App.vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import { router } from './router'
import { clearCachedAuthStatus } from './api'

function mountFatalFallback(message: string) {
  const el = document.getElementById('app')
  if (!el) return
  el.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;background:#f8fafc;color:#0f172a;font-family:Arial,sans-serif;">
      <div style="max-width:720px;width:100%;background:#fff;border:1px solid rgba(15,23,42,0.08);border-radius:16px;padding:24px;box-shadow:0 10px 24px rgba(15,23,42,0.08);">
        <div style="font-size:20px;font-weight:700;">成片工作台加载失败</div>
        <div style="margin-top:12px;line-height:1.6;">${String(message || '页面出现异常，请刷新后重试。')}</div>
      </div>
    </div>
  `
}

function reportAppError(message: string) {
  const detail = { message: String(message || '页面出现异常，请刷新后重试。') }
  try {
    window.dispatchEvent(new CustomEvent('chengpian-app-error', { detail }))
  } catch {
    mountFatalFallback(detail.message)
  }
}

try {
  window.addEventListener('error', (event) => {
    const err = event.error
    const message = err instanceof Error ? err.message : event.message
    reportAppError(message)
  })
} catch {
  // Ignore global error binding failures and rely on mount fallback.
}

try {
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    const message = reason instanceof Error ? reason.message : String(reason || '发生未处理异常')
    reportAppError(message)
  })
} catch {
  // Ignore global rejection binding failures and rely on mount fallback.
}

try {
  const app = createApp(App)

  app.config.errorHandler = (err, _instance, info) => {
    const detail = info ? ` (${info})` : ''
    const message = err instanceof Error ? `${err.message}${detail}` : `${String(err)}${detail}`
    console.error(err)
    reportAppError(message)
  }

  router.onError((err) => {
    console.error(err)
    reportAppError(err instanceof Error ? err.message : String(err))
  })

  window.addEventListener('chengpian-auth-required', () => {
    clearCachedAuthStatus()
    const next = router.currentRoute.value.fullPath
    const query = next && next !== '/login' ? { next } : undefined
    router.replace({ path: '/login', query }).catch(() => {})
  })

  app.use(router).use(ElementPlus, { locale: zhCn }).mount('#app')
} catch (err) {
  console.error(err)
  mountFatalFallback(err instanceof Error ? err.message : String(err))
}
