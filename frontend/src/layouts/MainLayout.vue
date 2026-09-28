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
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon>对话测试</el-menu-item>
        <el-menu-item index="/knowledge"><el-icon><Collection /></el-icon>知识库</el-menu-item>
        <el-menu-item index="/tickets"><el-icon><Tickets /></el-icon>工单</el-menu-item>
        <el-menu-item index="/customers"><el-icon><UserFilled /></el-icon>客户资产</el-menu-item>
        <el-menu-item index="/refunds"><el-icon><Money /></el-icon>退款管理</el-menu-item>
        <el-menu-item index="/sla"><el-icon><AlarmClock /></el-icon>SLA时效</el-menu-item>
        <el-menu-item index="/engineers"><el-icon><User /></el-icon>工程师</el-menu-item>
        <el-menu-item index="/audit"><el-icon><Document /></el-icon>审计日志</el-menu-item>
        <el-menu-item index="/notifications"><el-icon><Bell /></el-icon>通知记录</el-menu-item>
        <el-menu-item index="/config"><el-icon><Setting /></el-icon>系统配置</el-menu-item>
        <el-menu-item index="/monitor"><el-icon><DataLine /></el-icon>监控看板</el-menu-item>
      </el-menu>

      <div class="footer">
        <el-tag :type="online ? 'success' : 'danger'" effect="light">
          {{ online ? "🟢 后端在线" : "🔴 后端离线" }}
        </el-tag>
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
import { ref, onMounted } from "vue";
import axios from "axios";

const online = ref(false);
onMounted(async () => {
  try {
    await axios.get("/api/health", { timeout: 3000 });
    online.value = true;
  } catch { online.value = false; }
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
.menu .el-menu-item {
  margin: 4px 10px; border-radius: 8px;
}
.menu .el-menu-item.is-active {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
}
.footer { padding: 15px; text-align: center; }
.topbar {
  background: white; border-bottom: 1px solid #e5e7eb;
  display: flex; align-items: center; padding: 0 24px;
  height: 56px;
}
.route-title { font-size: 16px; font-weight: 600; color: #374151; }
.main-content { background: #f8fafc; padding: 24px; overflow-y: auto; }
</style>
