<template>
  <div>
    <div class="page-title">👷 工程师管理</div>

    <!-- ============ 顶部工具条 ============ -->
    <div class="card-panel toolbar">
      <div class="toolbar-left">
        <el-tag type="info" effect="plain">总人数：{{ engineers.length }}</el-tag>
        <el-tag type="success" effect="plain">在线：{{ onlineCount }}</el-tag>
        <el-tag effect="plain">离线：{{ engineers.length - onlineCount }}</el-tag>
        <el-tag type="warning" effect="plain">进行中工单：{{ totalLoad }}</el-tag>
      </div>
      <div class="toolbar-right">
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openAdd">新增工程师</el-button>
      </div>
    </div>

    <!-- ============ 筛选 ============ -->
    <div class="card-panel" style="margin-top:12px;">
      <el-radio-group v-model="statusFilter">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="online">🟢 在线</el-radio-button>
        <el-radio-button value="offline">⚪ 离线</el-radio-button>
      </el-radio-group>
    </div>

    <!-- ============ 表格 ============ -->
    <el-card shadow="never" style="margin-top:12px;">
      <el-table
        :data="filteredEngineers"
        v-loading="loading"
        stripe
        empty-text="暂无工程师，点右上角「新增工程师」添加"
      >
        <el-table-column prop="name" label="姓名" width="120">
          <template #default="{ row }">
            <el-avatar :size="32" style="background:linear-gradient(135deg,#4f46e5,#7c3aed); margin-right:8px;">
              {{ row.name.charAt(0) }}
            </el-avatar>
            <span style="font-weight:600;">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="技能" min-width="220">
          <template #default="{ row }">
            <el-tag
              v-for="s in row.skills"
              :key="s"
              size="small"
              effect="plain"
              type="primary"
              style="margin-right:4px;"
            >{{ s }}</el-tag>
            <span v-if="!row.skills.length" style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="region" label="区域" width="100" />

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">
              {{ row.status === "online" ? "🟢 在线" : "⚪ 离线" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="负载" width="180">
          <template #default="{ row }">
            <div class="load-bar">
              <el-progress
                :percentage="row.current_load / row.max_load * 100"
                :stroke-width="8"
                :show-text="false"
                :color="loadColor(row)"
              />
              <span class="load-text">{{ row.current_load }} / {{ row.max_load }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="phone" label="手机" width="140">
          <template #default="{ row }">
            <span v-if="row.phone">{{ row.phone }}</span>
            <span v-else style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.status === 'online' ? 'warning' : 'success'"
              link
              @click="toggle(row)"
            >
              {{ row.status === "online" ? "下线" : "上线" }}
            </el-button>
            <el-button size="small" type="primary" link @click="openEdit(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-popconfirm
              title="确认删除该工程师？"
              @confirm="doDelete(row)"
            >
              <template #reference>
                <el-button size="small" type="danger" link>
                  <el-icon><Delete /></el-icon> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ============ 新增 / 编辑 对话框 ============ -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '✏️ 编辑工程师' : '➕ 新增工程师'"
      width="560"
    >
      <el-form :model="form" label-width="110px" :rules="rules" ref="formRef">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="如 张工" />
        </el-form-item>
        <el-form-item label="技能" prop="skills">
          <el-select
            v-model="form.skills"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车创建，如 E102"
            style="width:100%;"
          >
            <el-option
              v-for="opt in skillOptions"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
          <div style="font-size:12px; color:#9ca3af; margin-top:4px;">
            支持自定义技能码，输入后按回车创建
          </div>
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="form.region" placeholder="如 华东" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="飞书 Open ID">
          <el-input v-model="form.feishu_open_id" placeholder="ou_xxxxx，选填，用于私聊通知" />
        </el-form-item>
        <el-form-item label="飞书 Chat ID">
          <el-input v-model="form.feishu_chat_id" placeholder="oc_xxxxx，选填，用于群通知" />
        </el-form-item>
        <el-form-item label="最大承接工单">
          <el-input-number v-model="form.max_load" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="状态" v-if="isEdit">
          <el-radio-group v-model="form.status">
            <el-radio value="online">🟢 在线</el-radio>
            <el-radio value="offline">⚪ 离线</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ isEdit ? "保存修改" : "创建" }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from "vue";
import { ElMessage } from "element-plus";
import { Refresh, Plus, Edit, Delete } from "@element-plus/icons-vue";
import api from "../api";

const engineers = ref([]);
const loading = ref(false);
const statusFilter = ref("");

const onlineCount = computed(() => engineers.value.filter((e) => e.status === "online").length);
const totalLoad = computed(() => engineers.value.reduce((s, e) => s + (e.current_load || 0), 0));

const filteredEngineers = computed(() => {
  if (!statusFilter.value) return engineers.value;
  return engineers.value.filter((e) => e.status === statusFilter.value);
});

// 技能选项（从已有工程师收集 + 常见故障码）
const skillOptions = computed(() => {
  const set = new Set(["E1", "E2", "E3", "E102", "E200"]);
  for (const e of engineers.value) {
    for (const s of e.skills || []) set.add(s);
  }
  return Array.from(set).sort();
});

function loadColor(row) {
  const pct = row.current_load / row.max_load;
  if (pct >= 0.9) return "#ef4444";
  if (pct >= 0.7) return "#f59e0b";
  return "#22c55e";
}

async function load() {
  loading.value = true;
  try {
    engineers.value = await api.listEngineers();
  } finally {
    loading.value = false;
  }
}

// ============ 新增/编辑 ============
const dialogVisible = ref(false);
const isEdit = ref(false);
const saving = ref(false);
const formRef = ref(null);

const defaultForm = () => ({
  id: null,
  name: "",
  skills: [],
  region: "",
  phone: "",
  feishu_open_id: "",
  feishu_chat_id: "",
  status: "online",
  max_load: 10,
});

const form = ref(defaultForm());

const rules = {
  name: [{ required: true, message: "请输入姓名", trigger: "blur" }],
  skills: [{ required: true, type: "array", min: 1, message: "至少选一个技能", trigger: "change" }],
};

function openAdd() {
  isEdit.value = false;
  form.value = defaultForm();
  dialogVisible.value = true;
  nextTick(() => formRef.value?.clearValidate());
}

function openEdit(row) {
  isEdit.value = true;
  form.value = {
    id: row.id,
    name: row.name,
    skills: [...(row.skills || [])],
    region: row.region || "",
    phone: row.phone || "",
    feishu_open_id: row.feishu_open_id || "",
    feishu_chat_id: row.feishu_chat_id || "",
    status: row.status || "online",
    max_load: row.max_load || 10,
  };
  dialogVisible.value = true;
  nextTick(() => formRef.value?.clearValidate());
}

async function save() {
  await formRef.value.validate();
  saving.value = true;
  try {
    const payload = {
      name: form.value.name.trim(),
      skills: form.value.skills,
      region: form.value.region.trim(),
      phone: form.value.phone.trim(),
      feishu_open_id: form.value.feishu_open_id.trim(),
      feishu_chat_id: form.value.feishu_chat_id.trim(),
      max_load: form.value.max_load,
    };

    if (isEdit.value) {
      payload.status = form.value.status;
      await api.updateEngineer(form.value.id, payload);
      ElMessage.success(`✅ 已保存 ${form.value.name}`);
    } else {
      await api.createEngineer(payload);
      ElMessage.success(`✅ 已创建 ${form.value.name}`);
    }
    dialogVisible.value = false;
    load();
  } catch (e) {
    // 拦截器已提示
  } finally {
    saving.value = false;
  }
}

// ============ 删除 ============
async function doDelete(row) {
  try {
    await api.deleteEngineer(row.id);
    ElMessage.success(`✅ 已删除 ${row.name}`);
    load();
  } catch (e) {
    // 拦截器已提示
  }
}

// ============ 上线/下线 ============
async function toggle(row) {
  const r = await api.toggleEngineer(row.id);
  ElMessage.success(`${row.name} 已切换为 ${r.status}`);
  load();
}

onMounted(load);
</script>

<style scoped>
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px;
}
.toolbar-left { display: flex; gap: 10px; align-items: center; }
.toolbar-right { display: flex; gap: 8px; }

.load-bar {
  display: flex; align-items: center; gap: 10px;
}
.load-bar .el-progress { flex: 1; }
.load-text {
  font-size: 12px; color: #6b7280;
  min-width: 60px; text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
