import type { DatasetDetail, RuleSet, RuleSetView, Metric, Finding, ColumnProfile as BackendColumnProfile } from '../types/backend'
import type { Dataset, DatasetHistoryEvent, DatasetRuleset, QualityRule, QualityDimension, ColumnProfile } from '../types'
import { createDefaultRules, ruleCondition } from '../data/qualityRules'
import { assertValidRuleset, qualityNote, RulesetValidationError } from './datasetValidation'
import { countStatisticalWarnings } from './statisticalWarnings'
import { isAutomaticIdentifierRule, resolveIdentifier } from './identifiers'
import { formatAllowedValues, parseAllowedValues } from './ruleSyntax'

const dateConditions = {
  on_or_before_date: 'On or before selected date', before_date: 'Before selected date',
  after_date: 'After selected date', on_or_after_date: 'On or after selected date',
} as const

const historyTitles: Readonly<Record<string, DatasetHistoryEvent['title'] | undefined>> = {
  version_uploaded: 'Dataset uploaded', check_completed: 'Validation ran',
  rule_set_assigned: 'Ruleset saved', version_corrected: 'Dataset edited', findings_ignored: 'Findings ignored',
}

export function rulesFromBackend(view: RuleSetView, identifier?: string | null): DatasetRuleset {
  const rules = view.configuration.rules.filter(rule => !(rule.kind === 'numeric' && rule.generated_for)).map((rule): QualityRule => {
    const base = {
      id: rule.id, enabled: rule.enabled ?? true, column: rule.column,
      condition: '', minimum: 0, maximum: 100,
      severity: rule.severity ?? 'error', backendRule: rule,
    }
    switch (rule.kind) {
      case 'required': case 'unique': case 'numeric': return { ...base, type: rule.kind, condition: ruleCondition(rule.kind) }
      case 'pattern': return { ...base, type: 'regex', condition: rule.pattern }
      case 'allowed_values': return { ...base, type: 'allowed', condition: formatAllowedValues(rule.values) }
      case 'range': return { ...base, type: 'range', minimum: rule.minimum, maximum: rule.maximum }
      case 'min': return { ...base, type: 'min', minimum: rule.minimum }
      case 'max': return { ...base, type: 'max', maximum: rule.maximum }
      case 'between_dates': return { ...base, type: 'date', condition: 'Between two selected dates', selectedDate: rule.start_date, endDate: rule.end_date, dateFormats: rule.formats }
      default: return { ...base, type: 'date', condition: dateConditions[rule.kind], selectedDate: rule.date, dateFormats: rule.formats }
    }
  })
  if (view.configuration.identifier_policy === 'auto' && identifier) {
    rules.push(...createDefaultRules(identifier).map(rule => ({
      ...rule, id: rule.type === 'required' ? 'GENERIC_ID_REQUIRED' : 'GENERIC_ID_UNIQUE', severity: 'error' as const,
    })))
  }
  return {
    id: view.id, name: view.name, description: 'Assigned rule revision ' + view.revision,
    kind: view.is_default ? 'default' : 'custom', rules, backendConfiguration: view.configuration,
  }
}

// Pure conversion for future transports; authoritative assigned policy is retained.
export function rulesToBackend(ruleset: DatasetRuleset, columns: readonly string[]): RuleSet {
  if (ruleset.kind !== 'custom') throw new RulesetValidationError('Create a custom ruleset before saving changes.')
  assertValidRuleset(ruleset, columns)
  const ids = new Map(ruleset.rules.map((rule, index) => [rule.id,
    /^[A-Z][A-Z0-9_]+$/.test(rule.id) ? rule.id : 'UI_' + index + '_' + rule.id.replace(/[^A-Za-z0-9_]/g, '_').toUpperCase()]))
  const structuralId = ruleset.backendConfiguration?.structural_rule_id ?? 'DATASET_COLUMNS'
  const used = new Set([structuralId, ...ids.values()])
  const result: RuleSet['rules'] = []
  for (const rule of ruleset.rules) {
    if (isAutomaticIdentifierRule(ruleset, rule)) continue
    const id = ids.get(rule.id)
    if (!id) throw new RulesetValidationError('Rule ID is missing.')
    const common = { id, column: rule.column, enabled: rule.enabled, severity: rule.severity ?? 'error',
      explanation: rule.column + ' must satisfy ' + rule.type + '.' }
    const prerequisite = () => {
      let parserId = id + '_PARSE'
      while (used.has(parserId)) parserId += '_P'
      used.add(parserId)
      result.push({ ...common, id: parserId, kind: 'numeric', generated_for: id })
      return parserId
    }
    switch (rule.type) {
      case 'required': case 'unique': case 'numeric': result.push({ ...common, kind: rule.type }); break
      case 'regex': result.push({ ...common, kind: 'pattern', pattern: rule.condition, explanation: rule.column + ' must match ' + rule.condition + '.' }); break
      case 'allowed': {
        const values = parseAllowedValues(rule.condition)
        result.push({ ...common, kind: 'allowed_values', values, explanation: rule.column + ' must be one of: ' + values.join(', ') + '.' }); break
      }
      case 'min': result.push({ ...common, kind: 'min', minimum: Number(rule.minimum), prerequisite: prerequisite(),
        explanation: rule.column + ' must satisfy min: ' + rule.minimum + '.' }); break
      case 'max': result.push({ ...common, kind: 'max', maximum: Number(rule.maximum), prerequisite: prerequisite(),
        explanation: rule.column + ' must satisfy max: ' + rule.maximum + '.' }); break
      case 'range': result.push({ ...common, kind: 'range', minimum: Number(rule.minimum), maximum: Number(rule.maximum), prerequisite: prerequisite(),
        explanation: rule.column + ' must satisfy range: ' + rule.minimum + ' through ' + rule.maximum + '.' }); break
      case 'date': {
        const formats = [...(rule.dateFormats ?? ['%Y-%m-%d'])]
        const explanation = rule.column + ' must satisfy ' + rule.condition + ': ' + rule.selectedDate
          + (rule.condition === 'Between two selected dates' ? ' through ' + rule.endDate + ' (inclusive).' : '.')
        if (rule.condition === 'Between two selected dates') result.push({ ...common, explanation, kind: 'between_dates', formats, start_date: rule.selectedDate ?? '', end_date: rule.endDate ?? '' })
        else {
          const kind = rule.condition === 'On or before selected date' ? 'on_or_before_date' : rule.condition === 'Before selected date' ? 'before_date'
            : rule.condition === 'After selected date' ? 'after_date' : 'on_or_after_date'
          result.push({ ...common, explanation, kind, formats, date: rule.selectedDate ?? '' })
        }
        break
      }
    }
  }
  const policy = ruleset.backendConfiguration?.identifier_policy ?? 'configured'
  return {
    ...ruleset.backendConfiguration, schema_version: 1, name: ruleset.name,
    structural_rule_id: structuralId, identifier_policy: policy,
    required_columns: [...new Set([...(ruleset.backendConfiguration?.required_columns ?? (policy === 'auto' ? [] : columns)),
      ...ruleset.rules.filter(rule => !isAutomaticIdentifierRule(ruleset, rule)).map(rule => rule.column)])],
    rules: result,
  }
}

function profileFromBackend(profile: BackendColumnProfile, findings: readonly Finding[]): ColumnProfile {
  const summary: ColumnProfile['summary'] = profile.observed_types.length === 1
    && profile.numeric_min !== null && profile.numeric_max !== null
    ? { kind: 'number-range', minimum: profile.numeric_min, maximum: profile.numeric_max }
    : profile.observed_types.length === 1 && profile.observed_types[0] === 'date' && profile.date_min && profile.date_max
      ? { kind: 'date-range', minimum: profile.date_min, maximum: profile.date_max }
      : { kind: 'top-values', values: profile.top_categories }
  return { name: profile.column, observedTypes: profile.observed_types, missingCount: profile.missing_count,
    warningCount: countStatisticalWarnings(profile.column, findings), uniqueCount: profile.distinct_count, summary }
}

export function datasetFromBackend(detail: DatasetDetail): Dataset {
  const version = detail.selected_version, run = detail.latest_run
  const headers = version?.metadata.headers ?? []
  const result = run?.processing_status === 'completed' ? run.result : null
  const compatible = !!result && (result.metric_semantics === 'row-based-v1'
    || ['tabular-validation/2.0.0', 'tabular-validation/2.1.0'].includes(result.implementation_version))
  const metrics = compatible ? result?.metrics : undefined
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
  const assigned = rulesFromBackend(detail.assigned_rules)
  const identifier = detail.resolved_identifier_column !== undefined ? detail.resolved_identifier_column : resolveIdentifier(assigned, headers).column
  const ruleset = rulesFromBackend(detail.assigned_rules, identifier)
  // Counts and issue labels belong to the rules pinned to the completed run, not unsaved/current changes.
  const appliedView = result ? { ...detail.assigned_rules, configuration: result.configuration } : null
  const appliedBase = appliedView ? rulesFromBackend(appliedView) : null
  const applied = appliedView && appliedBase ? rulesFromBackend(appliedView,
    result?.resolved_identifier_column ?? resolveIdentifier(appliedBase, headers).column) : null
  const visible = applied?.rules.filter(rule => rule.enabled) ?? []
  const issues = findings.filter(finding => (finding.category ?? 'validation') === 'validation'
    && (visible.some(rule => rule.id === finding.rule_id) || finding.rule_id === result?.configuration.structural_rule_id))
  let note = result ? compatible ? qualityNote : 'Run validation to calculate row-based quality scores.' : 'Validation results are not available.'
  if (detail.data_changed_since_run) note = 'Data changed. Run validation to calculate profiles, issues, and quality scores.'
  else if (detail.ignored_cell_count) note += ' Ignored rule findings are excluded from error counts; completeness still reflects actual missing cells.'
  const globalWarnings = findings.filter(finding => finding.category && finding.category !== 'validation' && !finding.affected_record_numbers.length)
  if (globalWarnings.length) note += ' Dataset warnings: ' + [...new Set(globalWarnings.map(finding => finding.explanation))].join(' ')
  return {
    id: detail.dataset.id, name: detail.dataset.name,
    source: (detail.source_format ?? version?.metadata.format ?? 'file').toUpperCase() + ' upload', sourceIcon: 'file',
    filename: detail.source_filename ?? version?.metadata.original_filename,
    downloadFilename: version ? detail.dataset.id + '_v' + version.number + '.' + (version.metadata.format ?? 'csv') : undefined,
    uploadedAt: detail.uploaded_at ?? undefined, uploadedBy: detail.uploaded_by ?? undefined,
    rowCount: version?.metadata.row_count ?? 0, columns: headers,
    version: version ? 'v' + version.number : 'Not available', versionId: version?.id, latestRunId: run?.id,
    isCurrentVersion: !!version && version.id === detail.latest_version_id,
    processingStatus: run?.processing_status ?? 'not_started', processingError: run?.error_code ?? undefined,
    status: run?.processing_status === 'running' ? 'running' : run?.processing_status === 'failed' ? 'failed'
      : !result ? 'unvalidated' : findings.length ? 'needs-review' : visible.length ? 'healthy' : 'unvalidated',
    lastValidatedAt: result?.checked_at ?? null, rulesChangedSinceRun: detail.rules_changed_since_run,
    reviewChangedSinceRun: detail.review_changed_since_run ?? false, dataChangedSinceRun: detail.data_changed_since_run ?? false,
    validationPending: detail.validation_pending ?? (!result || !compatible || detail.rules_changed_since_run
      || !!detail.review_changed_since_run || !!detail.data_changed_since_run),
    cellReview: run?.processing_status === 'running' || run?.processing_status === 'failed' ? null : detail.cell_review ?? null,
    quality: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null,
    qualityDimensions: dimensions, qualityNote: note,
    columnProfiles: result?.profile.columns.map(profile => profileFromBackend(profile, findings)) ?? null,
    validation: result ? { checksRun: visible.length, issues: issues.map(finding => ({
      id: finding.rule_id, column: finding.column ?? 'Dataset',
      rule: visible.find(rule => rule.id === finding.rule_id)?.type ?? finding.rule_id,
      message: finding.explanation, affectedRows: finding.affected_count,
    })) } : null,
    ruleset,
    history: detail.recent_events.flatMap(event => {
      const title = Object.hasOwn(historyTitles, event.action) ? historyTitles[event.action] : undefined
      return title ? [{ id: String(event.sequence), occurredAt: event.created_at, title, description: event.description || event.actor }] : []
    }),
  }
}
