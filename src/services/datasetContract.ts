import type { DatasetDetail, RuleSet, RuleSetView, Metric, ColumnProfile as BackendColumnProfile } from '../types/backend'
import type { Dataset, DatasetRuleset, QualityRule, QualityDimension, ColumnProfile } from '../types'
import { createDefaultRules } from '../data/qualityRules'
import { assertValidRuleset, qualityNote, RulesetValidationError } from './datasetValidation'

const dateConditions = {
  not_future: 'On or before today', before_today: 'Before today',
  after_today: 'After today', on_or_after_today: 'On or after today',
} as const

export function rulesFromBackend(view: RuleSetView, identifier?: string | null): DatasetRuleset {
  const rules = view.configuration.rules.map((rule): QualityRule => {
    const base = {
      id: rule.id, enabled: rule.enabled ?? true, column: rule.column,
      condition: '', minimum: '' as const, maximum: '' as const,
      severity: rule.severity ?? 'error', backendRule: rule,
    }
    switch (rule.kind) {
      case 'required': case 'unique': case 'numeric': return { ...base, type: rule.kind }
      case 'pattern': return { ...base, type: 'regex', condition: rule.pattern }
      case 'allowed_values': return { ...base, type: 'allowed', condition: rule.values.join(', ') }
      case 'range': return { ...base, type: 'range', minimum: rule.minimum, maximum: rule.maximum }
      case 'min': return { ...base, type: 'min', minimum: rule.minimum }
      case 'max': return { ...base, type: 'max', maximum: rule.maximum }
      case 'date': return { ...base, type: 'date', condition: 'Valid date', dateFormats: rule.formats }
      default: {
        const parser = view.configuration.rules.find(candidate => candidate.id === rule.prerequisite)
        return { ...base, type: 'date', condition: dateConditions[rule.kind], dateFormats: parser?.kind === 'date' ? parser.formats : ['%Y-%m-%d'] }
      }
    }
  })
  if (view.configuration.identifier_policy === 'auto' && identifier) {
    for (const rule of createDefaultRules(identifier)) {
      if (!rules.some(existing => existing.type === rule.type && existing.column === identifier && existing.enabled)) rules.push(rule)
    }
  }
  return {
    id: view.id, name: view.name, description: 'Assigned rule revision ' + view.revision,
    kind: view.is_default ? 'default' : 'custom', rules,
    backendConfiguration: view.configuration,
  }
}

// A pure conversion for future transports. No requests or persistence happen here.
export function rulesToBackend(ruleset: DatasetRuleset, columns: readonly string[]): RuleSet {
  assertValidRuleset({ ...ruleset, rules: ruleset.rules.map(rule => ({ ...rule, enabled: true })) }, columns)
  const ids = new Map(ruleset.rules.map((rule, index) => [rule.id,
    /^[A-Z][A-Z0-9_]+$/.test(rule.id) ? rule.id : 'UI_' + index + '_' + rule.id.replace(/[^A-Za-z0-9_]/g, '_').toUpperCase()]))
  const structuralId = ruleset.backendConfiguration?.structural_rule_id ?? 'DATASET_COLUMNS'
  const used = new Set([structuralId])
  for (const id of ids.values()) {
    if (used.has(id)) throw new RulesetValidationError('Rule IDs conflict with the structure rule.')
    used.add(id)
  }
  const result: RuleSet['rules'] = []
  const ordered = [...ruleset.rules].sort((a, b) => Number(isParser(b)) - Number(isParser(a)))
  for (const rule of ordered) {
    const id = ids.get(rule.id)
    if (!id) throw new RulesetValidationError('Rule ID is missing.')
    const common = { id, column: rule.column, enabled: rule.enabled, severity: rule.severity ?? 'error',
      explanation: rule.backendRule?.explanation ?? rule.column + ' must satisfy ' + rule.type + '.' }
    const prerequisite = (kind: 'numeric' | 'date') => {
      const original = rule.backendRule && 'prerequisite' in rule.backendRule ? rule.backendRule.prerequisite : undefined
      const parser = ruleset.rules.find(candidate => candidate.id === original && candidate.column === rule.column
        && (!rule.enabled || candidate.enabled) && (kind === 'numeric' ? candidate.type === 'numeric' : candidate.type === 'date' && candidate.condition === 'Valid date'))
      if (parser) return ids.get(parser.id) ?? parser.id
      let parserId = id + '_PARSE'
      while (used.has(parserId)) parserId += '_P'
      used.add(parserId)
      const parseBase = { ...common, id: parserId, explanation: rule.column + ' must contain a valid ' + kind + ' value.' }
      result.push(kind === 'numeric' ? { ...parseBase, kind } : { ...parseBase, kind, formats: [...(rule.dateFormats ?? ['%Y-%m-%d'])] })
      return parserId
    }
    switch (rule.type) {
      case 'required': case 'unique': case 'numeric': result.push({ ...common, kind: rule.type }); break
      case 'regex': result.push({ ...common, kind: 'pattern', pattern: rule.condition }); break
      case 'allowed': {
        // Preserve values containing commas when an existing backend rule was not edited.
        const original = rule.backendRule?.kind === 'allowed_values' ? rule.backendRule.values : undefined
        const values = original?.join(', ') === rule.condition ? original : [...new Set(rule.condition.split(',').map(value => value.trim()).filter(Boolean))]
        result.push({ ...common, kind: 'allowed_values', values }); break
      }
      case 'min': result.push({ ...common, kind: 'min', minimum: Number(rule.minimum), prerequisite: prerequisite('numeric') }); break
      case 'max': result.push({ ...common, kind: 'max', maximum: Number(rule.maximum), prerequisite: prerequisite('numeric') }); break
      case 'range': result.push({ ...common, kind: 'range', minimum: Number(rule.minimum), maximum: Number(rule.maximum), prerequisite: prerequisite('numeric') }); break
      case 'date':
        if (rule.condition === 'Valid date') result.push({ ...common, kind: 'date', formats: [...(rule.dateFormats ?? ['%Y-%m-%d'])] })
        else {
          const kind = rule.condition === 'On or before today' ? 'not_future' : rule.condition === 'Before today' ? 'before_today'
            : rule.condition === 'After today' ? 'after_today' : 'on_or_after_today'
          result.push({ ...common, kind, prerequisite: prerequisite('date') })
        }
        break
    }
  }
  return {
    ...ruleset.backendConfiguration, schema_version: 1, name: ruleset.name,
    structural_rule_id: structuralId, identifier_policy: 'configured',
    required_columns: [...new Set([...(ruleset.backendConfiguration?.required_columns ?? columns), ...ruleset.rules.map(rule => rule.column)])],
    rules: result,
  }
}
function isParser(rule: QualityRule) { return rule.type === 'numeric' || rule.type === 'date' && rule.condition === 'Valid date' }

function profileFromBackend(profile: BackendColumnProfile): ColumnProfile {
  const summary: ColumnProfile['summary'] = profile.observed_types.every(type => type === 'integer' || type === 'number')
    && profile.numeric_min !== null && profile.numeric_max !== null
    ? { kind: 'number-range', minimum: profile.numeric_min, maximum: profile.numeric_max }
    : profile.observed_types.length === 1 && profile.observed_types[0] === 'date' && profile.date_min && profile.date_max
      ? { kind: 'date-range', minimum: profile.date_min, maximum: profile.date_max }
      : { kind: 'top-values', values: profile.top_categories }
  return { name: profile.column, observedTypes: profile.observed_types, missingCount: profile.missing_count, uniqueCount: profile.distinct_count, summary }
}

export function datasetFromBackend(detail: DatasetDetail): Dataset {
  const version = detail.selected_version, run = detail.latest_run
  const result = run?.processing_status === 'completed' ? run.result : null
  // Older saved reports retain their historical semantics; require a rerun for row scores.
  const metrics = result?.implementation_version === 'tabular-validation/2.0.0' ? result.metrics : undefined
  const metric = (id: string, label: string, value: Metric | undefined, description: string): QualityDimension => ({
    id, label, score: value?.status === 'available' ? value.percentage ?? null : null,
    passed: value?.numerator ?? null, total: value?.denominator ?? null,
    description: value?.status === 'available' ? description : value?.reason ?? 'Not available',
  })
  const dimensions = [
    metric('completeness', 'Completeness', metrics?.completeness, 'rows with no missing cells'),
    metric('validity', 'Validity', metrics?.valid_row_rate, 'rows without rule errors'),
    metric('uniqueness', 'Uniqueness', metrics?.uniqueness, 'rows unique in all tagged columns'),
  ]
  const scores = dimensions.flatMap(dimension => dimension.score === null ? [] : [dimension.score])
  const findings = result?.findings ?? []
  return {
    id: detail.dataset.id, name: detail.dataset.name,
    source: (version?.metadata.format ?? 'file').toUpperCase() + ' upload', sourceIcon: 'file',
    filename: version?.metadata.original_filename, downloadFilename: version?.metadata.original_filename,
    uploadedAt: detail.uploaded_at ?? undefined, uploadedBy: detail.uploaded_by ?? undefined,
    rowCount: version?.metadata.row_count ?? 0, columns: version?.metadata.headers ?? [],
    version: version ? 'v' + version.number : 'Not available', versionId: version?.id, latestRunId: run?.id,
    isCurrentVersion: !!version && version.id === detail.latest_version_id,
    processingStatus: run?.processing_status ?? 'not_started', processingError: run?.error_code ?? undefined,
    status: run?.processing_status === 'running' ? 'running' : run?.processing_status === 'failed' ? 'failed'
      : !result ? 'unvalidated' : result.validation_status === 'failed' || findings.length ? 'needs-review' : 'healthy',
    lastValidatedAt: result?.checked_at ?? null, rulesChangedSinceRun: detail.rules_changed_since_run,
    quality: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
    qualityDimensions: dimensions, qualityNote: result && !metrics ? 'Re-run validation to calculate row-based quality scores.' : result ? qualityNote : 'Validation results are not available.',
    columnProfiles: result?.profile.columns.map(profileFromBackend) ?? null,
    validation: result ? {
      checksRun: result.rule_results.filter(rule => rule.status !== 'skipped').length,
      issues: findings.map((finding, index) => ({ id: finding.rule_id + ':' + index, column: finding.column ?? 'Dataset',
        rule: finding.rule_id, message: finding.explanation, affectedRows: finding.affected_count })),
    } : null,
    ruleset: rulesFromBackend(detail.assigned_rules, result?.resolved_identifier_column),
    history: detail.recent_events.map(event => ({ id: String(event.sequence), occurredAt: event.created_at,
      title: event.action.replaceAll('_', ' '), description: event.actor })),
  }
}

