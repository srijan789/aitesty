import { useState } from 'react';

export default function ProjectForm({ onCreate }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [deadline, setDeadline] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      await onCreate({ name, description, deadline: deadline || null });
      setName('');
      setDescription('');
      setDeadline('');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2>New Project</h2>
      <input
        placeholder="Project name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <textarea
        placeholder="Description (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
      <button type="submit" disabled={submitting}>
        {submitting ? 'Creating…' : 'Create Project'}
      </button>
      {error && <p className="error-text">{error}</p>}
    </form>
  );
}
