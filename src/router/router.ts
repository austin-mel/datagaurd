import { createRouter, createWebHistory } from 'vue-router'
import { OverviewView, DatasetsView } from '@/views'

const base = import.meta.env.BASE_URL
const requestedRoute = new URLSearchParams(window.location.search).get('__dataguard_route')

// Restore GitHub Pages deep links before Vue Router reads the initial location.
if (window.location.pathname === base && requestedRoute) {
  try {
    const destination = new URL(requestedRoute, window.location.origin)
    if (destination.origin === window.location.origin && destination.pathname.startsWith(base)) {
      window.history.replaceState(window.history.state, '', destination.pathname + destination.search + destination.hash)
    }
  } catch {
    // A malformed redirect should leave the normal workspace entry point usable.
  }
}

const router = createRouter({
  history: createWebHistory(base),
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
  document.title = `Dataguard | ${to.meta.title ?? 'Workspace'}`
})

export default router
