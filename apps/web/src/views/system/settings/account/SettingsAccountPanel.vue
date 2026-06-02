<script setup lang="ts">
import { ElButton, ElInput } from 'element-plus'
import { formatDateTime } from '../../../../utils/dateTime'

type UserAccount = {
  id: number
  username: string
  created_at: string
  enabled: boolean
}

type AccountPanelModel = {
  accountLoading: boolean
  accountSaving: boolean
  userAccounts: UserAccount[]
  subUsername: string
  subPassword: string
  resetPasswords: Record<number, string>
  accountQuickSummary: string
  createSubAccount: () => Promise<void>
  toggleSubAccount: (user: UserAccount, enabled: boolean) => Promise<void>
  resetSubAccountPassword: (user: UserAccount) => Promise<void>
}

defineProps<{
  authUsername: string
  showPlainSecrets: boolean
  model: AccountPanelModel
}>()
</script>

<template>
  <section class="card" style="padding: 20px">
    <div class="section-title">账号管理</div>
    <div class="softItem muted" style="margin-top: 8px; line-height: 1.45">{{ model.accountQuickSummary }}</div>
    <div class="muted" style="margin-top: 8px; line-height: 1.45">当前登录账号：{{ authUsername || '管理员' }}。子账号可登录使用系统，但不能管理其他账号。</div>

    <div class="softItem" style="margin-top: 12px">
      <div style="font-weight: 760">创建子账号</div>
      <div class="rowGrid" style="margin-top: 10px">
        <ElInput :model-value="model.subUsername" placeholder="子账号用户名" @update:model-value="model.subUsername = String($event || '')" />
        <ElInput :model-value="model.subPassword" :type="showPlainSecrets ? 'text' : 'password'" placeholder="子账号密码（至少 8 位）" @update:model-value="model.subPassword = String($event || '')" />
      </div>
      <div class="row" style="margin-top: 10px; gap: 8px">
        <ElButton type="primary" :disabled="model.accountSaving || !model.subUsername.trim() || !model.subPassword" @click="model.createSubAccount">创建子账号</ElButton>
      </div>
    </div>

    <div class="softItem" style="margin-top: 12px">
      <div style="font-weight: 760">已创建子账号</div>
      <div v-if="model.accountLoading" class="muted" style="margin-top: 8px">正在读取子账号列表…</div>
      <div v-else-if="!model.userAccounts.length" class="muted" style="margin-top: 8px">当前还没有子账号。</div>
      <div v-else class="voiceList" style="margin-top: 10px">
        <div v-for="user in model.userAccounts" :key="user.id" class="voiceRow">
          <div>
            <div style="font-weight: 760">{{ user.username }}</div>
            <div class="muted" style="margin-top: 4px">创建时间：{{ formatDateTime(user.created_at) }}</div>
            <div class="row" style="margin-top: 8px; gap: 8px; flex-wrap: wrap">
              <ElInput :model-value="model.resetPasswords[user.id]" :type="showPlainSecrets ? 'text' : 'password'" placeholder="输入新密码（至少 8 位）" style="min-width: 240px; max-width: 320px" @update:model-value="model.resetPasswords[user.id] = String($event || '')" />
              <ElButton size="small" :disabled="model.accountSaving || !model.resetPasswords[user.id]" @click="model.resetSubAccountPassword(user)">重置密码</ElButton>
            </div>
          </div>
          <div class="row" style="gap: 8px; flex-wrap: wrap; justify-content: flex-end">
            <div class="pill" :class="user.enabled ? 'ok' : 'bad'">{{ user.enabled ? '已启用' : '已停用' }}</div>
            <ElButton size="small" :disabled="model.accountSaving" @click="model.toggleSubAccount(user, !user.enabled)">{{ user.enabled ? '停用' : '启用' }}</ElButton>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.rowGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
}

@media (max-width: 980px) {
  .rowGrid {
    grid-template-columns: 1fr;
  }
}
</style>
