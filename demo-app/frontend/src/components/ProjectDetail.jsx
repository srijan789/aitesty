import { useEffect, useState, useCallback } from 'react';
import * as api from '../api.js';
import TaskForm from './TaskForm.jsx';
import TaskItem from './TaskItem.jsx';
import ProjectEditModal from './ProjectEditModal.jsx';

export default function ProjectDetail({ projectId, onChanged }) {
  const [project, setProject] = useState(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getProject(projectId);
      setProject(data);
    } catch (err) {
      setError(err.message);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAddTask(payload) {
    await api.addTask(projectId, payload);
    await load();
  }

  async function handleToggle(taskId) {
    await api.toggleTask(projectId, taskId);
    await load();
  }

  async function handleSaveEdit(payload) {
    await api.updateProject(projectId, payload);
    setEditing(false);
    await load();
    onChanged?.();
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!project) return <p>Loading…</p>;

  return (
    <div className="project-detail">
      <div className="project-detail-header">
        <div>
          <h2>{project.name}</h2>
          {project.description && <p className="muted">{project.description}</p>}
          {project.deadline && <p className="muted">Due {project.deadline}</p>}
        </div>
        <button onClick={() => setEditing(true)}>Edit</button>
      </div>

      <div className="progress-bar">
        <div className="progress-bar-fill" style={{ width: `${project.progress.progressPercent}%` }} />
      </div>
      <p className="muted">
        {project.progress.completed} of {project.progress.total} tasks complete (
        {project.progress.progressPercent}%)
      </p>

      <TaskForm onAdd={handleAddTask} />

      <ul className="task-list">
        {project.tasks.map((task) => (
          <TaskItem key={task.id} task={task} onToggle={() => handleToggle(task.id)} />
        ))}
        {project.tasks.length === 0 && <p className="empty-state">No tasks yet.</p>}
      </ul>

      {editing && (
        <ProjectEditModal project={project} onSave={handleSaveEdit} onClose={() => setEditing(false)} />
      )}
    </div>
  );
}
