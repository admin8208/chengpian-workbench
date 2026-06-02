<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, clearCachedAuthStatus, fetchAuthStatus, writeCachedAuthStatus, type AuthStatus } from '../../api'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const saving = ref(false)
const err = ref('')
const info = ref('')
const status = ref<AuthStatus | null>(null)

const username = ref('admin')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)

const AUTH_BOOT_HTTP = {
  timeoutMs: 3000,
  maxAttempts: 1,
}

const setupMode = computed(() => Boolean(status.value?.setup_required))
const submitLabel = computed(() => (setupMode.value ? '创建管理员并登录' : '登录'))
const nextPath = computed(() => {
  const next = typeof route.query.next === 'string' ? route.query.next : ''
  return next && next.startsWith('/') ? next : '/creator/ai'
})

async function loadStatus() {
  loading.value = true
  err.value = ''
  try {
    const next = await fetchAuthStatus(AUTH_BOOT_HTTP, { force: true })
    status.value = next
    if (next.authenticated) {
      await router.replace(nextPath.value)
      return
    }
    if (!next.setup_required) username.value = ''
  } catch (error) {
    err.value = error instanceof Error ? error.message : '认证状态读取失败'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (saving.value) return
  err.value = ''
  info.value = ''
  if (!username.value.trim()) {
    err.value = '请输入用户名'
    return
  }
  if (!password.value) {
    err.value = '请输入密码'
    return
  }
  if (setupMode.value && password.value !== confirmPassword.value) {
    err.value = '两次输入的密码不一致'
    return
  }
  saving.value = true
  try {
    const body = { username: username.value.trim(), password: password.value }
    const next = setupMode.value ? await api.authSetup(body) : await api.authLogin(body)
    status.value = writeCachedAuthStatus(next)
    info.value = setupMode.value ? '管理员账号已创建，正在进入系统…' : '登录成功，正在进入系统…'
    await router.replace(nextPath.value)
  } catch (error) {
    clearCachedAuthStatus()
    err.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    saving.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="loginPage">
    <section class="loginCard card">
      <div class="loginBrand">成片工作台</div>
      <div class="loginTitle">{{ setupMode ? '初始化管理员账号' : '登录系统' }}</div>
      <div class="softItem muted" style="margin-top: 12px; line-height: 1.5">
        {{ setupMode ? '这是首次启用。先创建一个管理员账号，之后所有操作都需要登录。' : '登录后才能访问项目、任务、设置和素材文件。' }}
      </div>

      <div v-if="loading" class="softItem muted" style="margin-top: 16px">正在检查登录状态…</div>

      <template v-else>
        <div v-if="info" class="softItem" style="margin-top: 16px; color: var(--ok)">{{ info }}</div>
        <div v-if="err" class="softItem" style="margin-top: 16px; color: var(--danger)">{{ err }}</div>

        <div class="loginForm">
          <label class="loginLabel">用户名</label>
          <input v-model="username" class="loginInput" type="text" autocomplete="username" placeholder="请输入管理员用户名" />

          <label class="loginLabel">密码</label>
          <input v-model="password" class="loginInput" :type="showPassword ? 'text' : 'password'" :autocomplete="setupMode ? 'new-password' : 'current-password'" placeholder="请输入密码" @keyup.enter="submit" />

          <template v-if="setupMode">
            <label class="loginLabel">确认密码</label>
            <input v-model="confirmPassword" class="loginInput" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" placeholder="请再次输入密码" @keyup.enter="submit" />
          </template>

          <label class="loginToggle">
            <input v-model="showPassword" type="checkbox" />
            <span>显示当前输入的密码</span>
          </label>

          <button class="loginButton" :disabled="saving" @click="submit">
            {{ saving ? '处理中…' : submitLabel }}
          </button>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.loginPage {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.loginCard {
  width: min(100%, 460px);
  padding: 28px;
}

.loginBrand {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-faint);
}

.loginTitle {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 880;
  letter-spacing: -0.03em;
}

.loginForm {
  margin-top: 20px;
  display: grid;
  gap: 10px;
}

.loginLabel {
  font-size: 13px;
  color: var(--ink-soft);
}

.loginInput {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink);
  padding: 14px 16px;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

html.dark .loginInput {
  background: rgba(15, 23, 42, 0.7);
}

.loginInput:focus {
  border-color: rgba(29, 78, 216, 0.45);
  box-shadow: 0 0 0 4px var(--ring);
}

.loginToggle {
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-soft);
  font-size: 13px;
}

.loginButton {
  margin-top: 8px;
  border: 0;
  border-radius: 16px;
  padding: 14px 18px;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: white;
  font-size: 15px;
  font-weight: 760;
  cursor: pointer;
  box-shadow: 0 16px 28px rgba(29, 78, 216, 0.22);
}

.loginButton:disabled {
  cursor: not-allowed;
  opacity: 0.7;
  box-shadow: none;
}
</style>
