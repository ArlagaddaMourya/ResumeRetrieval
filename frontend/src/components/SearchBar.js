import React, { useState } from 'react';
import { Search } from 'lucide-react';

export default function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('');

  const handleSearch = () => {
    if (!query || loading) return;
    onSearch(query);
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-100 w-full">
      <h2 className="text-2xl font-bold mb-4 text-gray-800 flex items-center">
        <Search className="mr-3 text-green-600" /> Search Résumés
      </h2>
      <div className="flex space-x-2">
        <input
          type="text"
          placeholder="e.g., python developer with 3-5 years"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-grow p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:outline-none transition-shadow"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="bg-green-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-green-700 disabled:bg-green-300 transition-colors transform hover:scale-105"
        >
          {loading ? "..." : "Search"}
        </button>
      </div>
    </div>
  );
}
