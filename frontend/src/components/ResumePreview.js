import React, { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Download, AlertTriangle } from 'lucide-react';

// Use the correct CSS import paths
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// This tells react-pdf to look for 'pdf.worker.min.js' in the 'public' folder.
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';


const API_BASE = "http://127.0.0.1:8000";

export default function ResumePreview({ resumeId, resumeName, onClose }) {
  const [numPages, setNumPages] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setNumPages(null);
    setError(null);
    if (resumeId) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [resumeId]);

  if (!resumeId) return null;

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setError(null); // Clear previous errors on success
  }

  // --- NEW: Improved Error Handler ---
  function onDocumentLoadError(error) {
    console.error("PDF Load Error:", error);
    let errorMessage = "This could be a DOC/DOCX file, which can't be previewed, or the PDF file is corrupted.";
    
    // Check for common error messages to provide better feedback
    if (error.message.includes('Failed to fetch')) {
        errorMessage = "Failed to fetch the PDF file. This might be a network or CORS issue. Please check the browser console for more details.";
    } else if (error.message.includes('Invalid PDF structure')) {
        errorMessage = "The PDF file appears to be corrupted or has an invalid structure.";
    } else if (error.message.includes('Missing PDF')) {
        errorMessage = "The PDF file could not be found on the server.";
    }

    setError({
        title: "Preview not available.",
        message: errorMessage + " You can still try downloading the original file."
    });
  }
  
  const fileUrl = `${API_BASE}/resume/${resumeId}/file`;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex justify-center items-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-4xl h-full flex flex-col" onClick={(e) => e.stopPropagation()}>
        <header className="flex justify-between items-center p-4 border-b">
          <h3 className="text-xl font-bold text-gray-800 truncate pr-4">{resumeName || 'Resume Preview'}</h3>
          <div className='flex items-center space-x-4'>
             <a href={fileUrl} download className="flex items-center bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors text-sm">
                <Download className="mr-2 h-4 w-4" />
                Download
             </a>
             <button onClick={onClose} className="text-3xl font-light text-gray-500 hover:text-gray-800">&times;</button>
          </div>
        </header>
        <div className="flex-grow overflow-auto p-4 bg-gray-100">
          {error ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
                <AlertTriangle className="h-16 w-16 text-yellow-500 mb-4" />
                <h4 className="text-lg font-bold text-gray-800">{error.title}</h4>
                <p className="max-w-md mt-2 text-gray-600">{error.message}</p>
            </div>
          ) : (
            <Document
              file={fileUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={
                <div className="flex justify-center items-center h-full">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                </div>
              }
              className="flex justify-center"
            >
              <div className="space-y-4">
                {Array.from(new Array(numPages || 0), (el, index) => (
                  <div key={`page_${index + 1}`} className="bg-white shadow-lg">
                    <Page pageNumber={index + 1} />
                  </div>
                ))}
              </div>
            </Document>
          )}
        </div>
      </div>
    </div>
  );
}
