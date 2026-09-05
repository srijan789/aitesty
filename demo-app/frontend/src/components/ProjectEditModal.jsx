import { useState } from 'react';

export default function ProjectEditModal({ project, onSave, onClose }) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description || '');
  const [deadline, setDeadline] = useState(project.deadline || '');
  const [status, setStatus] = useState(project.status);

  async function handleSubmit(e) {
    e.preventDefault();
    await onSave({ name, description, deadline: deadline || null, status });
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h3>Edit Project</h3>
        <input value={name} onChange={(e) => setName(e.target.value)} required />
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
        </select>
        <div className="modal-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit">Save</button>
        </div>
      </form>
    </div>
  );
}
