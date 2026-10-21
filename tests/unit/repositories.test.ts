import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createHttpDatasetRepository,
  ApiError,
  createDatasetRepository,
  BackendUnavailableError,
  type DatasetRepository,
} from '@/services'
import { dataset, datasetId, ruleset, workspace } from '../fixtures/workspace'

export function repository(overrides: Partial<DatasetRepository> = {}): DatasetRepository {
  return {
    source: { kind: 'api' }, getWorkspace: vi.fn(async () => workspace()), getDataset: vi.fn(async () => dataset()),
    updateRuleset: vi.fn(async () => dataset()), revalidate: vi.fn(async () => dataset()), applyCellReview: vi.fn(async () => dataset()),
    download: vi.fn(async () => ({ filename: 'test.csv', blob: new Blob(['test']) })),
    getUploadPolicy: vi.fn(async () => ({ extensions: ['.csv'], max_upload_bytes: 100 })), upload: vi.fn(async () => dataset()), ...overrides,
  }
}

describe('HTTP repository', () => {
  afterEach(() => vi.useRealTimers())
  it('encodes IDs, normalizes the base URL and sends JSON mutations', async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => Response.json(dataset()))
    const repo = createHttpDatasetRepository('/api/v1/', fetcher)
    await repo.getDataset('id/with space')
    expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/datasets/id%2Fwith%20space')
    await repo.updateRuleset(datasetId, ruleset())
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/datasets/${datasetId}/ruleset`, expect.objectContaining({ method: 'PUT', body: JSON.stringify(ruleset()), headers: { Accept: 'application/json', 'Content-Type': 'application/json' } })])
    await repo.revalidate(datasetId, 'v2')
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ method: 'POST', body: '{"version":"v2"}' })
    const review = { version: 'v1', groupId: 'g', rowNumber: 1, scope: 'one' as const, action: { type: 'delete-row' as const } }
    await repo.applyCellReview(datasetId, review)
    expect(fetcher.mock.calls[3]?.[1]?.body).toBe(JSON.stringify(review))
  })
  it('parses workspace and policy responses', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json(workspace())).mockResolvedValueOnce(Response.json({ extensions: ['.csv'], max_upload_bytes: 50 }))
    const repo = createHttpDatasetRepository(undefined, fetcher)
    expect(await repo.getWorkspace()).toEqual(workspace())
    expect(await repo.getUploadPolicy!()).toEqual({ extensions: ['.csv'], max_upload_bytes: 50 })
  })
  it('sends multipart files and worksheet names without forcing JSON headers', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(dataset()))
    await createHttpDatasetRepository(undefined, fetcher).upload!({ file: new File(['source'], 'data.xlsx'), sheetName: 'Inventory' })
    const init = fetcher.mock.calls[0]?.[1]
    expect(init?.headers).toEqual({ Accept: 'application/json' })
    const body = init?.body as FormData
    expect(body.get('sheet_name')).toBe('Inventory')
    expect((body.get('file') as File).name).toBe('data.xlsx')
    expect(await (body.get('file') as File).text()).toBe('source')
  })
  it('preserves file bytes and uses the supplied download filename', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response('a,b\r\n1,2', { headers: { 'Content-Disposition': 'attachment; filename="original.csv"' } })).mockResolvedValueOnce(new Response('fallback'))
    const repo = createHttpDatasetRepository(undefined, fetcher)
    const downloaded = await repo.download(datasetId, 'v 1')
    expect(downloaded.filename).toBe('original.csv')
    expect(await downloaded.blob.text()).toBe('a,b\r\n1,2')
    expect(fetcher.mock.calls[0]?.[0]).toContain('?version=v%201')
    expect((await repo.download(datasetId, 'v2')).filename).toBe('dataset_v2.csv')
  })
  it.each([502, 503, 504, 500])('classifies gateway/proxy status %i as unavailable', async status => {
    const repo = createHttpDatasetRepository(undefined, vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status })))
    await expect(repo.getWorkspace()).rejects.toBeInstanceOf(BackendUnavailableError)
  })
  it.each([401, 403, 409, 422, 500])('surfaces structured status %i without fallback', async status => {
    const repo = createHttpDatasetRepository(undefined, vi.fn<typeof fetch>().mockResolvedValue(Response.json({ error: { message: 'Request denied' } }, { status })))
    await expect(repo.getWorkspace()).rejects.toMatchObject({ message: 'Request denied', status })
  })
  it('preserves missing dataset errors', async () => {
    const repo = createHttpDatasetRepository(undefined, vi.fn<typeof fetch>().mockResolvedValue(Response.json({ error: { message: 'Dataset not found' } }, { status: 404 })))
    await expect(repo.getDataset(datasetId)).rejects.toMatchObject({ message: 'Dataset not found', status: 404 })
  })
  it('rejects invalid contracts as contract errors, not network failures', async () => {
    const repo = createHttpDatasetRepository(undefined, vi.fn<typeof fetch>().mockResolvedValue(Response.json({ datasets: [] })))
    await expect(repo.getWorkspace()).rejects.toThrow(/invalid workspace/)
  })
  it('classifies transport errors and aborts stalled workspace requests after 15 seconds', async () => {
    await expect(createHttpDatasetRepository(undefined, vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'))).getWorkspace()).rejects.toBeInstanceOf(BackendUnavailableError)
    vi.useFakeTimers()
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    }))
    const request = createHttpDatasetRepository(undefined, fetcher).getWorkspace()
    const assertion = expect(request).rejects.toBeInstanceOf(BackendUnavailableError)
    await vi.advanceTimersByTimeAsync(15_000)
    await assertion
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('workspace source selection', () => {
  it.each(['empty', 'html', 'json'])('uses samples when the workspace endpoint returns a %s 404', async format => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const response = format === 'json'
      ? Response.json({ detail: 'Not Found' }, { status: 404 })
      : new Response(format === 'html' ? '<html>Not Found</html>' : '', { status: 404, headers: { 'Content-Type': 'text/html' } })
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response)
    const fallback = repository({ source: { kind: 'seeded', reason: 'not-configured' } })
    const repo = createDatasetRepository(createHttpDatasetRepository(undefined, fetcher), fallback)

    expect(await repo.getWorkspace()).toEqual(workspace())
    expect(repo.source).toEqual({ kind: 'seeded', reason: 'backend-unavailable' })
    expect(consoleError).toHaveBeenCalledWith('Workspace API request failed (404): /api/v1/workspace')
    await repo.getDataset(datasetId)
    await repo.updateRuleset(datasetId, ruleset())
    expect(fallback.getDataset).toHaveBeenCalledWith(datasetId)
    expect(fallback.updateRuleset).toHaveBeenCalledWith(datasetId, ruleset())
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('treats an empty live workspace as authoritative and shares concurrent initialization', async () => {
    const primary = repository({ getWorkspace: vi.fn(async () => workspace([])) })
    const fallback = repository({ source: { kind: 'seeded', reason: 'not-configured' } })
    const repo = createDatasetRepository(primary, fallback)
    const [first, second] = await Promise.all([repo.getWorkspace(), repo.getWorkspace()])
    expect(first.datasets).toEqual([])
    expect(second).toEqual(first)
    expect(primary.getWorkspace).toHaveBeenCalledTimes(1)
    expect(fallback.getWorkspace).not.toHaveBeenCalled()
    expect(repo.source.kind).toBe('api')
  })
  it('selects samples only for unavailable backends', async () => {
    const fallback = repository({ source: { kind: 'seeded', reason: 'not-configured' } })
    const repo = createDatasetRepository(repository({ getWorkspace: vi.fn().mockRejectedValue(new BackendUnavailableError()) }), fallback)
    await repo.getDataset(datasetId)
    expect(repo.source).toEqual({ kind: 'seeded', reason: 'backend-unavailable' })
    expect(fallback.getDataset).toHaveBeenCalledWith(datasetId)
  })
  it.each([new ApiError('Forbidden', 403), new Error('Invalid schema')])('does not hide %s with samples', async error => {
    const fallback = repository()
    await expect(createDatasetRepository(repository({ getWorkspace: vi.fn().mockRejectedValue(error) }), fallback).getWorkspace()).rejects.toBe(error)
    expect(fallback.getWorkspace).not.toHaveBeenCalled()
  })
  it('never replays a failed live write against samples', async () => {
    const fallback = repository()
    const primary = repository({ updateRuleset: vi.fn().mockRejectedValue(new BackendUnavailableError('lost response')) })
    const repo = createDatasetRepository(primary, fallback)
    await repo.getWorkspace()
    await expect(repo.updateRuleset(datasetId, ruleset())).rejects.toThrow('lost response')
    expect(fallback.updateRuleset).not.toHaveBeenCalled()
    expect(repo.source.kind).toBe('api')
  })
  it('reports unsupported sample uploads', async () => {
    const repo = createDatasetRepository(undefined, repository({ getUploadPolicy: undefined, upload: undefined }))
    await expect(repo.getUploadPolicy!()).rejects.toThrow(/not available/)
    await expect(repo.upload!({ file: new File(['x'], 'x.csv') })).rejects.toThrow(/not available/)
  })
})
