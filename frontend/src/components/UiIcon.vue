<script setup>
import {
  Activity, AlertCircle, ArrowLeft, ArrowRight, ArrowUp, Bot, CalendarDays, CircleDollarSign, ClipboardPlus, Clock3, Copy, Droplet, FileText, HeartPulse, History,
  Hospital, House, IdCard, Info, Leaf, LogOut, MapPin, PanelLeft, PanelRight, Phone, Pill, Plus, Ruler, Search, Send, ShieldCheck, Square, Thermometer, Upload, UserRound, Users, WalletCards, Weight, Wind, Zap,
} from '@lucide/vue'

defineProps({ name: { type: String, required: true }, size: { type: [Number, String], default: 24 } })

const icons = {
  ai: Bot,
  alert: AlertCircle,
  arrowLeft: ArrowLeft,
  arrowRight: ArrowRight,
  arrowUp: ArrowUp,
  calendar: CalendarDays,
  clipboard: ClipboardPlus,
  copy: Copy,
  dollar: CircleDollarSign,
  droplet: Droplet,
  heart: HeartPulse,
  hourglass: Clock3,
  idCard: IdCard,
  info: Info,
  record: FileText,
  history: History,
  hospital: Hospital,
  home: House,
  logo: Leaf,
  mapPin: MapPin,
  panelLeft: PanelLeft,
  panelRight: PanelRight,
  phone: Phone,
  pill: Pill,
  logout: LogOut,
  plus: Plus,
  ruler: Ruler,
  search: Search,
  send: Send,
  shield: ShieldCheck,
  stop: Square,
  thermometer: Thermometer,
  upload: Upload,
  user: UserRound,
  users: Users,
  activity: Activity,
  wallet: WalletCards,
  weight: Weight,
  wind: Wind,
  zap: Zap,
}
</script>

<template>
  <svg
    v-if="name === 'loading'"
    class="logo-loader"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    role="status"
    aria-label="加载中"
    focusable="false"
  >
    <path d="M11 20a10 10 0 0 0 10-10 25.9 25.9 0 0 0-1.04-7.281 1 1 0 0 0-1.755-.325C15.833 5.5 13 5.5 9.8 6.1A7 7 0 0 0 11 20" />
    <path d="M2 21a5 5 0 0 1 2.911-4.544C7.613 15.212 8.351 15.24 11 13" />
  </svg>
  <component v-else :is="icons[name] || Leaf" :size="size" aria-hidden="true" focusable="false" />
</template>

<style scoped>
.logo-loader {
  display: inline-block;
  flex: none;
  overflow: visible;
  color: currentColor;
  vertical-align: middle;
}

.logo-loader :deep(path) {
  stroke-linecap: round;
  stroke-linejoin: round;
}

.logo-loader :deep(path:nth-of-type(1)) {
  stroke-dasharray: 60;
  stroke-dashoffset: 60;
  animation: logo-loader-outline 2.2s cubic-bezier(.4, 0, .2, 1) infinite;
}

.logo-loader :deep(path:nth-of-type(2)) {
  stroke-dasharray: 20;
  stroke-dashoffset: 20;
  animation: logo-loader-stem 2.2s cubic-bezier(.4, 0, .2, 1) infinite;
}

@keyframes logo-loader-outline {
  0%, 8% {
    stroke-dashoffset: 60;
    opacity: .25;
  }

  44%, 78% {
    stroke-dashoffset: 0;
    opacity: 1;
  }

  100% {
    stroke-dashoffset: -60;
    opacity: 0;
  }
}

@keyframes logo-loader-stem {
  0%, 22% {
    stroke-dashoffset: 20;
    opacity: 0;
  }

  54%, 78% {
    stroke-dashoffset: 0;
    opacity: 1;
  }

  100% {
    stroke-dashoffset: -20;
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .logo-loader :deep(path) {
    animation: none !important;
    stroke-dashoffset: 0;
    opacity: 1;
  }
}
</style>
