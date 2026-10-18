import { describe, expect, it } from 'vitest'
import { compilePortablePattern, parseAllowedValues } from '@/services/ruleSyntax'

describe('portable patterns', () => {
  it.each([
    ['\\d{2}', '12', true], ['\\d{2}', '１２', false], ['\\w+', 'ABC_12', true],
    ['\\w+', 'café', false], ['\\D+', 'abc', true], ['[\\dA-F]+', '12AF', true],
    ['(?:red|blue)', 'blue', true], ['a.b', 'a\nb', false], ['a.b', 'a\rb', true],
    ['abc', 'xabc', false], ['abc', 'abc\n', false], ['a[-]b', 'a-b', true],
  ])('matches %s against %s: %s', (pattern, value, matches) => {
    expect(compilePortablePattern(String(pattern)).test(String(value))).toBe(matches)
  })
  it.each(['', 'é', 'x'.repeat(201), '\\', '\\bword', '(?=a)', '(?i)a', '(a)\\1', '[\\D]',
    '[]', '[a', '[a&&b]', '[a--b]', '[[]', 'a++', 'a*+', 'a?+', 'a{2}+', 'a{1000001}', 'a{no}', ']', '}', '('])(
    'rejects unsupported or malformed syntax %s', pattern => expect(() => compilePortablePattern(pattern)).toThrow(),
  )
})

describe('allowed values', () => {
  it('preserves quoted whitespace, commas and escaped quotes', () => {
    expect(parseAllowedValues(' alpha, "New York, NY", "a""b", " padded " ')).toEqual(['alpha', 'New York, NY', 'a"b', ' padded '])
  })
  it.each(['', 'a,', ',a', 'a,a', '" "', '"unterminated', '"a"oops', 'a"b'])('rejects %s', value => {
    expect(() => parseAllowedValues(value)).toThrow()
  })
})
