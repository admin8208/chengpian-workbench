<script setup lang="ts">
defineProps<{
  projectCount: number
  runningProjectCount: number
  failedProjectCount: number
  finalProjectCount: number
}>()
</script>

<template>
  <div class="status-grid">
    <div class="status-card">
      <div class="status-label">全部项目</div>
      <div class="status-value">{{ projectCount }}</div>
    </div>
    <div class="status-card" :class="{ 'status-warning': runningProjectCount > 0 }">
      <div class="status-label">生成中</div>
      <div class="status-value">{{ runningProjectCount }}</div>
    </div>
    <div class="status-card" :class="{ 'status-bad': failedProjectCount > 0 }">
      <div class="status-label">有失败</div>
      <div class="status-value">{{ failedProjectCount }}</div>
    </div>
    <div class="status-card" :class="{ 'status-ok': finalProjectCount > 0 }">
      <div class="status-label">有成片</div>
      <div class="status-value">{{ finalProjectCount }}</div>
    </div>
  </div>
</template>

<style scoped>
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-card {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  transition: all 0.25s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.status-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.status-card.status-ok {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.05);
}

.status-card.status-warning {
  border-color: rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.05);
}

.status-card.status-bad {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.05);
}

.status-label {
  font-size: 14px;
  color: var(--ink-soft);
  margin-bottom: 4px;
}

.status-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
}

@media (max-width: 768px) {
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
