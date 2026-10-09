<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { DataguardIcon, DataguardLogo } from '@/assets'

const route = useRoute()
</script>

<template>
  <div class="app-shell min-h-screen bg-ivory text-ink">
    <aside class="sidebar bg-ink text-porcelain" aria-label="Workspace navigation">
      <RouterLink
        :to="{ name: 'overview' }"
        class="brand flex items-center px-[9px]"
        aria-label="Dataguard overview"
      >
        <img :src="DataguardLogo" class="brand-logo" width="155" height="37" alt="Dataguard" />
        <img :src="DataguardIcon" class="brand-icon" width="33" height="37" alt="Dataguard" />
      </RouterLink>

      <nav aria-label="Main">
        <p class="nav-label mb-[11px] px-3.5 text-[10px] font-semibold tracking-[0.14em] text-nav-muted">
          WORKSPACE
        </p>
        <div class="navigation flex flex-col gap-1.5">
          <RouterLink
            :to="{ name: 'overview' }"
            class="nav-link text-nav-text hover:bg-porcelain/10 aria-[current=page]:bg-cobalt aria-[current=page]:text-porcelain"
            aria-label="Overview"
          >
            <svg class="icon size-[18px]" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="3" width="7" height="7" rx="1.5" />
              <rect x="14" y="3" width="7" height="7" rx="1.5" />
              <rect x="3" y="14" width="7" height="7" rx="1.5" />
              <rect x="14" y="14" width="7" height="7" rx="1.5" />
            </svg>
            <span>Overview</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'datasets' }"
            class="nav-link text-nav-text hover:bg-porcelain/10 aria-[current=page]:bg-cobalt aria-[current=page]:text-porcelain"
            aria-label="Datasets"
          >
            <svg class="icon size-[18px]" viewBox="0 0 24 24" aria-hidden="true">
              <ellipse cx="12" cy="5" rx="8" ry="3" />
              <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
            </svg>
            <span>Datasets</span>
          </RouterLink>
        </div>
      </nav>
    </aside>

    <div class="min-w-0">
      <header class="topbar flex items-center border-b border-line">
        <div class="flex items-center gap-[11px] text-xs text-muted">
          <span>Workspace</span>
          <svg class="icon size-3" viewBox="0 0 24 24" aria-hidden="true">
            <path d="m9 5 7 7-7 7" />
          </svg>
          <span class="font-[550] text-ink" aria-current="page">{{ route.meta.title }}</span>
        </div>
      </header>
      <main class="page-content mx-auto max-w-[1580px]">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 224px minmax(0, 1fr);
}

.brand-logo { width: 155px; height: auto; }
.brand-icon { display: none; }

.sidebar {
  position: sticky;
  top: 0;
  align-self: start;
  display: flex;
  height: 100vh;
  flex-direction: column;
  gap: 30px;
  padding: 28px 18px 20px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 13px;
}

.icon {
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.topbar {
  min-height: 73px;
  padding: 17px 34px;
}

.page-content {
  padding: 30px 34px 22px;
}

@media (max-width: 1250px) {
  .app-shell { grid-template-columns: 192px minmax(0, 1fr); }
  .sidebar { padding-inline: 13px; }
  .brand { padding-inline: 3px; }
  .brand-logo { width: 145px; }
  .topbar, .page-content { padding-inline: 25px; }
}

@media (max-width: 1020px) {
  .app-shell { grid-template-columns: 77px minmax(0, 1fr); }
  .sidebar { align-items: center; padding-inline: 11px; }
  .brand { padding: 0; }
  .brand-logo, .nav-label, .nav-link span { display: none; }
  .brand-icon { display: block; }
  .nav-link { padding: 14px 16px; }
}

@media (max-width: 540px) {
  .app-shell { display: block; }
  .sidebar { position: static; height: auto; align-items: stretch; gap: 18px; padding: 17px 18px 12px; }
  .brand-logo { display: block; width: 150px; }
  .brand-icon { display: none; }
  .navigation { flex-direction: row; gap: 5px; }
  .nav-link { flex: 1; justify-content: center; gap: 7px; padding: 10px 8px; font-size: 11px; }
  .nav-link span { display: block; }
  .nav-link .icon { width: 15px; height: 15px; }
  .topbar { min-height: 54px; padding: 12px 18px; }
  .page-content { padding: 25px 17px 20px; }
}
</style>
