import React, { useState } from 'react';
import './App.css';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(0);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    setSelectedFile(file);
    setResult(null);
    setProgress(0);
    setFileContent(null);
    
    if (file) {
      readFileContent(file);
    }
  };

  const getFileIcon = (file) => {
    if (!file) return <span className="file-icon">📄</span>;
    
    const type = file.type;
    if (type.startsWith('image/')) return <span className="file-icon">🖼️</span>;
    if (type === 'application/pdf') return <span className="file-icon">📄</span>;
    if (type.includes('sheet') || type.includes('excel') || type === 'text/csv') return <span className="file-icon">📊</span>;
    return <span className="file-icon">📄</span>;
  };

  const simulateProgress = () => {
    setProgress(0);
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) {
          clearInterval(interval);
          return 90;
        }
        return prev + Math.random() * 15;
      });
    }, 200);
    return interval;
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('Please select a file first!');
      return;
    }

    setUploading(true);
    const progressInterval = simulateProgress();
    
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const apiUrl = process.env.NODE_ENV === 'production' 
        ? '/api/extract' 
        : 'http://localhost:5000/extract';
        
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      clearInterval(progressInterval);
      setProgress(100);

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
      clearInterval(progressInterval);
      setProgress(0);
      console.error('Upload error:', error);
      setResult({
        success: false,
        message: 'Failed to connect to text extraction service'
      });
    } finally {
      setUploading(false);
    }
  };

  const [fileContent, setFileContent] = useState(null);
  const [fileContentLoading, setFileContentLoading] = useState(false);

  const readFileContent = async (file) => {
    if (!file) return null;
    
    setFileContentLoading(true);
    
    try {
      const fileType = file.type;
      
      // Handle images
      if (fileType.startsWith('image/')) {
        const imageUrl = URL.createObjectURL(file);
        setFileContent({ type: 'image', content: imageUrl });
        return;
      }
      
      // Handle CSV files
      if (fileType === 'text/csv' || file.name.toLowerCase().endsWith('.csv')) {
        const text = await file.text();
        const lines = text.split('\n').slice(0, 20); // Show first 20 lines
        setFileContent({ type: 'csv', content: lines.join('\n'), fullContent: text });
        return;
      }
      
      // Handle Excel files (show basic info since we can't parse without library)
      if (fileType.includes('sheet') || fileType.includes('excel') || 
          file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls')) {
        setFileContent({ 
          type: 'excel', 
          content: `Excel file: ${file.name}\nSize: ${(file.size / 1024).toFixed(2)} KB\n\nThis Excel file will be processed by the server to extract its content.` 
        });
        return;
      }
      
      // Handle PDF files (show basic info since we can't parse without library)
      if (fileType === 'application/pdf') {
        setFileContent({ 
          type: 'pdf', 
          content: `PDF file: ${file.name}\nSize: ${(file.size / 1024).toFixed(2)} KB\n\nThis PDF file will be processed by the server to extract its text content.` 
        });
        return;
      }
      
      // Handle other text-based files
      try {
        const text = await file.text();
        const preview = text.length > 2000 ? text.substring(0, 2000) + '...' : text;
        setFileContent({ type: 'text', content: preview, fullContent: text });
      } catch (error) {
        setFileContent({ 
          type: 'binary', 
          content: `File: ${file.name}\nSize: ${(file.size / 1024).toFixed(2)} KB\nType: ${fileType}\n\nThis file will be processed by the server.` 
        });
      }
    } catch (error) {
      console.error('Error reading file:', error);
      setFileContent({ 
        type: 'error', 
        content: `Error reading file: ${file.name}\n\nThe file will still be processed by the server.` 
      });
    } finally {
      setFileContentLoading(false);
    }
  };

  const renderFilePreview = () => {
    if (!selectedFile) return null;

    if (fileContentLoading) {
      return (
        <div className="file-preview">
          <div className="spinner"></div>
          <p>Loading file content...</p>
        </div>
      );
    }

    if (!fileContent) {
      return (
        <div className="file-preview">
          {getFileIcon(selectedFile)}
          <div className="file-details">
            <p className="filename">{selectedFile.name}</p>
            <p className="filesize">{(selectedFile.size / 1024).toFixed(2)} KB</p>
            <p className="filetype">{selectedFile.type || 'Unknown format'}</p>
          </div>
        </div>
      );
    }

    // Render based on content type
    switch (fileContent.type) {
      case 'image':
        return (
          <div className="file-preview">
            <img 
              src={fileContent.content} 
              alt="Preview" 
              className="preview-image"
            />
          </div>
        );
      
      case 'csv':
      case 'text':
      case 'excel':
      case 'pdf':
      case 'binary':
      case 'error':
        return (
          <div className="file-preview">
            <div className="file-content-display">
              <div className="file-header">
                {getFileIcon(selectedFile)}
                <span className="file-name">{selectedFile.name}</span>
              </div>
              <div className="file-content-text">
                <pre>{fileContent.content}</pre>
              </div>
            </div>
          </div>
        );
      
      default:
        return (
          <div className="file-preview">
            {getFileIcon(selectedFile)}
            <div className="file-details">
              <p className="filename">{selectedFile.name}</p>
              <p className="filesize">{(selectedFile.size / 1024).toFixed(2)} KB</p>
              <p className="filetype">{selectedFile.type || 'Unknown format'}</p>
            </div>
          </div>
        );
    }
  };

  if (result) {
    return (
      <div className="App results-view">
        <div className="results-header">
          <div className="header-content">
            <h1>Extraction Results</h1>
            <button 
              onClick={() => {setResult(null); setSelectedFile(null); setProgress(0); setFileContent(null); setFileContentLoading(false);}}
              className="extract-another-btn"
            >
              Extract Another File
            </button>
          </div>
          
          <div className="metadata-grid">
            <div className="metadata-item">
              <span className="metadata-label">File</span>
              <span className="metadata-value">{result.filename}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">File Type</span>
              <span className="metadata-value">{result.fileType}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Method</span>
              <span className="metadata-value">{result.extractionMethod}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Characters</span>
              <span className="metadata-value">{result.characterCount?.toLocaleString() || 'N/A'}</span>
            </div>
          </div>
        </div>

        <div className="results-content">
          {/* Original Document */}
          <div className="document-panel">
            <div className="panel-header">
              <span className="panel-icon">📄</span>
              <h2>Original Document</h2>
            </div>
            <div className="panel-content">
              {renderFilePreview()}
            </div>
          </div>

          {/* Extracted Text */}
          <div className="document-panel">
            <div className="panel-header">
              {result.success ? (
                <span className="panel-icon success">✅</span>
              ) : (
                <span className="panel-icon error">❌</span>
              )}
              <h2>Extracted Text</h2>
            </div>
            
            <div className="panel-content">
              {result.success ? (
                <div className="extracted-text">
                  <pre>{result.text}</pre>
                </div>
              ) : (
                <div className="error-display">
                  <span className="error-icon">❌</span>
                  <p className="error-title">Extraction Failed</p>
                  <p className="error-message">{result.message}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App upload-view">
      <div className="upload-container">
        <div className="header">
          <span className="main-icon">🤐</span>
          <h1>Annonybara Extractor</h1>
          <p>Upload your documents and extract text with AI precision</p>
        </div>

        <div className="upload-section">
          {/* File Upload Area */}
          <div className="file-upload-area">
            <input
              type="file"
              onChange={handleFileChange}
              className="file-input"
              id="file-input"
              accept="image/*,.pdf,.xlsx,.xls,.csv,.txt"  
            />
            <label htmlFor="file-input" className="upload-label">
              {selectedFile ? (
                <div className="selected-file">
                  {getFileIcon(selectedFile)}
                  <div className="selected-file-info">
                    <p className="selected-filename">{selectedFile.name}</p>
                    <p className="selected-filesize">{(selectedFile.size / 1024).toFixed(2)} KB</p>
                  </div>
                </div>
              ) : (
                <div className="upload-prompt">
                  <span className="upload-icon">📤</span>
                  <p className="upload-text">Click to upload or drag and drop</p>
                  <p className="upload-subtext">Maximum file size: 10MB</p>
                </div>
              )}
            </label>
          </div>

          {/* Supported Formats */}
          <div className="supported-formats">
            <p className="formats-title">Supported Formats:</p>
            <div className="formats-grid">
              <div className="format-item">
                <span className="format-icon">🖼️</span>
                <span>Images: JPEG, PNG, BMP, TIFF</span>
              </div>
              <div className="format-item">
                <span className="format-icon">📄</span>
                <span>PDF Documents</span>
              </div>
              <div className="format-item">
                <span className="format-icon">📊</span>
                <span>Excel: XLS, XLSX</span>
              </div>
              <div className="format-item">
                <span className="format-icon">📋</span>
                <span>CSV Files</span>
              </div>
              <div className="format-item">
                <span className="format-icon">📝</span>
                <span>Text Files: TXT</span>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          {uploading && (
            <div className="progress-section">
              <div className="progress-info">
                <span className="progress-text">Extracting text...</span>
                <span className="progress-percent">{Math.round(progress)}%</span>
              </div>
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <div className="processing-status">
                <div className="spinner"></div>
                <span>Processing your document...</span>
              </div>
            </div>
          )}

          {/* Upload Button */}
          <button 
            onClick={handleUpload}
            disabled={uploading || !selectedFile}
            className="upload-button"
          >
            {uploading ? (
              <>
                <div className="button-spinner"></div>
                <span>Processing...</span>
              </>
            ) : (
              <>
                <span className="button-icon">📤</span>
                <span>Extract Text</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;