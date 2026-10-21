<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <header class="topbar flex items-center border-b border-line">
    <div class="flex items-center gap-2.75 text-xs text-muted">
      <span>Workspace</span>
      <SVGIcons name="chevron" class="size-3" />
      <span class="font-[550] text-ink" aria-current="page">{{ route.meta.title }}</span>
    </div>
  </header>
</template>

<style scoped>
.topbar { min-height: 73px; padding: 17px 34px; }
@media (max-width: 1250px) { .topbar { padding-inline: 25px; } }
@media (max-width: 540px) { .topbar { min-height: 54px; padding: 12px 18px; } }
</style>
