window.DataAnalystUI = window.DataAnalystUI || {};

window.DataAnalystUI.charts = (() => {
  const { escapeHtml, formatNumber } = window.DataAnalystUI.renderers;
  const { downloadChartCsv, downloadChartPng, downloadChartSvg } = window.DataAnalystUI.exports;
  const state = { query: "", type: "auto", view: "recommended", specs: [] };

  function renderChartGrid(chartGrid, chartSpecs, setError) {
    state.specs = chartSpecs || [];
    ensureChartToolbar(chartGrid, setError);
    if (!state.specs.length) {
      chartGrid.innerHTML = `
        <section class="section-block chart-empty-state">
          <h3>暂无图表建议</h3>
          <p class="muted-copy">当前数据集暂未生成可视化摘要。可以补充日期、金额、分类字段，或在分析目标中明确趋势、分组、贡献等问题。</p>
        </section>
      `;
      updateVisibleCount(chartGrid);
      return;
    }
    chartGrid.innerHTML = state.specs.map((spec, index) => renderChart(spec, index)).join("");
    bindChartActions(chartGrid, setError);
    applyChartFilters(chartGrid);
  }

  function ensureChartToolbar(chartGrid, setError) {
    const host = chartGrid.parentElement;
    if (!host || document.querySelector("#chartInteractionToolbar")) return;
    const toolbar = document.createElement("div");
    toolbar.id = "chartInteractionToolbar";
    toolbar.className = "chart-interaction-toolbar";
    toolbar.innerHTML = `
      <div class="chart-view-switch" aria-label="Chart views">
        <button class="chart-view-chip active" type="button" data-chart-view="recommended">推荐图表</button>
        <button class="chart-view-chip" type="button" data-chart-view="all">全部图表</button>
        <button class="chart-view-chip" type="button" data-chart-view="review">需复核</button>
      </div>
      <label>
        <span>筛选图表</span>
        <input id="chartSearchInput" class="text-input compact-input" type="search" placeholder="标题 / 说明 / 字段">
      </label>
      <label>
        <span>图表类型</span>
        <select id="chartTypeSelect" class="text-input compact-input">
          <option value="auto">自动</option>
          <option value="bar">柱状</option>
          <option value="line">折线</option>
          <option value="range">范围</option>
          <option value="compact">紧凑</option>
        </select>
      </label>
      <button id="downloadAllChartsCsv" class="secondary-action" type="button">导出全部 CSV</button>
      <span id="chartVisibleCount" class="toolbar-counter">0 个图表</span>
    `;
    host.insertBefore(toolbar, chartGrid);
    toolbar.querySelectorAll("[data-chart-view]").forEach((button) => {
      button.addEventListener("click", () => {
        state.view = button.dataset.chartView || "recommended";
        toolbar.querySelectorAll("[data-chart-view]").forEach((item) => item.classList.toggle("active", item === button));
        applyChartFilters(chartGrid);
      });
    });
    toolbar.querySelector("#chartSearchInput")?.addEventListener("input", (event) => {
      state.query = event.target.value.trim().toLowerCase();
      applyChartFilters(chartGrid);
    });
    toolbar.querySelector("#chartTypeSelect")?.addEventListener("change", (event) => {
      state.type = event.target.value;
      applyChartFilters(chartGrid);
    });
    toolbar.querySelector("#downloadAllChartsCsv")?.addEventListener("click", () => {
      if (!state.specs.length) {
        setError("当前没有可导出的图表数据。");
        return;
      }
      state.specs.forEach(downloadChartCsv);
    });
  }

  function renderChart(spec, index = 0) {
    const rows = (spec.data || []).slice(0, 12);
    if (!rows.length) return "";
    const chartType = normalizeChartType(spec.chart_type);
    const width = 720;
    const rowHeight = 38;
    const labelWidth = 190;
    const height = chartType === "line" ? 310 : Math.max(170, rows.length * rowHeight + 44);
    const svgBody = chartType === "line"
      ? renderLineChart(rows, spec, width, height, labelWidth)
      : chartType === "range"
        ? renderRangeChart(rows, spec, width, rowHeight, labelWidth)
        : renderBarChart(rows, spec, width, rowHeight, labelWidth);
    const takeaway = buildChartTakeaway(rows, spec);
    const meta = `${rows.length} 条记录 · X: ${spec.x || "n/a"} · Y: ${spec.y || "n/a"}`;
    const stats = buildChartStats(rows, spec);
    const legend = buildChartLegend(chartType);

    return `
      <article class="chart-card" data-chart-index="${index}" data-chart-type="${escapeHtml(chartType)}" data-chart-priority="${escapeHtml(getChartPriority(spec, chartType))}">
        <div class="chart-card-header">
          <div>
            <span class="chart-kicker">${escapeHtml(translateChartType(spec.chart_type))}</span>
            <h3>${escapeHtml(spec.title)}</h3>
          </div>
          <span class="chart-meta">${escapeHtml(meta)}</span>
        </div>
        <div class="chart-actions">
          <button class="secondary-action" type="button" data-chart-download="png" data-chart-index="${index}">PNG</button>
          <button class="secondary-action" type="button" data-chart-download="svg" data-chart-index="${index}">SVG</button>
          <button class="secondary-action" type="button" data-chart-download="csv" data-chart-index="${index}">CSV</button>
          <button class="secondary-action" type="button" data-chart-focus data-chart-index="${index}">聚焦</button>
        </div>
        <p class="muted-copy">${escapeHtml(spec.description || "")}</p>
        <div class="chart-stat-strip">
          ${stats.map((item) => `<span class="chart-stat"><b>${escapeHtml(item.label)}</b>${escapeHtml(item.value)}</span>`).join("")}
        </div>
        <div class="chart-legend">
          ${legend.map((item) => `<span><i class="${escapeHtml(item.className)}"></i>${escapeHtml(item.label)}</span>`).join("")}
        </div>
        <div class="chart-scroll">
          <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(spec.title)}" xmlns="http://www.w3.org/2000/svg">
            ${svgBody}
          </svg>
        </div>
        <div class="chart-takeaway">
          <strong>${escapeHtml(takeaway.label)}</strong>
          <span>${escapeHtml(takeaway.detail)}</span>
        </div>
      </article>
    `;
  }

  function renderBarChart(rows, spec, width, rowHeight, labelWidth) {
    const values = rows.map((row) => Number(row[spec.y] || 0));
    const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1);
    const plotWidth = width - labelWidth - 86;
    const top = 26;
    const maxIndex = values.findIndex((value) => Math.abs(value) === maxAbs);
    const guideLines = [0.25, 0.5, 0.75, 1]
      .map((ratio) => {
        const x = labelWidth + ratio * plotWidth;
        return `<line x1="${x}" y1="14" x2="${x}" y2="${rows.length * rowHeight + 24}" class="chart-grid-line"></line>`;
      })
      .join("");

    return rows
      .map((row, index) => {
        const rawValue = Number(row[spec.y] || 0);
        const barWidth = Math.max(2, (Math.abs(rawValue) / maxAbs) * plotWidth);
        const x = labelWidth;
        const y = index * rowHeight + top;
        const fill = rawValue < 0 ? "var(--chart-negative)" : index === maxIndex ? "var(--chart-highlight)" : "var(--chart-primary)";
        const label = String(row[spec.x] ?? "").slice(0, 24);
        return `
          ${index === 0 ? guideLines : ""}
          <text x="0" y="${y + 16}" class="chart-label">${escapeHtml(label)}</text>
          <rect x="${x}" y="${y}" width="${barWidth}" height="20" rx="5" fill="${fill}" class="chart-bar">
            <title>${escapeHtml(`${row[spec.x] ?? ""}: ${formatNumber(rawValue)}`)}</title>
          </rect>
          <text x="${Math.min(x + barWidth + 10, width - 62)}" y="${y + 15}" class="chart-value">${escapeHtml(formatNumber(rawValue))}</text>
          ${index === rows.length - 1 ? `<text x="${labelWidth}" y="${rows.length * rowHeight + 38}" class="chart-axis-label">${escapeHtml(spec.y || "value")}</text>` : ""}
        `;
      })
      .join("");
  }

  function renderRangeChart(rows, spec, width, rowHeight, labelWidth) {
    const rangeRows = rows.map((row) => ({
      label: row[spec.x],
      min: Number(row.min ?? row[spec.y] ?? 0),
      mean: Number(row.mean ?? row[spec.y] ?? 0),
      max: Number(row.max ?? row[spec.y] ?? 0),
    }));
    const values = rangeRows.flatMap((row) => [row.min, row.mean, row.max]);
    const minValue = Math.min(...values, 0);
    const maxValue = Math.max(...values, 1);
    const plotWidth = width - labelWidth - 86;
    const top = 30;
    const scale = (value) => labelWidth + ((value - minValue) / Math.max(maxValue - minValue, 1)) * plotWidth;
    const guideLines = [0, 0.5, 1]
      .map((ratio) => {
        const x = labelWidth + ratio * plotWidth;
        const value = minValue + ratio * (maxValue - minValue);
        return `
          <line x1="${x}" y1="14" x2="${x}" y2="${rows.length * rowHeight + 24}" class="chart-grid-line"></line>
          <text x="${x}" y="11" class="chart-axis-label" text-anchor="middle">${escapeHtml(formatNumber(value))}</text>
        `;
      })
      .join("");
    return rangeRows
      .map((row, index) => {
        const y = index * rowHeight + top;
        const x1 = scale(row.min);
        const x2 = scale(row.max);
        const meanX = scale(row.mean);
        return `
          ${index === 0 ? guideLines : ""}
          <text x="0" y="${y + 16}" class="chart-label">${escapeHtml(String(row.label ?? "").slice(0, 24))}</text>
          <line x1="${x1}" y1="${y + 10}" x2="${x2}" y2="${y + 10}" class="range-line">
            <title>${escapeHtml(`${row.label}: min ${formatNumber(row.min)}, mean ${formatNumber(row.mean)}, max ${formatNumber(row.max)}`)}</title>
          </line>
          <circle cx="${x1}" cy="${y + 10}" r="4" class="range-end"></circle>
          <circle cx="${x2}" cy="${y + 10}" r="4" class="range-end"></circle>
          <circle cx="${meanX}" cy="${y + 10}" r="6" class="range-point"></circle>
          <text x="${Math.min(meanX + 10, width - 62)}" y="${y + 15}" class="chart-value">${escapeHtml(formatNumber(row.mean))}</text>
          ${index === rows.length - 1 ? `<text x="${labelWidth}" y="${rows.length * rowHeight + 38}" class="chart-axis-label">${escapeHtml(spec.y || "value")}</text>` : ""}
        `;
      })
      .join("");
  }

  function renderLineChart(rows, spec, width, height, labelWidth) {
    const values = rows.map((row) => Number(row[spec.y] || 0));
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 1);
    const plotWidth = width - labelWidth - 56;
    const plotHeight = height - 82;
    const top = 34;
    const baselineY = top + ((max - 0) / Math.max(max - min, 1)) * plotHeight;
    const points = rows.map((row, index) => {
      const x = labelWidth + (rows.length === 1 ? 0 : (index / (rows.length - 1)) * plotWidth);
      const y = top + ((max - Number(row[spec.y] || 0)) / Math.max(max - min, 1)) * plotHeight;
      return { x, y, label: row[spec.x], value: Number(row[spec.y] || 0) };
    });
    const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
    const areaPath = `${path} L ${points.at(-1).x} ${top + plotHeight} L ${points[0].x} ${top + plotHeight} Z`;
    const guides = [0, 0.5, 1]
      .map((ratio) => {
        const y = top + ratio * plotHeight;
        return `<line x1="${labelWidth}" y1="${y}" x2="${labelWidth + plotWidth}" y2="${y}" class="chart-grid-line"></line>`;
      })
      .join("");

    return `
      ${guides}
      <line x1="${labelWidth}" y1="${baselineY}" x2="${labelWidth + plotWidth}" y2="${baselineY}" class="chart-baseline"></line>
      <path d="${areaPath}" class="chart-line-area"></path>
      <path d="${path}" fill="none" class="chart-line-path"></path>
      ${points
        .map(
          (point, index) => `
            <circle cx="${point.x}" cy="${point.y}" r="${index === points.length - 1 ? 5 : 3}" class="chart-point">
              <title>${escapeHtml(`${point.label}: ${formatNumber(point.value)}`)}</title>
            </circle>
            <text x="${point.x}" y="${height - 18}" class="chart-label" text-anchor="middle">${escapeHtml(String(point.label).slice(0, 8))}</text>
            ${index === points.length - 1 ? `<text x="${Math.min(point.x + 10, width - 70)}" y="${point.y - 10}" class="chart-value">${escapeHtml(formatNumber(point.value))}</text>` : ""}
          `
        )
        .join("")}
    `;
  }

  function bindChartActions(chartGrid, setError) {
    chartGrid.querySelectorAll("[data-chart-download]").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.chartIndex || 0);
        const spec = state.specs[index];
        const card = chartGrid.querySelector(`[data-chart-index="${index}"]`);
        if (!spec) return;
        if (button.dataset.chartDownload === "svg" && !downloadChartSvg(card, spec)) setError("没有找到可导出的 SVG 图表。");
        if (button.dataset.chartDownload === "png" && !downloadChartPng(card, spec)) setError("没有找到可导出的 PNG 图表。");
        if (button.dataset.chartDownload === "csv") downloadChartCsv(spec);
      });
    });
    chartGrid.querySelectorAll("[data-chart-focus]").forEach((button) => {
      button.addEventListener("click", () => {
        const card = chartGrid.querySelector(`[data-chart-index="${button.dataset.chartIndex}"]`);
        card?.classList.toggle("chart-card-focus");
        card?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });
  }

  function applyChartFilters(chartGrid) {
    const cards = Array.from(chartGrid.querySelectorAll(".chart-card"));
    cards.forEach((card) => {
      const matchesQuery = !state.query || card.textContent.toLowerCase().includes(state.query);
      const matchesType = state.type === "auto" || state.type === "compact" || card.dataset.chartType === state.type;
      const matchesView =
        state.view === "all" ||
        (state.view === "recommended" && card.dataset.chartPriority !== "review") ||
        (state.view === "review" && card.dataset.chartPriority === "review");
      card.classList.toggle("hidden", !(matchesQuery && matchesType && matchesView));
      card.classList.toggle("chart-card-compact", state.type === "compact");
    });
    updateVisibleCount(chartGrid);
  }

  function updateVisibleCount(chartGrid) {
    const counter = document.querySelector("#chartVisibleCount");
    if (!counter) return;
    const cards = Array.from(chartGrid.querySelectorAll(".chart-card"));
    const visible = cards.filter((card) => !card.classList.contains("hidden")).length;
    counter.textContent = `${visible} / ${cards.length} 个图表`;
  }

  function normalizeChartType(type) {
    if (type === "line") return "line";
    if (type === "range") return "range";
    return "bar";
  }

  function getChartPriority(spec, chartType) {
    const text = `${spec.title || ""} ${spec.description || ""} ${spec.y || ""}`.toLowerCase();
    if (chartType === "range" || text.includes("correlation") || text.includes("相关") || text.includes("波动")) return "review";
    const rows = spec.data || [];
    if (rows.some((row) => Number(row[spec.y] || row.mean || 0) < 0)) return "review";
    return "recommended";
  }

  function translateChartType(type) {
    const labels = { bar: "柱状图", line: "折线图", range: "范围图" };
    return labels[type] || type || "图表";
  }

  function buildChartStats(rows, spec) {
    const values = rows.map((row) => Number(row[spec.y] || row.mean || 0)).filter((value) => Number.isFinite(value));
    if (!values.length) return [{ label: "记录", value: String(rows.length) }];
    const total = values.reduce((sum, value) => sum + value, 0);
    const mean = total / values.length;
    return [
      { label: "记录", value: String(rows.length) },
      { label: "均值", value: formatNumber(mean) },
      { label: "最高", value: formatNumber(Math.max(...values)) },
      { label: "最低", value: formatNumber(Math.min(...values)) },
    ];
  }

  function buildChartLegend(chartType) {
    if (chartType === "line") {
      return [
        { label: "趋势线", className: "legend-primary" },
        { label: "末值高亮", className: "legend-highlight" },
      ];
    }
    if (chartType === "range") {
      return [
        { label: "最小-最大", className: "legend-range" },
        { label: "均值", className: "legend-highlight" },
      ];
    }
    return [
      { label: "普通值", className: "legend-primary" },
      { label: "最高贡献", className: "legend-highlight" },
      { label: "负值", className: "legend-negative" },
    ];
  }

  function buildChartTakeaway(rows, spec) {
    const values = rows.map((row) => Number(row[spec.y] || 0));
    if (!values.length) return { label: "可视化摘要", detail: "暂无可计算的数值摘要。" };
    const max = Math.max(...values);
    const min = Math.min(...values);
    const maxRow = rows[values.indexOf(max)] || {};
    const minRow = rows[values.indexOf(min)] || {};
    const delta = values.length > 1 ? values.at(-1) - values[0] : 0;
    if (normalizeChartType(spec.chart_type) === "line") {
      return {
        label: delta >= 0 ? "趋势上行" : "趋势下行",
        detail: `首尾变化 ${formatNumber(delta)}，最高点 ${maxRow[spec.x] ?? "n/a"} 为 ${formatNumber(max)}。`,
      };
    }
    return {
      label: "最高贡献",
      detail: `${maxRow[spec.x] ?? "n/a"} 最高，为 ${formatNumber(max)}；最低 ${minRow[spec.x] ?? "n/a"} 为 ${formatNumber(min)}。`,
    };
  }

  return { renderChart, renderChartGrid };
})();
