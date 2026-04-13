export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://ai-voice-receptionist-36vr.onrender.com";

export async function api(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const getTenantSettings = (tid: string) => api(`/admin/settings/${tid}`);
export const updateTenantSettings = (tid: string, data: Record<string, unknown>) =>
  api(`/admin/settings/${tid}`, { method: "PATCH", body: JSON.stringify(data) });
export const getFaqs = (tid: string) => api(`/admin/faq/${tid}`);
export const createFaq = (tid: string, data: Record<string, unknown>) =>
  api(`/admin/faq/${tid}`, { method: "POST", body: JSON.stringify(data) });
export const updateFaq = (tid: string, id: number, data: Record<string, unknown>) =>
  api(`/admin/faq/${tid}/${id}`, { method: "PATCH", body: JSON.stringify(data) });
export const deleteFaq = (tid: string, id: number) =>
  api(`/admin/faq/${tid}/${id}`, { method: "DELETE" });
export const getCustomers = (tid: string) => api(`/admin/customers/${tid}`);
export const getCalls = (tid: string) => api(`/admin/calls/${tid}`);
export const getAnalytics = (tid: string) => api(`/admin/analytics/${tid}`);
export const getOAuthStatus = (tid: string) => api(`/oauth/status/${tid}`);
