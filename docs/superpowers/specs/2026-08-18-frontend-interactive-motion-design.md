# 温润诊所患者端交互动画设计

日期：2026-08-18  
状态：设计定稿，待实施  
范围：患者端 Vue 3 前端的动效语言、时长 token、组件过渡、页面编排与无障碍降级。  
依赖：[视觉与交互重构设计](./2026-08-18-frontend-visual-interaction-redesign.md)  
明确边界：本文不改后端接口、AI graph 或业务流程；不引入 GSAP、Framer Motion、Lottie 或大型动画库；不恢复已被视觉稿否决的装饰性氛围动画。

## 1. 结论先行

患者端动效采用 **“临床反馈，而非装饰表演”**：动画只用来确认操作发生、交代界面从哪来到哪去、以及在等待时降低不确定性。绿色品牌可以出现在 focus glow、选中边框和成功勾选上，但不能用呼吸灯、扫光、漂浮光斑或整页入场来制造“智能感”。

一句话体验目标：**用户每次点击后 160ms 内看到控件回应，220ms 内看清新面板从哪出现；等待超过 300ms 才出现骨架；任何位移在减少动态偏好下都退化为淡入或瞬间切换。**

与视觉稿第 5.5 节对齐，并把它扩成可实施的编排合同：

| 层级 | 时长 | 用途 |
|---|---:|---|
| 控件反馈 | 80–160ms | hover、press、focus、边框、背景 |
| 浮层进出 | 180–220ms | Dialog、Drawer、菜单、确认条 |
| 内容替换 | 160–200ms | Tab、列表刷新、步骤切换 |
| 结果确认 | 220–280ms | 成功面板、勾选、金额锁定 |
| 禁止 | >400ms 的常规交互；>5s 且无法暂停的循环；整页入场；无限脉冲装饰 |

## 2. 设计依据

本方案对照当前前端页面（登录、首页、壳层导航、挂号、缴费、科室、档案、健康助手）后，再对照以下公开规范形成，而不是从消费级 App 的炫技动效反推。

1. [NHS：动画必须尊重减少动态设置](https://nhsdigital.github.io/accessibility-checklist/pages/2.3.3-animation-respects-reduce-motion-settings/)指出，滚动视差和点击触发的非必要位移会诱发前庭反应；非必要运动必须可关闭。
2. [WCAG 2.2 Understanding 2.3.3 Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)把视差、整页翻页、大位移列为高风险；尊重 `prefers-reduced-motion` 即可满足该条。
3. [WCAG 2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html)要求自动播放超过 5 秒的运动必须可暂停；本产品因此禁止超过 5 秒的装饰循环。
4. [WCAG 2.3.1 Three Flashes](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)禁止 1 秒内闪烁超过 3 次；流式光标用 1Hz 闪烁，加载点用透明度而非大幅跳动。
5. [NN/g：动画时长](https://www.nngroup.com/articles/animation-duration/)建议常规 UI 动效落在 100–500ms，进入略长于退出；超过 500ms 会被感知为延迟。
6. [Material 3：缓动与时长](https://m3.material.io/styles/motion/easing-and-duration/applying-easing-and-duration)把运动拆成 **空间运动**（位移/缩放）与 **效果运动**（颜色/透明度）；进入用 decelerate，退出用 accelerate。
7. [Apple：Reduced Motion 评估](https://developer.apple.com/help/app-store-connect/manage-app-accessibility/reduced-motion-evaluation-criteria)要求视差、缩放、旋转、多轴运动在减少动态时替换为溶解或颜色变化，而不是直接“删光所有反馈”。
8. 视觉稿第 2 节的 NHS Hub / 按钮 / 错误摘要原则：动效必须服务“看清下一步”，不能抢占主按钮或错误摘要的注意力。

### 2.1 本产品选用的技术路线

不引入新动画框架。理由：现有栈已是 Vue 3 + 原生 CSS；视觉稿明确禁止大型 UI 框架；患者任务以表单、列表、确认、对话为主，CSS transition + Vue `<Transition>` 足够。

实施载体：

- CSS 自定义属性作为唯一时长/缓动源。
- Vue `<Transition>` / `<TransitionGroup>` 只用于 Dialog、Drawer、消息气泡、步骤面板、Toast。
- 加载态继续用现有 `UiState` + skeleton，不另做 Lottie。
- JavaScript 只负责 `matchMedia('(prefers-reduced-motion: reduce)')` 关闭平滑滚动，以及按钮 loading 时锁定宽度。

## 3. 现状审查

当前代码同时存在三套互相打架的动效：旧“宣纸/琥珀金”氛围、AI 夜间诊室装饰、以及视觉重构后在部分页面加上的克制动效。`index.css` 末尾已经用 `animation: none !important` 关掉了 stagger、琥珀金顶线、AI 呼吸光和欢迎区入场，说明方向已经从“氛围表演”转向“稳态界面”，但还没有正向的交互动画合同。

### 3.1 值得保留的反馈

| 现有行为 | 位置 | 处置 |
|---|---|---|
| 按钮/输入 160ms 边框与阴影 | `Home.vue` 服务卡、`Assistant.vue` composer | 提升为全局 token |
| Focus ring：2px brand + mint glow | `index.css` `:focus-visible` | 保留，作为唯一强制反馈 |
| Dialog overlay fade + 内容上浮 | `ConfirmDialog.vue` / `.shared-dialog` | 缩短到 180/220ms，位移不超过 12px |
| 发送按钮 press 缩放 | 助手 composer | 改为 0.98，去掉 hover 上浮 1px 以上 |
| 列表行 hover 背景 | 表格、记录行 | 只做颜色，不做位移 |
| 流式光标 1s step blink | `.chat-stream-cursor` | 保留，但 reduced-motion 时改为静态竖线 |

### 3.2 必须移除或改写的运动

| 现有行为 | 问题 | 替换 |
|---|---|---|
| `.amber-line` 3.5s 无限脉动 | 装饰循环 >5s，且与薄荷绿品牌冲突 | 删除顶线 |
| `@keyframes bgBreathe` 整页换底色 | 与内容阅读竞争 | 删除 |
| `.stagger` 逐项 80ms，最长 720ms | 超过视觉稿 240ms 上限，列表会“一排排跳进来” | 列表一次性出现，或最多 3 项、总延迟 ≤160ms |
| `.view-hero` 呼吸点、大字水印 | 首页不是品牌海报 | 首页已改为“下一步”卡，不再做 hero 呼吸 |
| `.aiBeaconBreathe` / `.aiGlowDrift` | 旋转光斑、缩放、无限循环 | 删除；欢迎区静态图标即可 |
| 快捷卡 hover 扫光 `translateX(130%)` | 消费级电商手势，医疗场景过炫 | 只改边框色和浅底 |
| 卡片 hover `translateY(-3px~-4px)` | 大面积空间运动，前庭风险高 | 可点击卡最多 -1px 或完全不做位移 |
| `.msgShake` 左右抖动 | 错误已有摘要与边框，抖动无信息增量 | 删除；错误只做颜色/图标出现 |
| `.page { animation: fadeUp 500ms }` | 整页入场被视觉稿明确禁止 | 路由切换无动画 |
| 助手 `scrollIntoView({ behavior: 'smooth' })` | 减少动态时仍平滑滚动 | 根据媒体查询切 `auto` |

### 3.3 页面级缺口

- **登录**：提交后按钮没有宽度锁定 spinner；登录/注册切换是瞬间替换，容易丢失焦点，但不应做 3D 翻页。
- **首页**：服务入口已有 160ms hover，但“下一步”卡、列表出现仍是硬切；加载没有 300ms 门槛。
- **导航**：侧栏活动态和移动底栏活动态是瞬间变色，缺少 160ms 指示条过渡。
- **挂号**：弹窗字段仍有 60–360ms 错落入场；成功仍可能只插一条消息卡，而不是结果面板过渡。
- **缴费**：支付方式选中只有边框跳变，没有 160ms 的边框/浅底过渡。
- **健康助手**：消息硬插入；状态点无动画语义；Drawer 无进出过渡；急症条出现时没有 live region 以外的视觉强调节奏。

## 4. 动效原则

1. **因果优先。** 用户点了什么，什么就动；后台完成什么，结果区才动。禁止与当前任务无关的循环。
2. **空间运动克制。** 位移只用于“面板从边缘进入”和“消息从输入框附近出现”。卡片、按钮、列表行默认只做颜色/透明度。
3. **进入慢、离开快。** 进入用 decelerate 220ms，离开用 accelerate 180ms，符合 Material 3 与 NN/g。
4. **一次只动一层。** 打开挂号 Dialog 时，背后页面冻结，不再同时做列表 stagger。
5. **等待有门槛。** 小于 300ms 的请求不闪 skeleton；超过则骨架尺寸必须接近真实内容，避免布局跳动。
6. **状态不能只靠运动。** 成功、错误、急症必须同时有图标、文案和语义色；运动只是附加确认。
7. **医疗信任压过趣味。** 禁止心跳监护仪隐喻、呼吸灯、光斑、金色脉动。助手在线状态如果没有真实心跳协议，不得用脉冲绿点暗示“医生在线”。

## 5. Motion Token

在 `:root` 中用语义名替换现有 `--dur-fast/med/slow`（250/400/500ms 对患者任务过慢）和 `--ease-soft/enter/exit`。旧变量可暂时别名到新值，但新代码只引用下表。

### 5.1 时长

| Token | 值 | 用途 |
|---|---:|---|
| `--motion-instant` | 80ms | `:active` 缩放、开关拨动 |
| `--motion-fast` | 160ms | hover、focus、色、边框、底栏指示 |
| `--motion-med` | 220ms | Dialog/Drawer 进入、步骤切换、消息进入 |
| `--motion-exit` | 180ms | 浮层离开、菜单收起 |
| `--motion-emphasis` | 280ms | 成功勾选、结果面板展开 |
| `--motion-skeleton-delay` | 300ms | 显示骨架的最短等待 |

任何常规交互不得超过 400ms。循环类只允许：spinner 0.8s 线性旋转、流式光标 1s step、生成状态点 1.2s 透明度循环；三者都必须在 `prefers-reduced-motion: reduce` 时停止位移。

### 5.2 缓动

来自 Material 3 的公开曲线，不自造弹性过冲。

| Token | 曲线 | 用途 |
|---|---|---|
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | 同屏状态（hover、色、指示条） |
| `--ease-enter` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | 进入屏幕 |
| `--ease-exit` | `cubic-bezier(0.3, 0, 0.8, 0.15)` | 离开屏幕 |
| `--ease-linear` | `linear` | 仅 spinner 旋转 |

禁止 `transition: all`。必须显式列出 `color, background-color, border-color, box-shadow, transform, opacity`。禁止弹性过冲（`scale(1.06)` 再回 1）用在日期格子、号源卡或主按钮上。

### 5.3 位移预算

| 元素 | 最大位移 | 最大缩放 |
|---|---:|---:|
| 按钮 `:active` | 0 | 0.98 |
| 可点击卡片 hover | 1px 上移，可选用 0 | 1.00 |
| Dialog 内容进入 | 12px 上移 | 1.00 |
| 桌面 Drawer | 100% 自身宽度，从左或右 | 1.00 |
| 移动端 Sheet | 24px 上移 + 透明度 | 1.00 |
| 聊天气泡进入 | 8px 上移 | 1.00 |
| 页面、Hero、背景 | 禁止 | 禁止 |

遮罩只做透明度 0 → 0.18（浅）或 0 → 0.38（阻断确认），时长与面板进入相同。

## 6. 共享组件动效合同

组件必须先满足视觉稿第 8 节的状态，再套用本表。没有列出的组件默认只做 160ms 颜色过渡。

### 6.1 Button

- hover：160ms 背景与边框，无位移。
- `:active`：80ms `scale(0.98)`，`transform-origin: center`。
- loading：文字替换为“处理中…”+ 16px spinner；按钮 `min-width` 保持提交前宽度，防止布局跳动。
- disabled：无 hover 运动。
- reduced-motion：取消 scale，只保留颜色。

### 6.2 FormField / 输入

- hover：边框到 `mint-200`，160ms。
- focus：边框到 `brand-700` + 3px mint glow，160ms。
- 错误：边框与错误文案 160ms 出现；禁止 shake。
- 登录/注册切换：表单区 160ms 透明度交叉淡入，焦点移到第一个字段；禁止 3D flip。

### 6.3 Dialog / Drawer / Sheet

统一用 Vue `<Transition name="overlay">` 和内部 `name="panel"`。

| 阶段 | 遮罩 | 面板 |
|---|---|---|
| 进入 | opacity 220ms `--ease-enter` | Dialog：`translateY(12px)` → 0 + opacity；桌面 Drawer：从边缘滑入 220ms；移动 Sheet：`translateY(24px)` → 0 |
| 离开 | 180ms `--ease-exit` | 反向，时长 180ms |

规则：

- 打开时焦点进入；关闭后归还触发按钮，这个行为已经在 `ConfirmDialog.vue` 中存在，动效不得打断它。
- 进入动画结束前不自动把焦点跳到会引发滚动的元素。
- 移动端挂号/支付确认用全屏 Sheet，不用桌面 Dialog 的上浮。

### 6.4 Tabs

指示条用 `transform: translateX(...)` 160ms `--ease-standard` 在两个 tab 之间滑动，而不是瞬间换背景。面板内容 160ms 淡入，不做左右滑动（避免与手势返回冲突）。

### 6.5 Alert / Toast / 结果面板

- Alert：160ms 透明度；插入时不得把下方内容猛推超过一次正常行高而不做过渡。优先预留空间，或 180ms `grid-template-rows: 0fr → 1fr`。
- Toast：只用于次要确认（如“已复制订单号”）。进入 180ms，停留 4s，离开 160ms。超过 5s 必须有关闭按钮。
- 挂号成功、支付成功：不用 Toast 作为唯一证据；结果面板 220ms 展开，内部文字不再逐行 stagger。

### 6.6 Skeleton / Spinner

- Spinner：24–36px，边框旋转 0.8s linear；reduced-motion 时改为静态环形 + 文字“加载中”。
- Skeleton：禁止无限 `scale` 呼吸；只用 1.5s 的透明度 0.55↔0.9。reduced-motion 时静态浅底。
- 请求 <300ms：不渲染骨架，避免闪白。

### 6.7 导航

- 桌面侧栏活动项：左侧 3px 指示条高度 160ms 变化，背景 160ms 淡入浅绿。
- 移动底栏活动项：顶部 2px 指示条 160ms；图标不做 scale(1.05)。
- 路由切换：主内容无滑动、无淡入。浏览器后退应立即显示目标页。

## 7. 页面编排

以下编排建立在视觉稿第 7 节的信息结构之上，只规定“什么时候动、动多少”。

### 7.1 登录与注册

场景节奏：

1. 页面本身无入场动画；品牌区和表单卡首屏静态可见。
2. 输入 focus：160ms glow。
3. 点击登录：按钮立即进入 loading，80ms 内出现 spinner，表单其余控件 `pointer-events: none`。
4. 失败：错误摘要 160ms 出现并获焦；对应字段边框变红。无抖动。
5. 成功：直接 `router.replace('/home')`，不做庆祝动画。
6. 切到注册：标题和字段 160ms 淡入，焦点回到用户名。

禁止：卡片悬浮呼吸、品牌区光斑漂移、密码可见图标的旋转一周。

### 7.2 首页

1. 数据返回前：若超过 300ms，只给“下一步”卡和两个列表做骨架，服务入口可先静态渲染（入口不依赖接口）。
2. 数据出现：一次性替换，无 stagger。
3. 服务入口 hover：160ms 边框 + 浅阴影，**无 translateY**（与当前 `Home.vue` 第二段 scoped 样式一致）。
4. “下一步”主按钮 press：0.98 scale。
5. 近期记录/今日号源行 hover：仅背景，点击走链接。

首页状态点（`.status-dot`）保持静态 mint 圆点 + 浅光晕，**禁止** `breathe` 缩放。它表示“这里是下一步”，不是在线心跳。

### 7.3 科室医生

- 搜索输入 focus 用标准输入动效。
- 选中科室：160ms 边框与背景；右侧医生列表替换用 160ms 淡入，滚动位置重置到列表顶，但页面本身不滚动动画。
- 科室项必须是 button/link，hover 不做卡片上浮。

### 7.4 预约挂号

列表：Tab 指示条 160ms；表格/卡片 hover 仅背景。

预约流程（视觉稿 4 步）动效：

| 步骤变化 | 运动 |
|---|---|
| 打开 Dialog/Sheet | 遮罩 + 面板 220ms |
| 步 1→2→3 内容切换 | 两步内容 160ms 交叉淡入，同时进行，总时长不超过 200ms；步骤条当前点 160ms |
| 选中号源/时段 | 160ms 边框到 brand-700 + 勾选图标 220ms `scale(0.85→1)`，无弹跳过冲 |
| 进入复核 | 复核摘要 220ms 展开，不使用 `max-height: 0→200px` 这种不精确动画 |
| 提交 | 主按钮 loading，选项区禁用 |
| 成功 | 关闭流程层 180ms 后，页面内结果面板 220ms 出现 |

取消挂号：危险 Dialog 与普通 Dialog 相同时长，不额外抖动。

### 7.5 挂号详情

页面静态进入。时间线新增记录不动画。退号确认沿用 Dialog 合同。

### 7.6 缴费与支付

- 待缴摘要卡静态。金额数字**禁止**滚动跳动（容易被当成促销，也难以无障碍播报）。
- 支付方式：选中 160ms 边框与浅底，配合原生 radio，不靠缩放表达选中。
- 确认支付：按钮 loading + 防双击。
- 成功：结果面板 220ms；可把金额行做一次 160ms 背景高亮，不高亮整页。

### 7.7 我的档案

- 进入编辑：底部保存栏 180ms 自下出现（移动端需避开底栏）。
- 保存成功：字段级 160ms 成功提示，或页级 Alert；无彩带动画。
- 身份证显示/隐藏：文字瞬间切换，可对“显示完整信息”按钮做 160ms 颜色反馈。

### 7.8 健康助手

这是动效密度最高的一页，但仍必须比旧 AI 壳克制。旧 `.ai-shell` 的光斑、扫光、欢迎区错落入场全部不迁入新助手页。

**欢迎态**

- 图标、标题、说明、4 个快捷问题同时静态出现。
- 快捷问题 hover：160ms 边框与 `mint-050` 底，箭头不做 `translate(3px,-3px)`。

**发送与回复**

| 事件 | 运动 | 文案/无障碍 |
|---|---|---|
| 用户消息出现 | 220ms `opacity + translateY(8px)`，从输入区方向理解即可，不从屏幕外飞入 | 无额外播报 |
| 生成中 | 状态行 160ms 出现；圆点只做透明度 1.2s 循环，位移 ≤2px | 必须有“正在查询号源 / 正在整理信息”文字；`aria-live=polite` |
| 流式正文 | 字符追加本身不动画；光标 1Hz 闪烁 | reduced-motion 时光标常亮 |
| 停止 | 停止按钮无位移，160ms 与发送按钮交叉淡入 | 名称“停止” |
| 助手消息完成 | 若非流式整段插入，用与用户消息相同的 220ms 进入 | “AI 生成”标签静态 |
| 引用折叠 | `details` 展开 180ms 高度，不弹跳 | 文案“查看依据（N）” |

滚动：新消息用 `scrollIntoView`。`prefers-reduced-motion: reduce` 或 `matchMedia` 为真时 `behavior: 'auto'`。当前 `Assistant.vue` 写死 `smooth`，实施时必须改。

**急症条**

- 出现：160ms 透明度，插在最新回复前。
- 禁止闪烁、禁止无限放大。
- `role="alert"` / `aria-live="assertive"` 已经足够，不要再加抖动。

**挂号中断确认**

- 面板 220ms 展开。
- 主按钮 loading 时两颗按钮都禁用。
- 确认成功后，确认条 180ms 收起，随后助手继续回复。

**历史会话 / 就诊资料 Drawer**

- 左 Drawer、右 Drawer 各从对应边缘滑入 220ms，遮罩 220ms。
- 当前 `v-if` 瞬间挂载，实施时包 `<Transition>`。
- 列表项 hover 只改背景，不 `translateX(3px)`。

**快捷入口菜单**

- 从 “+” 按钮向上 180ms 出现（opacity + 8px）。
- 点遮罩或再点 “+” 以 160ms 收起。

**Composer**

- `focus-within`：160ms 边框与 glow，**禁止**整个输入条 `translateY(-2px)`。
- 发送 `:active`：`scale(0.98)`。
- 输入框高度 1–4 行变化用 160ms `height`（或 `grid-template-rows`），避免跳动遮挡底栏。

## 8. 减少动态与安全阈值

### 8.1 全局 CSS

必须按类分层覆盖，禁止用一条 `* { animation-duration: 0.01ms !important }` 把 spinner、focus ring 和颜色过渡全部掐死。`scroll-behavior` 在 reduce 时设为 `auto`。

| 类别 | reduce 时 |
|---|---|
| hover 颜色、focus ring | 保留 ≤160ms 或瞬间 |
| 位移、缩放、stagger、扫光 | `transform: none`；相关 animation 关闭 |
| Dialog/Drawer | 仅 opacity 150ms，或瞬间出现 |
| Spinner | 静态环形图标 + 文字“加载中”，不旋转 |
| 骨架脉冲 | 静态浅块 |
| 流式光标 | 常亮竖线 |
| 平滑滚动 | `auto` |

### 8.2 产品内开关

视觉稿未要求独立“关闭动画”设置。本阶段只尊重操作系统 `prefers-reduced-motion`，不新增设置页。若后续要做站内开关，必须是全局、可持久化，并与 OS 设置取“任一为减少即减少”。

### 8.3 硬性安全

- 任何动画不得在 1 秒内闪烁超过 3 次。
- 禁止自动播放超过 5 秒且无法暂停的装饰运动。本产品直接禁止该类运动，因此不需要暂停按钮。
- 禁止视差、整页缩放、旋转超过 15°、多轴漂浮。
- 急症和错误不得使用会掩盖文字对比的闪烁底色。

## 9. Vue 实现约定

### 9.1 过渡类名

只使用这 5 个名字，避免每页自造 keyframes。

| 名称 | 进入 | 离开 | 用于 |
|---|---|---|---|
| `fade` | opacity 160ms `--ease-standard` | 160ms | Tab 面板、局部替换 |
| `pop` | opacity + `translateY(12px)` 220ms `--ease-enter` | 180ms `--ease-exit` | Dialog、结果面板、菜单 |
| `drawer-left` | `translateX(-100%)` 220ms | 180ms | 历史会话 |
| `drawer-right` | `translateX(100%)` 220ms | 180ms | 就诊资料 |
| `message-in` | opacity + `translateY(8px)` 220ms | 无离开或 160ms fade | 聊天气泡 |

`TransitionGroup` 仅用于聊天消息。列表数据刷新不要用 move 动画，避免行交换时整表扭动。

### 9.2 文件落点

- Token 与全局 `@keyframes`（仅 `spin`、`cursor-blink`、`status-pulse`）放 `frontend/src/index.css`。
- 过渡类放 `frontend/src/index.css` 的 Motion 段，不继续堆进 `views.css`。
- 页面不得再写独立的 `fadeUp`、`aiRise`、`msgShake`。
- 实施时可删除已无引用的 amber / grain / mode-select 氛围动画，但那是视觉稿 Phase 1 的职责；本文只要求新代码不依赖它们。

### 9.3 现有时长别名

迁移期：

```css
--dur-fast: var(--motion-fast);
--dur-med: var(--motion-med);
--dur-slow: var(--motion-emphasis);
--ease-soft: var(--ease-standard);
```

目标是新组件不再读取 `--dur-*`。

## 10. 验收标准

### 全局

- [ ] 新代码不使用 `transition: all`、无限装饰循环、整页 `fadeUp`、shake、扫光。
- [ ] hover/focus/press 均 ≤160ms；浮层进入 220ms、离开 180ms。
- [ ] 路由切换无滑动、无全屏溶解。
- [ ] 加载 <300ms 不闪骨架；spinner 有文字替代。
- [ ] `prefers-reduced-motion: reduce` 下无位移/缩放/平滑滚动。
- [ ] 1 秒内无元素闪烁超过 3 次。

### 关键路径

- [ ] 登录提交有宽度锁定 loading，失败无抖动，成功无庆祝动画。
- [ ] 首页服务卡 hover 不位移；“下一步”点静态。
- [ ] 挂号 4 步切换为淡入而非字段 stagger；成功为结果面板而非仅 toast。
- [ ] 支付方式选中 160ms 边框过渡；金额无滚动数字。
- [ ] 助手新消息 220ms 进入；生成状态有文字；Drawer 有进出；`scrollIntoView` 尊重减少动态。
- [ ] Dialog 开关不破坏 focus trap 与 return focus。

### 设备

至少在 360×800、390×844、768×1024、1440×900 确认：底栏、Sheet、composer 的进出不会把主按钮推出可视区或与键盘重叠。

## 11. 非目标

- 不恢复琥珀金顶线、宣纸噪点动画、模式选择页动效。
- 不做暗色模式专属动效。
- 不做页面间共享元素转场（shared element / hero transform）。
- 不给骨架或空状态配插画 Lottie。
- 不用动效表达“AI 更聪明”（禁止光球、粒子、打字机整段重放）。
- 不在本阶段增加站内动画开关页。

## 12. 实施顺序

1. 在 `index.css` 写入 motion token，并把 `--dur-*` 别名过去。
2. 补齐 `fade` / `pop` / `drawer-*` / `message-in` 与全局 reduced-motion 分层规则。
3. 给 `ConfirmDialog`、助手 Drawer、挂号/支付弹层接上 `<Transition>`。
4. 去掉按钮和卡片的大位移 hover；统一 press `scale(0.98)`。
5. 改助手滚动行为与消息进入；删除仍存活的 AI 氛围 keyframes 引用。
6. 按登录 → 首页 → 挂号 → 支付 → 助手走一遍验收清单，并用系统“减少动态”各走一遍。

本顺序可并入视觉稿 Phase 1–2（token 与基础组件）执行，不必单独开一条与视觉重构无关的动效分支。
