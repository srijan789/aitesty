import { useState } from 'react';

export default function TaskForm({ onAdd }) {
  const [title, setTitle] = useState('');
  const [assignee, setAssignee] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim()) return;
    await onAdd({ title, assignee });
    setTitle('');
    setAssignee('');
  }

  return (
    <form className="task-form" onSubmit={handleSubmit}>
      <input
        placeholder="Task title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
      />
      <input
        placeholder="Assignee (optional)"
        value={assignee}
        onChange={(e) => setAssignee(e.target.value)}
      />
      <button type="submit">Add Task</button>
    </form>
  );
}
