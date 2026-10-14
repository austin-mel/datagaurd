import { createDefaultRules, ruleCondition } from './qualityRules'
import type { Dataset } from '@/types'
import { seededRowCounts } from './datasetRows'

type DatasetSeed = Omit<Dataset, 'validation' | 'quality' | 'qualityDimensions' | 'qualityNote' | 'status' | 'processingStatus' | 'rulesChangedSinceRun'>

// Fictional catalog records from the visual reference. Session state is cloned below.
export const seededDatasets: readonly DatasetSeed[] = [
  {
    id: 'facilities',
    name: 'County facilities',
    source: 'CSV upload',
    sourceIcon: 'file',
    filename: 'facilities.csv',
    uploadedAt: '2026-10-07T09:12:00-07:00',
    uploadedBy: 'Alex Lee',
    downloadFilename: 'county_facilities_v3.csv',
    history: [
      { id: 'facilities-v3-uploaded', occurredAt: '2026-10-07T09:12:00-07:00', title: 'Version v3 uploaded', description: 'Alex Lee · 20 rows, 6 columns' },
      { id: 'facilities-v3-validated', occurredAt: '2026-10-07T09:12:02-07:00', title: 'Profile, validation, and scoring completed', description: 'System · 5 issues · Overall quality 89.1 / 100' },
      { id: 'facilities-v3-suggestion', occurredAt: '2026-10-07T09:12:03-07:00', title: 'County correction suggested', description: 'System · 2 rows · Awaiting your decision' },
    ],
    rowCount: seededRowCounts.facilities,
    version: 'v3',
    isCurrentVersion: true,
    lastValidatedAt: '2026-10-07T09:12:00-07:00',
    columns: ['facility_id', 'facility_name', 'county', 'facility_type', 'inspection_score', 'inspection_date'],
    columnProfiles: [
      { name: 'facility_id', observedTypes: ['text'], missingCount: 2, uniqueCount: 17, summary: { kind: 'top-values', values: [{ value: 'FAC-004', count: 2 }] } },
      { name: 'facility_name', observedTypes: ['text'], missingCount: 0, uniqueCount: 20, summary: { kind: 'top-values', values: [{ value: 'Bayview Clinic', count: 1 }] } },
      { name: 'county', observedTypes: ['text'], missingCount: 0, uniqueCount: 4, summary: { kind: 'top-values', values: [{ value: 'Sacramento', count: 8 }, { value: 'Alameda', count: 6 }] } },
      { name: 'facility_type', observedTypes: ['text'], missingCount: 0, uniqueCount: 3, summary: { kind: 'top-values', values: [{ value: 'Clinic', count: 10 }, { value: 'School', count: 6 }] } },
      { name: 'inspection_score', observedTypes: ['integer'], missingCount: 0, uniqueCount: 18, summary: { kind: 'number-range', minimum: -8, maximum: 108, minimumInvalid: true, maximumInvalid: true } },
      { name: 'inspection_date', observedTypes: ['date'], missingCount: 0, uniqueCount: 16, summary: { kind: 'date-range', minimum: '2026-09-01', maximum: '2026-10-12' } },
    ],
    ruleset: {
      id: 'facilities-checks',
      name: 'Facilities checks',
      description: 'Required and unique facility IDs, inspection scores and dates, and approved counties.',
      kind: 'custom',
      rules: [
        ...createDefaultRules('facility_id'),
        { id: 'score-range', enabled: true, column: 'inspection_score', type: 'range', condition: '', minimum: 0, maximum: 100 },
        { id: 'inspection-date', enabled: true, column: 'inspection_date', type: 'date', condition: ruleCondition('date'), selectedDate: '2026-10-07', minimum: 0, maximum: 100 },
        { id: 'county-allowed', enabled: true, column: 'county', type: 'allowed', condition: 'Alameda, Contra Costa, Sacramento', minimum: 0, maximum: 100 },
      ],
    },
  },
  {
    id: 'customers',
    name: 'Customer master',
    source: 'CSV upload',
    sourceIcon: 'file',
    filename: 'customers.csv',
    downloadFilename: 'customer_master_v12.csv',
    history: [
      { id: 'customers-v12-validated', occurredAt: '2026-10-07T08:54:00-07:00', title: 'Profile, validation, and scoring completed', description: 'System · 2 issues · Overall quality 97.8 / 100' },
    ],
    rowCount: seededRowCounts.customers,
    version: 'v12',
    isCurrentVersion: true,
    lastValidatedAt: '2026-10-07T08:54:00-07:00',
    columns: ['customer_id', 'customer_name', 'email', 'country'],
    columnProfiles: [
      { name: 'customer_id', observedTypes: ['text'], missingCount: 1243, uniqueCount: 242447, summary: { kind: 'top-values', values: [{ value: 'CUS-001204', count: 3 }] } },
      { name: 'customer_name', observedTypes: ['text'], missingCount: 0, uniqueCount: 244900, summary: { kind: 'top-values', values: [{ value: 'Alex Lee', count: 12 }] } },
      { name: 'email', observedTypes: ['text'], missingCount: 2100, uniqueCount: 244810, summary: { kind: 'top-values', values: [{ value: 'contact@example.com', count: 8 }] } },
      { name: 'country', observedTypes: ['text'], missingCount: 45, uniqueCount: 28, summary: { kind: 'top-values', values: [{ value: 'United States', count: 176432 }, { value: 'Canada', count: 31320 }] } },
    ],
    ruleset: {
      id: 'customer-id-checks', name: 'Customer ID checks',
      description: 'Required and unique customer IDs.',
      kind: 'default', rules: createDefaultRules('customer_id'),
    },
  },
]

export function createSeededDatasets(): DatasetSeed[] {
  return seededDatasets.map(dataset => structuredClone(dataset))
}

