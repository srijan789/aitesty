import { useEffect, useState, useCallback } from 'react';
import * as api from './api.js';
import ProjectForm from './components/ProjectForm.jsx';
import ProjectList from './components/ProjectList.jsx';
import ProjectDetail from './components/ProjectDetail.jsx';
import SearchBar from './components/SearchBar.jsx';

export default function App() {
  const [projects, setProjects] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchError, setSearchError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState('');

  const loadProjects = useCallback(async () => {
    try {
      const data = await api.listProjects(statusFilter || undefined);
      setProjects(data);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  async function handleCreate(payload) {
    await api.createProject(payload);
    await loadProjects();
  }

  async function handleDelete(id) {
    await api.deleteProject(id);
    if (selectedId === id) setSelectedId(null);
    await loadProjects();
  }

  async function handleSearch(query) {
    if (!query.trim()) {
      setSearchResults(null);
      setSearchError('');
      return;
    }
    try {
      const results = await api.searchProjects(query);
      setSearchResults(results);
      setSearchError('');
    } catch (err) {
      setSearchResults(null);
      setSearchError(err.message);
    }
  }

  const visibleProjects = searchResults ?? projects;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Project Manager</h1>
        <SearchBar onSearch={handleSearch} error={searchError} />
      </header>

      <main className="app-main">
        <section className="app-sidebar">
          <ProjectForm onCreate={handleCreate} />

          <div className="filter-row">
            <label htmlFor="status-filter">Status</label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          {error && <p className="error-text">{error}</p>}

          <ProjectList
            projects={visibleProjects}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onDelete={handleDelete}
          />
        </section>

        <section className="app-content">
          {selectedId ? (
            <ProjectDetail key={selectedId} projectId={selectedId} onChanged={loadProjects} />
          ) : (
            <p className="empty-state">Select a project to see its details.</p>
          )}
        </section>
      </main>
    </div>
  );
}
