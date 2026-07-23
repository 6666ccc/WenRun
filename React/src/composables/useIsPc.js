import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useIsPc() {
  const query = window.matchMedia('(min-width: 1024px)')
  const isPc = ref(query.matches)
  const update = (event) => { isPc.value = event.matches }
  onMounted(() => query.addEventListener('change', update))
  onBeforeUnmount(() => query.removeEventListener('change', update))
  return isPc
}
