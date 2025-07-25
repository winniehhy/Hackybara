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
      const response = await fetch('http://localhost:5000/ocr', {
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
          outputFile: data.output_file
        });
      } else {
        setResult({
          success: false,
          message: data.message || 'OCR processing failed',
          filename: data.filename
        });
      }
    } catch (error) {
      console.error('Upload error:', error);
      setResult({
        success: false,
        message: 'Failed to connect to OCR service'
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="App">
      <div className="upload-container">
        <h1>OCR File Upload</h1>
        <div className="upload-section">
          <input
            type="file"
            onChange={handleFileChange}
            className="file-input"
            accept="image/*"
          />
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
            {uploading ? 'Processing...' : 'Upload & Extract Text'}
          </button>
        </div>

        {result && (
          <div className="result-section">
            <h3>OCR Result:</h3>
            {result.success ? (
              <div className="success-result">
                <p><strong>File:</strong> {result.filename}</p>
                <p><strong>Processed at:</strong> {result.timestamp}</p>
                <p><strong>Output saved to:</strong> {result.outputFile}</p>
                <div className="extracted-text">
                  <h4>Extracted Text:</h4>
                  <pre>{result.text}</pre>
                </div>
              </div>
            ) : (
              <div className="error-result">
                <p><strong>Error:</strong> {result.message}</p>
                {result.filename && <p><strong>File:</strong> {result.filename}</p>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;