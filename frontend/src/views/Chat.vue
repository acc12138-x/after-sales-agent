<template>
  <div class="chat-page">
    <div class="page-title">💬 对话测试</div>

    <!-- ============ 顶部工具条 ============ -->
    <div class="card-panel toolbar">
      <div class="toolbar-left">
        <el-tag type="info" effect="plain">
          🧵 Thread: {{ threadId }}
        </el-tag>
        <el-tag :type="backendOk ? 'success' : 'danger'" effect="plain">
          {{ backendOk ? "🟢 后端在线" : "🔴 后端离线" }}
        </el-tag>
      </div>
      <div class="toolbar-right">
        <el-button @click="newThread" :icon="Refresh">新会话</el-button>
        <el-button @click="clearHistory" :icon="Delete">清空</el-button>
      </div>
    </div>

    <!-- ============ 快捷示例 ============ -->
    <div class="card-panel examples">
      <span class="examples-label">💡 快捷示例：</span>
      <el-button
        v-for="(ex, i) in examples"
        :key="i"
        size="small"
        @click="quickSend(ex)"
      >{{ ex }}</el-button>
    </div>

    <!-- ============ 消息列表 ============ -->
    <div ref="msgList" class="message-list">
      <el-empty v-if="!messages.length" description="暂无消息，发送第一条吧 👇" />

      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="message-row"
        :class="msg.role"
      >
        <el-avatar
          :size="36"
          :style="msg.role === 'user' ? 'background:#4f46e5' : 'background:#7c3aed'"
        >
          <el-icon :size="20">
            <User v-if="msg.role === 'user'" />
            <Tools v-else />
          </el-icon>
        </el-avatar>

        <div class="message-body">
          <div class="message-content" v-html="renderContent(msg.content)"></div>

          <div v-if="msg.meta" class="message-meta">
            <el-tag size="small" effect="plain">意图：{{ msg.meta.intent }}</el-tag>
            <el-tag size="small" effect="plain">置信度：{{ fmtConf(msg.meta.confidence) }}</el-tag>
            <el-tag size="small" effect="plain">耗时：{{ msg.meta.elapsed }}s</el-tag>
            <el-button link type="primary" size="small" @click="msg.showDetail = !msg.showDetail">
              {{ msg.showDetail ? "收起" : "详情" }}
            </el-button>
          </div>

          <el-collapse-transition>
            <pre v-if="msg.showDetail && msg.meta" class="meta-json">{{ JSON.stringify(msg.meta, null, 2) }}</pre>
          </el-collapse-transition>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="message-row assistant">
        <el-avatar :size="36" style="background:#7c3aed">
          <el-icon :size="20"><Tools /></el-icon>
        </el-avatar>
        <div class="message-body">
          <el-tag type="info" effect="plain">
            <el-icon class="is-loading"><Loading /></el-icon>
            思考中...
          </el-tag>
        </div>
      </div>
    </div>

    <!-- ============ 底部输入 ============ -->
    <div class="input-bar card-panel">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        placeholder="输入问题，例如：E102 报警怎么排查 / 帮我报修 XY200 故障码 E102 / 订单到哪了"
        resize="none"
        @keydown.enter.exact.prevent="send"
      />
      <el-button
        type="primary"
        :icon="Promotion"
        :loading="loading"
        @click="send"
        size="large"
      >发送</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from "vue";
import { ElMessage } from "element-plus";
import { Refresh, Delete, User, Tools, Promotion, Loading } from "@element-plus/icons-vue";
import api from "../api";

const threadId = ref("web-" + Math.random().toString(36).slice(2, 10));
const messages = ref([]);
const input = ref("");
const loading = ref(false);
const backendOk = ref(false);
const msgList = ref(null);

const examples = [
  "E102 报警怎么排查",
  "帮我报修 XY200 设备，故障码 E102",
  "我的 XY200 设备坏了",
  "订单到哪了 O20260201002",
  "我要退货",
  "转人工",
];

async function checkBackend() {
  try {
    await fetch("/api/health");
    backendOk.value = true;
  } catch {
    backendOk.value = false;
  }
}

function newThread() {
  threadId.value = "web-" + Math.random().toString(36).slice(2, 10);
  messages.value = [];
  ElMessage.success("已开启新会话");
}

function clearHistory() {
  messages.value = [];
}

function quickSend(text) {
  input.value = text;
  send();
}

function fmtConf(v) {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  return isNaN(n) ? String(v) : n.toFixed(3);
}

function renderContent(text) {
  if (!text) return "";
  // 换行 -> <br>，简单防 XSS
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}

async function scrollToBottom() {
  await nextTick();
  if (msgList.value) {
    msgList.value.scrollTop = msgList.value.scrollHeight;
  }
}

async function send() {
  const text = input.value.trim();
  if (!text || loading.value) return;

  messages.value.push({ role: "user", content: text });
  input.value = "";
  loading.value = true;
  await scrollToBottom();

  const t0 = Date.now();

  try {
    const resp = await api.chat({
      message: text,
      thread_id: threadId.value,
      user_id: "vue-client",
    });

    const dt = ((Date.now() - t0) / 1000).toFixed(2);

    let answer = resp.answer || "（后端返回空）";
    if (resp.hitl_pending) {
      answer = "**【需要人工确认】** " + (resp.hitl_reason || "") + "\n\n" + answer;
    }

    messages.value.push({
      role: "assistant",
      content: answer,
      meta: {
        intent: resp.intent,
        confidence: resp.confidence,
        flow_status: resp.flow_status,
        hitl_pending: resp.hitl_pending,
        elapsed: dt,
        citations: resp.citations,
      },
      showDetail: false,
    });
  } catch (err) {
    const detail = err?.response?.data?.detail || err.message || "未知错误";
    messages.value.push({
      role: "assistant",
      content: "❌ 请求失败：" + (typeof detail === "string" ? detail : JSON.stringify(detail)),
    });
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}

onMounted(checkBackend);
</script>

<style scoped>
.chat-page {
  display: flex; flex-direction: column;
  height: calc(100vh - 56px - 48px);
  gap: 12px;
}

.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px;
}
.toolbar-left { display: flex; gap: 10px; align-items: center; }
.toolbar-right { display: flex; gap: 8px; }

.examples {
  padding: 12px 20px;
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.examples-label { color: #6b7280; font-size: 13px; }

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  display: flex; flex-direction: column; gap: 16px;
}

.message-row { display: flex; gap: 12px; }
.message-row.user { flex-direction: row-reverse; }
.message-row.user .message-body { align-items: flex-end; }

.message-body {
  display: flex; flex-direction: column;
  max-width: 75%;
  gap: 6px;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-break: break-word;
  font-size: 14px;
}
.message-row.user .message-content {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  color: white;
  border-top-right-radius: 2px;
}
.message-row.assistant .message-content {
  background: #f3f4f6;
  color: #111827;
  border-top-left-radius: 2px;
}

.message-meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

.meta-json {
  background: #1f2937; color: #f3f4f6;
  padding: 10px; border-radius: 8px;
  font-size: 12px; max-height: 200px; overflow: auto;
}

.input-bar {
  display: flex; gap: 12px; align-items: flex-end;
  padding: 16px;
}
.input-bar .el-input { flex: 1; }
</style>
