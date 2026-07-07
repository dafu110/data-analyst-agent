window.DataAnalystUI = window.DataAnalystUI || {};

window.DataAnalystUI.renderers = (() => {
  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function clearElement(element) {
    if (!element) return;
    while (element.firstChild) {
      element.removeChild(element.firstChild);
    }
  }

  function appendTextElement(parent, tagName, text, className) {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    element.textContent = text ?? "";
    parent.appendChild(element);
    return element;
  }

  function metric(label, value) {
    return `
      <article class="metric">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(String(value))}</strong>
      </article>
    `;
  }

  function csvCell(value) {
    const text = String(value ?? "");
    return `"${text.replaceAll('"', '""')}"`;
  }

  function safeFilename(value) {
    return String(value || "download").replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);
  }

  function formatNumber(value) {
    const number = Number(value || 0);
    return Number.isInteger(number) ? String(number) : number.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }

  return {
    appendTextElement,
    clearElement,
    csvCell,
    escapeHtml,
    formatNumber,
    metric,
    safeFilename,
  };
})();
