export default function TaskItem({ task, onToggle }) {
  return (
    <li className={task.completed ? 'task-item completed' : 'task-item'}>
      <label>
        <input type="checkbox" checked={task.completed} onChange={onToggle} />
        <span>{task.title}</span>
      </label>
      {task.assignee && <span className="muted">{task.assignee}</span>}
    </li>
  );
}
