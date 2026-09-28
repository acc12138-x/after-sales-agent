<template>
  <div>
    <div class="page-title">⏱️ SLA 时效管理</div>

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
      <!-- SLA 规则 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span style="font-weight:600;">📋 SLA 规则配置</span></template>
          <el-table :data="rulesTable" size="small" stripe>
            <el-table-column prop="type" label="工单类型" width="120" />
            <el-table-column prop="label" label="标签" width="100" />
            <el-table-column prop="urgent" label="紧急(小时)" width="120" align="center" />
            <el-table-column prop="normal" label="普通(小时)" align="center" />
          </el-table>
          <el-alert type="info" :closable="false" style="margin-top:12px;">
            预警阈值：剩余时间少于总时长 30% 时标记为"预警"
          </el-alert>
        </el-card>
      </el-col>

      <!-- 手动扫描 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span style="font-weight:600;">🔍 手动操作</span></template>
          <el-button type="primary" @click="doScan" :loading="scanning">
            🔄 立即扫描所有工单
          </el-button>
          <el-button @click="loadAll">刷新</el-button>
          <el-alert type="success" :closable="false" style="margin-top:12px;">
            <template #title>
              💡 建议每 5 分钟自动扫描一次（生产环境用 Celery / Cron 定时任务）
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
import axios from "axios";

const api = axios.create({ baseURL: "/api" });
api.interceptors.response.use(r => r.data, e => { ElMessage.error(e?.response?.data?.detail || e.message); return Promise.reject(e); });

const summary = ref({ total: 0, normal: 0, warning: 0, overdue: 0, achieved: 0, achievement_rate: 0 });
const rules = ref({});
const scanning = ref(false);

const rulesTable = computed(() => {
  const out = [];
  const r = rules.value.sla_rules || {};
  for (const [k, v] of Object.entries(r)) {
    if (k === "default") continue;
    out.push({ type: k, label: v.label || k, urgent: v.urgent, normal: v.normal });
  }
  return out;
});

async function loadAll() {
  try {
    const [s, r] = await Promise.all([api.get("/sla/summary"), api.get("/sla/rules")]);
    summary.value = s;
    rules.value = r;
  } catch (e) {}
}

async function doScan() {
  scanning.value = true;
  try {
    const r = await api.post("/sla/scan");
    ElMessage.success(`扫描完成：共 ${r.checked} 单，预警 ${r.warning}，超时 ${r.overdue}`);
    await loadAll();
  } finally { scanning.value = false; }
}

onMounted(loadAll);
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }
</style>
