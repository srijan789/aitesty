export default function ProjectList({ projects, selectedId, onSelect, onDelete }) {
  if (projects.length === 0) {
    return <p className="empty-state">No projects yet.</p>;
  }

  return (
    <ul className="project-list">
      {projects.map((project) => (
        <li
          key={project.id}
          className={project.id === selectedId ? 'project-row selected' : 'project-row'}
        >
          <button className="project-row-main" onClick={() => onSelect(project.id)}>
            <span className="project-name">{project.name}</span>
            <span className={`status-badge ${project.status}`}>{project.status}</span>
            <span className="progress-text">{project.progress.progressPercent}%</span>
          </button>
          <button
            className="delete-button"
            title="Delete project"
            onClick={() => onDelete(project.id)}
          >
            ✕
          </button>
        </li>
      ))}
    </ul>
  );
}
