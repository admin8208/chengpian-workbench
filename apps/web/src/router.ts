import { createRouter, createWebHistory } from 'vue-router'
import { fetchAuthStatus, readCachedAuthStatus } from './api'
import { HttpError } from './api/http'

const AUTH_BOOT_HTTP = {
  timeoutMs: 3000,
  maxAttempts: 1,
}

const LoginView = () => import('./views/auth/LoginView.vue')
const AiProjectView = () => import('./features/project-workbench/pages/AiProjectView.vue')
const NetworkProjectView = () => import('./features/project-workbench/pages/NetworkProjectView.vue')
const ProjectModeResolverView = () => import('./views/creator/shared/ProjectModeResolverView.vue')
const SettingsView = () => import('./views/system/settings/SettingsView.vue')
const HealthView = () => import('./views/system/HealthView.vue')
const JobsView = () => import('./views/system/JobsView.vue')
const LibraryView = () => import('./views/system/LibraryView.vue')
const VideoToAudioView = () => import('./views/tools/VideoToAudioView.vue')
const NotFoundView = () => import('./views/shared/NotFoundView.vue')
const RecentProjectsView = () => import('./views/project/RecentProjectsView.vue')
const AiCreatorCenterView = () => import('./views/creator/ai/AiCreatorCenterView.vue')
const NetworkCreatorCenterView = () => import('./views/creator/network/NetworkCreatorCenterView.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { title: '登录', public: true } },
    { path: '/', redirect: '/creator/ai' },
    { path: '/creator', redirect: '/creator/ai' },
    { path: '/creator/ai', name: 'creatorAi', component: AiCreatorCenterView, meta: { title: '智能创作' } },
    { path: '/creator/network', name: 'creatorNetwork', component: NetworkCreatorCenterView, meta: { title: '素材创作' } },
    { path: '/recent', name: 'recentProjects', component: RecentProjectsView, meta: { title: '项目中心' } },
    { path: '/p/mix/:id', name: 'mixProject', component: ProjectModeResolverView, props: true, meta: { title: '项目分流中' } },
    { path: '/p/ai/:id', name: 'aiProject', component: AiProjectView, props: true, meta: { title: '智能创作工作流' } },
    { path: '/p/network/:id', name: 'networkProject', component: NetworkProjectView, props: true, meta: { title: '素材创作工作流' } },

    { path: '/library', name: 'library', component: LibraryView, meta: { title: '素材库' } },
    { path: '/video-audio', name: 'videoAudio', component: VideoToAudioView, meta: { title: '视频转音频' } },
    { path: '/jobs', name: 'jobs', component: JobsView, meta: { title: '任务中心' } },
    { path: '/settings', name: 'settings', component: SettingsView, meta: { title: '设置' } },
    { path: '/health', name: 'health', component: HealthView, meta: { title: '健康检查' } },

    { path: '/:pathMatch(.*)*', name: 'notFound', component: NotFoundView, meta: { title: '页面不存在' } },
  ],
})

router.beforeEach(async (to) => {
  const isPublic = Boolean(to.meta.public)
  const cachedStatus = readCachedAuthStatus()
  if (cachedStatus) {
    if (cachedStatus.setup_required) {
      if (to.name === 'login') return true
      return { name: 'login', query: { next: to.fullPath } }
    }
    if (!cachedStatus.authenticated && !isPublic) {
      return { name: 'login', query: { next: to.fullPath } }
    }
    if (cachedStatus.authenticated && to.name === 'login') {
      const next = typeof to.query.next === 'string' && to.query.next.startsWith('/') ? to.query.next : '/creator/ai'
      return next
    }
    void fetchAuthStatus(AUTH_BOOT_HTTP).catch(() => {})
    return true
  }

  let status
  try {
    status = await fetchAuthStatus(AUTH_BOOT_HTTP)
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) {
      if (isPublic) return true
      return { name: 'login', query: { next: to.fullPath } }
    }
    if (isPublic) return true
    return true
  }

  if (status.setup_required) {
    if (to.name === 'login') return true
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (!status.authenticated && !isPublic) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (status.authenticated && to.name === 'login') {
    const next = typeof to.query.next === 'string' && to.query.next.startsWith('/') ? to.query.next : '/creator/ai'
    return next
  }
  return true
})
