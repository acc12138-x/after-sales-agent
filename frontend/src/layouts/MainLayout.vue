<template>
  <el-container style="height: 100vh;">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon :size="28"><Tools /></el-icon>
        <div>
          <div class="logo-title">售后助手</div>
          <div class="logo-sub">Enterprise Agent</div>
        </div>
      </div>

      <el-menu :default-active="$route.path" router class="menu">
        <el-menu-item
          v-for="item in menus"
          :key="item.path"
          :index="item.path"
          v-show="hasPerm(item.perm)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          {{ item.label }}
        </el-menu-item>
      </el-menu>

      <div class="footer">
        <div v-if="user" class="user-info">
          <el-avatar :size="28" :style="{ background: roleColor(user.role) }">
            {{ (user.name || "?").charAt(0) }}
          </el-avatar>
          <div class="user-detail">
            <div class="user-name">{{ user.name }}</div>
            <div class="user-role">{{ user.role_label }}</div>
          </div>
          <el-button size="small" link @click="doLogout" title="退出">
            <el-icon><SwitchButton /></el-icon>
          </el-button>
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <span class="route-title">{{ $route.name }}</span>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessageBox, ElMessage } from "element-plus";
import {
  Tools, ChatDotRound, Collection, Tickets, UserFilled, Money,
  AlarmClock, User, Document, Bell, Setting, DataLine, SwitchButton,
} from "@element-plus/icons-vue";
import api from "../api";

const router = useRouter();
const user = ref(null);

const MENUS = [
  { path: "/chat",          label: "对话测试",  icon: ChatDotRound },
  { path: "/knowledge",     label: "知识库",    icon: Collection },
  { path: "/tickets",       label: "工单",      icon: Tickets },
  { path: "/customers",     label: "客户资产",  icon: UserFilled },
  { path: "/refunds",       label: "退款管理",  icon: Money,       perm: "refund.view" },
  { path: "/sla",           label: "SLA时效",   icon: AlarmClock },
  { path: "/engineers",     label: "工程师",    icon: User,        perm: "user.view" },
  { path: "/people",        label: "人员管理",  icon: UserFilled,  perm: "user.view" },
  { path: "/audit",         label: "审计日志",  icon: Document,    perm: "audit.view" },
  { path: "/notifications", label: "通知记录",  icon: Bell },
  { path: "/config",        label: "系统配置",  icon: Setting,     perm: "sla.edit" },
  { path: "/monitor",       label: "监控看板",  icon: DataLine },
];

const menus = MENUS;

const perms = computed(() => (user.value && user.value.effective_permissions) || []);
const isAdmin = computed(() => perms.value.includes("*"));

function hasPerm(p) {
  if (!p) return true;
  if (isAdmin.value) return true;
  return perms.value.includes(p);
}

function roleColor(r) {
  return { admin: "#ef4444", supervisor: "#f59e0b", engineer: "#4f46e5", agent: "#22c55e" }[r] || "#9ca3af";
}

async function doLogout() {
  try {
    await ElMessageBox.confirm("确定退出登录？", "提示", { type: "warning" });
  } catch { return; }
  try { await api.logout(); } catch (e) {}
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_user");
  ElMessage.success("已退出");
  router.push("/login");
}

onMounted(async () => {
  const cached = localStorage.getItem("auth_user");
  if (cached) {
    try { user.value = JSON.parse(cached); } catch (e) {}
  }
  try {
    const me = await api.me();
    user.value = me;
    localStorage.setItem("auth_user", JSON.stringify(me));
  } catch (e) {
    router.push("/login");
  }
});
</script>

<style scoped>
.sidebar {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-right: 1px solid #e5e7eb;
  display: flex; flex-direction: column;
}
.logo {
  display: flex; align-items: center; gap: 12px;
  padding: 20px; border-bottom: 1px solid #e5e7eb;
  color: #4f46e5;
}
.logo-title { font-weight: 700; font-size: 16px; }
.logo-sub { font-size: 11px; color: #6b7280; }
.menu { border: none; background: transparent; flex: 1; overflow-y: auto; }
.menu .el-menu-item { margin: 4px 10px; border-radius: 8px; }
.menu .el-menu-item.is-active {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
}
.footer { padding: 12px 16px; border-top: 1px solid #e5e7eb; }
.user-info { display: flex; align-items: center; gap: 10px; }
.user-detail { flex: 1; min-width: 0; }
.user-name {
  font-size: 13px; font-weight: 600; color: #111827;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.user-role { font-size: 11px; color: #6b7280; }
.topbar {
  background: white; border-bottom: 1px solid #e5e7eb;
  display: flex; align-items: center; padding: 0 24px;
  height: 56px;
}
.route-title { font-size: 16px; font-weight: 600; color: #374151; }
.main-content { background: #f8fafc; padding: 24px; overflow-y: auto; }
</style>
