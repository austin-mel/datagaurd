<script setup lang="ts">
import { RouterView } from 'vue-router'
import { WorkspaceSidebar, WorkspaceTopbar, WorkspaceSourceBanner } from '@/components'
</script>

<template>
  <div class="app-shell min-h-screen bg-ivory text-ink">
    <WorkspaceSidebar />
    <div class="min-w-0">
      <WorkspaceTopbar />
      <main class="page-content mx-auto max-w-[1580px]">
        <WorkspaceSourceBanner />
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell { display: grid; grid-template-columns: 224px minmax(0, 1fr); }
.page-content { padding: 30px 34px 22px; }
@media (max-width: 1250px) {
  .app-shell { grid-template-columns: 192px minmax(0, 1fr); }
  .page-content { padding-inline: 25px; }
}
@media (max-width: 1020px) { .app-shell { grid-template-columns: 77px minmax(0, 1fr); } }
@media (max-width: 540px) {
  .app-shell { display: block; }
  .page-content { padding: 25px 17px 20px; }
}
</style>
