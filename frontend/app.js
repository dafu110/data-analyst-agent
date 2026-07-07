const {
  form,
  appShell,
  workspace,
  actorInput,
  organizationInput,
  roleInput,
  workspaceInput,
  apiTokenInput,
  fileInput,
  fileName,
  goalInput,
  dataDictionaryInput,
  reportAudience,
  deliveryFormat,
  dataPreview,
  previewMeta,
  fieldMappingList,
  applyFieldMapping,
  clearFieldMapping,
  previewTable,
  submitButton,
  statusBadge,
  taskTitle,
  emptyState,
  errorState,
  agentStateTitle,
  agentStateDetail,
  currentActionLabel,
  currentActionDetail,
  nextActionLabel,
  stagePills,
  metricGrid,
  executiveSummaryBlock,
  executiveConfidence,
  executiveSummaryContent,
  qualityGateBlock,
  qualityGateList,
  qualityGateCount,
  qualityList,
  qualityCount,
  columnList,
  columnCount,
  planList,
  traceList,
  jobTimeline,
  chartGrid,
  reportHistory,
  jobList,
  refreshJobs,
  followupForm,
  followupQuestion,
  followupAnswer,
  suggestedQuestions,
  followupJobLabel,
  opsMetricGrid,
  refreshMetrics,
  statusBreakdown,
  statusTotal,
  currentJob,
  jobIdLabel,
  jobSummary,
  insightBlock,
  insightList,
  insightCount,
  semanticBlock,
  semanticList,
  semanticCount,
  questionBlock,
  questionList,
  questionCount,
  actionBlock,
  actionList,
  actionCount,
  metricDefinitionBlock,
  metricDefinitionList,
  metricDefinitionCount,
  toolResults,
  reportText,
  copyReport,
  downloadReport,
  downloadHtmlReport,
  downloadCsvReport,
  downloadPdfReport,
  downloadPptReport,
  cancelJob,
  goalTemplateButtons,
  sourceModeButtons,
  sourceHint,
  fieldConfidenceSummary,
  recoveryPanel,
  retryWithCurrentSettings,
  clearErrorAction,
  trustScoreLabel,
  exportPresetButtons,
  jobSearchInput,
  jobStatusFilter,
  agentReasoningList,
  agentNextStepTitle,
  agentNextStepDetail,
  interventionCard,
  interventionTitle,
  interventionDetail,
  reviewPlanShortcut,
  askDetailShortcut,
  cancelFromState,
  agentActivityBlock,
  agentActivityList,
  agentActivityCount,
  humanReviewBlock,
  humanReviewList,
  humanReviewStatus,
  useExampleData,
  emptyUseExampleData,
  planApprovalBlock,
  planApprovalStatus,
  planApprovalSummary,
  approvePlanAction,
  editGoalAction,
  cancelPlanAction,
  decisionBriefBlock,
  decisionBriefGrid,
  decisionBriefStatus,
  exportReadinessLabel,
  exportCheckList,
} = window.DataAnalystUI.elements;

const runtime = window.DataAnalystUI.runtime;

function setWorkspaceMode(mode, enabled = true) {
  const modes = ["has-dataset", "has-plan", "has-result", "is-running", "is-failed"];
  if (!mode) {
    modes.forEach((item) => {
      appShell?.classList.remove(item);
      workspace?.classList.remove(item);
      document.body.classList.remove(item);
    });
    return;
  }
  [appShell, workspace, document.body].forEach((target) => target?.classList.toggle(mode, enabled));
}

const statusLabels = {
  idle: "空闲",
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  done: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

actorInput.value = localStorage.getItem("daa.actor") || actorInput.value || "local";
organizationInput.value = localStorage.getItem("daa.organization") || organizationInput.value || "default";
roleInput.value = localStorage.getItem("daa.role") || roleInput.value || "analyst";
workspaceInput.value = localStorage.getItem("daa.workspace") || workspaceInput.value || "default";
apiTokenInput.value = "";
localStorage.removeItem("daa.apiToken");
actorInput.addEventListener("change", persistAccessSettings);
organizationInput.addEventListener("change", persistAccessSettings);
roleInput.addEventListener("change", persistAccessSettings);
workspaceInput.addEventListener("change", persistAccessSettings);

goalTemplateButtons.forEach((button) => {
  button.addEventListener("click", () => {
    goalInput.value = button.dataset.goalTemplate || goalInput.value;
    goalInput.focus();
  });
});

sourceModeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    sourceModeButtons.forEach((item) => item.classList.toggle("active", item === button));
    updateSourceHint(button.dataset.sourceMode || "file");
  });
});

useExampleData?.addEventListener("click", loadExampleDataset);
emptyUseExampleData?.addEventListener("click", loadExampleDataset);

exportPresetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    applyExportPreset(button.dataset.exportPreset || "business");
  });
});

retryWithCurrentSettings?.addEventListener("click", () => {
  if (submitButton.disabled) return;
  form.requestSubmit();
});

clearErrorAction?.addEventListener("click", () => setError(""));

reviewPlanShortcut?.addEventListener("click", () => activateTab("plan"));
askDetailShortcut?.addEventListener("click", () => {
  if (!runtime.latestResult) {
    followupQuestion.value = "你会先检查哪些字段口径和质量风险？";
  }
  activateTab("followup");
  followupQuestion?.focus();
});
cancelFromState?.addEventListener("click", () => cancelJob?.click());
approvePlanAction?.addEventListener("click", () => {
  runtime.planApproved = true;
  planApprovalStatus.textContent = "已批准";
  form.requestSubmit();
});
editGoalAction?.addEventListener("click", () => {
  goalInput.focus();
  goalInput.scrollIntoView({ behavior: "smooth", block: "center" });
});
cancelPlanAction?.addEventListener("click", () => {
  runtime.pendingPlanPayload = null;
  runtime.planApproved = false;
  planApprovalBlock?.classList.add("hidden");
  setStatus("idle", "空闲");
});

jobSearchInput?.addEventListener("input", filterJobRows);
jobStatusFilter?.addEventListener("change", filterJobRows);

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileName.textContent = file?.name || "閫夋嫨鎴栨嫋鍏?CSV / Excel";
  setWorkspaceMode("has-dataset", Boolean(file));
  setWorkspaceMode("has-plan", false);
  setWorkspaceMode("has-result", false);
  setWorkspaceMode("is-failed", false);
  renderLocalPreview(file);
  updateFieldConfidenceSummary(file);
  runtime.planApproved = false;
  runtime.pendingPlanPayload = null;
  planApprovalBlock?.classList.add("hidden");
});

applyFieldMapping.addEventListener("click", applyDetectedFieldMapping);
clearFieldMapping.addEventListener("click", () => {
  dataDictionaryInput.value = "";
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    activateTab(tab.dataset.tab);
    if (tab.dataset.tab === "jobs") loadJobs();
    if (tab.dataset.tab === "ops") loadMetrics();
  });
});

refreshJobs.addEventListener("click", loadJobs);
refreshMetrics.addEventListener("click", loadMetrics);
followupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await askFollowup(followupQuestion.value);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  persistAccessSettings();
  const payload = new FormData(form);
  payload.delete("actor");
  payload.delete("apiToken");
  if (!runtime.planApproved) {
    runtime.pendingPlanPayload = payload;
    showPlanApproval(payload);
    return;
  }
  runtime.pendingPlanPayload = payload;
  await submitAnalysisPayload(payload);
});

async function submitAnalysisPayload(payload) {
  resetResultPanels();
  setWorkspaceMode("has-plan", false);
  setWorkspaceMode("is-running", true);
  planApprovalBlock?.classList.add("hidden");
  setStatus("running", "运行中");
  setError("");
  submitButton.disabled = true;

  try {
    const response = await apiFetch("/api/analyze", {
      method: "POST",
      body: payload,
    });
    const job = await readJson(response);
    if (!response.ok || job.error) {
      throw new Error(job.error || "分析失败。");
    }
    runtime.activeJobId = job.id;
    renderJob(job);
    pollJob(job.id);
  } catch (error) {
    setStatus("failed", "失败");
    setError(error.message);
    submitButton.disabled = false;
  } finally {
    runtime.planApproved = false;
  }
}

copyReport.addEventListener("click", async () => {
  if (!runtime.latestReport) return;
  await navigator.clipboard.writeText(runtime.latestReport);
  copyReport.textContent = "已复制";
  setTimeout(() => {
    copyReport.textContent = "复制";
  }, 1200);
});

downloadReport.addEventListener("click", () => {
  if (!runtime.latestReport) return;
  const blob = new Blob([runtime.latestReport], { type: "text/markdown;charset=utf-8" });
  downloadBlob(blob, "数据分析报告.md");
});

downloadHtmlReport.addEventListener("click", async () => {
  await downloadReportFile("html", "数据分析报告.html");
});

downloadCsvReport.addEventListener("click", async () => {
  await downloadReportFile("csv", "数据分析摘要.csv");
});

downloadPdfReport.addEventListener("click", async () => {
  await downloadReportFile("pdf", "数据分析报告.pdf");
});

downloadPptReport.addEventListener("click", async () => {
  await downloadReportFile("pptx", "数据分析报告.pptx");
});

cancelJob.addEventListener("click", async () => {
  if (!runtime.activeJobId) return;
  const response = await apiFetch(`/api/jobs/${runtime.activeJobId}`, { method: "DELETE" });
  const job = await readJson(response);
  if (!response.ok) {
    setError(job.error || "无法取消任务。");
    return;
  }
  renderJob(job);
  setStatus("failed", "已取消");
  submitButton.disabled = false;
});

async function pollJob(jobId) {
  clearTimeout(runtime.pollTimer);
  try {
    const response = await apiFetch(`/api/jobs/${jobId}`);
    const job = await readJson(response);
    if (!response.ok) {
      throw new Error(job.error || "无法读取任务状态。");
    }
    renderJob(job);

    if (job.status === "completed") {
      renderResult(job.result);
      setStatus("done", "已完成");
      submitButton.disabled = false;
      loadJobs();
      loadMetrics();
      return;
    }

    if (job.status === "failed" || job.status === "cancelled") {
      setStatus("failed", statusLabels[job.status]);
      setError(job.error || (job.status === "cancelled" ? "任务已取消。" : "分析失败。"));
      submitButton.disabled = false;
      return;
    }

    runtime.pollTimer = setTimeout(() => pollJob(jobId), 900);
  } catch (error) {
    setStatus("failed", "失败");
    setError(error.message);
    submitButton.disabled = false;
  }
}

async function loadJobs() {
  try {
    const response = await apiFetch("/api/jobs?limit=20");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "无法读取任务列表。");
    renderJobs(data.jobs || []);
  } catch (error) {
    jobList.innerHTML = `<section class="section-block"><p class="muted-copy">${escapeHtml(error.message)}</p></section>`;
  }
}

async function loadMetrics() {
  try {
    const response = await apiFetch("/api/metrics");
    const data = await readJson(response);
    if (!response.ok) throw new Error(data.error || "无法读取运行指标。");
    renderMetrics(data);
  } catch (error) {
    opsMetricGrid.innerHTML = metric("指标状态", "读取失败");
    statusBreakdown.innerHTML = `<p class="muted-copy">${escapeHtml(error.message)}</p>`;
  }
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === name);
  });
}

async function loadExampleDataset() {
  try {
    setError("");
    const response = await apiFetch("/api/examples/sales.csv");
    if (!response.ok) throw new Error("示例数据读取失败。");
    const blob = await response.blob();
    const file = new File([blob], "sales.csv", { type: "text/csv" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    goalInput.value = "用示例销售数据找出销售额、订单数、客单价的变化趋势，检查数据质量问题，并给出下一步业务建议。";
    goalInput.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    setError(error.message);
  }
}

function showPlanApproval(payload) {
  const file = fileInput.files[0];
  if (!file) {
    setError("请先选择 CSV / Excel 文件。");
    return;
  }
  setError("");
  setWorkspaceMode("has-dataset", true);
  setWorkspaceMode("has-plan", true);
  setWorkspaceMode("has-result", false);
  setWorkspaceMode("is-running", false);
  emptyState.classList.add("hidden");
  planApprovalBlock?.classList.remove("hidden");
  if (planApprovalStatus) planApprovalStatus.textContent = "绛夊緟鎵瑰噯";
  const goal = String(payload.get("goal") || goalInput.value || "").trim();
  const dictionary = parseDictionaryValue(String(payload.get("data_dictionary") || ""));
  const plannedSteps = buildPlannedSteps(goal, dictionary, file);
  planApprovalSummary.innerHTML = plannedSteps
    .map(
      (item) => `
        <article class="plan-card ${escapeHtml(item.kind || "")}">
          <span>${escapeHtml(item.kicker)}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.detail)}</p>
        </article>
      `
    )
    .join("");
  taskTitle.textContent = "等待计划确认";
  planList.innerHTML = plannedSteps
    .filter((item) => item.step)
    .map(
      (item, index) => `
        <li>
          <strong>${index + 1}. ${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.detail)}</p>
          <span class="tool-pill">${escapeHtml(item.tool || "agent")}</span>
        </li>
      `
    )
    .join("");
  renderTransparencyState({
    reasoning: [
      `已准备分析 ${file.name}，目标是：${goal || "通用数据分析"}。`,
      "批准后会读取数据、生成画像、执行分析步骤，并标记低置信度内容。",
    ],
    nextTitle: "等待你批准计划",
    nextDetail: "你可以先查看计划、编辑目标，或取消后重新选择数据。",
    interventionTitle: "现在需要你确认",
    interventionDetail: "确认目标和文件无误后点击批准执行；如果目标不对，先编辑目标。",
    interventionClass: "needs-review",
  });
  activateTab("overview");
}

function buildPlannedSteps(goal, dictionary, file) {
  const dictionaryCount = Object.keys(dictionary || {}).length;
  return [
    {
      kicker: "杈撳叆",
      title: file.name,
      detail: `${formatBytes(file.size)}，批准后上传到后端分析。`,
      kind: "input",
    },
    {
      kicker: "璁″垝",
      title: "数据画像与质量门禁",
      detail: "检查字段类型、缺失、重复、异常值、常量字段和口径风险。",
      tool: "profiler",
      step: true,
    },
    {
      kicker: "璁″垝",
      title: "涓氬姟瀛楁璇嗗埆",
      detail: dictionaryCount
        ? `使用 ${dictionaryCount} 条字段字典，并结合列名与样本识别日期、收入、渠道等角色。`
        : "根据列名和样本自动识别日期、收入、渠道、客户等角色。",
      tool: "semantics",
      step: true,
    },
    {
      kicker: "璁″垝",
      title: "洞察与图表生成",
      detail: "按目标生成指标、分组、趋势、贡献和图表建议。",
      tool: "sql/python",
      step: true,
    },
    {
      kicker: "浜や粯",
      title: "鎶ュ憡涓庡鏍哥偣",
      detail: "生成业务报告和导出文件，并标记低置信度结论和需要人工确认的项目。",
      tool: "reporter",
      step: true,
    },
  ];
}

function renderJob(job) {
  setWorkspaceMode("has-dataset", true);
  setWorkspaceMode("is-running", ["queued", "running"].includes(job.status));
  setWorkspaceMode("is-failed", ["failed", "cancelled"].includes(job.status));
  emptyState.classList.add("hidden");
  currentJob.classList.remove("hidden");
  cancelJob.classList.toggle("hidden", !["queued", "running"].includes(job.status));
  cancelFromState?.classList.toggle("hidden", !["queued", "running"].includes(job.status));
  taskTitle.textContent = job.filename || "鍒嗘瀽浠诲姟";
  jobIdLabel.textContent = shortJobId(job.id);
  jobSummary.textContent = `${statusLabels[job.status] || job.status} - ${job.goal}`;
  setStatus(job.status === "failed" ? "failed" : job.status === "completed" ? "done" : "running", statusLabels[job.status] || job.status);
  renderAgentActivity(job.events || []);
  jobTimeline.replaceChildren(...(job.events || []).map(renderJobEventNode));
}

function renderJobs(jobs) {
  if (!jobs.length) {
    reportHistory.replaceChildren();
    jobList.replaceChildren(createEmptySection("当前用户还没有分析任务。"));
    return;
  }
  const completed = jobs.filter((job) => job.status === "completed").slice(0, 4);
  reportHistory.innerHTML = completed.length
    ? `
      <section class="section-block">
        <div class="section-heading">
          <h3>鎶ュ憡鍘嗗彶</h3>
          <span>${completed.length}</span>
        </div>
        <div class="history-grid">
          ${completed.map((job) => renderHistoryCard(job)).join("")}
        </div>
      </section>
    `
    : "";
  jobList.replaceChildren(...jobs.map(renderJobRowNode));
  jobList.querySelectorAll(".job-row").forEach((row) => {
    row.addEventListener("click", () => openJob(row.dataset.jobId));
  });
  reportHistory.querySelectorAll("[data-history-action]").forEach((button) => {
    button.addEventListener("click", () => handleHistoryAction(button));
  });
  filterJobRows();
}

function filterJobRows() {
  const query = (jobSearchInput?.value || "").trim().toLowerCase();
  const status = jobStatusFilter?.value || "all";
  jobList.querySelectorAll(".job-row").forEach((row) => {
    const text = row.textContent.toLowerCase();
    const rowStatus = row.querySelector("b")?.className || "";
    const matchesQuery = !query || text.includes(query);
    const matchesStatus = status === "all" || rowStatus.includes(status);
    row.classList.toggle("hidden", !(matchesQuery && matchesStatus));
  });
}

async function openJob(jobId) {
  if (!jobId) return;
  try {
    const response = await apiFetch(`/api/jobs/${jobId}`);
    const job = await readJson(response);
    if (!response.ok) throw new Error(job.error || "无法读取任务。");
    runtime.activeJobId = job.id;
    renderJob(job);
    if (job.status === "completed" && job.result) {
      renderResult(job.result);
    }
    activateTab(job.status === "completed" ? "overview" : "timeline");
  } catch (error) {
    setError(error.message);
  }
}

function renderMetrics(data) {
  const capacity = `${data.active_jobs || 0}/${data.max_concurrent_jobs || 0}`;
  opsMetricGrid.innerHTML = [
    metric("总任务", data.total_jobs || 0),
    metric("运行容量", capacity),
    metric("已完成", data.completed_jobs || 0),
    metric("失败", data.failed_jobs || 0),
    metric("平均耗时", `${Math.round(data.avg_duration_ms || 0)} ms`),
    metric("P95 耗时", `${Math.round(data.p95_duration_ms || 0)} ms`),
    metric("报告数", data.generated_reports || 0),
    metric("环境", data.env || "local"),
  ].join("");

  const entries = Object.entries(data.by_status || {});
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0);
  statusTotal.textContent = String(total);
  statusBreakdown.innerHTML = entries
    .map(([status, value]) => {
      const percent = total ? Math.round((Number(value) / total) * 100) : 0;
      return `
        <div class="status-row">
          <span>${escapeHtml(statusLabels[status] || status)}</span>
          <div><i style="width:${percent}%"></i></div>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
      `;
    })
    .join("");
}

function updateSourceHint(mode) {
  if (!sourceHint) return;
  const hints = {
    file: "上传 CSV / Excel 后可继续确认字段口径。",
    database: "数据库连接会进入连接器配置；当前版本可先导出 CSV 后上传。",
    sheet: "在线表格连接会保留刷新来源；当前版本可先下载为 Excel。",
    api: "API 数据源会用于定时分析；当前版本可先保存为 CSV。",
  };
  sourceHint.textContent = hints[mode] || hints.file;
}

function applyExportPreset(preset) {
  const presets = {
    executive: { audience: "executive", format: "executive_brief", goal: "面向管理层总结关键变化、风险和下一步决策建议。" },
    client: { audience: "client", format: "business_report", goal: "生成适合客户汇报的业务报告，突出结论、证据和建议。" },
    diagnostic: { audience: "operator", format: "diagnostic", goal: "输出数据质量、指标口径和执行动作的诊断清单。" },
  };
  const selected = presets[preset];
  if (!selected) return;
  reportAudience.value = selected.audience;
  deliveryFormat.value = selected.format;
  goalInput.value = selected.goal;
  activateTab("report");
}

function updateFieldConfidenceSummary(file) {
  if (!fieldConfidenceSummary) return;
  if (!file) {
    fieldConfidenceSummary.innerHTML = `
      <strong>瀛楁鍙ｅ緞纭</strong>
      <p>上传后会根据列名和样本值推测日期、收入、渠道、客户等业务角色；低置信度字段建议手动确认。</p>
    `;
    return;
  }
  fieldConfidenceSummary.innerHTML = `
    <strong>字段口径确认</strong>
    <p>已读取 ${escapeHtml(file.name)}。请重点确认日期、金额、客户、渠道、地区等字段；无法确认的字段可在字段字典中补充。</p>
  `;
}

function renderResult(data) {
  setWorkspaceMode("has-dataset", true);
  setWorkspaceMode("has-plan", false);
  setWorkspaceMode("has-result", true);
  setWorkspaceMode("is-running", false);
  setWorkspaceMode("is-failed", false);
  runtime.latestResult = data;
  const profile = data.profile;
  runtime.latestReport = data.report_markdown || "";
  emptyState.classList.add("hidden");
  taskTitle.textContent = data.source_filename || "分析完成";

  metricGrid.innerHTML = [
    metric("行数", profile.rows),
    metric("字段数", profile.columns),
    metric("质量评分", `${Math.round((profile.quality_score || 0) * 100)}%`),
    metric("分析意图", data.analysis_intent?.label || "通用探索"),
    metric("步骤数", data.plan.steps.length),
  ].join("");
  if (trustScoreLabel) {
    const confidence = data.executive_summary?.confidence ?? profile.quality_score ?? 0;
    trustScoreLabel.textContent = `${Math.round(Number(confidence || 0) * 100)}%`;
  }
  renderResultTransparency(data);
  renderHumanReview(data);
  renderDecisionBrief(data);
  renderExportReadiness(data);

  renderExecutiveSummary(data.executive_summary);
  renderQualityGates(data.quality_gates || []);

  const insights = data.insights || [];
  insightBlock.classList.toggle("hidden", !insights.length);
  insightCount.textContent = insights.length;
  insightList.innerHTML = insights
    .map(
      (insight) => `
        <article class="insight-item ${escapeHtml(insight.severity || "info")}">
          <strong>${escapeHtml(insight.title)} <span>${escapeHtml(translateInsightType(insight.insight_type))} · ${Math.round((insight.confidence || 0) * 100)}%</span></strong>
          <p>${escapeHtml(insight.detail)}</p>
          ${renderInsightEvidence(insight)}
        </article>
      `
    )
    .join("");

  const semanticRoles = data.semantic_roles || [];
  semanticBlock.classList.toggle("hidden", !semanticRoles.length);
  semanticCount.textContent = semanticRoles.length;
  semanticList.innerHTML = semanticRoles
    .map((role) => `<span class="chip">${escapeHtml(translateRole(role.role))} · ${escapeHtml(role.column)} · ${Math.round((role.confidence || 0) * 100)}%</span>`)
    .join("");

  const warnings = profile.warnings.length ? profile.warnings : ["未发现明显重复行、缺失值或常量字段问题。"];
  qualityCount.textContent = warnings.length;
  qualityList.replaceChildren(
    createListItem(`质量评分：${Math.round((profile.quality_score || 0) * 100)}%`),
    ...Object.entries(profile.quality_dimensions || {}).map(([key, value]) => createListItem(`${translateQualityDimension(key)}：${Math.round(Number(value) * 100)}%`)),
    ...warnings.map((item) => createListItem(translateQualityText(item)))
  );

  const recommendedQuestions = data.suggested_questions || [];
  questionBlock.classList.toggle("hidden", !recommendedQuestions.length);
  questionCount.textContent = recommendedQuestions.length;
  questionList.replaceChildren(...recommendedQuestions.map(createSuggestionButton));
  questionList.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      followupQuestion.value = button.textContent;
      activateTab("followup");
    });
  });

  const actionItems = data.action_items || [];
  actionBlock.classList.toggle("hidden", !actionItems.length);
  actionCount.textContent = actionItems.length;
  actionList.innerHTML = actionItems.map(renderActionItem).join("");

  const metricDefinitions = data.metric_definitions || [];
  metricDefinitionBlock.classList.toggle("hidden", !metricDefinitions.length);
  metricDefinitionCount.textContent = metricDefinitions.length;
  metricDefinitionList.innerHTML = metricDefinitions.map(renderMetricDefinition).join("");

  columnCount.textContent = profile.column_names.length;
  columnList.replaceChildren(...profile.column_names.map((column) => createChip(`${column} · ${profile.dtypes[column] || "unknown"}`)));

  planList.replaceChildren(...data.plan.steps.map(renderPlanStepNode));
  traceList.replaceChildren(...(data.trace_spans || []).map(renderTraceSpanNode));
  toolResults.replaceChildren(...data.tool_results.map(renderToolResultNode));

  chartGrid.innerHTML = (data.chart_specs || []).length
    ? data.chart_specs.map((spec, index) => renderChart(spec, index)).join("")
    : `<section class="section-block"><h3>暂无图表建议</h3><p class="muted-copy">当前数据集暂未生成可视化摘要。</p></section>`;
  bindChartDownloads(data.chart_specs || []);
  if (window.DataAnalystUI?.charts?.renderChartGrid) {
    window.DataAnalystUI.charts.renderChartGrid(chartGrid, data.chart_specs || [], setError);
  }

  reportText.textContent = runtime.latestReport;
  renderFollowupSuggestions(data);
  activateTab("overview");
}

function resetResultPanels() {
  clearTimeout(runtime.pollTimer);
  setWorkspaceMode("has-result", false);
  setWorkspaceMode("is-running", false);
  setWorkspaceMode("is-failed", false);
  runtime.latestReport = "";
  runtime.latestResult = null;
  runtime.activeJobId = null;
  metricGrid.innerHTML = "";
  executiveSummaryBlock.classList.add("hidden");
  executiveSummaryContent.innerHTML = "";
  executiveConfidence.textContent = "0%";
  qualityGateBlock.classList.add("hidden");
  qualityGateList.innerHTML = "";
  qualityGateCount.textContent = "0";
  qualityList.innerHTML = "";
  qualityCount.textContent = "0";
  columnList.innerHTML = "";
  columnCount.textContent = "0";
  planList.innerHTML = "";
  traceList.innerHTML = "";
  jobTimeline.innerHTML = "";
  chartGrid.innerHTML = "";
  toolResults.innerHTML = "";
  reportText.textContent = "";
  renderAgentActivity([]);
  renderHumanReview(null);
  renderDecisionBrief(null);
  renderExportReadiness(null);
  planApprovalBlock?.classList.add("hidden");
  currentJob.classList.add("hidden");
  insightBlock.classList.add("hidden");
  insightList.innerHTML = "";
  insightCount.textContent = "0";
  semanticBlock.classList.add("hidden");
  semanticList.innerHTML = "";
  semanticCount.textContent = "0";
  questionBlock.classList.add("hidden");
  questionList.innerHTML = "";
  questionCount.textContent = "0";
  actionBlock.classList.add("hidden");
  actionList.innerHTML = "";
  actionCount.textContent = "0";
  metricDefinitionBlock.classList.add("hidden");
  metricDefinitionList.innerHTML = "";
  metricDefinitionCount.textContent = "0";
  cancelJob.classList.add("hidden");
  followupJobLabel.textContent = "未选择任务";
  followupAnswer.textContent = "选择一个已完成任务后，可以围绕报告继续追问。";
  suggestedQuestions.innerHTML = "";
}

function renderLocalPreview(file) {
  runtime.currentPreview = null;
  dataPreview.classList.add("hidden");
  previewMeta.textContent = "未读取";
  fieldMappingList.innerHTML = "";
  previewTable.innerHTML = "";

  if (!file) return;

  dataPreview.classList.remove("hidden");
  const lowerName = file.name.toLowerCase();
  const isCsv = lowerName.endsWith(".csv") || file.type.includes("csv");

  if (!isCsv) {
    previewMeta.textContent = "Excel 文件将在后端解析";
    previewTable.innerHTML = `<p class="muted-copy">当前浏览器预览仅支持 CSV。可以直接提交 Excel，后端会读取多 sheet 并进行分析。</p>`;
    return;
  }

  previewMeta.textContent = "正在读取预览...";
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = parseCsvPreview(String(reader.result || ""));
      if (!parsed.headers.length) {
        previewMeta.textContent = "未识别到字段";
        previewTable.innerHTML = `<p class="muted-copy">没有读取到可预览的 CSV 表头，请确认文件编码和分隔符。</p>`;
        return;
      }
      runtime.currentPreview = parsed;
      previewMeta.textContent = `${parsed.headers.length} 个字段，预览 ${parsed.rows.length} 行`;
      renderFieldMappingsSafe(parsed);
      renderPreviewTableSafe(parsed);
    } catch (error) {
      previewMeta.textContent = "读取失败";
      previewTable.innerHTML = `<p class="muted-copy">${escapeHtml(error.message)}</p>`;
    }
  };
  reader.onerror = () => {
    previewMeta.textContent = "读取失败";
    previewTable.innerHTML = `<p class="muted-copy">浏览器无法读取该文件，请重新选择后再试。</p>`;
  };
  reader.readAsText(file.slice(0, 512 * 1024), "utf-8");
}

function parseCsvPreview(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      cell += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      row.push(cell.trim());
      cell = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell.trim());
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      cell = "";
      if (rows.length >= 21) break;
      continue;
    }
    cell += char;
  }

  if (rows.length < 21 && (cell || row.length)) {
    row.push(cell.trim());
    if (row.some((value) => value !== "")) rows.push(row);
  }

  const headers = (rows[0] || []).map((header, index) => header || `字段${index + 1}`);
  return {
    headers,
    rows: rows.slice(1, 21).map((item) => headers.map((_, index) => item[index] || "")),
  };
}

function renderFieldMappingsSafe(parsed) {
  clearElement(fieldMappingList);
  parsed.headers.forEach((header, index) => {
    const samples = parsed.rows.map((row) => row[index]).filter(Boolean);
    const detected = detectFieldRole(header, samples);
    const sampleText = samples.slice(0, 3).join(" / ") || "no sample";
    const row = document.createElement("label");
    row.className = "field-mapping-row";
    const text = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = header;
    const sample = document.createElement("small");
    sample.textContent = sampleText;
    const select = document.createElement("select");
    select.dataset.column = header;
    buildFieldRoleOptions(detected).forEach((option) => select.appendChild(option));
    text.append(title, sample);
    row.append(text, select);
    fieldMappingList.appendChild(row);
  });
}

function buildFieldRoleOptions(selectedRole) {
  return fieldRoleChoices().map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    option.selected = value === selectedRole;
    return option;
  });
}

function fieldRoleChoices() {
  return [
    ["", "unspecified"],
    ["date", "date"],
    ["region", "region"],
    ["product", "product"],
    ["channel", "channel"],
    ["customer", "customer"],
    ["order", "order"],
    ["revenue", "revenue"],
    ["profit", "profit"],
    ["cost", "cost"],
    ["units", "units"],
    ["discount", "discount"],
    ["price", "price"],
  ];
}

function renderPreviewTableSafe(parsed) {
  const visibleHeaders = parsed.headers.slice(0, 8);
  const visibleRows = parsed.rows.slice(0, 20);
  clearElement(previewTable);
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  visibleHeaders.forEach((header) => {
    const cell = document.createElement("th");
    cell.textContent = header;
    headerRow.appendChild(cell);
  });
  thead.appendChild(headerRow);
  const tbody = document.createElement("tbody");
  visibleRows.forEach((row) => {
    const tableRow = document.createElement("tr");
    visibleHeaders.forEach((_, index) => {
      const cell = document.createElement("td");
      cell.textContent = row[index] || "";
      tableRow.appendChild(cell);
    });
    tbody.appendChild(tableRow);
  });
  table.append(thead, tbody);
  previewTable.appendChild(table);
}

function renderFieldMappings(parsed) {
  fieldMappingList.innerHTML = parsed.headers
    .map((header, index) => {
      const samples = parsed.rows.map((row) => row[index]).filter(Boolean);
      const detected = detectFieldRole(header, samples);
      const sampleText = samples.slice(0, 3).join(" / ") || "无样例";
      return `
        <label class="field-mapping-row">
          <span>
            <strong>${escapeHtml(header)}</strong>
            <small>${escapeHtml(sampleText)}</small>
          </span>
          <select data-column="${escapeHtml(header)}">
            ${fieldRoleOptions(detected)}
          </select>
        </label>
      `;
    })
    .join("");
}

function fieldRoleOptions(selectedRole) {
  const roles = [
    ["", "不指定"],
    ["date", "日期 date"],
    ["region", "地区 region"],
    ["product", "产品 product"],
    ["channel", "渠道 channel"],
    ["customer", "客户 customer"],
    ["order", "订单 order"],
    ["revenue", "收入 revenue"],
    ["profit", "利润 profit"],
    ["cost", "成本 cost"],
    ["units", "销量 units"],
    ["discount", "折扣 discount"],
    ["price", "价格 price"],
  ];
  return roles
    .map(([value, label]) => `<option value="${value}" ${value === selectedRole ? "selected" : ""}>${label}</option>`)
    .join("");
}

function detectFieldRole(header, samples) {
  const name = String(header || "").toLowerCase();
  const compact = name.replaceAll("_", "").replaceAll("-", "").replaceAll(" ", "");
  const text = `${name} ${compact}`;
  const numericRatio = samples.length ? samples.filter(isNumericValue).length / samples.length : 0;
  const dateRatio = samples.length ? samples.filter(isDateLikeValue).length / samples.length : 0;

  if (dateRatio >= 0.6 || /date|time|day|month|鏃ユ湡|鏃堕棿|鏈堜唤|缁熻鍛ㄦ湡/.test(text)) return "date";
  if (/region|province|city|area|鍦板尯|鍖哄煙|鐪亅鍩庡競/.test(text)) return "region";
  if (/product|sku|item|鍟嗗搧|浜у搧|鍝佺被/.test(text)) return "product";
  if (/channel|source|platform|娓犻亾|鏉ユ簮|骞冲彴/.test(text)) return "channel";
  if (/customer|client|member|user|瀹㈡埛|鐢ㄦ埛|浼氬憳/.test(text)) return "customer";
  if (/order|trade|transaction|璁㈠崟|浜ゆ槗/.test(text)) return "order";
  if (/revenue|sales|amount|gmv|鏀跺叆|閿€鍞|鎴愪氦棰潀閲戦|娴佹按/.test(text) && numericRatio >= 0.4) return "revenue";
  if (/profit|margin|鍒╂鼎|姣涘埄/.test(text) && numericRatio >= 0.4) return "profit";
  if (/cost|expense|鎴愭湰|璐圭敤/.test(text) && numericRatio >= 0.4) return "cost";
  if (/unit|qty|quantity|volume|count|閿€閲弢鏁伴噺|浠舵暟/.test(text) && numericRatio >= 0.4) return "units";
  if (/discount|coupon|鎶樻墸|浼樻儬/.test(text) && numericRatio >= 0.4) return "discount";
  if (/price|单价|价格|客单价/.test(text) && numericRatio >= 0.4) return "price";
  return "";
}

function renderPreviewTable(parsed) {
  const visibleHeaders = parsed.headers.slice(0, 8);
  const visibleRows = parsed.rows.slice(0, 20);
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  visibleHeaders.forEach((header) => {
    const cell = document.createElement("th");
    cell.textContent = header;
    headRow.append(cell);
  });
  thead.append(headRow);

  const tbody = document.createElement("tbody");
  visibleRows.forEach((row) => {
    const bodyRow = document.createElement("tr");
    visibleHeaders.forEach((_, index) => {
      const cell = document.createElement("td");
      cell.textContent = row[index] || "";
      bodyRow.append(cell);
    });
    tbody.append(bodyRow);
  });
  table.append(thead, tbody);
  previewTable.replaceChildren(table);
}

function applyDetectedFieldMapping() {
  const mapping = parseDictionaryValue(dataDictionaryInput.value);
  fieldMappingList.querySelectorAll("select[data-column]").forEach((select) => {
    if (select.value) {
      mapping[select.dataset.column] = select.value;
    } else {
      delete mapping[select.dataset.column];
    }
  });
  dataDictionaryInput.value = JSON.stringify(mapping, null, 2);
}

function parseDictionaryValue(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) return {};
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (error) {
    return {};
  }
}

function isNumericValue(value) {
  const normalized = String(value || "").replaceAll(",", "").replace("%", "").trim();
  return normalized !== "" && Number.isFinite(Number(normalized));
}

function isDateLikeValue(value) {
  const text = String(value || "").trim();
  if (!text) return false;
  return /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?$/.test(text) || /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$/.test(text);
}

async function askFollowup(question) {
  const cleanQuestion = (question || "").trim();
  if (!runtime.activeJobId || !runtime.latestResult) {
    followupAnswer.textContent = "请先打开一个已完成任务，再进行追问。";
    activateTab("followup");
    return;
  }
  if (!cleanQuestion) {
    followupAnswer.textContent = "请输入追问内容。";
    return;
  }
  followupAnswer.textContent = "正在基于当前报告生成回答...";
  try {
    const response = await apiFetch(`/api/jobs/${runtime.activeJobId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: cleanQuestion }),
    });
    const payload = await readJson(response);
    if (!response.ok) throw new Error(payload.error || payload.detail || "追问失败。");
    renderFollowupAnswer(payload);
    renderSuggestedQuestions(payload.suggested_questions || []);
    activateTab("followup");
  } catch (error) {
    followupAnswer.textContent = error.message;
  }
}

function renderFollowupAnswer(payload) {
  const article = document.createElement("article");
  article.className = "answer-card";

  const question = document.createElement("strong");
  question.textContent = payload.question || "";
  article.append(question);

  const answer = document.createElement("p");
  String(payload.answer || "")
    .split("\n")
    .forEach((line, index) => {
      if (index) answer.append(document.createElement("br"));
      answer.append(document.createTextNode(line));
    });
  article.append(answer);

  const evidence = document.createElement("div");
  evidence.className = "insight-evidence";
  evidence.append(createChip(`置信度 ${Math.round((payload.confidence || 0) * 100)}%`));
  if (payload.needs_review) evidence.append(createChip("建议人工复核"));
  (payload.citations || []).forEach((item) => evidence.append(createChip(item)));
  article.append(evidence);

  const actions = payload.followup_actions || [];
  if (actions.length) {
    const actionList = document.createElement("div");
    actionList.className = "followup-actions";
    actions.forEach((action) => actionList.append(createFollowupActionButton(action)));
    article.append(actionList);
  }

  followupAnswer.replaceChildren(article);
  bindFollowupGoalButtons();
}

function createChip(value) {
  const chip = document.createElement("span");
  chip.className = "chip";
  chip.textContent = value;
  return chip;
}

function createListItem(value) {
  const item = document.createElement("li");
  item.textContent = value;
  return item;
}

function createSuggestionButton(value) {
  const button = document.createElement("button");
  button.className = "suggestion-chip";
  button.type = "button";
  button.textContent = value;
  return button;
}

function renderPlanStepNode(step, index) {
  const item = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = `${index + 1}. ${step.title}`;
  const objective = document.createElement("p");
  objective.textContent = step.objective;
  const tool = document.createElement("span");
  tool.className = "tool-pill";
  tool.textContent = step.tool;
  item.append(title, objective, tool);
  return item;
}

function renderTraceSpanNode(span) {
  const item = document.createElement("li");
  item.className = `timeline-row ${safeClassName(span.status || "")}`;
  const label = document.createElement("strong");
  label.textContent = span.label;
  const detail = document.createElement("p");
  detail.textContent = `${span.step_id} 路 ${span.tool || "n/a"} 路 ${span.duration_ms || 0} ms`;
  const status = document.createElement("span");
  status.className = "tool-pill";
  status.textContent = span.status;
  item.append(label, detail, status);
  return item;
}

function renderJobEventNode(event) {
  const item = document.createElement("li");
  item.className = `timeline-row ${safeClassName(event.status || "")}`;
  const label = document.createElement("strong");
  label.textContent = translateEventLabel(event.label);
  const detail = document.createElement("p");
  detail.textContent = translateEventDetail(event.detail || "");
  const time = document.createElement("span");
  time.className = "tool-pill";
  time.textContent = formatTime(event.timestamp);
  item.append(label, detail, time);
  return item;
}

function renderJobRowNode(job) {
  const row = document.createElement("button");
  row.className = "job-row";
  row.type = "button";
  row.dataset.jobId = job.id || "";

  const titleBlock = document.createElement("span");
  const filename = document.createElement("strong");
  filename.textContent = job.filename || "鍒嗘瀽浠诲姟";
  const goal = document.createElement("small");
  goal.textContent = job.goal || "";
  titleBlock.append(filename, goal);

  const meta = document.createElement("span");
  meta.className = "job-row-meta";
  const status = document.createElement("b");
  status.className = safeClassName(job.status || "");
  status.textContent = statusLabels[job.status] || job.status || "unknown";
  const updated = document.createElement("small");
  updated.textContent = formatDateTime(job.updated_at);
  meta.append(status, updated);

  row.append(titleBlock, meta);
  return row;
}

function createEmptySection(message) {
  const section = document.createElement("section");
  section.className = "section-block";
  const copy = document.createElement("p");
  copy.className = "muted-copy";
  copy.textContent = message;
  section.append(copy);
  return section;
}

function renderToolResultNode(result) {
  const card = document.createElement("article");
  card.className = "tool-card";
  const title = document.createElement("strong");
  title.textContent = result.title;
  const step = document.createElement("p");
  step.textContent = `步骤 ID：${result.step_id}`;
  const output = document.createElement("pre");
  output.textContent = JSON.stringify(result.output, null, 2);
  card.append(title, step, output);
  return card;
}

function safeClassName(value) {
  return String(value).replace(/[^a-z0-9_-]/gi, "");
}

function createFollowupActionButton(action) {
  const wrapper = document.createElement("div");
  wrapper.className = "followup-action";

  const title = document.createElement("strong");
  title.textContent = action.title || "可继续分析";
  wrapper.append(title);

  const detail = document.createElement("p");
  detail.textContent = action.detail || "";
  wrapper.append(detail);

  if (!action.suggested_goal) return wrapper;

  const button = document.createElement("button");
  button.className = "secondary-action followup-use-goal";
  button.type = "button";
  button.dataset.suggestedGoal = action.suggested_goal;
  button.textContent = "使用这个目标";
  const goal = document.createElement("small");
  goal.textContent = action.suggested_goal;
  wrapper.append(button, goal);
  return wrapper;
}

function renderExecutiveSummary(summary) {
  executiveSummaryBlock.classList.toggle("hidden", !summary);
  if (!summary) {
    executiveSummaryContent.innerHTML = "";
    executiveConfidence.textContent = "0%";
    return;
  }
  executiveConfidence.textContent = `${Math.round((summary.confidence || 0) * 100)}%`;
  executiveSummaryContent.innerHTML = `
    <article class="summary-card">
      <strong>${escapeHtml(summary.headline || "已生成管理层摘要")}</strong>
      <p>${escapeHtml(summary.current_state || "")}</p>
      <div class="summary-grid">
        ${renderSummaryColumn("核心发现", summary.key_takeaways || [])}
        ${renderSummaryColumn("主要风险", summary.business_risks || [])}
        ${renderSummaryColumn("建议聚焦", summary.recommended_focus || [])}
      </div>
    </article>
  `;
}

function renderSummaryColumn(title, items) {
  return `
    <div>
      <b>${escapeHtml(title)}</b>
      <ul>${(items || []).slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderQualityGates(gates) {
  qualityGateBlock.classList.toggle("hidden", !gates.length);
  qualityGateCount.textContent = gates.length;
  qualityGateList.innerHTML = (gates || []).map(renderQualityGate).join("");
}

function renderQualityGate(gate) {
  return `
    <article class="quality-gate ${escapeHtml(gate.status || "review")}">
      <strong>${escapeHtml(gate.name || "质量门禁")} <span>${escapeHtml(gate.status || "review")} / ${escapeHtml(gate.severity || "medium")}</span></strong>
      <p>${escapeHtml(gate.detail || "")}</p>
    </article>
  `;
}

function renderDecisionBrief(data) {
  decisionBriefBlock?.classList.toggle("hidden", !data);
  if (!data || !decisionBriefGrid) {
    if (decisionBriefGrid) decisionBriefGrid.innerHTML = "";
    if (decisionBriefStatus) decisionBriefStatus.textContent = "待生成";
    return;
  }
  const reviewItems = buildHumanReviewItems(data);
  const topInsight = (data.insights || [])[0];
  const topAction = (data.action_items || [])[0];
  const quality = Math.round(Number(data.profile?.quality_score || 0) * 100);
  if (decisionBriefStatus) decisionBriefStatus.textContent = reviewItems.length ? `${reviewItems.length} 个复核点` : "可继续导出";
  const cards = [
    {
      kicker: "最重要结论",
      title: topInsight?.title || data.executive_summary?.headline || "已生成分析结果",
      detail: topInsight?.detail || data.executive_summary?.current_state || "请查看关键结论、图表和报告正文。",
      action: "看关键结论",
      target: "overview",
    },
    {
      kicker: "需要复核",
      title: reviewItems[0]?.title || `璐ㄩ噺璇勫垎 ${quality}%`,
      detail: reviewItems[0]?.detail || "当前没有明显阻塞点，导出前建议抽查关键指标口径。",
      action: reviewItems.length ? "处理复核点" : "查看口径",
      target: "overview",
    },
    {
      kicker: "下一步行动",
      title: topAction?.title || "导出报告或继续追问",
      detail: topAction?.detail || "可以切换老板版、客户版或诊断版报告，也可以围绕结果继续追问。",
      action: topAction ? "看行动项" : "去导出",
      target: topAction ? "overview" : "report",
    },
  ];
  decisionBriefGrid.innerHTML = cards
    .map(
      (card) => `
        <article class="decision-card">
          <span>${escapeHtml(card.kicker)}</span>
          <strong>${escapeHtml(card.title)}</strong>
          <p>${escapeHtml(card.detail)}</p>
          <button class="secondary-action" type="button" data-brief-target="${escapeHtml(card.target)}">${escapeHtml(card.action)}</button>
        </article>
      `
    )
    .join("");
  decisionBriefGrid.querySelectorAll("[data-brief-target]").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.briefTarget || "overview"));
  });
}

function renderExportReadiness(data) {
  if (!exportCheckList || !exportReadinessLabel) return;
  if (!data) {
    exportReadinessLabel.textContent = "未生成报告";
    exportCheckList.innerHTML = `
      <article class="export-check-item pending"><strong>等待报告</strong><p>完成一次分析后，这里会提示报告完整度和未复核项。</p></article>
    `;
    return;
  }
  const reviewItems = buildHumanReviewItems(data);
  const reportReady = Boolean(data.report_markdown);
  const chartCount = (data.chart_specs || []).length;
  const exportLabel = reportReady ? (reviewItems.length ? "建议先复核" : "可以导出") : "报告未就绪";
  exportReadinessLabel.textContent = exportLabel;
  const items = [
    {
      status: reportReady ? "ok" : "pending",
      title: reportReady ? "报告已生成" : "报告未生成",
      detail: reportReady ? "Markdown 报告已准备好，可继续导出 HTML / PDF / PPT。" : "请先完成分析任务。",
    },
    {
      status: reviewItems.length ? "review" : "ok",
      title: reviewItems.length ? `${reviewItems.length} 个未复核项` : "无强复核阻塞",
      detail: reviewItems.length ? "建议先处理总览中的复核点，再对外发送报告。" : "仍建议抽查关键指标口径。",
    },
    {
      status: chartCount ? "ok" : "pending",
      title: chartCount ? `${chartCount} 个图表可用` : "暂无图表",
      detail: chartCount ? "图表页可单独导出 SVG / CSV。" : "当前数据没有生成可视化摘要，报告仍可导出。",
    },
  ];
  exportCheckList.innerHTML = items
    .map(
      (item) => `
        <article class="export-check-item ${escapeHtml(item.status)}">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.detail)}</p>
        </article>
      `
    )
    .join("");
}

function bindFollowupGoalButtons() {
  followupAnswer.querySelectorAll("[data-suggested-goal]").forEach((button) => {
    button.addEventListener("click", () => {
      goalInput.value = button.dataset.suggestedGoal || "";
      goalInput.focus();
      goalInput.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

function renderActionItem(item) {
  const evidence = (item.evidence || []).slice(0, 3).map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("");
  return `
    <article class="action-item ${escapeHtml(item.priority || "medium")}">
      <strong>${escapeHtml(item.title || "行动项")} <span>${escapeHtml(item.priority || "medium")}</span></strong>
      <p>${escapeHtml(item.detail || "")}</p>
      ${item.next_step ? `<small>下一步：${escapeHtml(item.next_step)}</small>` : ""}
      ${evidence ? `<div class="insight-evidence">${evidence}</div>` : ""}
    </article>
  `;
}

function renderMetricDefinition(item) {
  const status = item.available ? "可计算" : "需补充字段";
  const columns = (item.columns || []).map((column) => `<span class="chip">${escapeHtml(column)}</span>`).join("");
  return `
    <article class="definition-item ${item.available ? "available" : "missing"}">
      <strong>${escapeHtml(item.name || "指标")} <span>${status}</span></strong>
      <code>${escapeHtml(item.formula || "")}</code>
      <p>${escapeHtml(item.reason || "")}</p>
      ${columns ? `<div class="insight-evidence">${columns}</div>` : ""}
    </article>
  `;
}

function renderFollowupAction(action) {
  return `
    <div class="followup-action">
      <strong>${escapeHtml(action.title || "可继续分析")}</strong>
      <p>${escapeHtml(action.detail || "")}</p>
      ${action.suggested_goal ? `<small>${escapeHtml(action.suggested_goal)}</small>` : ""}
    </div>
  `;
}

function renderFollowupActionWithGoal(action) {
  const suggestedGoal = action.suggested_goal || "";
  const goalAction = suggestedGoal
    ? `<button class="secondary-action followup-use-goal" type="button" data-suggested-goal="${escapeHtml(suggestedGoal)}">使用这个目标</button><small>${escapeHtml(suggestedGoal)}</small>`
    : "";
  return `
    <div class="followup-action">
      <strong>${escapeHtml(action.title || "可继续分析")}</strong>
      <p>${escapeHtml(action.detail || "")}</p>
      ${goalAction}
    </div>
  `;
}

function renderFollowupSuggestions(data) {
  followupJobLabel.textContent = runtime.activeJobId ? shortJobId(runtime.activeJobId) : "未选择任务";
  renderSuggestedQuestions(buildSuggestedQuestions(data));
}

function buildSuggestedQuestions(data) {
  if (data?.suggested_questions?.length) {
    return data.suggested_questions.slice(0, 5);
  }
  const questions = [
    "这份数据最值得关注的 3 个结论是什么？",
    "数据质量有什么风险，是否需要人工复核？",
    "下一步应该优先做哪些业务动作？",
  ];
  if (data?.time_series?.length) questions.splice(1, 0, "核心指标的趋势是增长还是下降？");
  if (data?.semantic_roles?.length) questions.push("哪些字段被识别成了关键业务指标？");
  return questions.slice(0, 5);
}

function renderSuggestedQuestions(questions) {
  clearElement(suggestedQuestions);
  (questions || []).forEach((question) => {
    const button = document.createElement("button");
    button.className = "suggestion-chip";
    button.type = "button";
    button.textContent = question;
    suggestedQuestions.appendChild(button);
    button.addEventListener("click", () => {
      followupQuestion.value = button.textContent;
      askFollowup(button.textContent);
    });
  });
}

function renderHistoryCard(job) {
  return `
    <article class="history-card">
      <strong>${escapeHtml(job.filename || "分析报告")}</strong>
      <span>${escapeHtml(formatDateTime(job.updated_at))}</span>
      <p>${escapeHtml(job.goal || "")}</p>
      <small>${escapeHtml(shortJobId(job.id))}</small>
      <div class="history-actions">
        <button class="secondary-action" type="button" data-history-action="open" data-job-id="${escapeHtml(job.id)}">打开</button>
        <button class="secondary-action" type="button" data-history-action="reuse" data-job-goal="${escapeHtml(job.goal || "")}">复制目标</button>
        <button class="secondary-action" type="button" data-history-action="ask" data-job-id="${escapeHtml(job.id)}">继续追问</button>
        <button class="secondary-action" type="button" data-history-action="export" data-job-id="${escapeHtml(job.id)}">导出</button>
      </div>
    </article>
  `;
}

function handleHistoryAction(button) {
  const action = button.dataset.historyAction;
  if (action === "reuse") {
    goalInput.value = button.dataset.jobGoal || goalInput.value;
    goalInput.focus();
    goalInput.scrollIntoView({ behavior: "smooth", block: "center" });
    return;
  }
  if (action === "ask") {
    openJob(button.dataset.jobId).then(() => activateTab("followup"));
    return;
  }
  if (action === "export") {
    openJob(button.dataset.jobId).then(() => activateTab("report"));
    return;
  }
  openJob(button.dataset.jobId);
}

function persistAccessSettings() {
  localStorage.setItem("daa.actor", actorInput.value.trim() || "local");
  localStorage.setItem("daa.organization", organizationInput.value.trim() || "default");
  localStorage.setItem("daa.role", roleInput.value.trim() || "analyst");
  localStorage.setItem("daa.workspace", workspaceInput.value.trim() || "default");
  localStorage.removeItem("daa.apiToken");
}

function requestHeaders() {
  const headers = {
    "X-Actor": actorInput.value.trim() || "local",
    "X-Org": organizationInput.value.trim() || "default",
    "X-Workspace": workspaceInput.value.trim() || "default",
    "X-Role": roleInput.value.trim() || "analyst",
  };
  const token = apiTokenInput.value.trim();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    headers["X-API-Token"] = token;
  }
  return headers;
}

function apiFetch(url, options = {}) {
  if (window.DataAnalystUI?.api?.createApiFetch) {
    const delegatedFetch = window.DataAnalystUI.api.createApiFetch(() => ({
      actor: actorInput.value.trim() || "local",
      organization: organizationInput.value.trim() || "default",
      workspace: workspaceInput.value.trim() || "default",
      role: roleInput.value.trim() || "analyst",
      apiToken: apiTokenInput.value.trim(),
    }));
    return delegatedFetch(url, options);
  }
  return fetch(url, {
    ...options,
    headers: {
      ...requestHeaders(),
      ...(options.headers || {}),
    },
  });
}

async function downloadReportFile(format, filename) {
  if (!runtime.activeJobId) {
    setError("请先完成一个分析任务，再导出报告。");
    return;
  }
  try {
    const response = await apiFetch(`/api/reports/${runtime.activeJobId}?format=${encodeURIComponent(format)}`);
    if (!response.ok) {
      const message = await readErrorMessage(response);
      throw new Error(message || "报告导出失败。");
    }
    const blob = await response.blob();
    downloadBlob(blob, filename);
    setError("");
  } catch (error) {
    setError(error.message);
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

function downloadBlob(blob, filename) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

async function readJson(response) {
  if (window.DataAnalystUI?.api?.readJson) {
    return window.DataAnalystUI.api.readJson(response);
  }
  const contentType = response.headers.get("Content-Type") || "";
  const text = await response.text();
  if (!contentType.includes("application/json")) {
    if (text.includes("<!DOCTYPE") || text.includes("<html")) {
      throw new Error("接口返回了页面而不是 JSON。通常是后端仍在运行旧版本，请重启服务后刷新浏览器。");
    }
    throw new Error(text || "接口没有返回 JSON。");
  }
  try {
    return text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error("接口返回的 JSON 无法解析，请刷新页面后重试。");
  }
}

function renderChart(spec, index = 0) {
  if (window.DataAnalystUI?.charts?.renderChart) {
    return window.DataAnalystUI.charts.renderChart(spec, index);
  }
  const rows = (spec.data || []).slice(0, 12);
  if (!rows.length) return "";
  const width = 620;
  const rowHeight = 34;
  const labelWidth = 180;
  const height = Math.max(120, rows.length * rowHeight + 28);
  const values = rows.map((row) => Number(row[spec.y] || 0));
  const maxAbs = Math.max(...values.map((value) => Math.abs(value)), 1);
  const plotWidth = width - labelWidth - 36;
  const bars = rows
    .map((row, index) => {
      const rawValue = Number(row[spec.y] || 0);
      const barWidth = Math.max(2, Math.abs(rawValue) / maxAbs * plotWidth);
      const x = labelWidth;
      const y = index * rowHeight + 22;
      const fill = rawValue < 0 ? "#c24135" : "#2563eb";
      return `
        <text x="0" y="${y + 15}" class="chart-label">${escapeHtml(row[spec.x])}</text>
        <rect x="${x}" y="${y}" width="${barWidth}" height="18" rx="3" fill="${fill}"></rect>
        <text x="${x + barWidth + 8}" y="${y + 14}" class="chart-value">${escapeHtml(formatNumber(rawValue))}</text>
      `;
    })
    .join("");

  return `
    <article class="chart-card" data-chart-index="${index}">
      <div class="section-heading">
        <h3>${escapeHtml(spec.title)}</h3>
        <span>${escapeHtml(translateChartType(spec.chart_type))}</span>
      </div>
      <div class="chart-actions">
        <button class="secondary-action" type="button" data-chart-download="svg" data-chart-index="${index}">瀵煎嚭 SVG</button>
        <button class="secondary-action" type="button" data-chart-download="csv" data-chart-index="${index}">瀵煎嚭 CSV</button>
      </div>
      <p class="muted-copy">${escapeHtml(spec.description)}</p>
      <div class="chart-scroll">
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(spec.title)}" xmlns="http://www.w3.org/2000/svg">
          ${bars}
        </svg>
      </div>
    </article>
  `;
}

function bindChartDownloads(chartSpecs) {
  if (window.DataAnalystUI?.charts?.renderChartGrid) {
    return;
  }
  chartGrid.querySelectorAll("[data-chart-download]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.chartIndex || 0);
      const spec = chartSpecs[index];
      if (!spec) return;
      if (button.dataset.chartDownload === "svg") {
        downloadChartSvg(index, spec);
      } else {
        downloadChartCsv(spec);
      }
    });
  });
}

function downloadChartSvg(index, spec) {
  const card = chartGrid.querySelector(`[data-chart-index="${index}"]`);
  const svg = card?.querySelector("svg");
  if (!svg) {
    setError("没有找到可导出的图表。");
    return;
  }
  const serialized = new XMLSerializer().serializeToString(svg);
  const blob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
  downloadBlob(blob, `${safeFilename(spec.title || "图表")}.svg`);
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

function csvCell(value) {
  const text = String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

function safeFilename(value) {
  return String(value || "download").replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);
}

function clearElement(element) {
  if (!element) return;
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function metric(label, value) {
  if (window.DataAnalystUI?.renderers?.metric) {
    return window.DataAnalystUI.renderers.metric(label, value);
  }
  return `
    <article class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </article>
  `;
}

function renderTransparencyState(state) {
  if (agentReasoningList) {
    agentReasoningList.innerHTML = (state.reasoning || [])
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("");
  }
  if (agentNextStepTitle) agentNextStepTitle.textContent = state.nextTitle || state.next || "";
  if (agentNextStepDetail) agentNextStepDetail.textContent = state.nextDetail || "";
  if (interventionTitle) interventionTitle.textContent = state.interventionTitle || "";
  if (interventionDetail) interventionDetail.textContent = state.interventionDetail || "";
  if (interventionCard) {
    interventionCard.classList.remove("needs-review", "blocked", "failed");
    if (state.interventionClass) interventionCard.classList.add(state.interventionClass);
  }
}

function renderResultTransparency(data) {
  if (!data?.profile) return;
  const profile = data.profile;
  const quality = Math.round(Number(profile.quality_score || 0) * 100);
  const semanticCountValue = (data.semantic_roles || []).length;
  const reviewItems = buildHumanReviewItems(data);
  const planStepCount = data.plan?.steps?.length || 0;
  const chartCount = (data.chart_specs || []).length;
  renderTransparencyState({
    reasoning: [
      `已读取 ${profile.rows} 行、${profile.columns} 个字段，质量评分 ${quality}%。`,
      `识别到 ${semanticCountValue} 个业务字段角色，用于判断日期、金额、客户、渠道等口径。`,
      `生成 ${planStepCount} 个分析步骤和 ${chartCount} 个图表建议，并把结论绑定到证据与置信度。`,
    ],
    nextTitle: reviewItems.length ? "先处理需要复核的点" : "审阅结论并选择导出或追问",
    nextDetail: reviewItems.length
      ? "建议先检查低置信度字段、质量门禁或异常结论，再把报告交给业务方。"
      : "当前没有明显人工阻塞点，可以查看关键结论、导出报告，或继续追问细节。",
    interventionTitle: reviewItems.length ? `${reviewItems.length} 个点建议人工复核` : "无需立即介入",
    interventionDetail: reviewItems.length
      ? "复核项已放在总览顶部，优先确认字段口径、数据质量和低置信度结论。"
      : "如业务目标变了，可以直接追问或用当前任务作为下一轮分析起点。",
    interventionClass: reviewItems.length ? "needs-review" : "",
  });
}

function renderAgentActivity(events) {
  const visibleEvents = (events || []).slice(-6);
  agentActivityBlock?.classList.toggle("hidden", !visibleEvents.length);
  if (agentActivityCount) agentActivityCount.textContent = String(visibleEvents.length);
  if (!agentActivityList) return;
  agentActivityList.innerHTML = visibleEvents
    .map(
      (event) => `
        <li class="${escapeHtml(event.status || "")}">
          <strong>${escapeHtml(translateEventLabel(event.label))}</strong>
          <p>${escapeHtml(translateEventDetail(event.detail || ""))}</p>
          <span>${escapeHtml(formatTime(event.timestamp))}</span>
        </li>
      `
    )
    .join("");
}

function renderHumanReview(data) {
  const items = buildHumanReviewItems(data);
  humanReviewBlock?.classList.toggle("hidden", !data);
  if (humanReviewStatus) {
    humanReviewStatus.textContent = data ? (items.length ? `${items.length} 个建议复核` : "无需立即介入") : "待分析";
  }
  if (!humanReviewList) return;
  if (!data) {
    humanReviewList.innerHTML = "";
    return;
  }
  const visibleItems = items.length
    ? items
    : [
        {
          status: "ok",
          title: "当前没有明显阻塞点",
          detail: "字段识别、质量门禁和结论置信度未触发强复核提醒。仍建议在对外汇报前抽查关键指标口径。",
          action: "可继续查看报告或追问",
        },
      ];
  humanReviewList.innerHTML = visibleItems
    .slice(0, 6)
    .map(
      (item) => `
        <article class="review-item ${escapeHtml(item.status)}">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.detail)}</p>
          <span>${escapeHtml(item.action)}</span>
        </article>
      `
    )
    .join("");
}

function buildHumanReviewItems(data) {
  if (!data?.profile) return [];
  const items = [];
  const profile = data.profile;
  if (Number(profile.quality_score || 0) < 0.75) {
    items.push({
      status: "needs-review",
      title: "数据质量评分偏低",
      detail: `当前质量评分为 ${Math.round(Number(profile.quality_score || 0) * 100)}%，建议先确认缺失、重复或异常值是否会影响结论。`,
      action: "先看数据质量",
    });
  }
  (data.quality_gates || [])
    .filter((gate) => gate.status && gate.status !== "pass")
    .slice(0, 2)
    .forEach((gate) => {
      items.push({
        status: gate.status === "fail" ? "blocked" : "needs-review",
        title: gate.name || "质量门禁需要复核",
        detail: gate.detail || "该质量门禁没有通过，建议确认后再采信结论。",
        action: gate.severity || "review",
      });
    });
  (data.semantic_roles || [])
    .filter((role) => Number(role.confidence || 0) < 0.7)
    .slice(0, 2)
    .forEach((role) => {
      items.push({
        status: "needs-review",
        title: `字段口径不够确定：${role.column}`,
        detail: `Agent 推测它是“${translateRole(role.role)}”，置信度 ${Math.round(Number(role.confidence || 0) * 100)}%。`,
        action: "补充字段字典",
      });
    });
  (data.insights || [])
    .filter((insight) => insight.needs_review || Number(insight.confidence || 0) < 0.65)
    .slice(0, 2)
    .forEach((insight) => {
      items.push({
        status: "needs-review",
        title: insight.title || "结论需要复核",
        detail: insight.detail || "该洞察置信度较低，建议结合原始数据或业务背景确认。",
        action: `置信度 ${Math.round(Number(insight.confidence || 0) * 100)}%`,
      });
    });
  (data.metric_definitions || [])
    .filter((definition) => definition.available === false)
    .slice(0, 2)
    .forEach((definition) => {
      items.push({
        status: "needs-review",
        title: `指标暂不可计算：${definition.name || "未命名指标"}`,
        detail: definition.reason || "缺少必要字段，建议补充数据或调整分析目标。",
        action: "调整目标或字段",
      });
    });
  return items;
}

function setStatus(kind, text) {
  statusBadge.className = `run-status ${kind}`;
  statusBadge.textContent = text;
  updateAgentCommand(kind, text);
}

function updateAgentCommand(kind, text) {
  const states = {
    idle: {
      title: "等待任务",
      detail: "准备接收 CSV / Excel 数据集",
      current: "等待数据集",
      currentDetail: "上传文件并确认目标后，Agent 会生成计划、执行工具并产出报告。",
      next: "上传数据",
      nextDetail: "选择文件、确认分析目标和字段口径后，Agent 会先规划再执行。",
      reasoning: ["等待数据上传和分析目标。", "上传后会先检查字段口径、质量风险和可用指标。"],
      interventionTitle: "上传前确认目标即可",
      interventionDetail: "如果字段口径不清楚或分析目标变化，先补充字段字典和目标。",
      interventionClass: "",
      stage: "intake",
      done: [],
    },
    queued: {
      title: "任务排队中",
      detail: "已接收数据，等待执行资源",
      current: "排队等待执行",
      currentDetail: "任务已进入队列；你可以查看时间线或取消任务。",
      next: "生成分析计划",
      nextDetail: "资源可用后会读取数据画像、识别字段角色，并生成分析步骤。",
      reasoning: ["已接收任务，正在等待执行资源。", "当前可以取消任务，也可以切到时间线查看接收记录。"],
      interventionTitle: "现在通常不用介入",
      interventionDetail: "如果文件选错或目标写错，可以取消任务后重新提交。",
      interventionClass: "",
      stage: "plan",
      done: ["intake"],
    },
    running: {
      title: "分析运行中",
      detail: "正在读取数据、执行工具并生成报告",
      current: "执行分析链路",
      currentDetail: "Agent 正在画像、规划、运行 SQL/Python、整理图表和报告。",
      next: "查看结果与证据",
      nextDetail: "完成后会把结论、图表、质量门禁和建议复核点集中放在总览里。",
      reasoning: ["正在把数据画像、字段角色和分析目标组合成执行链路。", "会优先标记低置信度字段、质量风险和需要业务确认的结论。"],
      interventionTitle: "运行中可观察或取消",
      interventionDetail: "如果发现任务方向不对，可以取消；否则等待结果页给出复核点。",
      interventionClass: "",
      stage: "execute",
      done: ["intake", "plan"],
    },
    done: {
      title: "分析已完成",
      detail: "报告、图表和追问上下文已准备好",
      current: "结果可审阅",
      currentDetail: "你可以查看结论证据、导出报告，或继续追问。",
      next: "导出或追问",
      nextDetail: "先检查总览里的人工复核点，再导出报告或继续追问关键结论。",
      reasoning: ["已完成分析链路，结果已按结论、证据、图表和报告组织。", "建议先看复核点，再决定是否导出或继续追问。"],
      interventionTitle: "现在应该审阅关键结论",
      interventionDetail: "重点看质量门禁、低置信度洞察和指标口径，再把报告交给业务方。",
      interventionClass: "",
      stage: "deliver",
      done: ["intake", "plan", "execute", "verify"],
    },
    failed: {
      title: "需要处理",
      detail: "任务失败或被取消，请查看错误恢复建议",
      current: "等待修复",
      currentDetail: "检查文件格式、字段字典、权限或服务状态后，可用当前设置重试。",
      next: "修复后重试",
      nextDetail: "先查看错误信息和恢复建议，修正输入或权限后再提交。",
      reasoning: ["任务没有完成，当前结果不能作为分析结论使用。", "需要先定位失败原因，再决定重试、清空错误或调整配置。"],
      interventionTitle: "需要你处理失败原因",
      interventionDetail: "检查文件格式、字段字典、权限配置或服务状态后，再用当前设置重试。",
      interventionClass: "failed",
      stage: "verify",
      done: ["intake"],
    },
  };
  const state = states[kind] || states.idle;
  if (agentStateTitle) agentStateTitle.textContent = state.title;
  if (agentStateDetail) agentStateDetail.textContent = state.detail;
  if (currentActionLabel) currentActionLabel.textContent = state.current;
  if (currentActionDetail) currentActionDetail.textContent = state.currentDetail;
  if (nextActionLabel) nextActionLabel.textContent = state.next;
  renderTransparencyState({
    reasoning: state.reasoning,
    nextTitle: state.next,
    nextDetail: state.nextDetail,
    interventionTitle: state.interventionTitle,
    interventionDetail: state.interventionDetail,
    interventionClass: state.interventionClass,
  });
  if (kind === "done" && runtime.latestResult) {
    renderResultTransparency(runtime.latestResult);
  }
  cancelFromState?.classList.toggle("hidden", !["queued", "running"].includes(kind));
  stagePills.forEach((pill) => {
    const stage = pill.dataset.stage;
    pill.classList.toggle("active", stage === state.stage);
    pill.classList.toggle("done", state.done.includes(stage));
  });
}
function setError(message) {
  if (!message) {
    errorState.classList.add("hidden");
    errorState.textContent = "";
    recoveryPanel?.classList.add("hidden");
    return;
  }
  errorState.classList.remove("hidden");
  errorState.textContent = message;
  recoveryPanel?.classList.remove("hidden");
}

function shortJobId(jobId) {
  return jobId ? `浠诲姟 ${jobId.slice(0, 8)}` : "";
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatNumber(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function translateChartType(type) {
  return type === "bar" ? "柱状图" : type;
}

function translateEventLabel(label) {
  const labels = {
    Queued: "已入队",
    Running: "运行中",
    Planning: "生成计划",
    "Executing tools": "执行工具",
    Completed: "已完成",
    Failed: "失败",
    Cancelled: "已取消",
  };
  return labels[label] || label;
}

function translateEventDetail(detail) {
  const details = {
    "Dataset accepted and waiting for analysis.": "数据集已接收，等待分析。",
    "Loading CSV and building dataset profile.": "正在读取 CSV 并生成数据画像。",
    "Analysis plan created from schema and goal.": "已根据字段结构和目标生成分析计划。",
    "Python and SQL analysis steps finished.": "Python 和 SQL 分析步骤已完成。",
    "Report generated and stored.": "报告已生成并保存。",
    "Cancellation requested.": "已请求取消任务。",
  };
  return details[detail] || detail;
}

function translateQualityText(text) {
  return text
    .replace("duplicate rows detected.", "行重复。")
    .replace("Constant columns detected:", "检测到常量字段：")
    .replace("missing values", "个缺失值");
}

function translateQualityDimension(key) {
  const dimensions = {
    completeness: "完整性",
    uniqueness: "唯一性",
    variability: "可变性",
    schema: "结构可用性",
  };
  return dimensions[key] || key;
}

function translateInsightType(type) {
  const types = {
    fact: "事实",
    finding: "发现",
    inference: "推断",
    recommendation: "建议",
    limitation: "边界",
  };
  return types[type] || type || "结论";
}

function renderInsightEvidence(insight) {
  const chips = [];
  if (insight.metric_value) chips.push(`指标：${insight.metric_value}`);
  (insight.evidence || []).slice(0, 3).forEach((item) => chips.push(item));
  if (insight.needs_review) chips.push("建议人工复核");
  if (!chips.length) return "";
  return `<div class="insight-evidence">${chips.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function translateRole(role) {
  const roles = {
    date: "日期",
    region: "区域",
    product: "产品",
    channel: "渠道",
    customer: "客户",
    order: "订单",
    revenue: "收入",
    profit: "利润",
    cost: "成本",
    units: "销量",
    discount: "折扣",
    price: "价格",
  };
  return roles[role] || role;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


