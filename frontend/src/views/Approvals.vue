<template>
  <div>
    <div class="page-title">✅ 主管审批台</div>

    <!-- 统计卡 -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" :class="{ highlight: stats.total_pending > 0 }">
          <el-statistic title="待处理" :value="stats.total_pending" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic title="待审批退款" :value="stats.refund_pending" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic title="待接单工单" :value="boardStats.assigned" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic title="处理中工单" :value="boardStats.in_progress" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic title="已通过退款" :value="stats.refund_approved" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic title="SLA 超时工单" :value="stats.overdue_tickets" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作区 -->
    <div class="toolbar card-panel">
      <div class="toolbar-left">
        <el-checkbox v-model="selectAllRefunds" @change="toggleSelectAll" :indeterminate="isIndeterminate">
          全选退款
        </el-checkbox>
        <el-input v-model="batchNote" placeholder="批量审批备注（可选）" clearable style="width:280px;" />
      </div>
      <div class="toolbar-right">
        <el-button :icon="Refresh" @click="load" :loading="loading">刷新</el-button>
        <el-button
          type="success"
          :disabled="selectedRefundIds.length === 0"
          :loading="submitting"
          @click="batchApprove('approve')"
        >批量通过 ({{ selectedRefundIds.length }})</el-button>
        <el-button
          type="danger"
          :disabled="selectedRefundIds.length === 0"
          :loading="submitting"
          @click="batchApprove('reject')"
        >批量驳回</el-button>
      </div>
    </div>

    <!-- 待审批退款 -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header>
        <span style="font-weight:600;">💰 待审批退款（{{ refunds.length }}）</span>
      </template>
      <el-empty v-if="!refunds.length" description="暂无待审批退款" :image-size="80" />
      <el-table v-else :data="refunds" stripe @selection-change="onSelectionChange" ref="refundTableRef">
        <el-table-column type="selection" width="45" />
        <el-table-column label="退款单号" width="150">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="100">
          <template #default="{ row }">
            <span style="color:#ef4444; font-weight:600;">¥{{ row.amount }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="customer_id" label="客户" width="90" />
        <el-table-column prop="order_id" label="订单" width="140" />
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="AI 建议" width="120">
          <template #default="{ row }">
            <el-tooltip :content="row.ai_reason || '-'">
              <el-tag :type="aiType(row.ai_suggestion)" size="small">
                {{ aiText(row.ai_suggestion) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="风控" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.risk_flag" type="danger" size="small">{{ row.risk_flag }}</el-tag>
            <span v-else style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="紧急" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.urgency === 'high'" type="danger" size="small">🔴</el-tag>
            <span v-else>🟢</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 全部未关闭工单 -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:600;">📋 全部未关闭工单（{{ open_tickets.length }}）</span>
          <el-input
            v-model="ticketKeyword"
            placeholder="搜索：工单号/设备/故障码/工程师"
            clearable
            size="small"
            style="width:260px;"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>
      <el-empty v-if="!filteredOpenTickets.length" description="暂无未关闭工单" :image-size="80" />
      <el-table v-else :data="filteredOpenTickets" stripe max-height="420">
        <el-table-column label="工单号" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.ticket_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="ticketStatusType(row.status)" size="small">
              {{ ticketStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="device_model" label="设备" width="100" />
        <el-table-column prop="error_code" label="故障码" width="100" />
        <el-table-column prop="assigned_to" label="工程师" width="100" />
        <el-table-column label="SLA" width="140">
          <template #default="{ row }">
            <div v-if="row.sla_status" :style="{color: slaColor(row.sla_status)}">
              {{ slaIcon(row.sla_status) }} {{ slaText(row) }}
            </div>
            <span v-else style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="warning"
              :loading="reassigning === row.ticket_id"
              @click="reassign(row)"
            >🔄 改派</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 超时工单 -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header>
        <span style="font-weight:600;">🔴 SLA 超时工单（{{ overdue_tickets.length }}）</span>
      </template>
      <el-empty v-if="!overdue_tickets.length" description="暂无超时工单" :image-size="80" />
      <el-table v-else :data="overdue_tickets" stripe>
        <el-table-column prop="ticket_id" label="工单号" width="150" />
        <el-table-column prop="device_model" label="设备" width="100" />
        <el-table-column prop="error_code" label="故障码" width="100" />
        <el-table-column prop="assigned_to" label="当前工程师" width="120" />
        <el-table-column label="截止时间" width="180">
          <template #default="{ row }">
            <span style="color:#ef4444;">{{ fmtTime(row.sla_deadline) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="warning"
              :loading="reassigning === row.ticket_id"
              @click="reassign(row)"
            >🔄 改派</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh, Search } from "@element-plus/icons-vue";
// 统一用共享客户端：它自带 Authorization 请求头与统一错误提示，
// 不必在本页重复实现一遍拦截器。
import api from "../api";

const stats = ref({ total_pending: 0, refund_pending: 0, refund_approved: 0, overdue_tickets: 0 });
const refunds = ref([]);
const overdue_tickets = ref([]);
const open_tickets = ref([]);
const boardStats = ref({ assigned: 0, in_progress: 0, pending: 0, resolved: 0, total_open: 0 });
const ticketKeyword = ref("");
const loading = ref(false);
const submitting = ref(false);
const reassigning = ref("");
const batchNote = ref("");
const selectedRefundIds = ref([]);
const selectAllRefunds = ref(false);
const refundTableRef = ref(null);

const isIndeterminate = computed(() => {
  return selectedRefundIds.value.length > 0 && selectedRefundIds.value.length < refunds.value.length;
});

const filteredOpenTickets = computed(() => {
  const kw = ticketKeyword.value.trim().toLowerCase();
  if (!kw) return open_tickets.value;
  return open_tickets.value.filter(t =>
    (t.ticket_id || "").toLowerCase().includes(kw) ||
    (t.device_model || "").toLowerCase().includes(kw) ||
    (t.error_code || "").toLowerCase().includes(kw) ||
    (t.assigned_to || "").toLowerCase().includes(kw)
  );
});

function ticketStatusText(s) {
  return {
    pending: "待处理", assigned: "待接单", accepted: "已接单",
    in_progress: "处理中", resolved: "已解决", closed: "已关闭",
    rejected: "已拒单", cancelled: "已取消",
  }[s] || s;
}
function ticketStatusType(s) {
  return {
    pending: "info", assigned: "warning", accepted: "primary",
    in_progress: "primary", resolved: "success", closed: "info",
    rejected: "danger",
  }[s] || "info";
}
function slaIcon(s) {
  return { normal: "🟢", warning: "🟠", overdue: "🔴" }[s] || "⚪";
}
function slaColor(s) {
  return { normal: "#16a34a", warning: "#d97706", overdue: "#dc2626" }[s] || "#9ca3af";
}
function slaText(row) {
  const sec = row.remain_seconds;
  if (sec === null || sec === undefined) {
    // 从 sla_deadline 反推
    if (!row.sla_deadline) return "-";
    const t = new Date(row.sla_deadline).getTime();
    const diff = Math.floor((t - Date.now()) / 1000);
    const abs = Math.abs(diff);
    const h = Math.floor(abs / 3600);
    const m = Math.floor((abs % 3600) / 60);
    const prefix = diff < 0 ? "超时 " : "剩 ";
    if (h >= 24) return `${prefix}${Math.floor(h/24)}d ${h%24}h`;
    if (h > 0) return `${prefix}${h}h ${m}m`;
    return `${prefix}${m}m`;
  }
  const abs = Math.abs(sec);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const prefix = sec < 0 ? "超时 " : "剩 ";
  if (h >= 24) return `${prefix}${Math.floor(h/24)}d ${h%24}h`;
  if (h > 0) return `${prefix}${h}h ${m}m`;
  return `${prefix}${m}m`;
}

function aiText(s) { return { approve: "建议通过", reject: "建议驳回", need_human: "需人工" }[s] || "-"; }
function aiType(s) { return { approve: "success", reject: "danger", need_human: "warning" }[s] || "info"; }
function fmtTime(t) { return t ? t.slice(0, 19).replace("T", " ") : "-"; }

async function load() {
  loading.value = true;
  try {
    const [p, s] = await Promise.all([
      api.get("/approvals/pending"),
      api.get("/approvals/stats"),
    ]);
    refunds.value = p.refunds || [];
    overdue_tickets.value = p.overdue_tickets || [];
    open_tickets.value = p.open_tickets || [];
    boardStats.value = p.stats || { assigned: 0, in_progress: 0, pending: 0, resolved: 0, total_open: 0 };
    stats.value = s;
    selectedRefundIds.value = [];
    selectAllRefunds.value = false;
  } finally {
    loading.value = false;
  }
}

function toggleSelectAll(val) {
  if (refundTableRef.value) {
    // 让表格自身触发 selection-change，保持勾选状态与 selectedRefundIds 一致
    refunds.value.forEach(r => refundTableRef.value.toggleRowSelection(r, !!val));
  } else {
    selectedRefundIds.value = val ? refunds.value.map(r => r.id) : [];
  }
}

// 监听表格选择
function onSelectionChange(rows) {
  selectedRefundIds.value = rows.map(r => r.id);
}

async function batchApprove(decision) {
  const word = decision === "approve" ? "通过" : "驳回";
  try {
    await ElMessageBox.confirm(
      `确认${word}选中的 ${selectedRefundIds.value.length} 笔退款？`,
      "确认",
      { type: "warning" }
    );
  } catch { return; }

  submitting.value = true;
  try {
    const r = await api.post("/approvals/refunds/batch", {
      refund_ids: selectedRefundIds.value,
      decision,
      note: batchNote.value,
    });
    ElMessage.success(`✅ 已${word} ${r.count} 笔`);
    batchNote.value = "";
    selectedRefundIds.value = [];
    selectAllRefunds.value = false;
    if (refundTableRef.value) {
      refundTableRef.value.clearSelection();
    }
    await load();
  } finally {
    submitting.value = false;
  }
}

async function reassign(row) {
  try {
    await ElMessageBox.confirm(`确认改派工单 ${row.ticket_id}？`, "提示", { type: "warning" });
  } catch { return; }

  reassigning.value = row.ticket_id;
  try {
    const r = await api.post(`/approvals/tickets/${row.ticket_id}/reassign`);
    ElMessage.success(`✅ ${r.old_engineer} → ${r.new_engineer}`);
    await load();
  } finally {
    reassigning.value = "";
  }
}

onMounted(load);
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }
.stat-card.highlight { border-color: #ef4444; }
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; gap: 12px; flex-wrap: wrap;
}
.toolbar-left { display: flex; gap: 12px; align-items: center; }
.toolbar-right { display: flex; gap: 8px; }
</style>
