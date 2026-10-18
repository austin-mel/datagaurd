import { existsSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { fileURLToPath } from 'node:url'

// Resolve app aliases and extensionless TS imports for the manifest exporter.
// Tests use Vitest's resolver and never load this script.
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('@/') || specifier.startsWith('.')) {
      const target = specifier.startsWith('@/')
        ? new URL('../src/' + specifier.slice(2), import.meta.url)
        : new URL(specifier, context.parentURL)
      if (target.protocol === 'file:') {
        for (const suffix of ['.ts', '/index.ts']) {
          const candidate = new URL(target.href + suffix)
          if (existsSync(fileURLToPath(candidate))) return nextResolve(candidate.href, context)
        }
      }
    }
    return nextResolve(specifier, context)
  },
})
