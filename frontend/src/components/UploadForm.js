import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, XCircle, Loader } from 'lucide-react';

const API_BASE = "http://127.0.0.1:8000";

export default function UploadForm() {
  // State to hold multiple files (an array of File objects)
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  // State to track upload progress and results
  const [status, setStatus] = useState({ message: '', error: false, results: [] });

  const handleFileChange = (e) => {
    // e.target.files is a FileList, convert it to an array
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
      setStatus({ message: '', error: false, results: [] });
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setStatus({ message: "Please select one or more files first.", error: true, results: [] });
      return;
    }

    setLoading(true);
    setStatus({ message: `Uploading ${files.length} file(s)...`, error: false, results: [] });

    // Create an array of upload promises
    const uploadPromises = files.map(file => {
      const formData = new FormData();
      formData.append("file", file);
      // We return the promise from axios, and add a .catch to handle individual errors
      return axios.post(`${API_BASE}/upload`, formData)
        .then(response => ({ name: file.name, status: 'success', data: response.data }))
        .catch(err => ({ name: file.name, status: 'error', message: err.response?.data?.detail || err.message }));
    });

    // Wait for all uploads to complete
    const results = await Promise.all(uploadPromises);

    setLoading(false);
    
    const successfulUploads = results.filter(r => r.status === 'success');
    const failedUploads = results.filter(r => r.status === 'error');

    // Set a final status message
    setStatus({
        message: `Upload complete. ${successfulUploads.length} succeeded, ${failedUploads.length} failed.`,
        error: failedUploads.length > 0,
        results: results // Store all results to display details
    });
    
    // Clear the file input for the next batch
    document.getElementById('file-input').value = '';
    setFiles([]);
  };

  const getFileLabel = () => {
    if (files.length === 0) {
      return 'Select .pdf, .doc, or .docx files';
    }
    if (files.length === 1) {
      return files[0].name;
    }
    return `${files.length} files selected`;
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-lg border border-gray-100 w-full">
      <h2 className="text-2xl font-bold mb-4 text-gray-800 flex items-center">
        <Upload className="mr-3 text-blue-600" /> Upload Résumés
      </h2>
      <div className="flex items-center space-x-4">
        <label htmlFor="file-input" className="flex-grow cursor-pointer">
          <div className="flex items-center p-3 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-gray-50 transition-colors">
            <FileText className="h-6 w-6 text-gray-400 mr-3" />
            <span className="text-gray-600 truncate">{getFileLabel()}</span>
          </div>
          <input
            id="file-input"
            type="file"
            accept=".pdf,.doc,.docx"
            onChange={handleFileChange}
            className="hidden"
            multiple // This is the key change to allow multiple file selection
          />
        </label>
        <button
          onClick={handleUpload}
          disabled={loading || files.length === 0}
          className="bg-blue-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-all duration-300 ease-in-out flex items-center justify-center transform hover:scale-105"
        >
          {loading ? (
            <Loader className="animate-spin h-5 w-5" />
          ) : (
            `Upload ${files.length || ''}`.trim()
          )}
        </button>
      </div>
      {status.message && (
        <div className="mt-4 space-y-2">
            <div className={`flex items-center text-sm ${status.error ? 'text-red-600' : 'text-green-600'}`}>
              {status.error ? <XCircle className="h-5 w-5 mr-2 flex-shrink-0" /> : <CheckCircle className="h-5 w-5 mr-2 flex-shrink-0" />}
              <span className="font-semibold">{status.message}</span>
            </div>
            {/* Optional: Display detailed results for each file */}
            {status.results.length > 0 && (
                 <ul className="text-xs text-gray-500 list-disc list-inside pl-2 max-h-32 overflow-y-auto">
                     {status.results.map((result, index) => (
                         <li key={index} className={`truncate ${result.status === 'error' ? 'text-red-500' : 'text-green-700'}`}>
                             {result.name}: {result.status === 'success' ? 'OK' : `Failed - ${result.message}`}
                         </li>
                     ))}
                 </ul>
            )}
        </div>
      )}
    </div>
  );
}
