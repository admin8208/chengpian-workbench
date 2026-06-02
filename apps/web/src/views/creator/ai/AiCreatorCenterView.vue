<script setup lang="ts">
import { useRouter } from 'vue-router'
import CreatorBaseForm from '../shared/CreatorBaseForm.vue'
import { useCreatorBaseForm } from '../shared/useCreatorBaseForm'

const router = useRouter()
const form = useCreatorBaseForm({
  router,
  materialMode: 'ai',
  heroTitle: '智能创作',
  modeLabel: '智能生图链路',
  modeHint: '先确认文案或转写，再由系统按镜头提示词连续生成画面。',
  createButtonLabel: '创建智能创作项目',
})
</script>

<template>
  <CreatorBaseForm
    :model="{
      title: form.title,
      source: form.source,
      selectedPack: form.selectedPack,
      inputMode: form.inputMode,
      materialMode: 'ai',
      mediaPickMode: 'smart',
      audioFileName: form.audioFile ? form.audioFile.name : '',
      creating: form.creating,
      err: form.err,
      info: form.info,
      packs: form.packs,
      modeLabel: form.modeLabel,
      modeHint: form.modeHint,
      heroTitle: form.heroTitle,
      createButtonLabel: form.createButtonLabel,
      setTitle: (value) => (form.title = value),
      setSource: (value) => (form.source = value),
      setSelectedPack: (value) => (form.selectedPack = value),
      setInputMode: (value) => (form.inputMode = value),
      setMediaPickMode: () => {},
      setAudioFile: (file) => (form.audioFile = file),
      createProject: form.createProject,
      clearErr: () => (form.err = ''),
      clearInfo: () => (form.info = ''),
    }"
  />
</template>
