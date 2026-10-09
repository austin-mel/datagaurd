import { cloneRuleset, createDefaultRules, ruleCondition, type DatasetRuleset } from './qualityRules'

export interface Dataset {
  id: string
  name: string
  source: string
  sourceIcon: 'file' | 'cloud'
  filename?: string
  rowCount: number
  version: string
  quality: number
  lastValidatedAt: string
  lastValidatedLabel: string
  columns: readonly string[]
  ruleset: DatasetRuleset
}

// Fictional catalog records from the visual reference. Session state is cloned below.
export const seededDatasets: readonly Dataset[] = [
  {
    id: 'facilities',
    name: 'County facilities',
    source: 'CSV upload',
    sourceIcon: 'file',
    filename: 'facilities.csv',
    rowCount: 20,
    version: 'v3',
    quality: 89.1,
    lastValidatedAt: '2026-10-07T09:12:00-07:00',
    lastValidatedLabel: 'Oct 7 · 09:12',
    columns: ['facility_id', 'facility_name', 'county', 'facility_type', 'inspection_score', 'inspection_date'],
    ruleset: {
      kind: 'custom',
      rules: [
        ...createDefaultRules('facility_id'),
        { id: 'score-range', enabled: true, column: 'inspection_score', type: 'range', condition: '', minimum: 0, maximum: 100 },
        { id: 'inspection-date', enabled: true, column: 'inspection_date', type: 'date', condition: ruleCondition('date'), minimum: 0, maximum: 100 },
        { id: 'county-allowed', enabled: true, column: 'county', type: 'allowed', condition: 'Alameda, Contra Costa, Sacramento', minimum: 0, maximum: 100 },
      ],
    },
  },
  {
    id: 'customers',
    name: 'Customer master',
    source: 'Salesforce API',
    sourceIcon: 'cloud',
    rowCount: 248512,
    version: 'v12',
    quality: 97.8,
    lastValidatedAt: '2026-10-07T08:54:00-07:00',
    lastValidatedLabel: 'Oct 7 · 08:54',
    columns: ['customer_id', 'customer_name', 'email', 'country'],
    ruleset: { kind: 'default', rules: createDefaultRules('customer_id') },
  },
]

export function createSeededDatasets(): Dataset[] {
  return seededDatasets.map(dataset => ({
    ...dataset,
    columns: [...dataset.columns],
    ruleset: cloneRuleset(dataset.ruleset),
  }))
}
