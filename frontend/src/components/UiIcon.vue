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
  <component :is="icons[name] || Leaf" :size="size" aria-hidden="true" focusable="false" />
</template>
