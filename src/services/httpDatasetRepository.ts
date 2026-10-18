import type { Dataset, DatasetWorkspace } from '@/types'
import type { UploadPolicy } from '@/types/backend'
import { BackendUnavailableError, type DatasetRepository } from './datasetRepositoryContract'
import { parseDataset, parseWorkspace, parseUploadPolicy } from './workspaceResponse'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

export function createHttpDatasetRepository(baseUrl = '/api/v1', fetcher: typeof fetch = fetch): DatasetRepository {
  const base = baseUrl.replace(/\/$/, '')
  const path = (id: string) => '/datasets/' + encodeURIComponent(id)
  async function request(route: string, init: RequestInit = {}, timeout = 120_000): Promise<Response> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    try {
      const response = await fetcher(base + route, { ...init, signal: controller.signal, headers: {
        Accept: 'application/json', ...(typeof init.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...init.headers,
      } })
      if (!response.ok) {
        // Vite returns an empty 500 when its upstream connection is refused.
        const proxyUnavailable = response.status === 500 && !response.headers.get('Content-Type')?.includes('application/json')
        const workspaceUnavailable = route === '/workspace' && response.status === 404
        if (workspaceUnavailable) console.error(`Workspace API request failed (404): ${base + route}`)
        if (workspaceUnavailable || proxyUnavailable || [502, 503, 504].includes(response.status)) throw new BackendUnavailableError('Backend unavailable. Please retry when the service is running.')
        const payload: unknown = await response.json().catch(() => null)
        const message = typeof payload === 'object' && payload !== null && 'error' in payload
          && typeof payload.error === 'object' && payload.error !== null && 'message' in payload.error
          && typeof payload.error.message === 'string' ? payload.error.message : `API request failed (${response.status}).`
        throw new ApiError(message, response.status)
      }
      // Consume the body under the same timeout as the headers.
      const body = await response.blob()
      return new Response(body, { status: response.status, headers: response.headers })
    } catch (cause) {
      if (cause instanceof ApiError || cause instanceof BackendUnavailableError) throw cause
      throw new BackendUnavailableError('Could not reach the backend. Check the connection and try again.', { cause })
    } finally { clearTimeout(timer) }
  }
  async function dataset(route: string, init?: RequestInit): Promise<Dataset> {
    return parseDataset(await (await request(route, init)).json())
  }
  return {
    source: { kind: 'api' },
    async getWorkspace(): Promise<DatasetWorkspace> {
      return parseWorkspace(await (await request('/workspace', {}, 15_000)).json())
    },
    getDataset: id => dataset(path(id)),
    updateRuleset: (id, ruleset) => dataset(path(id) + '/ruleset', { method: 'PUT', body: JSON.stringify(ruleset) }),
    revalidate: (id, version) => dataset(path(id) + '/validation', { method: 'POST', body: JSON.stringify({ version }) }),
    applyCellReview: (id, review) => dataset(path(id) + '/cell-reviews', { method: 'POST', body: JSON.stringify(review) }),
    async download(id, version) {
      const response = await request(path(id) + '/file?version=' + encodeURIComponent(version))
      const disposition = response.headers.get('Content-Disposition') ?? ''
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? `dataset_${version}.csv`
      return { filename, blob: await response.blob() }
    },
    async getUploadPolicy(): Promise<UploadPolicy> {
      return parseUploadPolicy(await (await request('/upload-policy')).json())
    },
    async upload({ file, sheetName }) {
      const body = new FormData()
      body.append('file', file)
      if (sheetName) body.append('sheet_name', sheetName)
      return dataset('/datasets', { method: 'POST', body })
    },
  }
}
