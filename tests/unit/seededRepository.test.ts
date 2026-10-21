import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createSeededDatasetRepository } from '@/services'
import type { DatasetRepository } from '@/services'
import { dataset, datasetId, rule, ruleset } from '../fixtures/workspace'

// Keep repository tests small; validation/statistics remain real. Actual demo IDs
// and generated rows are verified separately in datasetIdentity.test.ts.
vi.mock('@/data/datasets', () => ({
  createSeededDatasets: () => [dataset({ ruleset: ruleset([rule(), rule({ id: 'ID_UNIQUE', column: 'id', type: 'unique' })]) })],
}))
vi.mock('@/data/datasetRows', () => ({
  getSeededDatasetRows: () => [{ id: 'A', value: null }, { id: 'A', value: null }, { id: 'B', value: 10 }],
}))

describe('versioned sample repository', () => {
  let repo: DatasetRepository
  beforeEach(() => { repo = createSeededDatasetRepository() })
  const request = (groupId: string) => ({ version: 'v1', groupId, rowNumber: 1, scope: 'one' as const, action: { type: 'replace' as const, value: '20' } })
  it('returns isolated snapshots so consumers cannot mutate stored data', async () => {
    const loaded = await repo.getDataset(datasetId)
    loaded.name = 'Mutated'
    expect((await repo.getDataset(datasetId)).name).toBe('Test inventory')
    await expect(repo.getDataset('Test inventory')).rejects.toThrow(/not found/)
    await expect(repo.download(datasetId, 'v99')).rejects.toThrow(/not found/)
  })
  it('saves new rules without changing scores until explicit validation', async () => {
    const initial = await repo.getDataset(datasetId)
    const updated = await repo.updateRuleset(datasetId, ruleset([...initial.ruleset.rules, rule({ id: 'MIN', type: 'min', minimum: 15 })]))
    expect(updated).toMatchObject({ version: 'v1', quality: initial.quality, rulesChangedSinceRun: true, validationPending: true })
    const validated = await repo.revalidate(datasetId, 'v1')
    expect(validated).toMatchObject({ version: 'v2', validationPending: false, rulesChangedSinceRun: false })
    expect(validated.validation?.issues.some(i => i.id === 'MIN')).toBe(true)
    expect((await repo.revalidate(datasetId, 'v2')).version).toBe('v2')
    await expect(repo.revalidate(datasetId, 'v1')).rejects.toThrow(/newer version/)
    await expect(repo.updateRuleset(datasetId, ruleset([], { kind: 'default' }))).rejects.toThrow(/custom/)
  })
  it('preserves original download bytes and validates edits in their existing version', async () => {
    const original = await (await repo.download(datasetId, 'v1')).blob.text()
    const initial = await repo.getDataset(datasetId)
    const group = initial.cellReview!.find(g => g.ruleId === 'VALUE_REQUIRED')!
    const updated = await repo.applyCellReview(datasetId, request(group.id))
    expect(updated).toMatchObject({ version: 'v2', quality: null, columnProfiles: null, processingStatus: 'not_started', dataChangedSinceRun: true })
    expect(await (await repo.download(datasetId, 'v1')).blob.text()).toBe(original)
    expect(await (await repo.download(datasetId, 'v2')).blob.text()).toContain('"A","20"')
    const validated = await repo.revalidate(datasetId, 'v2')
    expect(validated.version).toBe('v2')
    expect(validated.validation?.issues.find(i => i.id === 'VALUE_REQUIRED')?.affectedRows).toBe(1)
  })
  it('deletes matching rows and remaps remaining review row numbers', async () => {
    const initial = await repo.getDataset(datasetId)
    const group = initial.cellReview!.find(g => g.ruleId === 'VALUE_REQUIRED')!
    const updated = await repo.applyCellReview(datasetId, { ...request(group.id), action: { type: 'delete-row' } })
    expect(updated.rowCount).toBe(2)
    expect(updated.cellReview?.flatMap(g => g.cells).every(c => c.rowNumber <= 2)).toBe(true)
    expect(updated.cellReview?.find(g => g.ruleId === 'VALUE_REQUIRED')?.cells[0]?.rowNumber).toBe(1)
  })
  it('ignores findings without changing source values or completeness', async () => {
    const initial = await repo.getDataset(datasetId)
    const group = initial.cellReview!.find(g => g.ruleId === 'VALUE_REQUIRED')!
    const ignored = await repo.applyCellReview(datasetId, { ...request(group.id), scope: 'all', action: { type: 'ignore', reason: 'Verified' } })
    expect(ignored.version).toBe('v1')
    expect(ignored.cellReview?.some(g => g.id === group.id)).toBe(false)
    const validated = await repo.revalidate(datasetId, 'v1')
    expect(validated.validation?.issues.some(i => i.id === 'VALUE_REQUIRED')).toBe(false)
    expect(validated.qualityDimensions[0]?.score).toBe(initial.qualityDimensions[0]?.score)
    expect(validated.history?.at(-2)?.title).toBe('Findings ignored')
  })
  it.each(['', ' ', 'bad\0value'])('rejects invalid replacement %j without creating a version', async value => {
    const initial = await repo.getDataset(datasetId)
    await expect(repo.applyCellReview(datasetId, { ...request(initial.cellReview![0]!.id), action: { type: 'replace', value } })).rejects.toThrow()
    expect((await repo.getDataset(datasetId)).version).toBe('v1')
  })
  it('guards stale findings, oversized reasons and bulk unique replacements', async () => {
    const initial = await repo.getDataset(datasetId)
    await expect(repo.applyCellReview(datasetId, request('missing'))).rejects.toThrow(/no longer available/)
    const group = initial.cellReview!.find(g => g.ruleId === 'ID_UNIQUE')!
    await expect(repo.applyCellReview(datasetId, { ...request(group.id), scope: 'all' })).rejects.toThrow(/one cell at a time/)
    await expect(repo.applyCellReview(datasetId, { ...request(group.id), action: { type: 'replace', value: 'A' } })).rejects.toThrow(/different/)
    await expect(repo.applyCellReview(datasetId, { ...request(group.id), action: { type: 'ignore', reason: 'x'.repeat(2001) } })).rejects.toThrow(/2000/)
  })
})
