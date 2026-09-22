<template>
  <section class="archive-panel trend-skeleton" aria-label="健康趋势加载中" aria-busy="true">
    <div class="trend-skeleton__line trend-skeleton__line--title" />
    <div class="trend-skeleton__line" />
    <div class="trend-skeleton__chart" />
    <span class="sr-only">健康趋势加载中…</span>
  </section>
</template>

<style scoped>
.trend-skeleton { display: grid; gap: 14px; min-height: 380px; overflow: hidden; }
.trend-skeleton__line, .trend-skeleton__chart {
  border-radius: 10px;
  background: linear-gradient(90deg, var(--color-surface-soft) 20%, var(--color-mint-050) 45%, var(--color-surface-soft) 70%);
  background-size: 220% 100%;
  animation: trend-skeleton 1.4s ease-in-out infinite;
}
.trend-skeleton__line { width: 46%; height: 16px; }
.trend-skeleton__line--title { width: 22%; height: 22px; }
.trend-skeleton__chart { height: 280px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes trend-skeleton { to { background-position: -120% 0; } }
@media (prefers-reduced-motion: reduce) { .trend-skeleton__line, .trend-skeleton__chart { animation: none; } }
</style>
