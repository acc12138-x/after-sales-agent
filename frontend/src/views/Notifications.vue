<template>
  <div>
    <div class="page-title">📨 通知记录</div>

    <!-- ============ 说明 + 统计 ============ -->
    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom:16px;"
    >
      <template #title>
        模拟通知：真实环境会调飞书 API / 短信网关推送。此处记录"已发送"的通知事件用于审计。
      </template>
    </el-alert>

    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col v-for="s in notifStats.slice(0, 6)" :key="s.event" :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic :title="s.event" :value="s.count" />
        </el-card>
      </el-col>
      <el-col v-if="notifStats.length === 0" :span="24">
        <el-card shadow="never">
          <el-empty description="暂无统计数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- ============ 筛选 ============ -->
    <div class="card-panel toolbar">
      <div class="toolbar-left">
        <el-select v-model="eventFilter" placeholder="事件类型" clearable style="width:200px;" @change="load">
          <el-option value="" label="全部事件" />
          <el-option value="ticket_assigned" label="🆕 ticket_assigned" />
          <el-option value="ticket_accepted" label="✅ ticket_accepted" />
          <el-option value="ticket_rejected" label="❌ ticket_rejected" />
          <el-option value="ticket_resolved" label="🎯 ticket_resolved" />
          <el-option value="ticket_closed" label="🔒 ticket_closed" />
        </el-select>
        <el-select v-model="channelFilter" placeholder="渠道" clearable style="width:120px;" @change="load">
          <el-option value="" label="全部渠道" />
          <el-option value="feishu" label="飞书" />
          <el-option value="sms" label="短信" />
          <el-option value="email" label="邮件" />
        </el-select>
        <el-input
          v-model="targetFilter"
          placeholder="接收人（工程师姓名）"
          clearable
          style="width:180px;"
          @keyup.enter="load"
          @clear="load"
        />
        <el-select v-model="limit" style="width:120px;" @change="load">
          <el-option :value="50" label="50 条" />
          <el-option :value="100" label="100 条" />
          <el-option :value="200" label="200 条" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
      </div>
      <div class="toolbar-right">
        <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <!-- ============ 表格 ============ -->
    <el-card shadow="never" style="margin-top:12px;">
      <el-table
        :data="notifications"
        v-loading="loading"
        stripe
        empty-text="暂无通知记录"
        max-height="calc(100vh - 420px)"
      >
        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            <span class="time-cell">{{ fmtTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="渠道" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="channelType(row.channel)">
              {{ channelText(row.channel) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="接收人" width="120">
          <template #default="{ row }">
            <el-avatar :size="24" style="background:#4f46e5; margin-right:6px;">
              {{ (row.target || "?").charAt(0) }}
            </el-avatar>
            <span style="font-weight:500;">{{ row.target }}</span>
          </template>
        </el-table-column>

        <el-table-column label="事件" width="200">
          <template #default="{ row }">
            <el-tag size="small" :type="eventType(row.event)" effect="plain">
              {{ eventIcon(row.event) }} {{ row.event }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="标题 / 内容" min-width="450">
          <template #default="{ row }">
            <div class="title-cell">
              <div class="title-line">{{ row.title || "-" }}</div>
              <div class="content-line">{{ row.content || "" }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'sent' ? 'success' : 'danger'" size="small">
              {{ row.status === "sent" ? "✅ 已发" : "❌ 失败" }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import api from "../api";

const notifications = ref([]);
const loading = ref(false);
const notifStats = ref([]);
const eventFilter = ref("");
const channelFilter = ref("");
const targetFilter = ref("");
const limit = ref(100);

function fmtTime(t) {
  if (!t) return "-";
  return t.slice(0, 19).replace("T", " ");
}

function channelText(c) {
  return { feishu: "飞书", sms: "短信", email: "邮件" }[c] || c;
}
function channelType(c) {
  return { feishu: "primary", sms: "success", email: "warning" }[c] || "info";
}
function eventIcon(e) {
  if (!e) return "📨";
  if (e.includes("assigned")) return "🆕";
  if (e.includes("accepted")) return "✅";
  if (e.includes("rejected")) return "❌";
  if (e.includes("resolved")) return "🎯";
  if (e.includes("closed")) return "🔒";
  return "📨";
}
function eventType(e) {
  if (!e) return "info";
  if (e.includes("assigned")) return "primary";
  if (e.includes("accepted")) return "success";
  if (e.includes("rejected")) return "danger";
  return "info";
}

async function load() {
  loading.value = true;
  try {
    const params = { limit: limit.value };
    if (eventFilter.value) params.event = eventFilter.value;
    if (channelFilter.value) params.channel = channelFilter.value;
    if (targetFilter.value.trim()) params.target = targetFilter.value.trim();
    const r = await api.listNotifications(params);
    notifications.value = r.items || [];
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    const r = await api.notifStats();
    notifStats.value = r.items || [];
  } catch {}
}

async function loadAll() {
  await Promise.all([load(), loadStats()]);
}

onMounted(loadAll);
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; gap: 12px; flex-wrap: wrap;
}
.toolbar-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.toolbar-right { display: flex; gap: 8px; }
.time-cell { font-family: monospace; font-size: 12px; color: #6b7280; }
.title-cell .title-line {
  font-weight: 500; font-size: 13px; color: #111827;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.title-cell .content-line {
  font-size: 12px; color: #6b7280; margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
</style>
