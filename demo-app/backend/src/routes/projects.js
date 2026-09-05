const express = require('express');
const store = require('../store');

const router = express.Router();

function computeProgress(project) {
  const total = project.tasks.length;
  const completed = project.tasks.filter((t) => t.completed).length;
  const progressPercent = total === 0 ? 0 : Math.round((completed / total) * 100);
  return { total, completed, progressPercent };
}

function serializeProject(project) {
  return { ...project, progress: computeProgress(project) };
}

// 1. Create project
router.post('/', (req, res) => {
  const { name, description, deadline } = req.body || {};
  if (!name || typeof name !== 'string' || !name.trim()) {
    return res.status(400).json({ error: 'name is required' });
  }
  const project = store.createProject({ name: name.trim(), description, deadline });
  res.status(201).json(serializeProject(project));
});

// 8. Search projects by name/keyword.
// Registered before '/:id' so the literal "search" path isn't swallowed as an :id.
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

router.get('/search', (req, res) => {
  const q = req.query.q || '';
  const regex = new RegExp(escapeRegex(q), 'i');
  const results = store.getAllProjects().filter((p) => regex.test(p.name));
  res.json(results.map(serializeProject));
});

// 2. List projects (optional ?status=active|completed)
router.get('/', (req, res) => {
  const { status } = req.query;
  let results = store.getAllProjects();
  if (status) {
    results = results.filter((p) => p.status === status);
  }
  res.json(results.map(serializeProject));
});

// 3. Get project details
router.get('/:id', (req, res) => {
  const id = Number(req.params.id);
  const project = store.getProjectById(id);
  if (!project) return res.status(404).json({ error: 'project not found' });
  res.json(serializeProject(project));
});

// 4. Update project
router.put('/:id', (req, res) => {
  const id = Number(req.params.id);
  const project = store.updateProject(id, req.body || {});
  if (!project) return res.status(404).json({ error: 'project not found' });
  res.json(serializeProject(project));
});

// 5. Delete project
router.delete('/:id', (req, res) => {
  const id = Number(req.params.id);
  const deleted = store.deleteProject(id);
  if (!deleted) return res.status(404).json({ error: 'project not found' });
  res.status(204).send();
});

// 6. Add task to a project
router.post('/:id/tasks', (req, res) => {
  const id = Number(req.params.id);
  const { title, assignee } = req.body || {};
  if (!title || typeof title !== 'string' || !title.trim()) {
    return res.status(400).json({ error: 'title is required' });
  }
  const task = store.addTask(id, { title: title.trim(), assignee });
  if (!task) return res.status(404).json({ error: 'project not found' });
  res.status(201).json(task);
});

// 7. Toggle a task's complete state
router.patch('/:id/tasks/:taskId/toggle', (req, res) => {
  const id = Number(req.params.id);
  const taskId = Number(req.params.taskId);
  const task = store.toggleTask(id, taskId);
  if (!task) return res.status(404).json({ error: 'project or task not found' });
  res.json(task);
});

module.exports = router;
