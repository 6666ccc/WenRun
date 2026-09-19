import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const read = (path) => readFileSync(join(here, path), 'utf8')
const source = read('../src/components/AppShell.vue')
const tabbar = read('../src/components/MobileTabbar.vue')
const router = read('../src/router/index.js')

test('sidebar brand logo is not targeted by generic brand span rules', () => {
  assert.match(source, /class="app-shell__logo"/)
  assert.match(source, /class="app-shell__brand-text"/)
  assert.doesNotMatch(source, /\.app-shell__brand span\b/)
  assert.match(source, /\.app-shell__logo\s*\{[^}]*display:\s*grid/)
})

test('patient navigation no longer exposes a separate assistant entry', () => {
  assert.doesNotMatch(source, /to: '\/assistant'/)
  assert.equal((source.match(/\{ to: '/g) || []).length, 3)
  assert.doesNotMatch(tabbar, /\/assistant|featured/)
  assert.equal((tabbar.match(/\{ to: '/g) || []).length, 3)
  assert.match(tabbar, /to: '\/home', icon: 'ai', label: '首页'/)
})

test('home route renders the assistant and the legacy assistant path redirects', () => {
  assert.match(router, /path: '\/home', component: \(\) => import\('\.\.\/views\/Assistant\.vue'\)/)
  assert.match(router, /path: '\/assistant', redirect: assistantRedirect/)
  assert.doesNotMatch(router, /Home\.vue/)
})
