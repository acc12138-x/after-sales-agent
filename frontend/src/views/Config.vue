<template>
  <div>
    <div class="page-title">⚙️ 系统配置</div>

    <el-alert type="info" :closable="false" style="margin-bottom:16px;">
      <template #title>
        直接填 Base URL + 模型名；点厂商按钮可一键填入。保存后点【热重载引擎】立即生效，无需重启服务。
      </template>
    </el-alert>

    <el-row :gutter="16">
      <!-- ============ LLM 配置 ============ -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span style="font-weight:600;">🧠 LLM 配置</span>
            <span style="color:#9ca3af; margin-left:12px; font-size:12px;">点下方厂商快速填入</span>
          </template>

          <div class="presets">
            <el-button size="small" @click="fillLLM('http://127.0.0.1:11434', 'modelscope.cn/Qwen/Qwen3-4B-GGUF:latest')">
              🦙 Ollama
            </el-button>
            <el-button size="small" @click="fillLLM('https://api.deepseek.com', 'deepseek-chat')">
              🐋 DeepSeek
            </el-button>
            <el-button size="small" @click="fillLLM('https://dashscope.aliyuncs.com/compatible-mode/v1', 'qwen-plus')">
              ☁️ 通义千问
            </el-button>
            <el-button size="small" @click="fillLLM('https://api.moonshot.cn/v1', 'moonshot-v1-8k')">
              🌙 Kimi
            </el-button>
            <el-button size="small" @click="fillLLM('https://open.bigmodel.cn/api/paas/v4', 'glm-4-flash')">
              🧠 智谱
            </el-button>
            <el-button size="small" @click="fillLLM('https://api.openai.com/v1', 'gpt-4o-mini')">
              🤖 OpenAI
            </el-button>
          </div>

          <el-form label-width="90px" style="margin-top:16px;">
            <el-form-item label="Base URL">
              <el-input v-model="llm.base_url" placeholder="本地填 http://127.0.0.1:11434；云端填厂商 URL" />
            </el-form-item>
            <el-form-item label="模型名">
              <el-input v-model="llm.model" placeholder="如 deepseek-chat / qwen-plus" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="llm.api_key"
                type="password"
                show-password
                :placeholder="llm.masked_key ? ('当前：' + llm.masked_key + '（留空不更新）') : '本地留空；云端必填'"
              />
            </el-form-item>
            <el-form-item label="当前模式">
              <el-tag :type="llmMode === 'ollama' ? 'success' : 'primary'">
                {{ llmMode === "ollama" ? "🦙 Ollama 原生" : "☁️ OpenAI 兼容" }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- ============ Embedding 配置 ============ -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span style="font-weight:600;">🎯 Embedding 配置</span>
            <span style="color:#9ca3af; margin-left:12px; font-size:12px;">注意：切换后需重建知识库索引</span>
          </template>

          <div class="presets">
            <el-button size="small" @click="fillEmb('http://127.0.0.1:11434', 'bge-m3:latest')">
              🦙 bge-m3
            </el-button>
            <el-button size="small" @click="fillEmb('https://dashscope.aliyuncs.com/compatible-mode/v1', 'text-embedding-v3')">
              ☁️ DashScope
            </el-button>
            <el-button size="small" @click="fillEmb('https://api.openai.com/v1', 'text-embedding-3-small')">
              🤖 OpenAI
            </el-button>
          </div>

          <el-form label-width="90px" style="margin-top:16px;">
            <el-form-item label="Base URL">
              <el-input v-model="emb.base_url" placeholder="本地填 http://127.0.0.1:11434；云端填厂商 URL" />
            </el-form-item>
            <el-form-item label="嵌入模型名">
              <el-input v-model="emb.model" placeholder="如 bge-m3:latest / text-embedding-v3" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="emb.api_key"
                type="password"
                show-password
                :placeholder="emb.masked_key ? ('当前：' + emb.masked_key + '（留空不更新）') : '本地留空；云端必填'"
              />
            </el-form-item>
            <el-form-item label="当前模式">
              <el-tag :type="embMode === 'ollama' ? 'success' : 'primary'">
                {{ embMode === "ollama" ? "🦙 Ollama 原生" : "☁️ OpenAI 兼容" }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- ============ RAG 参数 ============ -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header><span style="font-weight:600;">🔧 RAG 参数</span></template>
      <el-row :gutter="16">
        <el-col :span="6">
          <el-form-item label="Chunk Size">
            <el-input-number v-model="rag.chunk_size" :min="128" :max="2048" :step="64" style="width:100%;" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="Overlap">
            <el-input-number v-model="rag.chunk_overlap" :min="0" :max="512" :step="16" style="width:100%;" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="召回 TopK">
            <el-input-number v-model="rag.top_k_retrieve" :min="5" :max="100" :step="5" style="width:100%;" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="重排 TopK">
            <el-input-number v-model="rag.top_k_rerank" :min="1" :max="20" :step="1" style="width:100%;" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-card>

    <!-- ============ 操作区 ============ -->
    <el-card shadow="never" style="margin-top:16px;">
      <el-button type="primary" :icon="Check" :loading="saving" @click="save">💾 保存配置</el-button>
      <el-button type="warning" :icon="Refresh" :loading="reloading" @click="reload">🔥 热重载引擎</el-button>
      <el-button :icon="Document" @click="loadAll">📄 重新加载</el-button>
      <span style="margin-left:16px; color:#9ca3af; font-size:12px;">
        💡 保存后点【热重载引擎】即可生效
      </span>
    </el-card>

    <!-- ============ 当前配置预览 ============ -->
    <el-card shadow="never" style="margin-top:16px;">
      <template #header><span style="font-weight:600;">📄 当前 .env（脱敏）</span></template>
      <pre class="env-pre">{{ JSON.stringify(currentConfig, null, 2) }}</pre>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Check, Refresh, Document } from "@element-plus/icons-vue";
import api from "../api";

const llm = ref({ base_url: "", model: "", api_key: "", masked_key: "" });
const emb = ref({ base_url: "", model: "", api_key: "", masked_key: "" });
const rag = ref({ chunk_size: 512, chunk_overlap: 64, top_k_retrieve: 20, top_k_rerank: 5 });
const currentConfig = ref({});
const saving = ref(false);
const reloading = ref(false);

const llmMode = computed(() => {
  const u = (llm.value.base_url || "").toLowerCase();
  return u.includes("11434") || u.includes("ollama") ? "ollama" : "openai";
});
const embMode = computed(() => {
  const u = (emb.value.base_url || "").toLowerCase();
  return u.includes("11434") || u.includes("ollama") ? "ollama" : "openai";
});

function fillLLM(url, model) {
  llm.value.base_url = url;
  llm.value.model = model;
}
function fillEmb(url, model) {
  emb.value.base_url = url;
  emb.value.model = model;
}

async function loadAll() {
  const r = await api.getConfig();
  const cfg = r.config || {};
  currentConfig.value = cfg;

  llm.value.base_url = cfg.LLM_BASE_URL || cfg.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
  llm.value.model = cfg.LLM_MODEL || cfg.OLLAMA_LLM_MODEL || "";
  llm.value.masked_key = cfg.LLM_API_KEY || "";
  llm.value.api_key = "";

  emb.value.base_url = cfg.EMBEDDING_BASE_URL || cfg.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
  emb.value.model = cfg.EMBEDDING_MODEL || cfg.OLLAMA_EMBEDDING_MODEL || "bge-m3:latest";
  emb.value.masked_key = cfg.EMBEDDING_API_KEY || "";
  emb.value.api_key = "";

  rag.value.chunk_size = parseInt(cfg.CHUNK_SIZE) || 512;
  rag.value.chunk_overlap = parseInt(cfg.CHUNK_OVERLAP) || 64;
  rag.value.top_k_retrieve = parseInt(cfg.TOP_K_RETRIEVE) || 20;
  rag.value.top_k_rerank = parseInt(cfg.TOP_K_RERANK) || 5;
}

async function save() {
  saving.value = true;
  try {
    const updates = {
      LLM_PROVIDER: llmMode.value === "ollama" ? "ollama_native" : "openai_compat",
      LLM_BASE_URL: llm.value.base_url,
      LLM_MODEL: llm.value.model,
      EMBEDDING_PROVIDER: embMode.value === "ollama" ? "ollama_native" : "openai_compat",
      EMBEDDING_BASE_URL: emb.value.base_url,
      EMBEDDING_MODEL: emb.value.model,
      CHUNK_SIZE: String(rag.value.chunk_size),
      CHUNK_OVERLAP: String(rag.value.chunk_overlap),
      TOP_K_RETRIEVE: String(rag.value.top_k_retrieve),
      TOP_K_RERANK: String(rag.value.top_k_rerank),
    };

    if (llmMode.value === "ollama") {
      updates.OLLAMA_BASE_URL = llm.value.base_url;
      updates.OLLAMA_LLM_MODEL = llm.value.model;
    }
    if (embMode.value === "ollama") {
      updates.OLLAMA_EMBEDDING_MODEL = emb.value.model;
    }
    if (llm.value.api_key) updates.LLM_API_KEY = llm.value.api_key;
    if (emb.value.api_key) updates.EMBEDDING_API_KEY = emb.value.api_key;

    const r = await api.saveConfig({ values: updates });
    ElMessage.success(`✅ 已保存 ${r.updated_keys?.length || 0} 项`);
    await loadAll();
  } finally {
    saving.value = false;
  }
}

async function reload() {
  reloading.value = true;
  try {
    const r = await api.reloadConfig();
    ElMessage.success("✅ " + (r.components || []).join(" / "));
  } finally {
    reloading.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
.presets { display: flex; flex-wrap: wrap; gap: 6px; }
.env-pre {
  background: #1f2937; color: #f3f4f6;
  padding: 16px; border-radius: 8px;
  font-size: 12px; max-height: 400px; overflow: auto;
}
</style>
