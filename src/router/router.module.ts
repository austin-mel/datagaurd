import { createRouter, createWebHistory } from 'vue-router'
import { OverviewView, DatasetsView } from '@/views'
import { canonicalDatasetId } from '@/data/datasetIds'

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

router.beforeEach(to => {
  const id = to.query.dataset
  if (to.name === 'overview' && typeof id === 'string' && canonicalDatasetId(id) !== id) {
    return { path: to.path, query: { ...to.query, dataset: canonicalDatasetId(id) }, hash: to.hash, replace: true }
  }
})

router.afterEach((to) => {
  document.title = `Dataguard | ${to.meta.title ?? 'Workspace'}`
})

export default router
