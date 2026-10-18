import { createDefaultRules, ruleCondition } from './qualityRules'
import type { Dataset } from '@/types'
import { seededRowCounts } from './datasetRows'
import { seededDatasetIds } from './datasetIds'

type DatasetSeed = Omit<Dataset, 'validation' | 'quality' | 'qualityDimensions' | 'qualityNote' | 'status' | 'processingStatus' | 'rulesChangedSinceRun' | 'columnProfiles'>

// Sample catalog metadata; profiles, findings, and scores are calculated from source rows.
const seededDatasets: readonly DatasetSeed[] = [
  {
    id: seededDatasetIds.facilities,
    name: 'County facilities',
    source: 'CSV upload',
    sourceIcon: 'file',
    filename: 'facilities.csv',
    uploadedAt: '2026-10-07T09:12:00-07:00',
    uploadedBy: 'Alex Lee',
    downloadFilename: 'county_facilities_v3.csv',
    history: [
      { id: 'facilities-v3-uploaded', occurredAt: '2026-10-07T09:12:00-07:00', title: 'Dataset uploaded', description: 'Alex Lee · facilities.csv · v3' },
      { id: 'facilities-v3-validated', occurredAt: '2026-10-07T09:12:02-07:00', title: 'Validation ran', description: 'System · v3 · Validation results saved.' },
    ],
    rowCount: seededRowCounts.facilities,
    version: 'v3',
    isCurrentVersion: true,
    lastValidatedAt: '2026-10-07T09:12:02-07:00',
    columns: ['facility_id', 'facility_name', 'county', 'facility_type', 'inspection_score', 'inspection_date'],
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
    id: seededDatasetIds.customers,
    name: 'Customer master',
    source: 'CSV upload',
    sourceIcon: 'file',
    filename: 'customers.csv',
    uploadedAt: '2026-10-07T08:53:00-07:00',
    uploadedBy: 'Demo operator',
    downloadFilename: 'customer_master_v12.csv',
    history: [
      { id: 'customers-v12-validated', occurredAt: '2026-10-07T08:54:00-07:00', title: 'Validation ran', description: 'System · v12 · Validation results saved.' },
    ],
    rowCount: seededRowCounts.customers,
    version: 'v12',
    isCurrentVersion: true,
    lastValidatedAt: '2026-10-07T08:54:00-07:00',
    columns: ['customer_id', 'customer_name', 'email', 'country'],
    ruleset: {
      id: 'customer-id-checks', name: 'Customer ID checks',
      description: 'Required and unique customer IDs.',
      kind: 'default', rules: createDefaultRules('customer_id'),
    },
  },
  {
    id: seededDatasetIds.inventory, name: 'Office inventory', source: 'CSV upload', sourceIcon: 'file',
    filename: 'inventory.csv', downloadFilename: 'office_inventory_v1.csv',
    uploadedAt: '2026-10-07T09:00:00-07:00', uploadedBy: 'Demo operator',
    rowCount: seededRowCounts.inventory, version: 'v1', isCurrentVersion: true,
    lastValidatedAt: '2026-10-07T09:00:02-07:00',
    columns: ['product_id', 'product_name', 'category', 'quantity', 'unit_price'],
    history: [
      { id: 'inventory-upload', occurredAt: '2026-10-07T09:00:00-07:00', title: 'Dataset uploaded', description: 'Demo operator · inventory.csv · v1' },
      { id: 'inventory-check', occurredAt: '2026-10-07T09:00:02-07:00', title: 'Validation ran', description: 'System · v1 · Validation results saved.' },
    ],
    ruleset: {
      id: 'inventory-checks', name: 'Inventory checks', description: 'Product identifiers, stock levels, and prices.', kind: 'custom',
      rules: [
        ...createDefaultRules('product_id'),
        { id: 'quantity-min', enabled: true, column: 'quantity', type: 'min', condition: '', minimum: 0, maximum: 100 },
        { id: 'price-range', enabled: true, column: 'unit_price', type: 'range', condition: '', minimum: 0, maximum: 1000 },
      ],
    },
  },
]

export function createSeededDatasets(): DatasetSeed[] {
  return seededDatasets.map(dataset => {
    const copy = structuredClone(dataset)
    const automatic = copy.ruleset.kind === 'default'
    copy.ruleset = { ...copy.ruleset,
      backendConfiguration: { schema_version: 1, name: copy.ruleset.name, structural_rule_id: 'DATASET_COLUMNS',
        required_columns: automatic ? [] : [...copy.columns], rules: [],
        identifier_policy: automatic ? 'auto' : 'configured', identifier_column: automatic ? null : copy.columns[0] },
      rules: copy.ruleset.rules.map(rule => automatic ? { ...rule, id: rule.type === 'required' ? 'GENERIC_ID_REQUIRED' : 'GENERIC_ID_UNIQUE' } : rule),
    }
    return copy
  })
}

