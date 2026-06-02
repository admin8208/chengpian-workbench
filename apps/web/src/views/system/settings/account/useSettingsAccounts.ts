import { computed, ref, type Ref } from 'vue'
import { api, type AuthStatus, type UserAccount } from '../../../../api'

export function useSettingsAccounts(options: {
  err: Ref<string>
  info: Ref<string>
}) {
  const { err, info } = options
  const authStatus = ref<AuthStatus | null>(null)
  const accountLoading = ref(true)
  const accountSaving = ref(false)
  const userAccounts = ref<UserAccount[]>([])
  const subUsername = ref('')
  const subPassword = ref('')
  const resetPasswords = ref<Record<number, string>>({})

  const isAdmin = computed(() => Boolean(authStatus.value?.is_admin))
  const accountQuickSummary = computed(() => {
    if (accountLoading.value) return '正在读取账号权限…'
    if (!authStatus.value?.authenticated) return '未登录'
    if (!isAdmin.value) return `当前账号：${authStatus.value?.username || '子账号'} · 无子账号管理权限`
    return `当前管理员：${authStatus.value?.username || '管理员'} · 子账号 ${userAccounts.value.length} 个`
  })

  async function loadAccounts(failures?: string[]) {
    accountLoading.value = true
    try {
      authStatus.value = await api.authStatus()
      userAccounts.value = authStatus.value?.is_admin ? await api.authUsers() : []
    } catch (e: any) {
      authStatus.value = null
      userAccounts.value = []
      failures?.push(`账号信息加载失败：${e?.message ?? String(e)}`)
    } finally {
      accountLoading.value = false
    }
  }

  async function createSubAccount() {
    if (!isAdmin.value) {
      err.value = '仅管理员可创建子账号'
      return
    }
    if (!subUsername.value.trim()) {
      err.value = '请输入子账号用户名'
      return
    }
    if (!subPassword.value) {
      err.value = '请输入子账号密码'
      return
    }
    accountSaving.value = true
    err.value = ''
    info.value = ''
    try {
      await api.authCreateUser({ username: subUsername.value.trim(), password: subPassword.value })
      subUsername.value = ''
      subPassword.value = ''
      userAccounts.value = await api.authUsers()
      info.value = '子账号已创建。'
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      accountSaving.value = false
    }
  }

  async function toggleSubAccount(user: UserAccount, enabled: boolean) {
    if (!isAdmin.value) return
    accountSaving.value = true
    err.value = ''
    info.value = ''
    try {
      await api.authPatchUser(user.id, { enabled })
      userAccounts.value = await api.authUsers()
      info.value = enabled ? `已启用子账号 ${user.username}` : `已停用子账号 ${user.username}`
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      accountSaving.value = false
    }
  }

  async function resetSubAccountPassword(user: UserAccount) {
    if (!isAdmin.value) return
    const nextPassword = String(resetPasswords.value[user.id] || '')
    if (!nextPassword) {
      err.value = `请输入 ${user.username} 的新密码`
      return
    }
    accountSaving.value = true
    err.value = ''
    info.value = ''
    try {
      await api.authResetUserPassword(user.id, { password: nextPassword })
      resetPasswords.value = { ...resetPasswords.value, [user.id]: '' }
      info.value = `已重置子账号 ${user.username} 的密码`
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      accountSaving.value = false
    }
  }

  return {
    authStatus,
    accountLoading,
    accountSaving,
    userAccounts,
    subUsername,
    subPassword,
    resetPasswords,
    isAdmin,
    accountQuickSummary,
    loadAccounts,
    createSubAccount,
    toggleSubAccount,
    resetSubAccountPassword,
  }
}
