import { describe, expect, it, vi } from 'vitest'
import { createDatasetState, createRecentDatasetHistory, RECENT_DATASETS_KEY } from '@/stores'
import { seededDatasetIds } from '@/data'
import type { DatasetRepository } from '@/services'
import { dataset, datasetId, ruleset, workspace } from '../fixtures/workspace'

function repo(overrides: Partial<DatasetRepository> = {}): DatasetRepository {
  return { source: { kind: 'api' }, getWorkspace: vi.fn(async () => workspace()), getDataset: vi.fn(async () => dataset()),
    updateRuleset: vi.fn(async () => dataset({ rulesChangedSinceRun: true })), revalidate: vi.fn(async () => dataset({ version: 'v2' })),
    applyCellReview: vi.fn(async () => dataset({ version: 'v2' })), download: vi.fn(async () => ({ filename: 'data.csv', blob: new Blob(['id']) })), ...overrides }
}

describe('dataset state', () => {
  it('deduplicates pending loads and caches successful initialization', async () => {
    let resolve!: (value: ReturnType<typeof workspace>) => void
    const repository = repo({ getWorkspace: vi.fn(() => new Promise<ReturnType<typeof workspace>>(done => { resolve = done })) })
    const state = createDatasetState(repository)
    const first = state.load()
    expect(state.status.value).toBe('loading')
    expect(state.load()).toBe(first)
    resolve(workspace())
    await first
    await state.load()
    expect(state.status.value).toBe('ready')
    expect(state.source.value).toEqual({ kind: 'api' })
    expect(repository.getWorkspace).toHaveBeenCalledTimes(1)
  })
  it('exposes errors and permits retry', async () => {
    const repository = repo({ getWorkspace: vi.fn().mockRejectedValueOnce(new Error('Denied')).mockResolvedValueOnce(workspace()) })
    const state = createDatasetState(repository)
    await state.load()
    expect(state.error.value).toBe('Denied')
    expect(state.status.value).toBe('error')
    await state.load()
    expect(state.error.value).toBe('')
    expect(state.status.value).toBe('ready')
  })
  it('updates by identity even when display names repeat', async () => {
    const repository = repo({ getWorkspace: vi.fn(async () => workspace([dataset(), dataset({ id: 'other' })])) })
    const state = createDatasetState(repository)
    await state.load()
    await state.saveRuleset(datasetId, ruleset())
    expect(state.datasets.value.map(d => d.rulesChangedSinceRun)).toEqual([true, false])
    await state.applyCellReview(datasetId, { version: 'v1', groupId: 'g', rowNumber: 2, scope: 'one', action: { type: 'delete-row' } })
    expect(state.datasets.value.map(d => d.version)).toEqual(['v2', 'v1'])
    expect((await state.download(datasetId, 'v2')).filename).toBe('data.csv')
  })
  it('does not validate unchanged or missing datasets', async () => {
    const repository = repo(), state = createDatasetState(repository)
    await state.load()
    await state.revalidate(datasetId, 'v1')
    await state.revalidate('missing', 'v1')
    expect(repository.revalidate).not.toHaveBeenCalled()
  })
  it('clears stale scores while running and commits the resulting version', async () => {
    let resolve!: (value: ReturnType<typeof dataset>) => void
    const repository = repo({ getWorkspace: vi.fn(async () => workspace([dataset({ validationPending: true })])), revalidate: vi.fn(() => new Promise<ReturnType<typeof dataset>>(done => { resolve = done })) })
    const state = createDatasetState(repository)
    await state.load()
    const pending = state.revalidate(datasetId, 'v1')
    expect(state.datasets.value[0]).toMatchObject({ status: 'running', quality: null, validation: null, cellReview: null })
    resolve(dataset({ version: 'v2' }))
    await pending
    expect(state.datasets.value[0]).toMatchObject({ version: 'v2', processingStatus: 'completed' })
  })
  it.each([true, false])('reconciles failed validation when refresh succeeds: %s', async refreshed => {
    const repository = repo({ getWorkspace: vi.fn(async () => workspace([dataset({ validationPending: true })])),
      revalidate: vi.fn().mockRejectedValue(new Error('Lost response')),
      getDataset: refreshed ? vi.fn(async () => dataset({ version: 'v2' })) : vi.fn().mockRejectedValue(new Error('Offline')) })
    const state = createDatasetState(repository)
    await state.load()
    await expect(state.revalidate(datasetId, 'v1')).rejects.toThrow('Lost response')
    expect(state.datasets.value[0]).toMatchObject(refreshed ? { version: 'v2', processingStatus: 'completed' } : { processingStatus: 'failed', quality: null, validationPending: true })
  })
  it('gates uploads on live connectivity and inserts by ID', async () => {
    const repository = repo({ getUploadPolicy: vi.fn(async () => ({ extensions: ['.csv'], max_upload_bytes: 10 })), upload: vi.fn(async () => dataset({ version: 'v2' })) })
    const state = createDatasetState(repository)
    await expect(state.loadUploadPolicy()).rejects.toThrow(/live backend/)
    await state.load()
    await state.loadUploadPolicy()
    expect(state.uploadPolicy.value?.max_upload_bytes).toBe(10)
    await state.upload({ file: new File(['id'], 'data.csv') })
    expect(state.datasets.value).toHaveLength(1)
    expect(state.datasets.value[0]?.version).toBe('v2')
  })
})

describe('recent dataset history', () => {
  it('sorts current IDs and removes duplicate and invalid entries', () => {
    const storage = { getItem: () => JSON.stringify([{ datasetId: seededDatasetIds.facilities, openedAt: 1 }, { datasetId: seededDatasetIds.facilities, openedAt: 2 }, { datasetId: '', openedAt: 4 }, { datasetId: 'invalid', openedAt: -1 }]), setItem: vi.fn() }
    const history = createRecentDatasetHistory(storage)
    expect(history.visits.value).toEqual([{ datasetId: seededDatasetIds.facilities, openedAt: 2 }])
    expect(storage.setItem).toHaveBeenCalledWith(RECENT_DATASETS_KEY, JSON.stringify(history.visits.value))
  })
  it('discards sample-name aliases when reconciling current dataset IDs', () => {
    const history = createRecentDatasetHistory({ getItem: () => JSON.stringify([
      { datasetId: 'facilities', openedAt: 3 }, { datasetId: 'demo-facilities', openedAt: 2 },
      { datasetId: seededDatasetIds.facilities, openedAt: 1 },
    ]), setItem: vi.fn() })
    history.reconcile(Object.values(seededDatasetIds))
    expect(history.visits.value).toEqual([{ datasetId: seededDatasetIds.facilities, openedAt: 1 }])
  })
  it('caps at three, moves revisits to the front and reconciles deleted datasets', () => {
    const history = createRecentDatasetHistory({ getItem: () => null, setItem: vi.fn() })
    for (const id of ['a', 'b', 'c', 'd', 'b']) history.record(id, 10)
    history.record('', 10)
    history.record('bad', NaN)
    expect(history.visits.value.map(v => v.datasetId)).toEqual(['b', 'd', 'c'])
    history.reconcile(['c', 'd'])
    expect(history.lastOpenedId.value).toBe('d')
  })
  it.each(['broken JSON', '{}', 'null'])('recovers from corrupt storage %s', value => {
    const history = createRecentDatasetHistory({ getItem: () => value, setItem: () => { throw new Error('Quota') } })
    expect(history.visits.value).toEqual([])
    history.record('id', 1)
    expect(history.lastOpenedId.value).toBe('id')
  })
})
