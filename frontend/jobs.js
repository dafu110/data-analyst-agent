window.DataAnalystUI = window.DataAnalystUI || {};

window.DataAnalystUI.jobs = (() => {
  function isTerminal(status) {
    return ["completed", "failed", "cancelled"].includes(status);
  }

  function isRunning(status) {
    return ["queued", "running"].includes(status);
  }

  return { isRunning, isTerminal };
})();
