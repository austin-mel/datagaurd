import type { Dataset } from './dataset'
import type { RuleEditorCatalog } from './ruleset'

export interface DatasetWorkspace {
  datasets: Dataset[]
  ruleCatalog: RuleEditorCatalog
}

export type DatasetDataSource =
  | { kind: 'api' }
  | { kind: 'seeded'; reason: 'not-configured' | 'backend-unavailable' }
