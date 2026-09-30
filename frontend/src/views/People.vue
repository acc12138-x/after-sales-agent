<template>
  <div>
    <div class="page-title">👥 人员管理</div>

    <!-- 统计卡 -->
    <el-row :gutter="12" style="margin-bottom:16px;">
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="总人数" :value="stats.total" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="🟢 在线" :value="stats.online" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="⚪ 离线" :value="stats.offline" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="👨‍💼 工程师" :value="stats.engineer" /></el-card></el-col>
      <el-col :span="4"><el-card shadow="never" class="stat-card"><el-statistic title="👔 主管" :value="stats.supervisor" /></el-card></el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <el-button :icon="Refresh" @click="load" style="width:100%; height:100%;">刷新</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选 + 工具 -->
    <div class="card-panel toolbar">
      <div class="toolbar-left">
        <el-select v-model="filters.role" clearable placeholder="角色" style="width:140px;" @change="load">
          <el-option v-for="r in meta.roles" :key="r.code" :value="r.code" :label="r.label" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width:120px;" @change="load">
          <el-option value="online" label="🟢 在线" />
          <el-option value="offline" label="⚪ 离线" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="姓名/手机/飞书ID" clearable style="width:220px;" @keyup.enter="load" @clear="load" />
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
      </div>
      <div class="toolbar-right">
        <el-button
          :type="pendingList.length ? 'warning' : 'default'"
          :icon="Link"
          @click="openPending"
        >
          待绑定飞书账号{{ pendingList.length ? " (" + pendingList.length + ")" : "" }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openAdd">新增人员</el-button>
      </div>
    </div>

    <!-- 表格 -->
    <el-card shadow="never" style="margin-top:12px;">
      <el-table :data="filteredUsers" v-loading="loading" stripe empty-text="暂无人员">
        <el-table-column label="姓名" width="140">
          <template #default="{ row }">
            <el-avatar :size="30" :style="{ background: roleColor(row.role), marginRight: '8px' }">
              {{ row.name.charAt(0) }}
            </el-avatar>
            <span style="font-weight:600;">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTag(row.role)" size="small">{{ row.role_label }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="job" label="职业" width="90" />

        <el-table-column label="技能" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="s in (row.skills || [])" :key="s" size="small" effect="plain" style="margin-right:4px;">{{ s }}</el-tag>
            <span v-if="!row.skills || !row.skills.length" style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="region" label="区域" width="90" />

        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">
              {{ row.status === "online" ? "🟢 在线" : "⚪ 离线" }}
            </el-tag>
          </template>
        </el-table-column>


        <el-table-column prop="phone" label="手机号" width="130" />

        <el-table-column label="飞书 ID" width="180">
          <template #default="{ row }">
            <span v-if="row.feishu_open_id" style="font-family: monospace; font-size: 11px;">{{ row.feishu_open_id }}</span>
            <span v-else style="color:#9ca3af;">未绑定</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :type="row.status === 'online' ? 'warning' : 'success'" link @click="toggleStatus(row)">
              {{ row.status === "online" ? "下线" : "上线" }}
            </el-button>
            <el-button size="small" type="primary" link @click="openEdit(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-popconfirm title="确认删除？" @confirm="doDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" link>
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? ('✏️ 编辑 - ' + form.name) : '➕ 新增人员'"
      width="720px" top="5vh"
    >
      <el-tabs v-model="activeTab">
        <!-- Tab 1 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="form" label-width="100px" style="margin-top:12px;">
            <el-form-item label="姓名">
              <el-input v-model="form.name" placeholder="如 王工" />
            </el-form-item>
            <el-form-item label="角色">
              <el-select v-model="form.role" style="width:100%;">
                <el-option v-for="r in meta.roles" :key="r.code" :value="r.code" :label="r.label" />
              </el-select>
            </el-form-item>
            <el-form-item label="职业">
              <el-input v-model="form.job" placeholder="如 维修 / 客服 / 主管" />
            </el-form-item>
            <el-form-item label="部门">
              <el-input v-model="form.dept" />
            </el-form-item>
            <el-form-item label="区域">
              <el-input v-model="form.region" placeholder="如 华东 / 总部" />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="form.phone" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
            <el-form-item label="飞书 Open ID">
              <el-input v-model="form.feishu_open_id" placeholder="ou_xxxxx，用于飞书私聊通知" />
            </el-form-item>
            <el-form-item label="飞书 Chat ID">
              <el-input v-model="form.feishu_chat_id" placeholder="oc_xxxxx / chat:xxx，用于群通知与群会话" />
            </el-form-item>
            <el-form-item label="状态" v-if="isEdit">
              <el-radio-group v-model="form.status">
                <el-radio value="online">🟢 在线</el-radio>
                <el-radio value="offline">⚪ 离线</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Tab 2 技能与负载 -->
        <el-tab-pane label="技能与负载" name="skills">
          <el-form :model="form" label-width="100px" style="margin-top:12px;">
            <el-form-item label="技能">
              <el-select
                v-model="form.skills" multiple filterable allow-create default-first-option
                placeholder="输入后回车创建，如 E102" style="width:100%;"
              >
                <el-option v-for="opt in skillOptions" :key="opt" :label="opt" :value="opt" />
              </el-select>
              <div style="font-size:12px; color:#9ca3af; margin-top:4px;">支持自定义技能码</div>
            </el-form-item>
            <el-form-item label="最大承接">
              <el-input-number v-model="form.max_load" :min="1" :max="999" />
            </el-form-item>
            <el-form-item label="当前负载">
              <el-tag>{{ form.current_load || 0 }}</el-tag>
              <span style="font-size:12px; color:#9ca3af; margin-left:12px;">由工单自动维护</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- Tab 3 权限 -->
        <el-tab-pane label="权限" name="perms">
          <el-alert type="info" :closable="false" style="margin:12px 0;">
            <template #title>
              角色默认权限已自动继承。下方可额外允许或禁止个别权限。
            </template>
          </el-alert>

          <el-divider content-position="left">角色默认权限</el-divider>
          <el-tag v-for="p in rolePerms" :key="p" size="small" effect="plain" style="margin:4px 6px 4px 0;">
            {{ permLabel(p) }}
          </el-tag>

          <el-divider content-position="left">额外允许</el-divider>
          <el-checkbox-group v-model="form.permissions.allow">
            <el-checkbox v-for="p in allPerms" :key="p.code" :value="p.code" :label="p.code" style="width:200px;">
              {{ p.label }}
            </el-checkbox>
          </el-checkbox-group>

          <el-divider content-position="left">额外禁止</el-divider>
          <el-checkbox-group v-model="form.permissions.deny">
            <el-checkbox v-for="p in allPerms" :key="p.code" :value="p.code" :label="p.code" style="width:200px;">
              {{ p.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ isEdit ? "保存修改" : "创建" }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 待绑定飞书账号 -->
    <el-dialog v-model="pendingVisible" title="🔗 待绑定飞书账号" width="900px" top="6vh">
      <el-alert type="info" :closable="false" style="margin-bottom:12px;">
        <template #title>
          这些 open_id 来自用户给机器人发的消息。选定对应人员点「绑定」即可，
          之后该用户就能使用「我的工单」等依赖飞书身份的功能。
        </template>
      </el-alert>

      <div style="display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap;">
        <el-input v-model="manualOpenId" placeholder="手动登记 open_id（ou_xxxxx）" clearable style="width:280px;" />
        <el-input v-model="manualChatId" placeholder="chat_id（选填 oc_xxxxx）" clearable style="width:240px;" />
        <el-button type="primary" :icon="Plus" @click="doManualRecord">登记</el-button>
        <el-button :icon="Refresh" @click="loadPending">刷新</el-button>
      </div>

      <el-table
        :data="pendingList" v-loading="pendingLoading" stripe max-height="420"
        empty-text="暂无待绑定。用户发消息给机器人后会自动出现在这里。"
      >
        <el-table-column label="open_id" min-width="220">
          <template #default="{ row }">
            <span style="font-family: monospace; font-size: 12px;">{{ row.open_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="chat_id" width="170">
          <template #default="{ row }">
            <span v-if="row.chat_id" style="font-family: monospace; font-size: 11px;">{{ row.chat_id }}</span>
            <span v-else style="color:#9ca3af;">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="消息数" width="80" />
        <el-table-column label="最近消息" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="font-size:12px; color:#6b7280;">{{ row.last_text || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="绑定到" width="200">
          <template #default="{ row }">
            <el-select v-model="bindTarget[row.open_id]" filterable placeholder="选择人员" size="small" style="width:100%;">
              <el-option
                v-for="u in userOptions" :key="u.id" :value="u.id"
                :label="u.name + '（' + u.role_label + '）'"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="doBind(row)">绑定</el-button>
            <el-button size="small" type="danger" link @click="doDismiss(row)">忽略</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Refresh, Search, Plus, Edit, Delete, Link } from "@element-plus/icons-vue";
import api from "../api";

const users = ref([]);
const loading = ref(false);
const meta = ref({ roles: [], role_permissions: {}, all_permissions: [] });

const filters = reactive({ role: "", status: "", keyword: "" });

const stats = computed(() => {
  const s = { total: 0, online: 0, offline: 0, engineer: 0, supervisor: 0 };
  for (const u of users.value) {
    s.total++;
    if (u.status === "online") s.online++;
    else s.offline++;
    if (u.role === "engineer") s.engineer++;
    if (u.role === "supervisor") s.supervisor++;
  }
  return s;
});

const filteredUsers = computed(() => {
  let list = users.value;
  if (filters.keyword.trim()) {
    const kw = filters.keyword.trim().toLowerCase();
    list = list.filter(u =>
      (u.name || "").toLowerCase().includes(kw) ||
      (u.phone || "").includes(kw) ||
      (u.feishu_open_id || "").toLowerCase().includes(kw)
    );
  }
  return list;
});

const skillOptions = computed(() => {
  const set = new Set(["E1", "E2", "E3", "E102", "E200", "E205", "E308", "E411", "E503"]);
  for (const u of users.value) for (const s of (u.skills || [])) set.add(s);
  return Array.from(set).sort();
});

const allPerms = computed(() => meta.value.all_permissions || []);
const rolePerms = computed(() => meta.value.role_permissions?.[form.value.role] || []);

function permLabel(code) {
  const p = allPerms.value.find(x => x.code === code);
  return p ? p.label : code;
}

function roleTag(r) {
  return { admin: "danger", supervisor: "warning", engineer: "primary", agent: "success" }[r] || "info";
}
function roleColor(r) {
  return { admin: "#ef4444", supervisor: "#f59e0b", engineer: "#4f46e5", agent: "#22c55e" }[r] || "#9ca3af";
}
async function loadMeta() {
  try {
    meta.value = await api.getUsersMeta();
  } catch (e) { /* 拦截器已提示 */ }
}

async function load() {
  loading.value = true;
  try {
    const params = {};
    if (filters.role) params.role = filters.role;
    if (filters.status) params.status = filters.status;
    const r = await api.listUsers(params);
    users.value = r.items || [];
  } finally {
    loading.value = false;
  }
}

// 编辑
const dialogVisible = ref(false);
const isEdit = ref(false);
const saving = ref(false);
const activeTab = ref("basic");

const defaultForm = () => ({
  id: null,
  name: "",
  role: "engineer",
  job: "",
  dept: "",
  region: "",
  phone: "",
  email: "",
  feishu_open_id: "",
  feishu_chat_id: "",
  status: "online",
  skills: [],
  max_load: 10,
  current_load: 0,
  permissions: { allow: [], deny: [] },
});

const form = ref(defaultForm());

function openAdd() {
  isEdit.value = false;
  form.value = defaultForm();
  activeTab.value = "basic";
  dialogVisible.value = true;
}

function openEdit(row) {
  isEdit.value = true;
  const perms = row.permissions || {};
  form.value = {
    id: row.id,
    name: row.name,
    role: row.role,
    job: row.job || "",
    dept: row.dept || "",
    region: row.region || "",
    phone: row.phone || "",
    email: row.email || "",
    feishu_open_id: row.feishu_open_id || "",
    feishu_chat_id: row.feishu_chat_id || "",
    status: row.status || "online",
    skills: [...(row.skills || [])],
    max_load: row.max_load || 10,
    current_load: row.current_load || 0,
    permissions: {
      allow: [...(perms.allow || [])],
      deny: [...(perms.deny || [])],
    },
  };
  activeTab.value = "basic";
  dialogVisible.value = true;
}

async function save() {
  if (!form.value.name.trim()) return ElMessage.warning("请输入姓名");
  saving.value = true;
  try {
    const payload = {
      name: form.value.name.trim(),
      role: form.value.role,
      job: form.value.job.trim(),
      dept: form.value.dept.trim(),
      region: form.value.region.trim(),
      phone: form.value.phone.trim(),
      email: form.value.email.trim(),
      feishu_open_id: form.value.feishu_open_id.trim(),
      feishu_chat_id: form.value.feishu_chat_id.trim(),
      skills: form.value.skills,
      max_load: form.value.max_load,
      permissions: form.value.permissions,
    };
    if (isEdit.value) {
      payload.status = form.value.status;
      await api.updateUser(form.value.id, payload);
      ElMessage.success(`✅ 已保存 ${form.value.name}`);
    } else {
      await api.createUser(payload);
      ElMessage.success(`✅ 已创建 ${form.value.name}`);
    }
    dialogVisible.value = false;
    await load();
  } catch (e) { /* 拦截器提示 */ } finally {
    saving.value = false;
  }
}

async function doDelete(row) {
  try {
    await api.deleteUser(row.id);
    ElMessage.success(`✅ 已删除 ${row.name}`);
    await load();
  } catch (e) { /* 拦截器提示 */ }
}

async function toggleStatus(row) {
  const r = await api.toggleUserStatus(row.id);
  ElMessage.success(`${row.name} 已切换为 ${r.status}`);
  await load();
}

// ============ 待绑定飞书账号 ============
const pendingVisible = ref(false);
const pendingLoading = ref(false);
const pendingList = ref([]);
const bindTarget = reactive({});
const manualOpenId = ref("");
const manualChatId = ref("");

const userOptions = computed(() => users.value);

async function loadPending() {
  pendingLoading.value = true;
  try {
    const r = await api.getPendingBindings();
    pendingList.value = r.items || [];
  } catch (e) { /* 拦截器已提示 */ } finally {
    pendingLoading.value = false;
  }
}

function openPending() {
  pendingVisible.value = true;
  return loadPending();
}

async function doBind(row) {
  const uid = bindTarget[row.open_id];
  if (!uid) return ElMessage.warning("请先选择要绑定的人员");
  try {
    const r = await api.bindPending({
      open_id: row.open_id,
      user_id: uid,
      chat_id: row.chat_id || "",
    });
    ElMessage.success(`✅ 已绑定到 ${r.name}`);
    await Promise.all([loadPending(), load()]);
  } catch (e) { /* 拦截器已提示 */ }
}

async function doDismiss(row) {
  try {
    await api.dismissPending(row.open_id);
    ElMessage.success("已忽略");
    await loadPending();
  } catch (e) { /* 拦截器已提示 */ }
}

async function doManualRecord() {
  const oid = manualOpenId.value.trim();
  if (!oid) return ElMessage.warning("请输入 open_id");
  try {
    const r = await api.recordPending({
      open_id: oid,
      chat_id: manualChatId.value.trim(),
      note: "手动登记",
    });
    if (r.recorded === false) {
      ElMessage.warning(r.reason || "该 open_id 已在待绑定列表中或已绑定");
    } else {
      ElMessage.success("✅ 已登记");
    }
    manualOpenId.value = "";
    manualChatId.value = "";
    await loadPending();
  } catch (e) { /* 拦截器已提示 */ }
}

onMounted(async () => {
  await loadMeta();
  await load();
  await loadPending();
});
</script>

<style scoped>
.stat-card { text-align: center; padding: 4px; }
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; gap: 12px; flex-wrap: wrap;
}
.toolbar-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.toolbar-right { display: flex; gap: 8px; }
</style>
