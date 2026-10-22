<script setup lang="ts">
import { SVGIcons } from '@/assets'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <header class="flex min-h-[73px] items-center border-b border-line px-8.5 py-4.25 max-[1250px]:px-6.25 max-[540px]:min-h-[54px] max-[540px]:px-4.5 max-[540px]:py-3">
    <div class="flex items-center gap-2.75 text-xs text-muted">
      <span>Workspace</span>
      <SVGIcons name="chevron" class="size-3" />
      <span class="font-[550] text-ink" aria-current="page">{{ route.meta.title }}</span>
    </div>
  </header>
</template>
