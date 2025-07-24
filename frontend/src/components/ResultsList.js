import React from 'react';
// Import the Trash2 icon
import { User, Star, Briefcase, FileText, Trash2 } from 'lucide-react';

// Accept the new 'onDelete' prop
export default function ResultsList({ results, onPreview, onDelete }) {
  if (!results.length) {
    return null;
  }

  return (
    <div className="w-full mt-8">
      <h3 className="text-3xl font-bold mb-6 text-gray-800">Search Results</h3>
      <ul className="space-y-4">
        {results.map((r) => (
          // Use r._id which is what MongoDB provides
          <li key={r._id} className="bg-white p-5 rounded-xl shadow-md transition-all hover:shadow-xl hover:scale-[1.02] border border-gray-100">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="text-xl font-bold text-blue-800 flex items-center">
                  <User className="mr-2 h-5 w-5" /> {r.name}
                </h4>
                <div className="flex space-x-4 text-sm text-gray-600 mt-2">
                    <span className="flex items-center"><Briefcase className="mr-1.5 h-4 w-4" /> {r.years_experience} years exp.</span>
                    <span className="flex items-center"><Star className="mr-1.5 h-4 w-4 text-yellow-500" /> Score: {r.search_score.toFixed(2)}</span>
                </div>
                <p className="text-sm text-gray-500 mt-2">
                  <strong className="font-semibold">Skills:</strong> {r.skills.join(", ")}
                </p>
              </div>
              
              {/* --- NEW: Add a div to wrap the buttons for better layout --- */}
              <div className="flex space-x-2 flex-shrink-0 ml-4">
                <button
                  // Pass r._id to the onPreview function
                  onClick={() => onPreview(r._id, r.name)}
                  className="bg-gray-200 text-gray-800 font-semibold py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors flex items-center"
                >
                  <FileText className="mr-2 h-4 w-4" /> Preview
                </button>
                {/* --- NEW: The Delete Button --- */}
                <button
                  // Pass r._id to the onDelete function
                  onClick={() => onDelete(r._id)}
                  className="bg-red-100 text-red-700 font-semibold py-2 px-4 rounded-lg hover:bg-red-200 transition-colors flex items-center"
                  aria-label="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            {r.highlight && (
              <p className="mt-4 p-3 bg-yellow-50 border-l-4 border-yellow-400 text-sm text-gray-700 rounded-r-lg italic">
                "{r.highlight}"
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
