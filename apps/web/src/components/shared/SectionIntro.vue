<script setup lang="ts">
defineProps<{
  kicker?: string
  title: string
  desc?: string
}>()
</script>

<template>
  <div>
    <div v-if="kicker" class="sectionKicker">{{ kicker }}</div>
    <div class="cardTitle" :style="kicker ? 'margin-top: 4px' : ''">{{ title }}</div>
    <div v-if="desc" class="muted" style="margin-top: 6px">{{ desc }}</div>
  </div>
</template>
