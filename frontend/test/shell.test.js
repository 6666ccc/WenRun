import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const source = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '../src/components/AppShell.vue'),
  'utf8',
)

test('sidebar brand logo is not targeted by generic brand span rules', () => {
  assert.match(source, /class="app-shell__logo"/)
  assert.match(source, /class="app-shell__brand-text"/)
  assert.doesNotMatch(source, /\.app-shell__brand span\b/)
  assert.match(source, /\.app-shell__logo\s*\{[^}]*display:\s*grid/)
})
