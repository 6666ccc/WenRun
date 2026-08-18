import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useIsPc() {
  // AppShell keeps a compact icon rail on tablet, so tablet still uses the desktop shell.
  const query = window.matchMedia('(min-width: 768px)')
  const isPc = ref(query.matches)
  const update = (event) => { isPc.value = event.matches }
  onMounted(() => query.addEventListener('change', update))
  onBeforeUnmount(() => query.removeEventListener('change', update))
  return isPc
}
