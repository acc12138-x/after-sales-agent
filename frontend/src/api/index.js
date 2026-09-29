import axios from "axios";
import { ElMessage } from "element-plus";

const http = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers = config.headers || {};
      config.headers["Authorization"] = "Bearer " + token;
    }
    return config;
  },
  (err) => Promise.reject(err)
);

http.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const status = err.response && err.response.status;
    if (status === 401 && !location.hash.includes("/login")) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      location.hash = "#/login";
      ElMessage.error("登录已过期，请重新登录");
      return Promise.reject(err);
    }
    const msg = (err.response && err.response.data && err.response.data.detail) || err.message || "请求失败";
    ElMessage.error(typeof msg === "string" ? msg : JSON.stringify(msg));
    return Promise.reject(err);
  }
);

export default {
  login: (data) => http.post("/auth/login", data),
  me: () => http.get("/auth/me"),
  logout: () => http.post("/auth/logout"),
  changePassword: (data) => http.post("/auth/change-password", data),

  getDocs: () => http.get("/knowledge/docs"),
  getDocDetail: (id) => http.get("/knowledge/docs/" + id + "/detail"),
  deleteDoc: (id) => http.delete("/knowledge/docs/" + id),
  ingestText: (data) => http.post("/knowledge/ingest", data),
  ingestFile: (formData) => http.post("/knowledge/ingest-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  }),
  kbStats: () => http.get("/knowledge/stats"),

  chat: (data) => http.post("/chat", data),

  listTickets: (params) => http.get("/tickets", { params }),
  getTicket: (id) => http.get("/tickets/" + id),
  updateTicket: (id, data) => http.patch("/tickets/" + id, data),
  acceptTicket: (id) => http.post("/tickets/" + id + "/accept"),
  rejectTicket: (id, data) => http.post("/tickets/" + id + "/reject", data),
  startTicket: (id) => http.post("/tickets/" + id + "/start"),
  resolveTicket: (id, data) => http.post("/tickets/" + id + "/resolve", data),
  closeTicket: (id) => http.post("/tickets/" + id + "/close"),
  ticketAudit: (id) => http.get("/tickets/" + id + "/audit"),
  ticketNotifications: (id) => http.get("/tickets/" + id + "/notifications"),

  listEngineers: () => http.get("/engineers"),
  createEngineer: (data) => http.post("/engineers", data),
  updateEngineer: (id, data) => http.put("/engineers/" + id, data),
  deleteEngineer: (id) => http.delete("/engineers/" + id),
  toggleEngineer: (id) => http.post("/engineers/" + id + "/toggle-status"),

  getUsersMeta: () => http.get("/users/meta"),
  listUsers: (params) => http.get("/users", { params }),
  getUser: (id) => http.get("/users/" + id),
  createUser: (data) => http.post("/users", data),
  updateUser: (id, data) => http.put("/users/" + id, data),
  deleteUser: (id) => http.delete("/users/" + id),
  toggleUserStatus: (id) => http.post("/users/" + id + "/toggle-status"),
  getUserPermissions: (id) => http.get("/users/" + id + "/permissions"),
  checkUserPermission: (id, perm) => http.post("/users/" + id + "/check", { perm }),

  listAudit: (params) => http.get("/logs/audit", { params }),
  listNotifications: (params) => http.get("/logs/notifications", { params }),
  auditStats: () => http.get("/logs/audit/stats"),
  notifStats: () => http.get("/logs/notifications/stats"),

  getSlaSummary: () => http.get("/sla/summary"),
  getSlaRules: () => http.get("/sla/rules"),
  getSlaTickets: () => http.get("/sla/tickets"),
  scanSla: () => http.post("/sla/scan"),
  updateSlaRules: (data) => http.put("/sla/rules", data),

  getConfig: () => http.get("/admin/config"),
  saveConfig: (data) => http.post("/admin/config", data),
  reloadConfig: () => http.post("/admin/reload"),
  providerTemplates: () => http.get("/admin/provider-templates"),
  dashboardStats: () => http.get("/admin/dashboard/stats"),

  uploadCustomers: (formData) => http.post("/customers/import/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  }),
  confirmImportCustomers: (data) => http.post("/customers/import/confirm", data),
};
