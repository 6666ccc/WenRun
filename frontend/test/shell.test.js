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
  assert.match(source, /to: '\/archive', icon: 'user', label: '个人档案'/)
  assert.match(tabbar, /to: '\/archive', icon: 'user', label: '个人档案'/)
})

test('home and patient service routes share the workspace; legacy assistant path redirects', () => {
  const workspace = (path) => new RegExp(`path: '${path.replace(/[/:]/g, '\\$&')}', component: \\(\\) => import\\('\\.\\.\\/views\\/PatientWorkspace\\.vue'\\)`)
  for (const path of ['/home', '/registration', '/registration/:id']) assert.match(router, workspace(path))
  assert.match(router, /path: '\/assistant', redirect: assistantRedirect/)
  assert.match(router, /path: '\/user', redirect: userArchiveRedirect/)
  assert.match(router, /path: '\/archive', component: \(\) => import\('\.\.\/views\/PatientArchive\.vue'\)/)
  assert.doesNotMatch(router, /Home\.vue/)
})

test('workspace drawer content is reused by the standalone mobile views', () => {
  const workspace = read('../src/views/PatientWorkspace.vue')
  assert.match(workspace, /SideDrawer/)
  for (const name of ['RegistrationBooking', 'RegistrationRecord']) assert.match(workspace, new RegExp(name))
  assert.doesNotMatch(workspace, /UserProfile|User\.vue/)
  assert.match(read('../src/views/Registration.vue'), /RegistrationBooking/)
  assert.match(read('../src/views/RegistrationDetail.vue'), /RegistrationRecord/)
  assert.match(read('../src/views/RegistrationDetail.vue'), /path: '\/archive'[\s\S]*tab: 'registrations'/)
  assert.doesNotMatch(read('../src/views/Assistant.vue'), /assistant-task/)
})
