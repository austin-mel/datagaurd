<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { DataguardIcon, DataguardLogo, SVGIcons } from '@/assets'
</script>

<template>
  <aside class="sticky top-0 flex h-screen flex-col gap-7.5 self-start bg-ink px-4.5 pt-7 pb-5 text-porcelain max-[1250px]:px-3.25 max-[1020px]:items-center max-[1020px]:px-2.75 max-[540px]:static max-[540px]:h-auto max-[540px]:items-stretch max-[540px]:gap-4.5 max-[540px]:px-4.5 max-[540px]:pt-4.25 max-[540px]:pb-3" aria-label="Workspace navigation">
    <RouterLink
      :to="{ name: 'overview' }"
      class="flex items-center px-2.25 max-[1250px]:px-0.75 max-[1020px]:p-0"
      aria-label="Dataguard overview"
    >
      <img :src="DataguardLogo" class="h-auto w-[155px] max-[1250px]:w-[145px] max-[1020px]:hidden max-[540px]:block max-[540px]:w-[150px]" width="155" height="37" alt="Dataguard" />
      <img :src="DataguardIcon" class="hidden max-[1020px]:block max-[540px]:hidden" width="33" height="37" alt="Dataguard" />
    </RouterLink>

    <nav aria-label="Main">
      <p class="mb-2.75 max-[1020px]:hidden px-3.5 text-[10px] font-semibold tracking-[0.14em] text-nav-muted">
        WORKSPACE
      </p>
      <div class="flex flex-col gap-1.5 max-[540px]:flex-row max-[540px]:gap-1.25">
        <RouterLink
          :to="{ name: 'overview' }"
          class="flex items-center gap-3 rounded-lg px-3.5 py-3 text-[13px] max-[1020px]:px-4 max-[1020px]:py-3.5 max-[540px]:flex-1 max-[540px]:justify-center max-[540px]:gap-1.75 max-[540px]:px-2 max-[540px]:py-2.5 max-[540px]:text-[11px] text-nav-text hover:bg-porcelain/10 aria-[current=page]:bg-cobalt aria-[current=page]:text-porcelain"
          aria-label="Overview"
        >
          <SVGIcons name="overview" class="size-4.5 max-[540px]:size-3.75" />
          <span class="max-[1020px]:hidden max-[540px]:block">Overview</span>
        </RouterLink>
        <RouterLink
          :to="{ name: 'datasets' }"
          class="flex items-center gap-3 rounded-lg px-3.5 py-3 text-[13px] max-[1020px]:px-4 max-[1020px]:py-3.5 max-[540px]:flex-1 max-[540px]:justify-center max-[540px]:gap-1.75 max-[540px]:px-2 max-[540px]:py-2.5 max-[540px]:text-[11px] text-nav-text hover:bg-porcelain/10 aria-[current=page]:bg-cobalt aria-[current=page]:text-porcelain"
          aria-label="Datasets"
        >
          <SVGIcons name="database" class="size-4.5 max-[540px]:size-3.75" />
          <span class="max-[1020px]:hidden max-[540px]:block">Datasets</span>
        </RouterLink>
      </div>
    </nav>
  </aside>
</template>
