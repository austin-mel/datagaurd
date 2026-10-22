<script setup lang="ts">
import { RouterView } from 'vue-router'
import { WorkspaceSidebar, WorkspaceTopbar, WorkspaceSourceBanner } from '@/components'
</script>

<template>
  <div class="grid grid-cols-[224px_minmax(0,1fr)] min-h-screen max-[1250px]:grid-cols-[192px_minmax(0,1fr)] max-[1020px]:grid-cols-[77px_minmax(0,1fr)] max-[540px]:block bg-ivory text-ink">
    <WorkspaceSidebar />
    <div class="min-w-0">
      <WorkspaceTopbar />
      <main class="mx-auto max-w-[1580px] px-8.5 pt-7.5 pb-5.5 max-[1250px]:px-6.25 max-[540px]:px-4.25 max-[540px]:pt-6.25 max-[540px]:pb-5">
        <WorkspaceSourceBanner />
        <RouterView />
      </main>
    </div>
  </div>
</template>
