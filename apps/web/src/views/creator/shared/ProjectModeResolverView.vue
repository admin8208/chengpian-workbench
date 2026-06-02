<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElAlert, ElButton } from 'element-plus'
import { api } from '../../../api'

const route = useRoute()
const router = useRouter()
const busy = ref(true)
const err = ref('')

async function resolveProjectRoute() {
  const projectId = Number(route.params.id)
  if (!Number.isFinite(projectId) || projectId <= 0) {
    err.value = '项目编号无效。'
    busy.value = false
    return
  }
  busy.value = true
  err.value = ''
  try {
    const project = await api.getProject(projectId)
    const mode = String(project.render_config?.material_mode || '').trim().toLowerCase()
    await router.replace({ path: mode === 'ai' ? `/p/ai/${projectId}` : `/p/network/${projectId}` })
  } catch (e: any) {
    err.value = e?.message ?? String(e)
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  void resolveProjectRoute()
})
</script>

<template>
  <section class="card" style="margin-top: 16px">
    <div class="cardTitle">正在分配项目工作台</div>
    <div class="muted" style="margin-top: 10px">{{ busy ? '正在根据项目模式跳转到智能创作或素材创作工作台。' : '项目跳转失败。' }}</div>
    <ElAlert v-if="err" type="error" :title="err" show-icon style="margin-top: 12px" />
    <div v-if="err" class="row" style="margin-top: 12px; gap: 8px">
      <ElButton type="primary" @click="resolveProjectRoute">重试</ElButton>
      <ElButton @click="router.push('/recent')">返回项目中心</ElButton>
    </div>
  </section>
</template>
