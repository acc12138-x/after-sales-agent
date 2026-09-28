<template>
  <div>
    <div class="page-title">🎫 工单管理</div>

    <!-- ============ 统计卡 ============ -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="总工单" :value="stats.total" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="待接单" :value="stats.assigned" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="进行中" :value="stats.accepted + stats.in_progress" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="已解决" :value="stats.resolved + stats.closed" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="信息待补" :value="stats.incomplete" /></el-card></el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-button :icon="Refresh" @click="load" style="width:100%; height:100%;">刷新</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- ============ 筛选 ============ -->
    <el-card shadow="never" style="margin-bottom:16px;">
      <el-radio-group v-model="statusFilter" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="assigned">待接单</el-radio-button>
        <el-radio-button value="accepted">已接单</el-radio-button>
        <el-radio-button value="in_progress">处理中</el-radio-button>
        <el-radio-button value="resolved">已解决</el-radio-button>
        <el-radio-button value="closed">已关闭</el-radio-button>
      </el-radio-group>
      <el-checkbox v-model="incompleteOnly" style="margin-left:20px;" @change="load">
        只看信息待补
      </el-checkbox>
    </el-card>

    <!-- ============ 表格 ============ -->
    <el-card shadow="never">
      <el-table
        :data="tickets"
        v-loading="loading"
        stripe
        empty-text="暂无工单，去对话测试发一条 '帮我报修 XY200 故障码 E102'"
        @row-click="openDetail"
        style="cursor: pointer;"
      >
        <el-table-column prop="ticket_id" label="工单号" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" type="info">{{ row.ticket_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusIcon(row.status) }} {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备" width="120">
          <template #default="{ row }">
            <span v-if="row.device_model">{{ row.device_model }}</span>
            <el-tag v-else type="warning" size="small" effect="plain">待补</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="故障码" width="100">
          <template #default="{ row }">
            <span v-if="row.error_code">{{ row.error_code }}</span>
            <el-tag v-else type="warning" size="small" effect="plain">待补</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assigned_to" label="工程师" width="100" />
        <el-table-column label="派单次数" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.assign_count > 1" type="warning" size="small">{{ row.assign_count }}</el-tag>
            <span v-else>{{ row.assign_count || 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click.stop="openDetail(row)">
              <el-icon><View /></el-icon> 详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ============ 详情抽屉 ============ -->
    <el-drawer v-model="drawerVisible" :title="detail ? ('🎫 工单 ' + detail.ticket_id) : '工单详情'" size="820px">
      <div v-if="detailLoading" style="text-align:center; padding:60px;">
        <el-icon class="is-loading" :size="36"><Loading /></el-icon>
      </div>

      <div v-else-if="detail">
        <!-- 状态标签 + 关闭 -->
        <div style="margin-bottom:16px;">
          <el-tag :type="statusType(detail.status)" size="large">
            {{ statusIcon(detail.status) }} {{ statusText(detail.status) }}
          </el-tag>
          <el-tag v-if="!detail.is_complete" type="warning" size="large" style="margin-left:8px;">
            ⚠️ 待补全：{{ detail.missing_fields.join(", ") }}
          </el-tag>
        </div>

        <!-- 基本信息 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <el-descriptions title="基本信息" :column="1" border>
              <el-descriptions-item label="设备型号">
                <span v-if="detail.device_model">{{ detail.device_model }}</span>
                <el-tag v-else size="small" type="warning" effect="plain">待补</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="故障码">
                <span v-if="detail.error_code">{{ detail.error_code }}</span>
                <el-tag v-else size="small" type="warning" effect="plain">待补</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="派单次数">{{ detail.assign_count || 1 }}</el-descriptions-item>
              <el-descriptions-item label="联系人">{{ detail.contact || "-" }}</el-descriptions-item>
              <el-descriptions-item label="地址">{{ detail.address || "-" }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
          <el-col :span="12">
            <el-descriptions title="派单信息" :column="1" border>
              <el-descriptions-item label="当前工程师">{{ detail.assigned_to || "未派单" }}</el-descriptions-item>
              <el-descriptions-item label="拒单原因">{{ detail.reject_reason || "-" }}</el-descriptions-item>
              <el-descriptions-item label="解决备注">{{ detail.resolved_note || "-" }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>

        <!-- 时间线 -->
        <el-divider content-position="left">📅 状态时间线</el-divider>
        <el-row :gutter="8">
          <el-col v-for="(item, i) in timeline" :key="i" :span="4">
            <div class="tl-item" :class="{ done: item.time }">
              <div class="tl-label">{{ item.label }}</div>
              <div class="tl-time">{{ item.time ? fmtTime(item.time) : "—" }}</div>
            </div>
          </el-col>
        </el-row>

        <!-- 操作区 -->
        <el-divider content-position="left">🎬 可用操作</el-divider>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <el-button
            v-if="detail.status === 'assigned'"
            type="success" @click="doAction('accept')"
            :icon="Check" :loading="actionLoading"
          >✅ 接单</el-button>

          <el-button
            v-if="['assigned','accepted','in_progress'].includes(detail.status)"
            type="danger" plain @click="showRejectDialog"
            :icon="Close" :loading="actionLoading"
          >❌ 拒单</el-button>

          <el-button
            v-if="detail.status === 'accepted'"
            type="primary" @click="doAction('start')"
            :icon="VideoPlay" :loading="actionLoading"
          >🔧 开始处理</el-button>

          <el-button
            v-if="detail.status === 'in_progress'"
            type="success" @click="showResolveDialog"
            :icon="CircleCheck" :loading="actionLoading"
          >🎯 标记解决</el-button>

          <el-button
            v-if="detail.status === 'resolved'"
            type="primary" @click="doAction('close')"
            :icon="Lock" :loading="actionLoading"
          >🔒 关闭工单</el-button>

          <el-button
            v-if="!detail.is_complete"
            type="warning" @click="fillDialogVisible = true"
            :icon="Edit"
          >📝 补全信息</el-button>
        </div>

        <!-- 审计日志 -->
        <el-divider content-position="left">📋 审计日志</el-divider>
        <el-timeline v-if="auditLogs.length">
          <el-timeline-item
            v-for="log in auditLogs"
            :key="log.id"
            :timestamp="fmtTime(log.created_at)"
            placement="top"
          >
            <el-tag size="small" effect="plain">{{ log.actor }}</el-tag>
            <el-tag size="small" type="primary" effect="plain">{{ log.action }}</el-tag>
            <span style="margin-left:8px; color:#6b7280; font-size:12px;">{{ log.detail }}</span>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无审计记录" :image-size="60" />

        <!-- 通知记录 -->
        <el-divider content-position="left">📨 通知记录</el-divider>
        <el-timeline v-if="notifications.length">
          <el-timeline-item
            v-for="n in notifications"
            :key="n.id"
            :timestamp="fmtTime(n.created_at)"
            placement="top"
            color="#7c3aed"
          >
            <el-tag size="small" type="success" effect="plain">{{ n.target }}</el-tag>
            <el-tag size="small" effect="plain">{{ n.event }}</el-tag>
            <div style="margin-top:4px; font-size:13px; color:#374151;">{{ n.title }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无通知记录" :image-size="60" />
      </div>
    </el-drawer>

    <!-- 拒单对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="拒单原因" width="400">
      <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请填写拒单原因（如：缺配件）" />
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="doReject">确认拒单</el-button>
      </template>
    </el-dialog>

    <!-- 解决对话框 -->
    <el-dialog v-model="resolveDialogVisible" title="解决备注" width="400">
      <el-input v-model="resolveNote" type="textarea" :rows="3" placeholder="如：更换温度传感器后恢复正常" />
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="success" @click="doResolve">确认解决</el-button>
      </template>
    </el-dialog>

    <!-- 补全表单 -->
    <el-dialog v-model="fillDialogVisible" title="📝 补全工单信息" width="500">
      <el-form :model="fillForm" label-width="90px">
        <el-form-item label="设备型号">
          <el-input v-model="fillForm.device_model" placeholder="如 XY200" />
        </el-form-item>
        <el-form-item label="故障码">
          <el-input v-model="fillForm.error_code" placeholder="如 E102" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="fillForm.contact" placeholder="如 张三 138****8000" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="fillForm.address" placeholder="如 上海市浦东新区..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fillDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doFill">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Refresh, View, Loading, Check, Close, VideoPlay, CircleCheck, Lock, Edit,
} from "@element-plus/icons-vue";
import api from "../api";

const tickets = ref([]);
const loading = ref(false);
const statusFilter = ref("");
const incompleteOnly = ref(false);

const stats = computed(() => {
  const s = { total: 0, assigned: 0, accepted: 0, in_progress: 0, resolved: 0, closed: 0, incomplete: 0 };
  for (const t of tickets.value) {
    s.total++;
    if (t.status in s) s[t.status]++;
    if (!t.is_complete) s.incomplete++;
  }
  return s;
});

function statusIcon(s) {
  return { pending: "⏳", assigned: "📋", accepted: "✅", in_progress: "🔧", resolved: "🎯", closed: "🔒", rejected: "❌", cancelled: "🚫" }[s] || "❔";
}
function statusText(s) {
  return { pending: "待处理", assigned: "待接单", accepted: "已接单", in_progress: "处理中", resolved: "已解决", closed: "已关闭", rejected: "已拒单", cancelled: "已取消" }[s] || s;
}
function statusType(s) {
  return { pending: "info", assigned: "warning", accepted: "primary", in_progress: "primary", resolved: "success", closed: "info", rejected: "danger" }[s] || "info";
}
function fmtTime(t) {
  if (!t) return "-";
  return t.slice(0, 19).replace("T", " ");
}

async function load() {
  loading.value = true;
  try {
    const params = {};
    if (statusFilter.value) params.status = statusFilter.value;
    if (incompleteOnly.value) params.incomplete_only = true;
    const r = await api.listTickets(params);
    tickets.value = r.items || [];
  } finally {
    loading.value = false;
  }
}

// ============ 详情 ============
const drawerVisible = ref(false);
const detail = ref(null);
const detailLoading = ref(false);
const actionLoading = ref(false);
const auditLogs = ref([]);
const notifications = ref([]);

const timeline = computed(() => {
  const d = detail.value || {};
  return [
    { label: "创建", time: d.created_at },
    { label: "派单", time: d.assigned_at },
    { label: "接单", time: d.accepted_at },
    { label: "解决", time: d.resolved_at },
    { label: "关闭", time: d.closed_at },
  ];
});

async function openDetail(row) {
  drawerVisible.value = true;
  detailLoading.value = true;
  auditLogs.value = [];
  notifications.value = [];
  try {
    detail.value = await api.getTicket(row.ticket_id);
    const [a, n] = await Promise.all([
      api.ticketAudit(row.ticket_id).catch(() => ({ items: [] })),
      api.ticketNotifications(row.ticket_id).catch(() => ({ items: [] })),
    ]);
    auditLogs.value = a.items || [];
    notifications.value = n.items || [];
  } finally {
    detailLoading.value = false;
  }
}

async function doAction(action) {
  if (!detail.value) return;
  actionLoading.value = true;
  try {
    let r;
    if (action === "accept") r = await api.acceptTicket(detail.value.ticket_id);
    else if (action === "start") r = await api.startTicket(detail.value.ticket_id);
    else if (action === "close") r = await api.closeTicket(detail.value.ticket_id);
    ElMessage.success("✅ 操作成功");
    await openDetail({ ticket_id: detail.value.ticket_id });
    load();
  } finally {
    actionLoading.value = false;
  }
}

// ============ 拒单 ============
const rejectDialogVisible = ref(false);
const rejectReason = ref("");
function showRejectDialog() {
  rejectReason.value = "";
  rejectDialogVisible.value = true;
}
async function doReject() {
  if (!detail.value) return;
  actionLoading.value = true;
  try {
    await api.rejectTicket(detail.value.ticket_id, { reason: rejectReason.value || "无原因" });
    ElMessage.success("✅ 已拒单，系统已重新派单");
    rejectDialogVisible.value = false;
    await openDetail({ ticket_id: detail.value.ticket_id });
    load();
  } finally {
    actionLoading.value = false;
  }
}

// ============ 解决 ============
const resolveDialogVisible = ref(false);
const resolveNote = ref("");
function showResolveDialog() {
  resolveNote.value = "";
  resolveDialogVisible.value = true;
}
async function doResolve() {
  if (!detail.value) return;
  actionLoading.value = true;
  try {
    await api.resolveTicket(detail.value.ticket_id, { note: resolveNote.value || "已处理" });
    ElMessage.success("✅ 工单已解决");
    resolveDialogVisible.value = false;
    await openDetail({ ticket_id: detail.value.ticket_id });
    load();
  } finally {
    actionLoading.value = false;
  }
}

// ============ 补全 ============
const fillDialogVisible = ref(false);
const fillForm = ref({ device_model: "", error_code: "", contact: "", address: "" });

async function doFill() {
  if (!detail.value) return;
  const updates = {};
  for (const k of ["device_model", "error_code", "contact", "address"]) {
    if (fillForm.value[k]) updates[k] = fillForm.value[k];
  }
  if (!Object.keys(updates).length) {
    ElMessage.warning("至少填一项");
    return;
  }
  await api.updateTicket(detail.value.ticket_id, updates);
  ElMessage.success("✅ 已补全");
  fillDialogVisible.value = false;
  await openDetail({ ticket_id: detail.value.ticket_id });
  load();
}

// 打开补全时，预填当前值
function prefillFillForm() {
  if (!detail.value) return;
  fillForm.value = {
    device_model: detail.value.device_model || "",
    error_code: detail.value.error_code || "",
    contact: detail.value.contact || "",
    address: detail.value.address || "",
  };
}

onMounted(load);
</script>

<style scoped>
.stat-card {
  text-align: center;
  padding: 4px;
}
.tl-item {
  padding: 8px 4px;
  border-left: 3px solid #e5e7eb;
  padding-left: 10px;
  color: #9ca3af;
}
.tl-item.done { border-left-color: #4f46e5; color: #111827; }
.tl-label { font-size: 13px; font-weight: 600; }
.tl-time { font-size: 11px; margin-top: 2px; }
</style>
