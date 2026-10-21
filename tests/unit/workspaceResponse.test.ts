import { describe, expect, it } from 'vitest'
import { parseDataset, parseUploadPolicy, parseWorkspace } from '@/services'
import { dataset, workspace } from '../fixtures/workspace'

describe('transport contracts', () => {
  it('accepts a complete workspace and an authoritative empty catalog', () => {
    expect(parseWorkspace(workspace()).datasets).toHaveLength(1)
    expect(parseWorkspace(workspace([])).datasets).toEqual([])
    expect(parseDataset(dataset({ quality: null, validation: null, columnProfiles: null, cellReview: null }))).toMatchObject({ quality: null })
  })
  it.each([null, [], {}, { ...workspace(), datasets: [{}] }, { ...workspace(), ruleCatalog: null }])('rejects malformed workspaces %#', value => expect(() => parseWorkspace(value)).toThrow(/invalid workspace/))
  it.each([
    { rowCount: -1 }, { rowCount: 1.5 }, { quality: Infinity }, { status: 'unknown' }, { status: 'blocked' }, { lastValidatedAt: 'no-date' },
    { columns: [1] }, { validation: { checksRun: -1, issues: [] } }, { cellReview: [{ cells: [{ rowNumber: 0 }] }] },
    { history: [{ id: 'bad', occurredAt: 'bad', title: 'Unknown', description: '' }] },
  ])('rejects invalid dataset fields %j', patch => expect(() => parseDataset({ ...dataset(), ...patch })).toThrow(/invalid dataset/))
  it('validates upload limits', () => {
    expect(parseUploadPolicy({ extensions: ['.csv'], max_upload_bytes: 10 })).toEqual({ extensions: ['.csv'], max_upload_bytes: 10 })
    expect(() => parseUploadPolicy({ extensions: '.csv', max_upload_bytes: -1 })).toThrow(/upload policy/)
  })
})
