let currentEditingPlan = { scenarios: [] };

async function openPlanEditor() {
  const modal = document.getElementById('plan-editor-modal');
  const container = document.getElementById('plan-editor-scenarios-container');
  if (!modal || !container) return;

  container.innerHTML = '<div class="text-xs text-slate-500 py-6 text-center">Loading scenarios...</div>';
  modal.classList.remove('hidden');

  const projectId = window.location.pathname.split('/')[2];
  try {
    const res = await fetch(`/api/projects/${projectId}/test-plan`);
    if (!res.ok) throw new Error("No existing test plan");
    currentEditingPlan = await res.json();
    renderScenariosInEditor();
  } catch (err) {
    currentEditingPlan = { scenarios: [] };
    renderScenariosInEditor();
  }
}

function closePlanEditor() {
  const modal = document.getElementById('plan-editor-modal');
  if (modal) modal.classList.add('hidden');
}

function renderScenariosInEditor() {
  const container = document.getElementById('plan-editor-scenarios-container');
  if (!container) return;
  container.innerHTML = '';

  const scenarios = currentEditingPlan.scenarios || [];

  if (scenarios.length === 0) {
    container.innerHTML = '<div class="text-xs text-slate-400 italic text-center py-6">No scenarios found. Click "Add New Scenario" to create one.</div>';
    return;
  }

  scenarios.forEach((sc, scIndex) => {
    const card = document.createElement('div');
    card.className = 'bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3';
    card.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex-1 min-w-[200px]">
          <input type="text" class="sc-title w-full text-xs font-bold text-slate-900 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
            placeholder="Scenario Title" value="${escapeAttr(sc.title || '')}" onchange="updateScenarioField(${scIndex}, 'title', this.value)">
        </div>
        <div class="flex items-center space-x-2">
          <!-- Priority Selector -->
          <select class="sc-priority text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 font-semibold"
            onchange="updateScenarioField(${scIndex}, 'priority', this.value)">
            <option value="P0" ${sc.priority === 'P0' ? 'selected' : ''}>P0 - Blocker</option>
            <option value="P1" ${(!sc.priority || sc.priority === 'P1') ? 'selected' : ''}>P1 - High</option>
            <option value="P2" ${sc.priority === 'P2' ? 'selected' : ''}>P2 - Medium</option>
            <option value="P3" ${sc.priority === 'P3' ? 'selected' : ''}>P3 - Low</option>
          </select>

          <!-- Category Selector -->
          <select class="sc-category text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700"
            onchange="updateScenarioField(${scIndex}, 'category', this.value)">
            <option value="happy_path" ${sc.category === 'happy_path' ? 'selected' : ''}>Happy Path</option>
            <option value="edge_case" ${sc.category === 'edge_case' ? 'selected' : ''}>Edge Case</option>
            <option value="error_flow" ${sc.category === 'error_flow' ? 'selected' : ''}>Error Flow</option>
          </select>

          <!-- Status Selector -->
          <select class="sc-status text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700"
            onchange="updateScenarioField(${scIndex}, 'status', this.value)">
            <option value="pending_review" ${(!sc.status || sc.status === 'pending_review') ? 'selected' : ''}>Pending Review</option>
            <option value="marked_for_automation" ${sc.status === 'marked_for_automation' ? 'selected' : ''}>Marked for Auto</option>
            <option value="automated" ${sc.status === 'automated' ? 'selected' : ''}>Automated</option>
          </select>

          <button type="button" onclick="removeScenario(${scIndex})" class="text-slate-400 hover:text-rose-600 text-xs p-1" title="Delete Scenario">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
      </div>

      <!-- Preconditions -->
      <div>
        <label class="block text-[11px] font-semibold text-slate-500 mb-1">Preconditions</label>
        <input type="text" class="w-full text-xs text-slate-800 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
          value="${escapeAttr(sc.preconditions || '')}" placeholder="Required initial state (e.g., Authenticated user on /settings)..." onchange="updateScenarioField(${scIndex}, 'preconditions', this.value)">
      </div>

      <!-- Description -->
      <div>
        <label class="block text-[11px] font-semibold text-slate-500 mb-1">Description / Intent</label>
        <textarea class="sc-desc w-full text-xs text-slate-600 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
          rows="2" placeholder="Scenario description..." onchange="updateScenarioField(${scIndex}, 'description', this.value)">${escapeAttr(sc.description || '')}</textarea>
      </div>

      <!-- Expected Result -->
      <div>
        <label class="block text-[11px] font-semibold text-slate-500 mb-1">Expected Result</label>
        <input type="text" class="w-full text-xs text-slate-800 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
          value="${escapeAttr(sc.expected_result || '')}" placeholder="What should happen if successful..." onchange="updateScenarioField(${scIndex}, 'expected_result', this.value)">
      </div>

      <!-- Pass/Fail Criteria -->
      <div>
        <label class="block text-[11px] font-semibold text-slate-500 mb-1">Pass / Fail Verification Criteria</label>
        <textarea class="w-full text-xs text-slate-800 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
          rows="2" placeholder="Explicit verification points (e.g. 1. HTTP 200 returned, 2. Success toast banner is visible)..." onchange="updateScenarioField(${scIndex}, 'pass_fail_criteria', this.value)">${escapeAttr(sc.pass_fail_criteria || '')}</textarea>
      </div>
    `;
    container.appendChild(card);
  });
}

function updateScenarioField(index, field, value) {
  if (currentEditingPlan.scenarios && currentEditingPlan.scenarios[index]) {
    currentEditingPlan.scenarios[index][field] = value;
  }
}

function removeScenario(index) {
  if (currentEditingPlan.scenarios) {
    currentEditingPlan.scenarios.splice(index, 1);
    renderScenariosInEditor();
  }
}

function addNewScenarioToEditor() {
  if (!currentEditingPlan.scenarios) currentEditingPlan.scenarios = [];
  currentEditingPlan.scenarios.push({
    title: `New Scenario ${currentEditingPlan.scenarios.length + 1}`,
    category: 'happy_path',
    priority: 'P1',
    preconditions: '',
    description: '',
    steps: [
      { step_number: 1, action: "Navigate", target_element: "/", expected_outcome: "Page loads" }
    ],
    expected_result: 'Expected successful state',
    pass_fail_criteria: 'Verification assertions',
    status: 'pending_review'
  });
  renderScenariosInEditor();
}

async function savePlanEdits(projectId) {
  try {
    const res = await fetch(`/api/projects/${projectId}/test-plan`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentEditingPlan)
    });
    const data = await res.json();
    if (data.success) {
      closePlanEditor();
      window.location.reload();
    } else {
      alert("Error updating plan: " + (data.error || "Unknown error"));
    }
  } catch (err) {
    alert("Request error: " + err.message);
  }
}

async function toggleAutomation(projectId, scenarioId, btnEl) {
  if (!btnEl) return;
  const originalHtml = btnEl.innerHTML;
  btnEl.disabled = true;

  try {
    const res = await fetch(`/api/projects/${projectId}/scenarios/${scenarioId}/toggle-automation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.success) {
      const card = btnEl.closest('.scenario-card');
      const isMarked = data.new_status === 'marked_for_automation';

      if (card) {
        card.setAttribute('data-status', data.new_status);
        const statusPill = card.querySelector('.scenario-status-pill');
        if (statusPill) {
          if (isMarked) {
            statusPill.innerHTML = `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              <i class="fa-solid fa-check-circle mr-1"></i>Marked for Auto
            </span>`;
          } else {
            statusPill.innerHTML = `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
              <i class="fa-regular fa-clock mr-1"></i>Pending Review
            </span>`;
          }
        }
      }

      if (isMarked) {
        btnEl.className = 'toggle-automation-btn px-3 py-1 rounded-lg text-xs font-medium transition flex items-center space-x-1.5 bg-indigo-600 text-white hover:bg-indigo-700 shadow-xs';
        btnEl.innerHTML = '<i class="fa-solid fa-check text-[11px]"></i><span>Marked for Automation</span>';
      } else {
        btnEl.className = 'toggle-automation-btn px-3 py-1 rounded-lg text-xs font-medium transition flex items-center space-x-1.5 bg-slate-100 text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 border border-slate-200 shadow-xs';
        btnEl.innerHTML = '<i class="fa-regular fa-square-check text-[11px]"></i><span>Mark for Automation</span>';
      }

      // Update counter
      updateMarkedCounter();
    } else {
      alert("Failed to update status: " + (data.error || "Unknown error"));
      btnEl.innerHTML = originalHtml;
    }
  } catch (err) {
    alert("Network error: " + err.message);
    btnEl.innerHTML = originalHtml;
  } finally {
    btnEl.disabled = false;
  }
}

async function bulkMarkForAutomation(projectId) {
  if (!confirm("Mark all scenarios in this test plan for automation?")) return;

  try {
    const res = await fetch(`/api/projects/${projectId}/scenarios/bulk-mark-automation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'marked_for_automation' })
    });
    const data = await res.json();
    if (data.success) {
      window.location.reload();
    } else {
      alert("Error marking scenarios: " + (data.error || "Unknown error"));
    }
  } catch (err) {
    alert("Request error: " + err.message);
  }
}

async function deleteScenario(projectId, scenarioId, btnEl) {
  const card = btnEl ? btnEl.closest('.scenario-card') : document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"]`);
  const titleEl = card ? card.querySelector('h4') : null;
  const title = titleEl ? titleEl.textContent.trim() : 'this scenario';

  if (!confirm(`Are you sure you want to delete scenario "${title}"?`)) {
    return;
  }

  if (btnEl) btnEl.disabled = true;

  try {
    const res = await fetch(`/api/projects/${projectId}/scenarios/${scenarioId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await res.json();
    if (data.success) {
      if (card) {
        card.style.transition = 'all 0.25s ease-out';
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => {
          const section = card.closest('.scenario-category-section');
          card.remove();

          // Update category header count
          if (section) {
            const categoryCards = section.querySelectorAll('.scenario-card');
            const catHeader = section.querySelector('h3');
            if (catHeader) {
              const catTitle = catHeader.textContent.split('(')[0].trim();
              catHeader.textContent = `${catTitle} (${categoryCards.length})`;
            }
            if (categoryCards.length === 0) {
              const emptyMsg = document.createElement('p');
              emptyMsg.className = 'text-xs text-slate-400 italic bg-white p-4 rounded-xl border border-slate-200';
              emptyMsg.textContent = 'No scenarios remaining in this category.';
              section.appendChild(emptyMsg);
            }
          }

          // Update total counter in toolbar
          const totalScenariosEl = document.getElementById('total-scenarios-count');
          if (totalScenariosEl) {
            const currentTotal = document.querySelectorAll('.scenario-card').length;
            totalScenariosEl.textContent = `${currentTotal} Total Scenarios`;
          }

          // Update marked counter
          updateMarkedCounter();
        }, 250);
      }
    } else {
      alert("Failed to delete scenario: " + (data.error || data.message || "Unknown error"));
      if (btnEl) btnEl.disabled = false;
    }
  } catch (err) {
    alert("Network error: " + err.message);
    if (btnEl) btnEl.disabled = false;
  }
}

function updateMarkedCounter() {
  const cards = document.querySelectorAll('.scenario-card');
  let markedCount = 0;
  cards.forEach(card => {
    if (card.getAttribute('data-status') === 'marked_for_automation') {
      markedCount++;
    }
  });
  const countEl = document.getElementById('marked-count');
  if (countEl) {
    countEl.textContent = markedCount;
  }
}

function filterPlanScenarios(filterType) {
  const cards = document.querySelectorAll('.scenario-card');
  const sections = document.querySelectorAll('.scenario-category-section');

  // Update filter button styling
  ['all', 'pending', 'marked'].forEach(type => {
    const btn = document.getElementById(`filter-btn-${type}`);
    if (btn) {
      if ((filterType === 'all' && type === 'all') ||
          (filterType === 'pending_review' && type === 'pending') ||
          (filterType === 'marked_for_automation' && type === 'marked')) {
        btn.className = 'px-2.5 py-1 rounded-md font-medium text-slate-800 bg-white shadow-xs transition';
      } else {
        btn.className = 'px-2.5 py-1 rounded-md font-medium text-slate-600 hover:text-slate-800 transition';
      }
    }
  });

  cards.forEach(card => {
    const status = card.getAttribute('data-status');
    if (filterType === 'all') {
      card.style.display = '';
    } else if (filterType === status) {
      card.style.display = '';
    } else {
      card.style.display = 'none';
    }
  });
}

function togglePlanView(viewName) {
  const cardsView = document.getElementById('plan-cards-view');
  const mdView = document.getElementById('plan-md-view');
  const btnCards = document.getElementById('btn-view-cards');
  const btnMd = document.getElementById('btn-view-md');

  if (viewName === 'cards') {
    if (cardsView) cardsView.classList.remove('hidden');
    if (mdView) mdView.classList.add('hidden');
    if (btnCards) btnCards.className = 'px-3 py-1.5 rounded-lg font-medium bg-slate-100 text-slate-800 hover:bg-slate-200 transition';
    if (btnMd) btnMd.className = 'px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100 transition';
  } else {
    if (cardsView) cardsView.classList.add('hidden');
    if (mdView) mdView.classList.remove('hidden');
    if (btnMd) btnMd.className = 'px-3 py-1.5 rounded-lg font-medium bg-slate-100 text-slate-800 hover:bg-slate-200 transition';
    if (btnCards) btnCards.className = 'px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100 transition';
  }
}

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;');
}
