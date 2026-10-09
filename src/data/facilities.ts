export const facilities = {
  name: 'County facilities',
  source: 'CSV upload',
  rowCount: 20,
  version: 'v3',
  quality: 89.1,
} as const

export const facilityColumns = [
  'facility_id', 'facility_name', 'county', 'facility_type', 'inspection_score', 'inspection_date',
] as const

export const ruleTypes = [
  { value: 'required', label: 'Required' },
  { value: 'unique', label: 'Unique' },
  { value: 'regex', label: 'Regex' },
  { value: 'range', label: 'Min / max' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
  { value: 'allowed', label: 'Allowed values' },
  { value: 'date', label: 'Date constraint' },
] as const

export type RuleType = (typeof ruleTypes)[number]['value']

export interface QualityRule {
  id: string
  enabled: boolean
  column: (typeof facilityColumns)[number]
  type: RuleType
  condition: string
  minimum: number | ''
  maximum: number | ''
  severity: 'High' | 'Medium' | 'Low'
}

export function ruleCondition(type: RuleType): string {
  switch (type) {
    case 'required': return 'Not empty'
    case 'unique': return 'One occurrence per non-empty ID'
    case 'date': return 'On or before today'
    default: return ''
  }
}

export function createFacilityRules(): QualityRule[] {
  const base = { enabled: true, minimum: 0, maximum: 100 } as const
  return [
    { ...base, id: 'facility-required', column: 'facility_id', type: 'required', condition: ruleCondition('required'), severity: 'High' },
    { ...base, id: 'facility-unique', column: 'facility_id', type: 'unique', condition: ruleCondition('unique'), severity: 'High' },
    { ...base, id: 'score-range', column: 'inspection_score', type: 'range', condition: '', severity: 'High' },
    { ...base, id: 'inspection-date', column: 'inspection_date', type: 'date', condition: ruleCondition('date'), severity: 'Medium' },
    { ...base, id: 'county-allowed', column: 'county', type: 'allowed', condition: 'Alameda, Contra Costa, Sacramento', severity: 'Medium' },
  ]
}
