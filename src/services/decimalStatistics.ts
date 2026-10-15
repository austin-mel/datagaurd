// Mirror Python Decimal's 28 significant digits and half-even rounding for IQR fences.
// Values have already passed the same finite-number parser as backend parse_number.
type Decimal = { coefficient: bigint; exponent: number }
const power = (exponent: number) => 10n ** BigInt(exponent)
const absolute = (value: bigint) => value < 0n ? -value : value

function decimal(value: number): Decimal {
  const [mantissa = '0', exponent = '0'] = String(value).toLowerCase().split('e')
  const [whole = '0', fraction = ''] = mantissa.split('.')
  return { coefficient: BigInt(whole + fraction), exponent: Number(exponent) - fraction.length }
}

function rounded(coefficient: bigint, exponent: number): Decimal {
  const excess = absolute(coefficient).toString().length - 28
  if (excess > 0) {
    const divisor = power(excess), remainder = absolute(coefficient % divisor)
    let quotient = coefficient / divisor
    if (remainder * 2n > divisor || (remainder * 2n === divisor && absolute(quotient) % 2n === 1n)) quotient += coefficient < 0n ? -1n : 1n
    coefficient = quotient
    exponent += excess
  }
  return { coefficient, exponent }
}

function add(left: Decimal, right: Decimal): Decimal {
  const exponent = Math.min(left.exponent, right.exponent)
  return rounded(left.coefficient * power(left.exponent - exponent) + right.coefficient * power(right.exponent - exponent), exponent)
}
function subtract(left: Decimal, right: Decimal): Decimal {
  return add(left, { ...right, coefficient: -right.coefficient })
}
function multiply(left: Decimal, right: Decimal): Decimal {
  return rounded(left.coefficient * right.coefficient, left.exponent + right.exponent)
}
function compare(left: Decimal, right: Decimal): number {
  const exponent = Math.min(left.exponent, right.exponent)
  const difference = left.coefficient * power(left.exponent - exponent) - right.coefficient * power(right.exponent - exponent)
  return difference < 0n ? -1 : difference > 0n ? 1 : 0
}
const asNumber = (value: Decimal) => Number(value.coefficient.toString() + 'e' + value.exponent)

export function iqrFences(ordered: readonly number[], multiplier: number) {
  const quartile = (quarter: number) => {
    const position = (ordered.length - 1) * quarter / 4, index = Math.floor(position)
    const left = decimal(ordered[index] ?? 0), right = decimal(ordered[Math.min(index + 1, ordered.length - 1)] ?? 0)
    return add(left, multiply(subtract(right, left), decimal(position - index)))
  }
  const q1 = quartile(1), q3 = quartile(3), spread = subtract(q3, q1)
  const distance = multiply(decimal(multiplier), spread)
  const lower = subtract(q1, distance), upper = add(q3, distance)
  return { q1: asNumber(q1), q3: asNumber(q3), iqr: asNumber(spread), lower: asNumber(lower), upper: asNumber(upper),
    hasSpread: spread.coefficient !== 0n,
    isOutside: (value: number) => compare(decimal(value), lower) < 0 || compare(decimal(value), upper) > 0 }
}

// Compare exact ratios, like backend Fraction, rather than rounding percentage points first.
export function exceedsPercentage(numerator: number, denominator: number, threshold: number): boolean {
  if (!denominator) return false
  const bound = decimal(threshold)
  return compare({ coefficient: 100n * BigInt(numerator), exponent: 0 },
    { coefficient: bound.coefficient * BigInt(denominator), exponent: bound.exponent }) > 0
}
