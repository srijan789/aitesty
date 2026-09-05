const BASE = '/api/projects';

async function handle(res) {
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message = (data && data.error) || `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return data;
}

export function listProjects(status) {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return fetch(`${BASE}${query}`).then(handle);
}

export function searchProjects(q) {
  return fetch(`${BASE}/search?q=${encodeURIComponent(q)}`).then(handle);
}

export function getProject(id) {
  return fetch(`${BASE}/${id}`).then(handle);
}

export function createProject(payload) {
  return fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(handle);
}

export function updateProject(id, payload) {
  return fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(handle);
}

export function deleteProject(id) {
  return fetch(`${BASE}/${id}`, { method: 'DELETE' }).then(handle);
}

export function addTask(projectId, payload) {
  return fetch(`${BASE}/${projectId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(handle);
}

export function toggleTask(projectId, taskId) {
  return fetch(`${BASE}/${projectId}/tasks/${taskId}/toggle`, { method: 'PATCH' }).then(handle);
}
