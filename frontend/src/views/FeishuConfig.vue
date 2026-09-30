<template>
  <div>
    <div class="page-title">🤖 飞书配置</div>

    <el-card shadow="never" style="margin-bottom:16px;">
      <template #header><span style="font-weight:600;">应用凭证</span></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="App ID">{{ status.app_id }}</el-descriptions-item>
        <el-descriptions-item label="App Secret">
          <el-tag :type="status.app_secret_set ? 'success' : 'danger'" size="small">
            {{ status.app_secret_set ? "已配置" : "未配置" }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Token 状态" :span="2">
          <el-tag :type="status.token_ok ? 'success' : 'danger'">
            {{ status.token_ok ? "✅ 可获取" : "❌ 获取失败" }}
          </el-tag>
          <span style="margin-left:12px; color:#9ca3af; font-size:12px;">
            如需修改，编辑 .env：FEISHU_APP_ID / FEISHU_APP_SECRET
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" style="margin-bottom:16px;">
      <template #header>
        <span style="font-weight:600;">群 Webhook</span>
        <span style="color:#9ca3af; font-size:12px; margin-left:12px;">
          配置后事件会广播到群
        </span>
      </template>
      <el-table :data="channels" stripe>
        <el-table-column prop="key" label="群标识" width="200" />
        <el-table-column prop="label" label="群名" width="200" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.webhook_set ? 'success' : 'info'" size="small">
              {{ row.webhook_set ? "✅ 已配置" : "未配置" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="@所有人" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.at_all" type="warning" size="small">是</el-tag>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="openWebhook(row)">配置</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-bottom:16px;">
      <template #header><span style="font-weight:600;">事件 → 角色分发</span></template>
      <el-table :data="eventRoles" size="small" stripe>
        <el-table-column prop="event" label="事件" width="240" />
        <el-table-column label="私聊给角色">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r" size="small" style="margin-right:4px;">
              {{ roleLabel(r) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header><span style="font-weight:600;">手动测试</span></template>
      <el-form inline>
        <el-form-item label="用户">
          <el-select v-model="testForm.user_id" placeholder="选择用户" style="width:240px;">
            <el-option v-for="u in users" :key="u.id" :value="u.id"
                       :label="u.name + ' (' + u.role_label + ')' + (u.feishu_open_id ? ' ✅' : ' ❌')" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="testForm.title" style="width:180px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="testing" @click="doTestPrivate">
            发送测试消息
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="testResult" :type="testResult.ok ? 'success' : 'error'" :closable="false" style="margin-top:12px;">
        <template #title>{{ testResult.ok ? '✅ 发送成功' : '❌ 发送失败' }}</template>
        <div v-if="testResult.to">收件人: {{ testResult.to }}</div>
        <div v-if="testResult.error">错误: {{ testResult.error }}</div>
      </el-alert>
    </el-card>

    <el-dialog v-model="webhookVisible" :title="'配置 ' + (editingChannel.label || editingChannel.key)" width="600">
      <el-form label-width="100px">
        <el-form-item label="群名">
          <el-input v-model="editingChannel.label" />
        </el-form-item>
        <el-form-item label="Webhook URL">
          <el-input v-model="editingChannel.webhook" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
        </el-form-item>
        <el-form-item label="@所有人">
          <el-switch v-model="editingChannel.at_all" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="webhookVisible = false">取消</el-button>
        <el-button type="primary" @click="saveWebhook">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
// 统一用共享客户端：它自带 Authorization 请求头与统一错误提示，
// 不必在本页重复实现一遍拦截器。
import api from "../api";

const status = ref({ app_id: "", app_secret_set: false, token_ok: false });
const config = ref({});
const users = ref([]);
const testing = ref(false);
const testResult = ref(null);
const testForm = ref({ user_id: null, title: "测试通知", content: "这是一条测试消息" });

const webhookVisible = ref(false);
const editingChannel = ref({ key: "", label: "", webhook: "", at_all: false });

const ROLE_LABELS = { admin: "管理员", supervisor: "主管", engineer: "工程师", agent: "客服" };
function roleLabel(r) { return ROLE_LABELS[r] || r; }

const channels = computed(() => {
  const c = config.value.channels || {};
  return Object.entries(c).map(([k, v]) => ({ key: k, ...v }));
});

const eventRoles = computed(() => {
  const m = config.value.event_to_roles || {};
  return Object.entries(m).map(([event, roles]) => ({ event, roles }));
});

async function load() {
  try {
    const [s, c, u] = await Promise.all([
      api.get("/feishu/status"),
      api.get("/feishu/config"),
      api.get("/users"),
    ]);
    status.value = s;
    config.value = c;
    users.value = u.items || [];
  } catch (e) {}
}

function openWebhook(row) {
  editingChannel.value = { key: row.key, label: row.label, webhook: "", at_all: row.at_all };
  webhookVisible.value = true;
}

async function saveWebhook() {
  await api.put("/feishu/webhook", {
    channel: editingChannel.value.key,
    webhook: editingChannel.value.webhook,
    at_all: editingChannel.value.at_all,
  });
  ElMessage.success("已保存");
  webhookVisible.value = false;
  await load();
}

async function doTestPrivate() {
  if (!testForm.value.user_id) return ElMessage.warning("请选用户");
  testing.value = true;
  testResult.value = null;
  try {
    const r = await api.post("/feishu/test-private", testForm.value);
    testResult.value = r;
    if (r.ok) ElMessage.success("发送成功");
  } finally {
    testing.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
</style>
