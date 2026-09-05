let lastLogId = 0;
let pollInterval = null;
let currentFilter = 'ALL';

function initLogStream(runId, projectId) {
  const terminal = document.getElementById('terminal-output');
  const initMsg = document.getElementById('terminal-init-msg');

  async function poll() {
    try {
      const res = await fetch(`/api/runs/${runId}/logs?after_id=${lastLogId}`);
      if (!res.ok) return;

      const data = await res.json();
      if (initMsg) initMsg.remove();

      if (data.logs && data.logs.length > 0) {
        data.logs.forEach(log => {
          renderLogLine(log);
          lastLogId = Math.max(lastLogId, log.id);
        });

        const chk = document.getElementById('chk-autoscroll');
        if (chk && chk.checked) {
          terminal.scrollTop = terminal.scrollHeight;
        }
      }

      // Update Run Status Badge & Duration
      updateRunStatusUI(data.status, data.summary_stats);

      if (data.completed) {
        clearInterval(pollInterval);
        const cancelBtn = document.getElementById('btn-cancel-run');
        if (cancelBtn) cancelBtn.remove();
      }
    } catch (err) {
      console.error("Error polling logs:", err);
    }
  }

  // Initial immediate fetch
  poll();
  // Poll every 800ms
  pollInterval = setInterval(poll, 800);
}

function renderLogLine(log) {
  const terminal = document.getElementById('terminal-output');
  if (!terminal) return;

  const line = document.createElement('div');
  line.className = `log-entry flex items-start space-x-2.5 hover:bg-slate-800/50 px-1.5 py-0.5 rounded transition ${
    currentFilter !== 'ALL' && log.level !== currentFilter ? 'hidden' : ''
  }`;
  line.setAttribute('data-level', log.level);

  // Format time (HH:MM:SS)
  const timeStr = log.timestamp ? log.timestamp.substring(11, 19) : '--:--:--';

  let badgeColor = 'text-blue-400 bg-blue-950/60 border-blue-800';
  if (log.level === 'WARN') badgeColor = 'text-amber-400 bg-amber-950/60 border-amber-800';
  if (log.level === 'ERROR') badgeColor = 'text-rose-400 bg-rose-950/60 border-rose-800';
  if (log.level === 'DEBUG') badgeColor = 'text-slate-400 bg-slate-950/60 border-slate-800';

  line.innerHTML = `
    <span class="text-slate-500 select-none text-[11px] shrink-0 font-mono">[${timeStr}]</span>
    <span class="px-1.5 py-0.2 rounded border text-[10px] font-bold tracking-wider shrink-0 uppercase font-mono ${badgeColor}">
      ${log.level}
    </span>
    <span class="text-slate-200 flex-1 break-words">${escapeHtml(log.message)}</span>
  `;

  terminal.appendChild(line);
}

function updateRunStatusUI(status, stats) {
  const badge = document.getElementById('run-status-badge');
  const text = document.getElementById('run-status-text');
  if (!badge || !text) return;

  text.textContent = status.charAt(0).toUpperCase() + status.slice(1);

  badge.className = 'inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ';
  if (status === 'completed') {
    badge.className += 'bg-emerald-50 text-emerald-700 border border-emerald-200';
    badge.innerHTML = `<i class="fa-solid fa-circle-check mr-1.5 text-emerald-500"></i><span>Completed</span>`;
  } else if (status === 'running') {
    badge.className += 'bg-indigo-50 text-indigo-700 border border-indigo-200 animate-pulse';
    badge.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin mr-1.5"></i><span>Running</span>`;
  } else if (status === 'failed') {
    badge.className += 'bg-rose-50 text-rose-700 border border-rose-200';
    badge.innerHTML = `<i class="fa-solid fa-circle-xmark mr-1.5 text-rose-500"></i><span>Failed</span>`;
  } else if (status === 'cancelled') {
    badge.className += 'bg-slate-100 text-slate-600 border border-slate-200';
    badge.innerHTML = `<span>Cancelled</span>`;
  }

  // Update stats cards if provided
  if (stats) {
    const primary = document.getElementById('stat-primary');
    const secondary = document.getElementById('stat-secondary');
    if (primary && stats.total_scenarios !== undefined) {
      primary.textContent = stats.total_scenarios;
    } else if (primary && stats.passed !== undefined) {
      primary.textContent = `${stats.passed} / ${stats.total}`;
    }

    if (secondary && stats.routes_discovered !== undefined) {
      secondary.textContent = stats.routes_discovered;
    } else if (secondary && stats.failed !== undefined) {
      secondary.textContent = stats.failed;
    }
  }
}

function filterConsoleLogs(level) {
  currentFilter = level;
  document.querySelectorAll('.log-entry').forEach(el => {
    if (level === 'ALL' || el.getAttribute('data-level') === level) {
      el.classList.remove('hidden');
    } else {
      el.classList.add('hidden');
    }
  });
}

function clearConsoleDisplay() {
  const terminal = document.getElementById('terminal-output');
  if (terminal) terminal.innerHTML = '<div class="text-slate-500 text-[11px] italic">Console cleared.</div>';
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
