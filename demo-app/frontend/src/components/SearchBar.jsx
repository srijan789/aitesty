import { useState } from 'react';

export default function SearchBar({ onSearch, error }) {
  const [query, setQuery] = useState('');

  function handleChange(e) {
    const value = e.target.value;
    setQuery(value);
    onSearch(value);
  }

  return (
    <div className="search-bar">
      <input placeholder="Search projects…" value={query} onChange={handleChange} />
      {error && <span className="error-text">Search failed: {error}</span>}
    </div>
  );
}
