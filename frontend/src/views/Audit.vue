<template>
  <div>
    <div class="page-title">📋 审计日志</div>

    <!-- ============ 统计卡 ============ -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col v-for="s in auditStats.slice(0, 6)" :key="s.action" :span="4">
        <el-card shadow="never" class="stat-card">
          <el-statistic :title="s.action" :value="s.count" />
        </el-card>
      </el-col>
      <el-col v-if="auditStats.length === 0" :span="24">
        <el-card shadow="never">
          <el-empty description="暂无统计数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- ============ 筛选 ============ -->
    <div class="card-panel toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="actionFilter"
          placeholder="筛选 action（模糊匹配）"
          clearable
          style="width:240px;"
          @keyup.enter="load"
          @clear="load"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input
          v-model="targetFilter"
          placeholder="筛选目标 ID（工单号等）"
          clearable
          style="width:220px;"
          @keyup.enter="load"
          @clear="load"
        />
        <el-select v-model="limit" style="width:120px;" @change="load">
          <el-option :value="50" label="50 条" />
          <el-option :value="100" label="100 条" />
          <el-option :value="200" label="200 条" />
          <el-option :value="500" label="500 条" />
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
        :data="logs"
        v-loading="loading"
        stripe
        empty-text="暂无审计记录"
        max-height="calc(100vh - 400px)"
      >
        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            <span class="time-cell">{{ fmtTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作人" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.actor === 'system' ? 'info' : 'primary'">
              {{ row.actor || "-" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="动作" width="180">
          <template #default="{ row }">
            <el-tag size="small" :type="actionType(row.action)" effect="plain">
              {{ row.action }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="目标" width="140">
          <template #default="{ row }">
            <span v-if="row.target_id" style="font-family: monospace; font-size: 12px;">
              {{ row.target_id }}
            </span>
            <span v-else style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>

        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.result === 'ok' ? 'success' : 'danger'" size="small">
              {{ row.result === "ok" ? "✅" : "❌" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="详情" min-width="300">
          <template #default="{ row }">
            <div class="detail-cell" @click="showDetail(row)">
              <span class="detail-text">{{ row.detail }}</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="🔍 详情" width="600">
      <pre class="json-pre">{{ prettyDetail }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Search, Refresh } from "@element-plus/icons-vue";
import api from "../api";

const logs = ref([]);
const loading = ref(false);
const auditStats = ref([]);
const actionFilter = ref("");
const targetFilter = ref("");
const limit = ref(100);

function fmtTime(t) {
  if (!t) return "-";
  return t.slice(0, 19).replace("T", " ");
}

function actionType(action) {
  if (!action) return "info";
  if (action.includes("created")) return "success";
  if (action.includes("rejected") || action.includes("fail")) return "danger";
  if (action.includes("resolved") || action.includes("closed")) return "success";
  if (action.includes("accepted") || action.includes("start")) return "primary";
  return "info";
}

async function load() {
  loading.value = true;
  try {
    const params = { limit: limit.value };
    if (actionFilter.value.trim()) params.action = actionFilter.value.trim();
    if (targetFilter.value.trim()) params.target_id = targetFilter.value.trim();
    const r = await api.listAudit(params);
    logs.value = r.items || [];
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    const r = await api.auditStats();
    auditStats.value = r.items || [];
  } catch {}
}

async function loadAll() {
  await Promise.all([load(), loadStats()]);
}

// 详情
const detailVisible = ref(false);
const prettyDetail = ref("");
function showDetail(row) {
  try {
    const parsed = JSON.parse(row.detail || "{}");
    prettyDetail.value = JSON.stringify(parsed, null, 2);
  } catch {
    prettyDetail.value = row.detail || "";
  }
  detailVisible.value = true;
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
.detail-cell {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background 0.15s;
}
.detail-cell:hover { background: #f3f4f6; }
.detail-text {
  font-size: 12px; color: #374151;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical;
  overflow: hidden;
}
.json-pre {
  background: #1f2937; color: #f3f4f6;
  padding: 16px; border-radius: 8px;
  font-size: 13px; max-height: 400px; overflow: auto;
}
</style>
