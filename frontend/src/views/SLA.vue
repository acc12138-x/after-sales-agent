<template>
  <div>
    <div class="page-title">⏱️ SLA 时效管理</div>

    <!-- 汇总卡 -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col :span="6"><el-card shadow="never" class="stat-card"><el-statistic title="总工单" :value="summary.total" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never" class="stat-card"><el-statistic title="🟢 正常" :value="summary.normal" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never" class="stat-card"><el-statistic title="🟠 预警" :value="summary.warning" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="never" class="stat-card"><el-statistic title="🔴 超时" :value="summary.overdue" /></el-card></el-col>
    </el-row>

    <el-card shadow="never" style="margin-bottom:16px;">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="SLA 达标率">{{ summary.achievement_rate }}%</el-descriptions-item>
        <el-descriptions-item label="已达标工单">{{ summary.achieved }}</el-descriptions-item>
        <el-descriptions-item label="超时工单">{{ summary.overdue }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-row :gutter="16">
      <!-- 左：规则表格 + 编辑 -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:600;">📋 SLA 规则配置</span>
              <div>
                <el-button size="small" @click="startEdit" v-if="!editing">✏️ 编辑</el-button>
                <template v-else>
                  <el-button size="small" @click="cancelEdit">取消</el-button>
                  <el-button size="small" type="primary" :loading="saving" @click="saveRules">保存</el-button>
                </template>
              </div>
            </div>
          </template>

          <el-table :data="rulesTable" size="small" stripe>
            <el-table-column prop="label" label="工单类型" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ row.label || row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="代码" width="100" />
            <el-table-column label="紧急 (小时)" width="140">
              <template #default="{ row }">
                <el-input-number v-if="editing" v-model="row.urgent" :min="1" :max="72" size="small" style="width:110px;" />
                <span v-else>{{ row.urgent }}</span>
              </template>
            </el-table-column>
            <el-table-column label="普通 (小时)" width="140">
              <template #default="{ row }">
                <el-input-number v-if="editing" v-model="row.normal" :min="1" :max="240" size="small" style="width:110px;" />
                <span v-else>{{ row.normal }}</span>
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="120">
              <template #default="{ row }">
                <el-input v-if="editing" v-model="row.label" size="small" />
                <span v-else>{{ row.label }}</span>
              </template>
            </el-table-column>
          </el-table>

          <div style="margin-top:16px; display:flex; align-items:center; gap:12px;">
            <span style="font-weight:500;">预警阈值：</span>
            <template v-if="editing">
              <el-slider v-model="editWarningRatio" :min="0.1" :max="0.9" :step="0.05" style="width:200px;" />
              <span style="color:#4f46e5; font-weight:600;">{{ Math.round(editWarningRatio * 100) }}%</span>
              <span style="font-size:12px; color:#9ca3af;">剩余时间少于总时长 30% 时标为预警</span>
            </template>
            <template v-else>
              <el-tag>{{ Math.round(warningRatio * 100) }}%</el-tag>
            </template>
          </div>
        </el-card>
      </el-col>

      <!-- 右：实时工单 SLA 看板 -->
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:600;">🚨 实时工单 SLA</span>
              <el-button size="small" @click="loadAll" :loading="loading">刷新</el-button>
            </div>
          </template>

          <el-empty v-if="!slaTickets.length" description="暂无进行中工单" :image-size="60" />
          <div v-else class="ticket-list">
            <div
              v-for="t in slaTickets"
              :key="t.ticket_id"
              class="ticket-item"
              :class="t.sla_status"
            >
              <div class="ti-head">
                <span class="ti-id">{{ t.ticket_id }}</span>
                <span class="ti-status">{{ slaIcon(t.sla_status) }} {{ slaText(t) }}</span>
              </div>
              <div class="ti-body">
                <span>{{ t.device_model || '-' }} · {{ t.error_code || '-' }}</span>
                <span class="ti-assignee">→ {{ t.assigned_to || '未派单' }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 手动扫描 -->
        <el-card shadow="never" style="margin-top:16px;">
          <el-button type="primary" @click="doScan" :loading="scanning" style="width:100%;">
            🔄 立即扫描所有工单
          </el-button>
          <el-alert type="success" :closable="false" style="margin-top:12px;">
            <template #title>
              💡 后台每 5 分钟自动扫描一次。状态变化时会自动发飞书通知。
            </template>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";

const summary = ref({ total: 0, normal: 0, warning: 0, overdue: 0, achieved: 0, achievement_rate: 0 });
const rulesRaw = ref({ sla_rules: {}, warning_ratio: 0.3 });
const slaTickets = ref([]);
const scanning = ref(false);
const loading = ref(false);

const editing = ref(false);
const saving = ref(false);
const editRules = ref([]);
const editWarningRatio = ref(0.3);

const rulesTable = computed(() => {
  if (editing.value) return editRules.value;
  const out = [];
  const r = rulesRaw.value.sla_rules || {};
  for (const [k, v] of Object.entries(r)) {
    if (k === "default") continue;
    out.push({ type: k, label: v.label || k, urgent: v.urgent, normal: v.normal });
  }
  return out;
});

const warningRatio = computed(() => rulesRaw.value.warning_ratio || 0.3);

function slaIcon(s) {
  return { normal: "🟢", warning: "🟠", overdue: "🔴" }[s] || "⚪";
}

function slaText(t) {
  const sec = t.remain_seconds;
  if (sec === null || sec === undefined) return "-";
  const abs = Math.abs(sec);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const prefix = sec < 0 ? "超时 " : "剩 ";
  if (h >= 24) return `${prefix}${Math.floor(h/24)}d ${h%24}h`;
  if (h > 0) return `${prefix}${h}h ${m}m`;
  return `${prefix}${m}m`;
}

async function loadAll() {
  loading.value = true;
  try {
    const [s, r, t] = await Promise.all([
      api.getSlaSummary(),
      api.getSlaRules(),
      api.getSlaTickets(),
    ]);
    summary.value = s;
    rulesRaw.value = r;
    slaTickets.value = t.items || [];
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

function startEdit() {
  const r = rulesRaw.value.sla_rules || {};
  editRules.value = [];
  for (const [k, v] of Object.entries(r)) {
    if (k === "default") continue;
    editRules.value.push({
      type: k,
      label: v.label || k,
      urgent: v.urgent,
      normal: v.normal,
    });
  }
  editWarningRatio.value = rulesRaw.value.warning_ratio || 0.3;
  editing.value = true;
}

function cancelEdit() {
  editing.value = false;
  editRules.value = [];
}

async function saveRules() {
  saving.value = true;
  try {
    const sla_rules = {};
    for (const r of editRules.value) {
      sla_rules[r.type] = {
        urgent: r.urgent,
        normal: r.normal,
        label: r.label,
      };
    }
    // 保留 default
    const orig = rulesRaw.value.sla_rules || {};
    if (orig.default) sla_rules.default = orig.default;

    await api.updateSlaRules({
      sla_rules,
      warning_ratio: editWarningRatio.value,
    });
    ElMessage.success("✅ SLA 规则已保存");
    editing.value = false;
    await loadAll();
  } catch (e) {
    // 拦截器已提示
  } finally {
    saving.value = false;
  }
}

async function doScan() {
  scanning.value = true;
  try {
    const r = await api.scanSla();
    ElMessage.success(`扫描完成：共 ${r.checked} 单，预警 ${r.warning}，超时 ${r.overdue}，通知 ${r.notified || 0}`);
    await loadAll();
  } finally {
    scanning.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }

.ticket-list { max-height: 480px; overflow-y: auto; }

.ticket-item {
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  border-left: 3px solid #e5e7eb;
  background: #f9fafb;
  transition: all 0.15s;
}
.ticket-item:hover { background: #f3f4f6; }
.ticket-item.normal { border-left-color: #22c55e; }
.ticket-item.warning { border-left-color: #f59e0b; background: #fffbeb; }
.ticket-item.overdue { border-left-color: #ef4444; background: #fef2f2; }

.ti-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 4px;
}
.ti-id { font-family: monospace; font-size: 12px; font-weight: 600; color: #111827; }
.ti-status { font-size: 12px; font-weight: 500; }
.ticket-item.normal .ti-status { color: #16a34a; }
.ticket-item.warning .ti-status { color: #d97706; }
.ticket-item.overdue .ti-status { color: #dc2626; }

.ti-body {
  display: flex; justify-content: space-between;
  font-size: 12px; color: #6b7280;
}
.ti-assignee { color: #4f46e5; }
</style>
