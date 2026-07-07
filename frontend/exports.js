window.DataAnalystUI = window.DataAnalystUI || {};

window.DataAnalystUI.exports = (() => {
  const { csvCell, safeFilename } = window.DataAnalystUI.renderers;

  function downloadBlob(blob, filename) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  }

  async function downloadReportFile({ apiFetch, activeJobId, format, filename, setError }) {
    if (!activeJobId) {
      setError("请先完成一个分析任务，再导出报告。");
      return;
    }
    try {
      const response = await apiFetch(`/api/reports/${activeJobId}?format=${encodeURIComponent(format)}`);
      if (!response.ok) {
        const message = await window.DataAnalystUI.api.readErrorMessage(response);
        throw new Error(message || "报告导出失败。");
      }
      downloadBlob(await response.blob(), filename);
      setError("");
    } catch (error) {
      setError(error.message);
    }
  }

  function downloadChartCsv(spec) {
    const headers = [spec.x, spec.y].filter(Boolean);
    const lines = [headers.map(csvCell).join(",")];
    (spec.data || []).forEach((row) => {
      lines.push(headers.map((header) => csvCell(row[header])).join(","));
    });
    const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    downloadBlob(blob, `${safeFilename(spec.title || "图表数据")}.csv`);
  }

  function downloadChartSvg(card, spec) {
    const svg = card?.querySelector("svg");
    if (!svg) return false;
    const serialized = buildExportableSvg(svg);
    const blob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
    downloadBlob(blob, `${safeFilename(spec.title || "图表")}.svg`);
    return true;
  }

  function downloadChartPng(card, spec) {
    const svg = card?.querySelector("svg");
    if (!svg) return false;
    const bounds = getSvgExportBounds(svg);
    const serialized = buildExportableSvg(svg, bounds);
    const svgBlob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    const image = new Image();
    image.onload = () => {
      const scale = Math.max(2, window.devicePixelRatio || 1);
      const canvas = document.createElement("canvas");
      canvas.width = Math.ceil(bounds.width * scale);
      canvas.height = Math.ceil(bounds.height * scale);
      const context = canvas.getContext("2d");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => {
        if (blob) downloadBlob(blob, `${safeFilename(spec.title || "图表")}.png`);
      }, "image/png");
    };
    image.onerror = () => URL.revokeObjectURL(url);
    image.src = url;
    return true;
  }

  function buildExportableSvg(svg, bounds = getSvgExportBounds(svg)) {
    const clone = svg.cloneNode(true);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("viewBox", `${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`);
    clone.setAttribute("width", String(Math.ceil(bounds.width)));
    clone.setAttribute("height", String(Math.ceil(bounds.height)));
    clone.setAttribute("preserveAspectRatio", "xMinYMin meet");
    clone.insertBefore(buildSvgStyleElement(), clone.firstChild);
    return new XMLSerializer().serializeToString(clone);
  }

  function buildSvgStyleElement() {
    const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
    style.textContent = `
      .chart-label { fill: #334155; font: 12px Arial, sans-serif; }
      .chart-value { fill: #475569; font: 12px Arial, sans-serif; }
    `;
    return style;
  }

  function getSvgExportBounds(svg) {
    const fallback = getSvgViewBox(svg);
    try {
      const box = svg.getBBox();
      const minX = Math.min(fallback.x, box.x);
      const minY = Math.min(fallback.y, box.y);
      const maxX = Math.max(fallback.x + fallback.width, box.x + box.width);
      const maxY = Math.max(fallback.y + fallback.height, box.y + box.height);
      const padding = 32;
      return {
        x: Math.floor(minX - padding),
        y: Math.floor(minY - padding),
        width: Math.ceil(maxX - minX + padding * 2),
        height: Math.ceil(maxY - minY + padding * 2),
      };
    } catch (error) {
      const padding = 32;
      return {
        x: fallback.x - padding,
        y: fallback.y - padding,
        width: fallback.width + padding * 2,
        height: fallback.height + padding * 2,
      };
    }
  }

  function getSvgViewBox(svg) {
    const viewBox = svg.getAttribute("viewBox") || "0 0 960 540";
    const [x, y, width, height] = viewBox.split(/\s+/).map(Number);
    return {
      x: Number.isFinite(x) ? x : 0,
      y: Number.isFinite(y) ? y : 0,
      width: Number.isFinite(width) && width > 0 ? width : 960,
      height: Number.isFinite(height) && height > 0 ? height : 540,
    };
  }

  return { downloadBlob, downloadChartCsv, downloadChartPng, downloadChartSvg, downloadReportFile };
})();
