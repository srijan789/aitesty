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
      <div class="flex items-center justify-between gap-3">
        <div class="flex-1">
          <input type="text" class="sc-title w-full text-xs font-bold text-slate-900 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
            placeholder="Scenario Title" value="${escapeAttr(sc.title || '')}" onchange="updateScenarioField(${scIndex}, 'title', this.value)">
        </div>
        <select class="sc-category text-xs border border-slate-300 rounded-lg px-2.5 py-1.5 bg-white text-slate-700"
          onchange="updateScenarioField(${scIndex}, 'category', this.value)">
          <option value="happy_path" ${sc.category === 'happy_path' ? 'selected' : ''}>Happy Path</option>
          <option value="edge_case" ${sc.category === 'edge_case' ? 'selected' : ''}>Edge Case</option>
          <option value="error_flow" ${sc.category === 'error_flow' ? 'selected' : ''}>Error Flow</option>
        </select>
        <button type="button" onclick="removeScenario(${scIndex})" class="text-slate-400 hover:text-rose-600 text-xs px-1" title="Delete Scenario">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </div>

      <div>
        <textarea class="sc-desc w-full text-xs text-slate-600 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
          rows="2" placeholder="Scenario description..." onchange="updateScenarioField(${scIndex}, 'description', this.value)">${escapeAttr(sc.description || '')}</textarea>
      </div>

      <!-- Expected Result -->
      <div>
        <label class="block text-[11px] font-semibold text-slate-500 mb-1">Expected Result</label>
        <input type="text" class="w-full text-xs text-slate-800 border border-slate-300 rounded-lg px-2.5 py-1.5 focus:border-indigo-500 focus:outline-none"
          value="${escapeAttr(sc.expected_result || '')}" placeholder="What should happen if successful..." onchange="updateScenarioField(${scIndex}, 'expected_result', this.value)">
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
    description: '',
    steps: [
      { step_number: 1, action: "Navigate", target_element: "/", expected_outcome: "Page loads" }
    ],
    expected_result: 'Expected successful state',
    status: 'pending'
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

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;');
}
