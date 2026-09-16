import test from 'node:test'
import assert from 'node:assert/strict'

import {
  enhanceAssistantHtml,
  parseSlotLine,
  renderAssistantMarkdown,
  stripInternalIds,
} from '../src/features/assistant/markdown.js'
import { marked } from 'marked'

test('stripInternalIds hides schedule identifiers from patients', () => {
  assert.equal(
    stripInternalIds('下午 张伟，余号 20/20，挂号费 50 元（排班id=510）'),
    '下午 张伟，余号 20/20，挂号费 50 元',
  )
})

test('stripInternalIds hides parenthetical numeric ids', () => {
  assert.equal(
    stripInternalIds('上午 张伟 (id=537) ／ 李娜 (id=538)'),
    '上午 张伟 ／ 李娜',
  )
})

test('parseSlotLine reads period doctor remaining and fee', () => {
  assert.deepEqual(
    parseSlotLine('下午 张伟，余号 20/20，挂号费 50 元'),
    {
      raw: '下午 张伟，余号 20/20，挂号费 50 元',
      period: '下午',
      doctors: ['张伟'],
      remaining: '20/20',
      fee: '50',
    },
  )
})

test('enhanceAssistantHtml turns date groups into a slot board', () => {
  const html = enhanceAssistantHtml(
    '<p><strong>9月16日（今天）</strong></p><ul><li>下午 张伟，余号 20/20，挂号费 50 元</li><li>晚上 张伟，余号 10/10，挂号费 50 元</li></ul>',
  )
  assert.match(html, /chat-day__date/)
  assert.match(html, /今天/)
  assert.match(html, /chat-slots/)
  assert.match(html, /chat-slot__period/)
  assert.match(html, /张伟/)
  assert.match(html, /余号 20\/20/)
  assert.match(html, /¥50/)
  assert.doesNotMatch(html, /<ul>/)
})

test('ordinary lists stay lists', () => {
  const html = enhanceAssistantHtml('<ul><li>多喝水</li><li>清淡饮食</li></ul>')
  assert.match(html, /<ul>/)
  assert.doesNotMatch(html, /chat-slots/)
})

test('keeps each date as its own slot group', () => {
  marked.setOptions({ breaks: true, gfm: true })
  const html = renderAssistantMarkdown(`9月16日（今天）
- 晚上 张伟，余号 10/10，挂号费 50 元（排班id=1294）
9月17日（明天）
- 上午 张伟 (id=537) ／ 李娜 (id=538)`, {
    parse: (text) => marked.parse(text || ''),
    sanitize: (value) => value,
  })
  assert.equal((html.match(/class="chat-slots"/g) || []).length, 2)
  assert.match(html, /9月16日/)
  assert.match(html, /9月17日/)
  assert.doesNotMatch(html, /张伟 9月17日/)
  assert.doesNotMatch(html, /排班id/)
})
