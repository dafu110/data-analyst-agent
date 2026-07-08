window.DataAnalystUI = window.DataAnalystUI || {};

window.DataAnalystUI.labels = (() => {
  const statusLabels = {
  idle: "空闲",
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  done: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

  const agentCommandStates = {
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


  return {
    agentCommandStates,
    statusLabels,
    translateChartType,
    translateEventDetail,
    translateEventLabel,
    translateInsightType,
    translateQualityDimension,
    translateQualityText,
  };
})();
