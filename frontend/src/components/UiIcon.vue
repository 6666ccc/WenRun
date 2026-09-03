<script setup>
import {
  AlertCircle, ArrowLeft, ArrowRight, ArrowUp, Bot, CalendarDays, CircleDollarSign, Clock3, Copy, FileText, History,
  Hospital, House, Leaf, LogOut, PanelLeft, PanelRight, Plus, Search, Send, ShieldCheck, Square, UserRound, WalletCards, Zap,
} from '@lucide/vue'

defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 24 } })

const icons = {
  ai: Bot,
  alert: AlertCircle,
  arrowLeft: ArrowLeft,
  arrowRight: ArrowRight,
  arrowUp: ArrowUp,
  calendar: CalendarDays,
  copy: Copy,
  dollar: CircleDollarSign,
  hourglass: Clock3,
  record: FileText,
  history: History,
  hospital: Hospital,
  home: House,
  logo: Leaf,
  panelLeft: PanelLeft,
  panelRight: PanelRight,
  logout: LogOut,
  plus: Plus,
  search: Search,
  send: Send,
  shield: ShieldCheck,
  stop: Square,
  user: UserRound,
  wallet: WalletCards,
  zap: Zap,
}
</script>

<template>
  <component :is="icons[name] || Leaf" :size="size" aria-hidden="true" focusable="false" />
</template>
