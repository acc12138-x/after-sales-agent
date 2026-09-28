<template>
  <div>
    <div class="page-title">📊 运营监控看板</div>

    <!-- ============ 核心指标卡 ============ -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="📋 总工单" :value="stats.total_tickets" /></el-card></el-col>
      <el-col :span="5"><el-card shadow="never" class="stat-card"><el-statistic title="🆕 今日新增" :value="todayCount" /></el-card></el-col>
      <el-col :span="5"><el-card shadow="never" class="stat-card"><el-statistic title="🎯 解决率" :value="resolveRate" suffix="%" :precision="1" /></el-card></el-col>
      <el-col :span="5"><el-card shadow="never" class="stat-card"><el-statistic title="⏱️ 平均解决" :value="avgDisplay" /></el-card></el-col>
      <el-col :span="5"><el-card shadow="never" class="stat-card"><el-statistic title="📚 知识库切片" :value="stats.knowledge_chunks" /></el-card></el-col>
    </el-row>

    <!-- ============ 图表区 ============ -->
    <el-row :gutter="16">
      <!-- 7 天趋势 -->
      <el-col :span="16">
        <el-card shadow="never">
          <template #header><span style="font-weight:600;">📈 近 7 天新增工单</span></template>
          <div ref="trendChartEl" style="height: 280px;"></div>
        </el-card>
      </el-col>

      <!-- 状态分布 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><span style="font-weight:600;">🎫 状态分布</span></template>
          <div ref="statusChartEl" style="height: 280px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px;">
      <!-- 工程师负载 -->
      <el-col :span="16">
        <el-card shadow="never">
          <template #header><span style="font-weight:600;">👷 工程师负载</span></template>
          <div ref="engineerChartEl" style="height: 260px;"></div>
        </el-card>
      </el-col>

      <!-- 数据概览 + 快捷操作 -->
      <el-col :span="8">
        <el-card shadow="never">
          <template #header><span style="font-weight:600;">📊 数据概览</span></template>
          <el-row :gutter="12">
            <el-col :span="12"><el-statistic title="📋 审计" :value="stats.audit_count" /></el-col>
            <el-col :span="12"><el-statistic title="📨 通知" :value="stats.notification_count" /></el-col>
          </el-row>
          <el-divider />
          <el-button :icon="Refresh" @click="load" style="width:100%;" :loading="loading">
            刷新数据
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px;">
      <!-- SLA 达成 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span style="font-weight:600;">⏱️ SLA 时效分布</span>
            <el-tag v-if="stats.sla_summary" type="info" size="small" style="margin-left:8px;">
              达成率 {{ stats.sla_summary.achievement_rate || 0 }}%
            </el-tag>
          </template>
          <div ref="slaChartEl" style="height: 260px;"></div>
        </el-card>
      </el-col>

      <!-- 退款分布 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span style="font-weight:600;">💰 退款概览</span>
            <el-tag type="warning" size="small" style="margin-left:8px;">
              待审批 {{ stats.refund_pending || 0 }}
            </el-tag>
          </template>
          <el-row :gutter="12" style="margin-bottom:12px;">
            <el-col :span="8"><el-statistic title="退款单" :value="stats.refund_total || 0" /></el-col>
            <el-col :span="8"><el-statistic title="总金额" :value="stats.refund_amount || 0" prefix="¥" :precision="2" /></el-col>
            <el-col :span="8"><el-statistic title="待审批" :value="stats.refund_pending || 0" /></el-col>
          </el-row>
          <div ref="refundChartEl" style="height: 180px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 服务探活 -->
    <!-- ============ 服务探活 ============ -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header><span style="font-weight:600;">🔌 外部服务状态</span></template>
      <el-row :gutter="12">
        <el-col v-for="svc in services" :key="svc.name" :span="6">
          <div class="svc-item" :class="{ ok: svc.ok, err: !svc.ok }">
            <span class="svc-icon">{{ svc.ok ? "✅" : "❌" }}</span>
            <span class="svc-name">{{ svc.name }}</span>
            <span v-if="svc.latency" class="svc-latency">{{ svc.latency }}ms</span>
          </div>
        </el-col>
      </el-row>
      <div style="margin-top:12px; text-align:right; color:#9ca3af; font-size:12px;">
        🕒 数据更新：{{ lastUpdate }}
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import * as echarts from "echarts";
import api from "../api";

const stats = ref({
  total_tickets: 0,
  status_distribution: {},
  recent_7days: [],
  engineers: [],
  audit_count: 0,
  notification_count: 0,
  avg_resolve_seconds: 0,
  knowledge_chunks: 0,
});

const loading = ref(false);
const lastUpdate = ref("-");
const services = ref([
  { name: "Ollama", url: "/api/health", ok: false },
  { name: "FastAPI", url: "/api/health", ok: false },
  { name: "MySQL", url: "/api/tickets", ok: false },
  { name: "Chroma", url: "/api/knowledge/stats", ok: false },
]);

const trendChartEl = ref(null);
const statusChartEl = ref(null);
const engineerChartEl = ref(null);
const slaChartEl = ref(null);
const refundChartEl = ref(null);
let trendChart, statusChart, engineerChart, slaChart, refundChart;

// ============ 计算属性 ============
const todayCount = computed(() => {
  const today = new Date().toISOString().slice(5, 10); // MM-DD
  const item = (stats.value.recent_7days || []).find((d) => d.date === today);
  return item ? item.count : 0;
});

const resolveRate = computed(() => {
  const total = stats.value.total_tickets || 0;
  if (!total) return 0;
  const resolved = (stats.value.status_distribution?.resolved || 0)
                 + (stats.value.status_distribution?.closed || 0);
  return (resolved / total) * 100;
});

const avgDisplay = computed(() => {
  const s = stats.value.avg_resolve_seconds || 0;
  if (s < 60) return s.toFixed(0) + "s";
  if (s < 3600) return (s / 60).toFixed(1) + "min";
  return (s / 3600).toFixed(1) + "h";
});

// ============ ECharts ============
const PRIMARY = "#4f46e5";

function initCharts() {
  if (trendChartEl.value) trendChart = echarts.init(trendChartEl.value);
  if (statusChartEl.value) statusChart = echarts.init(statusChartEl.value);
  if (engineerChartEl.value) engineerChart = echarts.init(engineerChartEl.value);
  if (slaChartEl.value) slaChart = echarts.init(slaChartEl.value);
  if (refundChartEl.value) refundChart = echarts.init(refundChartEl.value);
}

function renderTrend() {
  if (!trendChart) return;
  const data = stats.value.recent_7days || [];
  trendChart.setOption({
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: data.map((d) => d.date),
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: { color: "#6b7280" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#f3f4f6" } },
      axisLabel: { color: "#6b7280" },
    },
    series: [{
      data: data.map((d) => d.count),
      type: "line",
      smooth: true,
      symbol: "circle",
      symbolSize: 10,
      lineStyle: { color: PRIMARY, width: 3 },
      itemStyle: { color: PRIMARY, borderWidth: 2, borderColor: "#fff" },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(79,70,229,0.35)" },
          { offset: 1, color: "rgba(79,70,229,0.02)" },
        ]),
      },
    }],
  });
}

function renderStatus() {
  if (!statusChart) return;
  const map = stats.value.status_distribution || {};
  const cn = { pending: "待接单", assigned: "已派单", accepted: "已接单", in_progress: "处理中", resolved: "已解决", closed: "已关闭", rejected: "已拒单", cancelled: "已取消" };
  const data = Object.entries(map).map(([k, v]) => ({ name: cn[k] || k, value: v }));

  statusChart.setOption({
    tooltip: { trigger: "item" },
    series: [{
      type: "pie",
      radius: ["45%", "72%"],
      itemStyle: { borderRadius: 6, borderColor: "#fff", borderWidth: 2 },
      label: { color: "#374151", fontSize: 12 },
      data: data.length ? data : [{ name: "暂无数据", value: 1 }],
      color: ["#a5b4fc", "#818cf8", "#6366f1", "#4f46e5", "#4338ca", "#7c3aed", "#a855f7", "#ec4899"],
    }],
  });
}

function renderEngineer() {
  if (!engineerChart) return;
  const data = stats.value.engineers || [];
  const names = data.map((e) => e.name);
  const loads = data.map((e) => e.load);

  engineerChart.setOption({
    grid: { left: 70, right: 30, top: 20, bottom: 30 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#f3f4f6" } },
      axisLabel: { color: "#6b7280" },
    },
    yAxis: {
      type: "category",
      data: names,
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: { color: "#374151", fontSize: 13 },
    },
    series: [{
      data: loads,
      type: "bar",
      barWidth: 22,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: "#c7d2fe" },
          { offset: 1, color: PRIMARY },
        ]),
        borderRadius: [0, 6, 6, 0],
      },
    }],
  });
}

function renderSLA() {
  if (!slaChart) return;
  const s = stats.value.sla_summary || {};
  const data = [
    { name: "🟢 正常", value: s.normal || 0, itemStyle: { color: "#22c55e" } },
    { name: "🟠 预警", value: s.warning || 0, itemStyle: { color: "#f59e0b" } },
    { name: "🔴 超时", value: s.overdue || 0, itemStyle: { color: "#ef4444" } },
  ].filter((d) => d.value > 0);
  slaChart.setOption({
    tooltip: { trigger: "item" },
    legend: { bottom: 0, textStyle: { color: "#6b7280" } },
    series: [{
      type: "pie",
      radius: ["40%", "68%"],
      itemStyle: { borderRadius: 6, borderColor: "#fff", borderWidth: 2 },
      label: { color: "#374151", fontSize: 12 },
      data: data.length ? data : [{ name: "暂无数据", value: 1, itemStyle: { color: "#e5e7eb" } }],
    }],
  });
}

function renderRefund() {
  if (!refundChart) return;
  const total = stats.value.refund_total || 0;
  const pending = stats.value.refund_pending || 0;
  const executed = total - pending;
  refundChart.setOption({
    grid: { left: 60, right: 30, top: 20, bottom: 30 },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#f3f4f6" } },
      axisLabel: { color: "#6b7280" },
    },
    yAxis: {
      type: "category",
      data: ["已执行", "待审批"],
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: { color: "#374151", fontSize: 13 },
    },
    series: [{
      data: [executed, pending],
      type: "bar",
      barWidth: 24,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: "#c7d2fe" },
          { offset: 1, color: "#4f46e5" },
        ]),
        borderRadius: [0, 6, 6, 0],
      },
    }],
  });
}

function handleResize() {
  trendChart?.resize();
  statusChart?.resize();
  engineerChart?.resize();
  slaChart?.resize();
  refundChart?.resize();
}

// ============ 服务探活 ============
async function probeServices() {
  for (const svc of services.value) {
    const t0 = Date.now();
    try {
      const r = await fetch(svc.url);
      svc.ok = r.ok;
      svc.latency = Date.now() - t0;
    } catch {
      svc.ok = false;
      svc.latency = 0;
    }
  }
}

// ============ 主加载 ============
async function load() {
  loading.value = true;
  try {
    const r = await api.dashboardStats();
    stats.value = { ...stats.value, ...r };
    lastUpdate.value = new Date().toLocaleString("zh-CN");
    await nextTick();
    renderTrend();
    renderStatus();
    renderEngineer();
    renderSLA();
    renderRefund();
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await nextTick();
  initCharts();
  await Promise.all([load(), probeServices()]);
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  trendChart?.dispose();
  statusChart?.dispose();
  engineerChart?.dispose();
  slaChart?.dispose();
  refundChart?.dispose();
});
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }
.svc-item {
  padding: 12px 16px; border-radius: 8px;
  display: flex; align-items: center; gap: 8px;
  background: #f9fafb; border: 1px solid #e5e7eb;
}
.svc-item.ok { background: #f0fdf4; border-color: #bbf7d0; }
.svc-item.err { background: #fef2f2; border-color: #fecaca; }
.svc-icon { font-size: 16px; }
.svc-name { flex: 1; font-weight: 500; }
.svc-latency { font-size: 12px; color: #9ca3af; }
</style>
