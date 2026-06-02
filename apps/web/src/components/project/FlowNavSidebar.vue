<script setup lang="ts">
import { ElIcon, ElTag, ElTooltip } from 'element-plus'
import { Check, CircleCheck, Loading, Warning, Film, ArrowRight } from '@element-plus/icons-vue'
import { useProjectFlowNav, type FlowNavProps, type FlowStep } from './projectFlowNav'

type FlowNavModel = FlowNavProps & {
  updateCurrentStep: (step: FlowStep) => void
  proceedToNext: () => void
}

const props = defineProps<{
  model: FlowNavModel
}>()

const {
  resolvedSteps,
  nextStepInfo,
  isStepActive,
  isStepCompleted,
  isStepCurrent,
  getStepStatus,
  getStepSummary,
} = useProjectFlowNav(props.model)

function selectStep(step: FlowStep) {
  props.model.updateCurrentStep(step)
}

function proceedToNext() {
  props.model.proceedToNext()
}
</script>

<template>
  <div class="flow-nav">
    <div class="nav-header">
      <div class="nav-title">
        <ElIcon><Film /></ElIcon>
        <span>生成视频流程</span>
      </div>
      <ElTag v-if="model.jobStatus === 'running'" type="warning" size="small">
        <ElIcon class="is-loading"><Loading /></ElIcon>
        执行中
      </ElTag>
      <ElTag v-else-if="model.jobStatus === 'failed'" type="danger" size="small">
        <ElIcon><Warning /></ElIcon>
        出错
      </ElTag>
      <ElTag v-else-if="model.jobStatus === 'done'" type="success" size="small">
        <ElIcon><CircleCheck /></ElIcon>
        完成
      </ElTag>
    </div>

    <div class="nav-steps">
        <ElTooltip 
          v-for="(step, idx) in resolvedSteps" 
        :key="step.key"
        :content="step.tips"
        placement="right"
        :effect="'dark'"
      >
        <div
          class="nav-step"
          :class="{
            active: isStepActive(step.key),
            completed: isStepCompleted(step.key),
            current: isStepCurrent(step.key),
            running: getStepStatus(step.key) === 'running',
            error: getStepStatus(step.key) === 'error',
          }"
          @click="selectStep(step.key)"
          :style="{
            '--step-color': step.color,
            borderColor: isStepActive(step.key) ? step.color : 'transparent'
          }"
        >
          <div class="step-indicator">
            <div 
              class="step-number" 
              v-if="!isStepCompleted(step.key) && getStepStatus(step.key) !== 'running'"
              :style="{
                backgroundColor: isStepActive(step.key) ? step.color : 'rgba(15, 23, 42, 0.06)'
              }"
            >
              {{ idx + 1 }}
            </div>
            <ElIcon v-else-if="getStepStatus(step.key) === 'running'" class="is-loading step-icon">
              <Loading />
            </ElIcon>
            <ElIcon v-else class="step-icon check">
              <Check />
            </ElIcon>
            <div 
              v-if="idx < resolvedSteps.length - 1" 
              class="step-line" 
              :class="{ completed: isStepCompleted(step.key) }"
              :style="{
                backgroundColor: isStepCompleted(step.key) ? step.color : 'rgba(15, 23, 42, 0.08)'
              }"
            ></div>
          </div>

          <div class="step-content">
            <div class="step-header">
              <ElIcon 
                class="step-icon-main" 
                :style="{
                  color: isStepActive(step.key) ? step.color : 'var(--ink-soft)'
                }"
              >
                <component :is="step.icon" />
              </ElIcon>
              <span class="step-label">{{ step.label }}</span>
              <ElTag 
                v-if="isStepCurrent(step.key) && !isStepActive(step.key)" 
                type="info" 
                size="small"
              >
                当前
              </ElTag>
            </div>
            <div class="step-desc">{{ step.desc }}</div>
            <div class="step-summary">{{ getStepSummary(step.key) }}</div>
          </div>
        </div>
      </ElTooltip>
    </div>

    <!-- 下一步按钮 -->
    <div v-if="nextStepInfo && model.canProceed && model.jobStatus !== 'running'" class="nav-actions">
      <el-button 
        type="primary" 
        :icon="ArrowRight"
        @click="proceedToNext"
        class="proceed-button"
        :style="{
          backgroundColor: nextStepInfo.color
        }"
      >
        下一步：{{ nextStepInfo.label }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.flow-nav {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.78);
  border-radius: 20px;
  border: 1px solid var(--line);
  height: fit-content;
  position: sticky;
  top: 16px;
}

html.dark .flow-nav {
  background: rgba(30, 41, 59, 0.78);
}

.nav-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.nav-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-steps {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-step {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 160ms ease;
  border: 1px solid transparent;
}

.nav-step:hover {
  background: rgba(0, 0, 0, 0.02);
}

html.dark .nav-step:hover {
  background: rgba(255, 255, 255, 0.02);
}

.nav-step.active {
  background: rgba(29, 78, 216, 0.08);
  border-color: rgba(29, 78, 216, 0.2);
}

.nav-step.completed {
  opacity: 0.7;
}

.nav-step.completed:hover {
  opacity: 1;
}

.nav-step.current {
  border-color: rgba(20, 184, 166, 0.3);
}

.nav-step.error {
  border-color: rgba(180, 35, 24, 0.2);
  background: rgba(180, 35, 24, 0.04);
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink);
}

.nav-step.active .step-number {
  background: var(--el-color-primary);
  color: white;
}

.nav-step.completed .step-number {
  background: rgba(21, 128, 61, 0.12);
  color: rgba(21, 128, 61, 1);
}

.step-icon {
  font-size: 14px;
}

.step-icon.check {
  color: rgba(21, 128, 61, 1);
}

.step-line {
  width: 2px;
  height: 24px;
  background: rgba(15, 23, 42, 0.08);
  border-radius: 1px;
}

.step-line.completed {
  background: rgba(21, 128, 61, 0.3);
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.step-icon-main {
  font-size: 16px;
  color: var(--ink-soft);
}

.nav-step.active .step-icon-main {
  color: var(--el-color-primary);
}

.step-label {
  font-size: 14px;
  font-weight: 600;
}

.step-desc {
  font-size: 12px;
  color: var(--ink-soft);
  margin-bottom: 4px;
}

.step-summary {
  font-size: 11px;
  color: var(--ink-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}

.proceed-button {
  width: 100%;
  font-size: 14px;
  font-weight: 600;
  padding: 12px;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.proceed-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.proceed-button:active {
  transform: translateY(0);
}

.is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
