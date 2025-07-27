import React, { useState } from 'react';
import './App.css';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setResult(null); // Clear previous results
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('Please select a file first!');
      return;
    }

    setUploading(true);
    
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      // Use relative path for production, localhost for development
      const apiUrl = process.env.NODE_ENV === 'production' 
        ? '/api/extract' 
        : 'http://localhost:5000/extract';
        
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.success) {
        setResult({
          success: true,
          text: data.text,
          filename: data.filename,
          timestamp: data.timestamp,
          fileType: data.file_type,
          extractionMethod: data.extraction_method,
          characterCount: data.character_count
        });
      } else {
        setResult({
          success: false,
          message: data.message || 'Text extraction failed',
          filename: data.filename,
          fileType: data.file_type,
          extractionMethod: data.extraction_method
        });
      }
    } catch (error) {
      console.error('Upload error:', error);
      setResult({
        success: false,
        message: 'Failed to connect to text extraction service'
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="App">
      <div className="upload-container">
        <h1>Multi-Format Text Extractor</h1>
        <div className="upload-section">
          <input
            type="file"
            onChange={handleFileChange}
            className="file-input"
            accept="image/*,.pdf,.xlsx,.xls,.csv"
          />
          <div className="supported-formats">
            <p><strong>Supported formats:</strong></p>
            <ul>
              <li>📷 Images: JPEG, PNG, BMP, TIFF (OCR)</li>
              <li>📄 PDF: Text-based and Scanned (OCR fallback)</li>
              <li>📊 Excel: XLS, XLSX</li>
              <li>📋 CSV files</li>
            </ul>
          </div>
          {selectedFile && (
            <p className="file-info">
              Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(2)} KB)
            </p>
          )}
          <button 
            onClick={handleUpload}
            className="upload-button"
            disabled={uploading}
          >
                        {uploading ? 'Processing...' : 'Extract Text'}
          </button>
        </div>

        {result && (
          <div className="result-section">
            <h3>Extraction Result:</h3>
            {result.success ? (
              <div className="success-result">
                <p><strong>File:</strong> {result.filename}</p>
                <p><strong>File Type:</strong> {result.fileType}</p>
                <p><strong>Extraction Method:</strong> {result.extractionMethod}</p>
                <p><strong>Processed at:</strong> {result.timestamp}</p>
                <p><strong>Characters extracted:</strong> {result.characterCount?.toLocaleString()}</p>
                <div className="extracted-text">
                  <h4>Extracted Text:</h4>
                  <pre>{result.text}</pre>
                </div>
              </div>
            ) : (
              <div className="error-result">
                <p><strong>Error:</strong> {result.message}</p>
                {result.filename && <p><strong>File:</strong> {result.filename}</p>}
                {result.fileType && <p><strong>File Type:</strong> {result.fileType}</p>}
                {result.extractionMethod && <p><strong>Attempted Method:</strong> {result.extractionMethod}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;