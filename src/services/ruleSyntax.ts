// Match backend rule_syntax.py. Store the raw pattern as a JSON string, without flags or slash delimiters.
export function compilePortablePattern(pattern: string): RegExp {
  if (!pattern.length || pattern.length > 200 || /[^\x00-\x7f]/.test(pattern)) throw new Error('Use a 1–200 character ASCII regex pattern without flags.')
  const classes: Record<string, string> = { d: '0-9', w: 'A-Za-z0-9_', s: ' \\t\\n\\r\\f\\v' }
  let output = '', inClass = false, classContent = false
  for (let index = 0; index < pattern.length; index++) {
    const char = pattern[index] ?? ''
    if (char === '\\') {
      const escaped = pattern[++index]
      if (escaped === undefined) throw new Error('Incomplete regex escape.')
      const content = classes[escaped.toLowerCase()]
      if (content !== undefined) {
        if (inClass && escaped !== escaped.toLowerCase()) throw new Error('Complement shorthand escapes must be outside character classes.')
        output += inClass ? content : '[' + (escaped !== escaped.toLowerCase() ? '^' : '') + content + ']'
      } else if ('nrtfv^$.*+?()[]{}|/\\'.includes(escaped) || (escaped === '-' && inClass)) output += '\\' + escaped
      else throw new Error('Unsupported regex escape. Use literal characters, ASCII classes or d/w/s shorthands.')
      classContent = true
    } else if (inClass) {
      if (char === ']') {
        if (!classContent) throw new Error('Empty character classes are not supported.')
        inClass = false
      } else if (char === '[' || ['&&', '~~', '--', '||'].includes(pattern.slice(index, index + 2))) throw new Error('Nested classes and set operations are not supported.')
      else if (char !== '^' || classContent) classContent = true
      output += char
    } else if (char === '[') { inClass = true; classContent = false; output += char }
    else if (char === ']' || char === '}') throw new Error('Escape literal closing brackets or braces.')
    else if (char === '{') {
      const quantifier = pattern.slice(index).match(/^\{[0-9]+(?:,[0-9]*)?\}/)?.[0]
      if (!quantifier) throw new Error('Use a valid repetition count or escape the brace.')
      if ((quantifier.match(/[0-9]+/g) ?? []).some(count => Number(count) > 1000000)) throw new Error('Regex repetition counts must not exceed 1000000.')
      output += quantifier
      index += quantifier.length - 1
      if (pattern[index + 1] === '+') throw new Error('Possessive quantifiers are not supported.')
    } else if (char === '(' && pattern.slice(index, index + 2) === '(?' && pattern.slice(index, index + 3) !== '(?:') throw new Error('Use plain or noncapturing groups; flags and lookarounds are not supported.')
    else if ('*+?'.includes(char) && pattern[index + 1] === '+') throw new Error('Possessive quantifiers are not supported.')
    else output += char === '.' ? '[^\\n]' : char
  }
  if (inClass) throw new Error('Unclosed character class.')
  try { return new RegExp('^(?:' + output + ')$(?![\\s\\S])', 'u') }
  catch { throw new Error('Enter a valid regular expression.') }
}

export function parseAllowedValues(text: string): string[] {
  const values: string[] = []
  let index = 0
  for (;;) {
    while (index < text.length && /\s/.test(text[index] ?? '')) index++
    let value = ''
    if (text[index] === '"') {
      index++
      for (;;) {
        if (index === text.length) throw new Error('Close the quoted allowed value.')
        const char = text[index++] ?? ''
        if (char !== '"') value += char
        else if (text[index] === '"') { value += '"'; index++ }
        else break
      }
      while (index < text.length && /\s/.test(text[index] ?? '')) index++
      if (index < text.length && text[index] !== ',') throw new Error('Separate allowed values with commas.')
    } else {
      const start = index
      while (index < text.length && text[index] !== ',') index++
      value = text.slice(start, index).trim()
      if (value.includes('"')) throw new Error('Quote the entire value and double embedded quotes.')
    }
    if (!value.trim() || values.includes(value)) throw new Error('Allowed values must be unique and nonblank.')
    values.push(value)
    if (index === text.length) return values
    index++
  }
}
