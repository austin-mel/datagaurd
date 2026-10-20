interface RuleFields {
  id: string
  column: string
  severity?: 'error' | 'warning'
  explanation: string
  enabled?: boolean
}

// Backend rule, finding, and upload types used by the current frontend and sample exporter.

export type AllowedRule = RuleFields & {
  kind: 'allowed_values'
  values: string[]
}

export type DateBetweenRule = RuleFields & {
  formats?: ('%Y-%m-%d' | '%m/%d/%Y' | '%d/%m/%Y')[]
  kind: 'between_dates'
  start_date: string
  end_date: string
}

export type DateBoundRule = RuleFields & {
  formats?: ('%Y-%m-%d' | '%m/%d/%Y' | '%d/%m/%Y')[]
  kind: 'on_or_before_date' | 'on_or_after_date' | 'before_date' | 'after_date'
  date: string
}

export type Finding = {
  rule_id: string
  column: string | null
  category?: 'validation' | 'schema' | 'statistical'
  baseline_id?: string | null
  severity: 'error' | 'warning'
  explanation: string
  observed_result: Record<string, JsonValue>
  threshold: Record<string, JsonValue>
  affected_count: number
  record_samples: RecordSample[]
  affected_record_numbers: number[]
}

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }

export type MaxRule = RuleFields & {
  kind: 'max'
  maximum: number
  prerequisite: string
}

export type MinRule = RuleFields & {
  kind: 'min'
  minimum: number
  prerequisite: string
}

export type NumericRule = RuleFields & {
  generated_for?: string | null
  kind: 'numeric'
}

export type PatternRule = RuleFields & {
  kind: 'pattern'
  pattern: string
}

export type RangeRule = RuleFields & {
  kind: 'range'
  minimum: number
  maximum: number
  prerequisite: string
}

export type RecordSample = {
  record_number: number
  value: string
}

export type RequiredRule = RuleFields & {
  kind: 'required'
}

export type RuleSet = {
  schema_version: 1
  name: string
  structural_rule_id: string
  required_columns: string[]
  rules: (RequiredRule | UniqueRule | PatternRule | AllowedRule | NumericRule | RangeRule | MinRule | MaxRule | DateBoundRule | DateBetweenRule)[]
  identifier_column?: string | null
  identifier_policy?: 'configured' | 'auto'
  statistics?: StatisticalSettings | null
}

export type StatisticalSettings = {
  statistical_min_samples?: number
  iqr_multiplier?: number
  missingness_increase_percentage_points?: number
  row_count_change_percentage?: number
  category_share_change_percentage_points?: number
}

export type UniqueRule = RuleFields & {
  kind: 'unique'
}

export type UploadPolicy = {
  max_rows?: number
  max_columns?: number
  max_cells?: number
  max_decoded_bytes?: number
  extensions: string[]
  max_upload_bytes: number
  source_kind?: 'file_upload'
}

export const defaultUploadPolicy: UploadPolicy = {
  extensions: ['.csv', '.tsv', '.xlsx', '.parquet'], max_upload_bytes: 104857600, source_kind: 'file_upload',
  max_rows: 500000, max_columns: 1000, max_cells: 2000000, max_decoded_bytes: 209715200,
}
