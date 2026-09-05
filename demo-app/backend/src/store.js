let projects = [];
let nextProjectId = 1;
let nextTaskId = 1;

function resetStore() {
  projects = [];
  nextProjectId = 1;
  nextTaskId = 1;
}

function getAllProjects() {
  return projects;
}

function getProjectById(id) {
  return projects.find((p) => p.id === id);
}

function createProject({ name, description = '', deadline = null }) {
  const project = {
    id: nextProjectId++,
    name,
    description,
    deadline,
    status: 'active',
    createdAt: new Date().toISOString(),
    tasks: [],
  };
  projects.push(project);
  return project;
}

function updateProject(id, updates) {
  const project = getProjectById(id);
  if (!project) return null;
  const { name, description, deadline, status } = updates;
  if (name !== undefined) project.name = name;
  if (description !== undefined) project.description = description;
  // BUG (intentional): should be `deadline !== undefined`. A truthy check means
  // sending `deadline: null` (or '') to clear an existing deadline is silently
  // ignored -- the response is still 200, but the old deadline never changes.
  // Editing a project to push its deadline *later* always works (truthy value),
  // so normal manual use never notices; only a test that clears a deadline back
  // to "none" catches it.
  if (deadline) project.deadline = deadline;
  if (status !== undefined) project.status = status;
  return project;
}

function deleteProject(id) {
  const index = projects.findIndex((p) => p.id === id);
  if (index === -1) return false;
  projects.splice(index, 1);
  return true;
}

function addTask(projectId, { title, assignee = '' }) {
  const project = getProjectById(projectId);
  if (!project) return null;
  const task = {
    id: nextTaskId++,
    title,
    assignee,
    completed: false,
    createdAt: new Date().toISOString(),
  };
  project.tasks.push(task);
  return task;
}

function toggleTask(projectId, taskId) {
  const project = getProjectById(projectId);
  if (!project) return null;
  const task = project.tasks.find((t) => t.id === taskId);
  if (!task) return null;
  task.completed = !task.completed;
  return task;
}

module.exports = {
  resetStore,
  getAllProjects,
  getProjectById,
  createProject,
  updateProject,
  deleteProject,
  addTask,
  toggleTask,
};
