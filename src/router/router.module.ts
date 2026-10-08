import { createRouter, createWebHistory } from 'vue-router'
import { OverviewView, DatasetsView } from '@/views'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      alias: '/overview',
      name: 'overview',
      component: OverviewView,
      meta: { title: 'Overview' },
    },
    {
      path: '/datasets',
      name: 'datasets',
      component: DatasetsView,
      meta: { title: 'Datasets' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'Workspace'} | Dataguard`
})

export default router
