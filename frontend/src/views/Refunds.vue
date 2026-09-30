<template>
  <div>
    <div class="page-title">💰 退款 / 赔付管理</div>

    <!-- 统计卡 -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="总计" :value="stats.total" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="待审批" :value="stats.pending" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="已通过" :value="stats.approved" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="已执行" :value="stats.executed" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="已驳回" :value="stats.rejected" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="总额" :value="stats.total_amount" prefix="¥" :precision="2" /></el-card></el-col>
    </el-row>

    <el-card shadow="never" style="margin-bottom:16px;">
      <el-form inline>
        <el-form-item label="关键词">
          <el-input
            v-model="keyword"
            placeholder="退款单号 / 客户ID / 订单号 / 工单号"
            clearable
            style="width:280px;"
            @keyup.enter="load"
            @clear="load"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="statusFilter" clearable placeholder="全部" style="width:150px;" @change="load">
            <el-option value="pending_approval" label="待审批" />
            <el-option value="approved" label="已通过" />
            <el-option value="executed" label="已执行" />
            <el-option value="rejected" label="已驳回" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="refunds" v-loading="loading" stripe @row-click="openDetail" style="cursor:pointer;">
        <el-table-column label="退款单号" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.refund_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ticket_id" label="工单" width="140" />
        <el-table-column prop="customer_id" label="客户" width="90" />
        <el-table-column prop="order_id" label="订单" width="140" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeText(row.refund_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="100">
          <template #default="{ row }">
            <span style="color:#ef4444; font-weight:600;">¥{{ row.amount }}</span>
          </template>
        </el-table-column>
        <el-table-column label="AI 建议" width="120">
          <template #default="{ row }">
            <el-tag :type="aiType(row.ai_suggestion)" size="small">
              {{ aiText(row.ai_suggestion) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风控" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.risk_flag" :type="riskType(row.risk_flag)" size="small">
              {{ row.risk_flag }}
            </el-tag>
            <span v-else style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click.stop="openDetail(row)">处理</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detail ? ('💰 退款单 ' + detail.refund_id) : ''" size="700px">
      <div v-if="detail">
        <!-- 状态 -->
        <div style="margin-bottom:16px;">
          <el-tag :type="statusType(detail.status)" size="large">{{ statusText(detail.status) }}</el-tag>
          <el-tag v-if="detail.risk_flag" :type="riskType(detail.risk_flag)" size="large" style="margin-left:8px;">
            ⚠️ {{ detail.risk_flag }}
          </el-tag>
        </div>

        <!-- 基本信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="客户 ID">{{ detail.customer_id }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ detail.order_id }}</el-descriptions-item>
          <el-descriptions-item label="关联工单">{{ detail.ticket_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="退款类型">{{ typeText(detail.refund_type) }}</el-descriptions-item>
          <el-descriptions-item label="金额" :span="2">
            <span style="color:#ef4444; font-size:18px; font-weight:700;">¥{{ detail.amount }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="原因" :span="2">{{ detail.reason || "-" }}</el-descriptions-item>
        </el-descriptions>

        <!-- AI 初审 -->
        <el-divider content-position="left">🤖 AI 初审</el-divider>
        <el-alert :type="aiType(detail.ai_suggestion)" :closable="false">
          <template #title>
            建议：{{ aiText(detail.ai_suggestion) }}（置信度 {{ (detail.ai_confidence * 100).toFixed(0) }}%）
          </template>
          <div>{{ detail.ai_reason }}</div>
        </el-alert>

        <!-- 审批结果 -->
        <template v-if="detail.approver">
          <el-divider content-position="left">✅ 审批结果</el-divider>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="审批人">{{ detail.approver }}</el-descriptions-item>
            <el-descriptions-item label="审批意见">{{ detail.approval_note || "-" }}</el-descriptions-item>
          </el-descriptions>
        </template>

        <!-- 操作按钮 -->
        <el-divider />
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <el-button
            v-if="['pending','ai_review','pending_approval'].includes(detail.status)"
            type="success" @click="showApproveDialog('approve')"
          >✅ 同意</el-button>
          <el-button
            v-if="['pending','ai_review','pending_approval'].includes(detail.status)"
            type="danger" plain @click="showApproveDialog('reject')"
          >❌ 驳回</el-button>
          <el-button
            v-if="detail.status === 'approved'"
            type="primary" @click="doExecute"
          >💸 执行退款</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 审批对话框 -->
    <el-dialog v-model="approveVisible" :title="approveDecision === 'approve' ? '✅ 同意退款' : '❌ 驳回退款'" width="420">
      <el-input v-model="approveNote" type="textarea" :rows="3" placeholder="审批意见（可选）" />
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button :type="approveDecision === 'approve' ? 'success' : 'danger'" @click="doApprove">
          确认{{ approveDecision === "approve" ? "同意" : "驳回" }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
// 统一用共享客户端：它自带 Authorization 请求头与统一错误提示。
// 千万不要在本页 axios.create() —— 自建实例不带 token，会得到 401「未登录」。
import api from "../api";

const refunds = ref([]);
const loading = ref(false);
const statusFilter = ref("");
const keyword = ref("");

const stats = computed(() => {
  const s = { total: 0, pending: 0, approved: 0, executed: 0, rejected: 0, total_amount: 0 };
  for (const r of refunds.value) {
    s.total++;
    s.total_amount += r.amount || 0;
    if (r.status === "pending_approval" || r.status === "pending" || r.status === "ai_review") s.pending++;
    else if (r.status === "approved") s.approved++;
    else if (r.status === "executed") s.executed++;
    else if (r.status === "rejected") s.rejected++;
  }
  return s;
});

function statusText(s) {
  return { pending: "待处理", ai_review: "AI 审核", pending_approval: "待审批", approved: "已通过", executed: "已执行", rejected: "已驳回", cancelled: "已取消" }[s] || s;
}
function statusType(s) {
  return { pending: "info", ai_review: "info", pending_approval: "warning", approved: "success", executed: "primary", rejected: "danger" }[s] || "info";
}
function aiText(s) { return { approve: "建议通过", reject: "建议驳回", need_human: "需人工" }[s] || "-"; }
function aiType(s) { return { approve: "success", reject: "danger", need_human: "warning" }[s] || "info"; }
function riskType(r) { return { normal: "success", suspicious: "warning", high_risk: "danger" }[r] || "info"; }
function typeText(t) { return { refund_only: "仅退款", return_refund: "退货退款", compensation: "赔付", shipping_fee: "运费" }[t] || t; }

async function load() {
  loading.value = true;
  try {
    const params = {};
    if (statusFilter.value) params.status = statusFilter.value;
    if (keyword.value.trim()) params.keyword = keyword.value.trim();
    const r = await api.get("/refunds", { params });
    refunds.value = r.items || [];
  } finally { loading.value = false; }
}

const drawerVisible = ref(false);
const detail = ref(null);

async function openDetail(row) {
  drawerVisible.value = true;
  try {
    detail.value = await api.get("/refunds/" + row.refund_id);
  } catch (e) {}
}

// 审批
const approveVisible = ref(false);
const approveDecision = ref("approve");
const approveNote = ref("");

function showApproveDialog(decision) {
  approveDecision.value = decision;
  approveNote.value = "";
  approveVisible.value = true;
}

async function doApprove() {
  try {
    await api.post("/refunds/" + detail.value.refund_id + "/approve", {
      decision: approveDecision.value,
      note: approveNote.value,
    });
    ElMessage.success("审批完成");
    approveVisible.value = false;
    await openDetail({ refund_id: detail.value.refund_id });
    load();
  } catch (e) {}
}

async function doExecute() {
  try {
    await api.post("/refunds/" + detail.value.refund_id + "/execute");
    ElMessage.success("✅ 退款已执行");
    await openDetail({ refund_id: detail.value.refund_id });
    load();
  } catch (e) {}
}

onMounted(load);
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }
</style>
