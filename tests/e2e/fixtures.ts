import { test as base, expect } from '@playwright/test'
import { dataset, datasetId, workspace, checkedAt } from '../fixtures/workspace'
import type { CellReviewRequest, Dataset, DatasetRuleset } from '../../src/types'

type ApiState = {
  datasets: Dataset[]
  workspaceStatus: number
  malformed: boolean
  failWrites: boolean
  failDownload: boolean
  writes: { method: string; path: string; body: string }[]
}

// Every API request is intercepted. An unexpected route fails the test instead
// of reaching a developer's backend. State is fresh for each browser context.
export const test = base.extend<{ api: ApiState }>({
  api: [async ({ page }, use) => {
    const api: ApiState = { datasets: [dataset()], workspaceStatus: 200, malformed: false, failWrites: false, failDownload: false, writes: [] }
    const unexpected: string[] = [], browserErrors: string[] = []
    page.on('pageerror', error => browserErrors.push(error.message))
    await page.route('**/api/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname, method = request.method()
      if (path === '/api/v1/workspace' && method === 'GET') {
        return route.fulfill({ status: api.workspaceStatus, json: api.workspaceStatus !== 200 ? { error: { message: 'Workspace access denied' } } : api.malformed ? { datasets: [{}] } : workspace(api.datasets) })
      }
      if (path === '/api/v1/upload-policy') return route.fulfill({ json: { extensions: ['.csv', '.xlsx'], max_upload_bytes: 1024 * 1024 } })
      if (method !== 'GET') {
        api.writes.push({ method, path, body: request.postData() ?? '' })
        if (api.failWrites) return route.fulfill({ status: 409, json: { error: { message: 'Version conflict. Refresh and try again.' } } })
      }
      if (path === '/api/v1/datasets' && method === 'POST') {
        const uploaded = dataset({ id: '22222222-2222-4222-8222-222222222222', name: 'Uploaded inventory', filename: 'upload.csv' })
        api.datasets.unshift(uploaded)
        return route.fulfill({ status: 201, json: uploaded })
      }
      const record = api.datasets.find(d => path.startsWith(`/api/v1/datasets/${d.id}`))
      if (record) {
        if (path.endsWith('/file')) return api.failDownload
          ? route.fulfill({ status: 500, json: { error: { message: 'Download failed' } } })
          : route.fulfill({ contentType: 'text/csv', headers: { 'Content-Disposition': 'attachment; filename="inventory_v1.csv"' }, body: 'id,value\r\nA,10\r\nB,\r\n' })
        if (path.endsWith('/ruleset') && method === 'PUT') {
          record.ruleset = request.postDataJSON() as DatasetRuleset
          record.rulesChangedSinceRun = true
          record.validationPending = true
        } else if (path.endsWith('/cell-reviews') && method === 'POST') {
          const review = request.postDataJSON() as CellReviewRequest
          record.cellReview = []
          record.reviewChangedSinceRun = true
          record.validationPending = true
          if (review.action.type !== 'ignore') {
            record.version = 'v2'
            record.dataChangedSinceRun = true
            record.processingStatus = 'not_started'
            record.quality = null
            record.validation = null
            record.columnProfiles = null
            if (review.action.type === 'delete-row') record.rowCount--
          }
        } else if (path.endsWith('/validation') && method === 'POST') {
          Object.assign(record, { version: 'v2', quality: 100, processingStatus: 'completed', status: 'healthy', validationPending: false,
            rulesChangedSinceRun: false, reviewChangedSinceRun: false, dataChangedSinceRun: false, cellReview: [],
            validation: { checksRun: record.ruleset.rules.length, issues: [] },
            history: [...(record.history ?? []), { id: 'validated', occurredAt: checkedAt, title: 'Validation ran', description: 'v2 · Validation results saved.' }] })
        } else if (path !== `/api/v1/datasets/${record.id}` || method !== 'GET') {
          unexpected.push(`${method} ${path}`)
          return route.fulfill({ status: 500, json: { error: { message: 'Unexpected test request' } } })
        }
        return route.fulfill({ json: record })
      }
      unexpected.push(`${method} ${path}`)
      return route.fulfill({ status: 500, json: { error: { message: 'Unexpected test request' } } })
    })
    await use(api)
    expect(unexpected, 'Unexpected API calls').toEqual([])
    expect(browserErrors, 'Uncaught application errors').toEqual([])
  }, { auto: true }],
})
export { expect, datasetId }
