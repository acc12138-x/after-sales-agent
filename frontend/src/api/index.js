import axios from "axios";
import { ElMessage } from "element-plus";

const http = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

http.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || "请求失败";
    ElMessage.error(typeof msg === "string" ? msg : JSON.stringify(msg));
    return Promise.reject(err);
  }
);

export default {
  // ---------- 知识库 ----------
  getDocs: () => http.get("/knowledge/docs"),
  getDocDetail: (id) => http.get(`/knowledge/docs/${id}/detail`),
  deleteDoc: (id) => http.delete(`/knowledge/docs/${id}`),
  ingestText: (data) => http.post("/knowledge/ingest", data),
  ingestFile: (formData) => http.post("/knowledge/ingest-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  }),
  kbStats: () => http.get("/knowledge/stats"),

  // ---------- 对话 ----------
  chat: (data) => http.post("/chat", data),

  // ---------- 工单 ----------
  listTickets: (params) => http.get("/tickets", { params }),
  getTicket: (id) => http.get(`/tickets/${id}`),
  updateTicket: (id, data) => http.patch(`/tickets/${id}`, data),
  acceptTicket: (id) => http.post(`/tickets/${id}/accept`),
  rejectTicket: (id, data) => http.post(`/tickets/${id}/reject`, data),
  startTicket: (id) => http.post(`/tickets/${id}/start`),
  resolveTicket: (id, data) => http.post(`/tickets/${id}/resolve`, data),
  closeTicket: (id) => http.post(`/tickets/${id}/close`),
  ticketAudit: (id) => http.get(`/tickets/${id}/audit`),
  ticketNotifications: (id) => http.get(`/tickets/${id}/notifications`),

  // ---------- 工程师 ----------
  listEngineers: () => http.get("/engineers"),
  createEngineer: (data) => http.post("/engineers", data),
  updateEngineer: (id, data) => http.put(`/engineers/${id}`, data),
  deleteEngineer: (id) => http.delete(`/engineers/${id}`),
  toggleEngineer: (id) => http.post(`/engineers/${id}/toggle-status`),

  // ---------- 人员（users） ----------
  getUsersMeta: () => http.get("/users/meta"),
  listUsers: (params) => http.get("/users", { params }),
  getUser: (id) => http.get(`/users/${id}`),
  createUser: (data) => http.post("/users", data),
  updateUser: (id, data) => http.put(`/users/${id}`, data),
  deleteUser: (id) => http.delete(`/users/${id}`),
  toggleUserStatus: (id) => http.post(`/users/${id}/toggle-status`),
  getUserPermissions: (id) => http.get(`/users/${id}/permissions`),
  checkUserPermission: (id, perm) => http.post(`/users/${id}/check`, { perm }),

  // ---------- 审计/通知 ----------
  // ---------- SLA ----------
  getSlaSummary: () => http.get("/sla/summary"),
  getSlaRules: () => http.get("/sla/rules"),
  getSlaTickets: () => http.get("/sla/tickets"),
  scanSla: () => http.post("/sla/scan"),
  updateSlaRules: (data) => http.put("/sla/rules", data),

  listAudit: (params) => http.get("/logs/audit", { params }),
  listNotifications: (params) => http.get("/logs/notifications", { params }),
  auditStats: () => http.get("/logs/audit/stats"),
  notifStats: () => http.get("/logs/notifications/stats"),

  // ---------- 系统配置 ----------
  getConfig: () => http.get("/admin/config"),
  saveConfig: (data) => http.post("/admin/config", data),
  reloadConfig: () => http.post("/admin/reload"),
  providerTemplates: () => http.get("/admin/provider-templates"),
  dashboardStats: () => http.get("/admin/dashboard/stats"),
};
