<script setup>
import {
  AlertCircle, ArrowLeft, Bot, CalendarDays, CircleDollarSign, Clock3, FileText, History, Hospital,
  House, Leaf, LogOut, PanelRight, Plus, Search, Send, UserRound, WalletCards,
} from '@lucide/vue'

defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 24 } })

const icons = {
  ai: Bot,
  alert: AlertCircle,
  arrowLeft: ArrowLeft,
  calendar: CalendarDays,
  dollar: CircleDollarSign,
  hourglass: Clock3,
  record: FileText,
  history: History,
  hospital: Hospital,
  home: House,
  logo: Leaf,
  panelRight: PanelRight,
  logout: LogOut,
  plus: Plus,
  search: Search,
  send: Send,
  user: UserRound,
  wallet: WalletCards,
}
</script>

<template>
  <component :is="icons[name] || Leaf" :size="size" />
</template>
