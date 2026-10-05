import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Match Vite's TypeScript-first resolution for the auth modules under test.
export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith('.') && context.parentURL) {
    for (const suffix of ['.ts', '/index.ts']) {
      const url = new URL(specifier + suffix, context.parentURL)
      if (existsSync(fileURLToPath(url))) return nextResolve(url.href, context)
    }
  }
  return nextResolve(specifier, context)
}
