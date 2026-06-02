<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElIcon, ElTooltip, ElAlert } from 'element-plus'
import { Sunny, Moon, PictureFilled, Setting, Monitor, Clock, FolderOpened, Tickets, VideoPlay, Files } from '@element-plus/icons-vue'
import { api } from './api/index'
import { clearCachedAuthStatus } from './api'

const globalError = ref('')

const route = useRoute()
const router = useRouter()

const isDark = ref(false)
const authBusy = ref(false)

function applyDarkClass(next: boolean) {
  try {
    document.documentElement.classList.toggle('dark', next)
  } catch {
    // Ignore DOM class sync failures.
  }
}

function readInitialDarkMode() {
  try {
    const saved = window.localStorage.getItem('chengpian-dark')
    if (saved === '1') return true
    if (saved === '0') return false
  } catch {
    // Ignore localStorage access failures.
  }
  try {
    return !!window.matchMedia?.('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

function toggleDark() {
  isDark.value = !isDark.value
  applyDarkClass(isDark.value)
  try {
    window.localStorage.setItem('chengpian-dark', isDark.value ? '1' : '0')
  } catch {
    // Ignore localStorage write failures.
  }
}

function handleGlobalError(event: Event) {
  const detail = (event as CustomEvent<{ message?: string }>).detail
  globalError.value = String(detail?.message || '页面出现异常，请刷新后重试。')
}

const isAuthPage = computed(() => route.path === '/login')

async function logout() {
  if (authBusy.value) return
  authBusy.value = true
  try {
    await api.authLogout()
  } catch {
    // Ignore logout API failures and force navigation back to login.
  } finally {
    clearCachedAuthStatus()
    authBusy.value = false
  }
  await router.replace({ path: '/login' })
}

const navItems = [
  { path: '/creator/ai', title: '智能创作', hint: '智能出图', icon: PictureFilled },
  { path: '/creator/network', title: '素材创作', hint: '自动匹配素材', icon: Files },
  { path: '/recent', title: '项目中心', hint: '项目列表', icon: Clock },
  { path: '/jobs', title: '任务中心', hint: '全局执行', icon: Tickets },
  { path: '/library', title: '素材库', hint: '公共素材', icon: FolderOpened },
  { path: '/video-audio', title: '视频转音频', hint: '提取音轨', icon: VideoPlay },
  { path: '/health', title: '健康检查', hint: '运行状态', icon: Monitor },
  { path: '/settings', title: '设置', hint: '系统配置', icon: Setting },
]

onMounted(() => {
  isDark.value = readInitialDarkMode()
  applyDarkClass(isDark.value)
  window.addEventListener('chengpian-app-error', handleGlobalError as EventListener)
})

onUnmounted(() => {
  window.removeEventListener('chengpian-app-error', handleGlobalError as EventListener)
})
</script>

<template>
  <router-view v-if="isAuthPage" />

  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand" @click="$router.push('/creator/ai')">
        <div class="brandMark"></div>
        <div>
          <div class="brandTitle">成片工作台</div>
          <div class="brandSub">智能/素材双工作台</div>
        </div>
      </div>

      <nav class="nav">
        <ul class="nav-list">
          <li v-for="item in navItems" :key="item.path">
            <router-link
              :to="item.path"
              class="navLink"
            >
              <div class="navItem" :class="{ active: $route.path.startsWith(item.path) }">
                <div class="navItemLeft">
                  <ElIcon class="navIcon"><component :is="item.icon" /></ElIcon>
                  <span>{{ item.title }}</span>
                </div>
                <span class="navHint">{{ item.hint }}</span>
              </div>
            </router-link>
          </li>
        </ul>
      </nav>

      <div class="sidebar-footer">
        <button class="logout-btn" :disabled="authBusy" @click="logout">退出登录</button>
        <ElTooltip :content="isDark ? '切换到浅色模式' : '切换到深色模式'" placement="right">
          <button class="theme-toggle" @click="toggleDark()">
            <ElIcon size="18">
              <Sunny v-if="isDark" />
              <Moon v-else />
            </ElIcon>
          </button>
        </ElTooltip>
      </div>
    </aside>

    <div class="main">
      <main class="page">
        <ElAlert
          v-if="globalError"
          type="error"
          :title="globalError"
          show-icon
          closable
          @close="globalError = ''"
          style="margin-bottom: 16px"
        />
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 6px 12px;
  cursor: pointer;
  user-select: none;
}

.logout-btn {
  width: 100%;
  margin-bottom: 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--ink);
  padding: 10px 12px;
  cursor: pointer;
}

html.dark .logout-btn {
  background: rgba(15, 23, 42, 0.68);
}

.logout-btn:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.brandMark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: radial-gradient(12px 12px at 30% 30%, rgba(255, 255, 255, 0.95), transparent 55%),
    linear-gradient(135deg, rgba(29, 78, 216, 0.98), rgba(15, 118, 110, 0.88));
  box-shadow: 0 14px 28px rgba(29, 78, 216, 0.2);
}

.brandTitle {
  font-size: 16px;
  font-weight: 880;
  letter-spacing: -0.02em;
}

.brandSub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--ink-faint);
}

.nav {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  overflow-y: auto;
}

.navLink {
  text-decoration: none;
  color: inherit;
  display: block;
}

.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.nav-list li {
  margin: 0;
  padding: 0;
}

.navItem {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--line);
  color: var(--ink);
  transition: all 160ms ease;
}

.navItem:last-child {
  border-bottom: none;
}

.navItem:hover {
  background: rgba(255, 255, 255, 0.68);
}

html.dark .navItem:hover {
  background: rgba(30, 41, 59, 0.68);
}

.navItem.active {
  background: linear-gradient(180deg, rgba(29, 78, 216, 0.12), rgba(15, 118, 110, 0.08));
  border-left: 3px solid #1d4ed8;
}

.navItemLeft {
  display: flex;
  align-items: center;
  gap: 8px;
}

.navIcon {
  font-size: 16px;
}

.navHint {
  font-size: 11px;
  color: var(--ink-faint);
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px;
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: center;
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  transition: all 160ms ease;
}

.theme-toggle:hover {
  background: rgba(255, 255, 255, 0.68);
}

html.dark .theme-toggle {
  background: rgba(30, 41, 59, 0.8);
}

html.dark .theme-toggle:hover {
  background: rgba(30, 41, 59, 1);
}
</style>
