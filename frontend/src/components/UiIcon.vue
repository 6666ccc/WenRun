<script setup>
import {
  Bot, CalendarDays, CircleDollarSign, Clock3, FileText, Hospital,
  House, Leaf, LogOut, Search, UserRound, WalletCards,
} from '@lucide/vue'

defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 24 } })

const icons = {
  ai: Bot,
  calendar: CalendarDays,
  dollar: CircleDollarSign,
  hourglass: Clock3,
  record: FileText,
  hospital: Hospital,
  home: House,
  logo: Leaf,
  logout: LogOut,
  search: Search,
  user: UserRound,
  wallet: WalletCards,
}
</script>

<template>
  <component :is="icons[name] || Leaf" :size="size" />
</template>
