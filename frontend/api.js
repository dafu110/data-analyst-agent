window.DataAnalystUI = window.DataAnalystUI || {};

window.DataAnalystUI.api = (() => {
  function buildHeaders(getAccessSettings, extraHeaders = {}) {
    const settings = getAccessSettings();
    const headers = {
      "X-Actor": settings.actor || "local",
      "X-Org": settings.organization || "default",
      "X-Workspace": settings.workspace || "default",
      "X-Role": settings.role || "analyst",
      "X-Plan": settings.plan || "free",
      ...extraHeaders,
    };
    if (settings.apiToken) {
      headers.Authorization = `Bearer ${settings.apiToken}`;
      headers["X-API-Token"] = settings.apiToken;
    }
    return headers;
  }

  function createApiFetch(getAccessSettings) {
    return function apiFetch(url, options = {}) {
      return fetch(url, {
        ...options,
        headers: buildHeaders(getAccessSettings, options.headers || {}),
      });
    };
  }

  async function readJson(response) {
    const contentType = response.headers.get("Content-Type") || "";
    const text = await response.text();
    if (!contentType.includes("application/json")) {
      if (text.includes("<!DOCTYPE") || text.includes("<html")) {
        throw new Error("接口返回了页面而不是 JSON。请停止旧服务后重新启动，再刷新浏览器。");
      }
      throw new Error(text || "接口没有返回 JSON。");
    }
    try {
      return text ? JSON.parse(text) : {};
    } catch (error) {
      throw new Error("接口返回的 JSON 无法解析，请刷新页面后重试。");
    }
  }

  async function readErrorMessage(response) {
    const contentType = response.headers.get("Content-Type") || "";
    if (contentType.includes("application/json")) {
      try {
        const payload = await response.json();
        return payload.error || payload.detail || "";
      } catch (error) {
        return "";
      }
    }
    return (await response.text()) || "";
  }

  return { buildHeaders, createApiFetch, readErrorMessage, readJson };
})();
