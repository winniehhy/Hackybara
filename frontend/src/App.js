import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [fileContent, setFileContent] = useState(null);
  const [fileContentLoading, setFileContentLoading] = useState(false);
  const [piiStatus, setPiiStatus] = useState(null);
  const [piiResults, setPiiResults] = useState(null);
  const [showPiiResults, setShowPiiResults] = useState(false);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    setSelectedFile(file);
    setResult(null);
    setProgress(0);
    setFileContent(null);
    setPiiStatus(null);
    setPiiResults(null);
    setShowPiiResults(false);
    
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

  // Poll for PII results with improved error handling and retry logic
  const pollPiiResults = async (fileId) => {
    const maxAttempts = 60; // 60 attempts * 2 seconds = 2 minutes max
    let attempts = 0;

    const poll = async () => {
      try {
        const apiUrl = process.env.NODE_ENV === 'production' 
          ? `/api/document/${fileId}/pii` 
          : `http://localhost:5000/document/${fileId}/pii`;
          
        console.log(`Polling PII results for ${fileId}, attempt ${attempts + 1}`);
        const response = await fetch(apiUrl);
        
        if (response.ok) {
          const piiData = await response.json();
          console.log('PII detection completed:', piiData);
          setPiiResults(piiData);
          setPiiStatus('completed');
          return;
        } else if (response.status === 404) {
          // PII results not ready yet
          attempts++;
          if (attempts < maxAttempts) {
            console.log(`PII results not ready, will retry in 2 seconds (${attempts}/${maxAttempts})`);
            setTimeout(poll, 2000); // Poll every 2 seconds
          } else {
            console.log('PII detection timeout after maximum attempts');
            setPiiStatus('timeout');
          }
        } else {
          console.error('PII polling error:', response.status, response.statusText);
          setPiiStatus('error');
        }
      } catch (error) {
        console.error('Error polling PII results:', error);
        attempts++;
        if (attempts < maxAttempts) {
          console.log(`Network error, retrying in 2 seconds (${attempts}/${maxAttempts})`);
          setTimeout(poll, 2000);
        } else {
          console.log('PII detection failed after maximum attempts');
          setPiiStatus('error');
        }
      }
    };

    // Start polling immediately
    poll();
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
        
      console.log('Starting file upload and text extraction...');
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      clearInterval(progressInterval);
      setProgress(100);

      console.log('Server response:', data);

      if (data.success) {
        setResult({
          success: true,
          text: data.text,
          filename: data.filename,
          timestamp: data.timestamp,
          fileType: data.file_type,
          extractionMethod: data.extraction_method,
          characterCount: data.character_count,
          fileId: data.file_id,
          piiDetectionStatus: data.pii_detection_status
        });

        // Handle PII detection based on server response
        if (data.pii_detection_status === 'started') {
          console.log('PII detection started, beginning polling...');
          setPiiStatus('processing');
          pollPiiResults(data.file_id);
        } else if (data.pii_detection_status === 'unavailable') {
          console.log('PII detection unavailable');
          setPiiStatus('unavailable');
        } else {
          console.log('PII detection not applicable');
          setPiiStatus('not_applicable');
        }
      } else {
        setResult({
          success: false,
          message: data.message || 'Text extraction failed',
          filename: data.filename,
          fileType: data.file_type,
          extractionMethod: data.extraction_method,
          fileId: data.file_id
        });
        setPiiStatus('not_applicable');
      }
    } catch (error) {
      clearInterval(progressInterval);
      setProgress(0);
      console.error('Upload error:', error);
      setResult({
        success: false,
        message: 'Failed to connect to text extraction service'
      });
      setPiiStatus('error');
    } finally {
      setUploading(false);
    }
  };

  const readFileContent = async (file) => {
    if (!file) return null;
    
    setFileContentLoading(true);
    
    try {
      const fileType = file.type;
      
      if (fileType.startsWith('image/')) {
        const imageUrl = URL.createObjectURL(file);
        setFileContent({ type: 'image', content: imageUrl });
        return;
      }
      
      if (fileType === 'text/csv' || file.name.toLowerCase().endsWith('.csv')) {
        const text = await file.text();
        const lines = text.split('\n').slice(0, 20);
        setFileContent({ type: 'csv', content: lines.join('\n'), fullContent: text });
        return;
      }
      
      if (fileType.includes('sheet') || fileType.includes('excel') || 
          file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls')) {
        setFileContent({ 
          type: 'excel', 
          content: `Excel file: ${file.name}\nSize: ${(file.size / 1024).toFixed(2)} KB\n\nThis Excel file will be processed by the server to extract its content.` 
        });
        return;
      }
      
      if (fileType === 'application/pdf') {
        setFileContent({ 
          type: 'pdf', 
          content: `PDF file: ${file.name}\nSize: ${(file.size / 1024).toFixed(2)} KB\n\nThis PDF file will be processed by the server to extract its text content.` 
        });
        return;
      }
      
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

  const renderPiiStatus = () => {
    const getStatusIcon = () => {
      switch (piiStatus) {
        case 'processing':
          return <div className="pii-spinner"></div>;
        case 'completed':
          return <span className="status-icon success">✅</span>;
        case 'error':
        case 'timeout':
          return <span className="status-icon error">❌</span>;
        case 'unavailable':
        case 'not_applicable':
          return <span className="status-icon disabled">⚪</span>;
        default:
          return <span className="status-icon pending">⏳</span>;
      }
    };

    const getStatusText = () => {
      switch (piiStatus) {
        case 'processing':
          return 'Detecting sensitive information...';
        case 'completed':
          return 'PII Detection Complete';
        case 'error':
          return 'PII Detection Failed';
        case 'timeout':
          return 'PII Detection Timeout';
        case 'unavailable':
          return 'PII Detection Unavailable';
        case 'not_applicable':
          return 'No text to analyze';
        default:
          return 'Waiting for text extraction...';
      }
    };

    return (
      <div className="pii-status-item">
        {getStatusIcon()}
        <span className="pii-status-text">{getStatusText()}</span>
        {piiStatus === 'completed' && piiResults && (
          <button 
            onClick={() => setShowPiiResults(true)}
            className="review-pii-btn"
          >
            Review Detected PII ({piiResults.pii_summary?.total_pii_found || 0} found)
          </button>
        )}
      </div>
    );
  };

  const renderPiiModal = () => {
    if (!showPiiResults || !piiResults) return null;

    const summary = piiResults.pii_summary || {};
    const matches = piiResults.pii_matches || [];

    return (
      <div className="pii-modal-overlay" onClick={() => setShowPiiResults(false)}>
        <div className="pii-modal" onClick={e => e.stopPropagation()}>
          <div className="pii-modal-header">
            <h3>PII Detection Results</h3>
            <button 
              className="pii-modal-close"
              onClick={() => setShowPiiResults(false)}
            >
              ×
            </button>
          </div>
          
          <div className="pii-modal-content">
            <div className="pii-summary">
              <h4>Summary</h4>
              <div className="pii-summary-grid">
                <div className="pii-summary-item">
                  <span className="pii-label">Total PII Found:</span>
                  <span className="pii-value">{summary.total_pii_found || 0}</span>
                </div>
                <div className="pii-summary-item">
                  <span className="pii-label">High Confidence:</span>
                  <span className="pii-value">{summary.high_confidence_count || 0}</span>
                </div>
                <div className="pii-summary-item">
                  <span className="pii-label">Processing Time:</span>
                  <span className="pii-value">{piiResults.processing_duration?.toFixed(2)}s</span>
                </div>
                <div className="pii-summary-item">
                  <span className="pii-label">Model Used:</span>
                  <span className="pii-value">{piiResults.model_used || 'gemma3'}</span>
                </div>
              </div>
            </div>

            {matches && matches.length > 0 && (
              <div className="pii-matches">
                <h4>Detected PII Items ({matches.length})</h4>
                <div className="pii-matches-list">
                  {matches.map((match, index) => (
                    <div key={index} className="pii-match-item">
                      <div className="pii-match-header">
                        <span className="pii-type">{match.type}</span>
                        <span className={`pii-confidence ${match.confidence >= 0.8 ? 'high' : match.confidence >= 0.6 ? 'medium' : 'low'}`}>
                          Confidence: {(match.confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="pii-match-text">"{match.text}"</div>
                      <div className="pii-match-position">
                        Position: {match.start_pos} - {match.end_pos}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!matches || matches.length === 0) && (
              <div className="no-pii-found">
                <h4>✅ No PII Detected</h4>
                <p>Great! No personally identifiable information was found in this document.</p>
              </div>
            )}

            <div className="pii-modal-footer">
              <p className="pii-disclaimer">
                <strong>Note:</strong> This PII detection is automated and may not catch all sensitive information. 
                Please review the document manually for complete data privacy compliance.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (result) {
    return (
      <div className="App results-view">
        <div className="results-header">
          <div className="header-content">
            <h1>Extraction Results</h1>
            <button 
              onClick={() => {
                setResult(null); 
                setSelectedFile(null); 
                setProgress(0); 
                setFileContent(null); 
                setFileContentLoading(false);
                setPiiStatus(null);
                setPiiResults(null);
                setShowPiiResults(false);
              }}
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

        {/* Process Flow Section */}
        <div className="process-flow">
          <h2>Processing Steps</h2>
          <div className="process-steps">
            <div className="process-step completed">
              <span className="step-icon">✅</span>
              <span className="step-text">Text Extracted</span>
            </div>
            
            <span className="process-arrow">→</span>
            
            <div className={`process-step ${piiStatus === 'completed' ? 'completed' : piiStatus === 'processing' ? 'processing' : piiStatus === 'error' || piiStatus === 'timeout' ? 'error' : ''}`}>
              {renderPiiStatus()}
            </div>
            
            {piiStatus === 'completed' && (
              <>
                <span className="process-arrow">→</span>
                <div className="process-step completed">
                  <span className="step-icon">✅</span>
                  <span className="step-text">Ready for Review</span>
                </div>
              </>
            )}
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

        {/* PII Results Modal */}
        {renderPiiModal()}
      </div>
    );
  }

  return (
    <div className="App">
      <div className="upload-container">
        <div className="upload-header">
          <h1>Annoybara Extractor</h1>
          <p>Upload documents to extract text and detect sensitive information</p>
        </div>

        <div className="upload-section">
          <div className="file-input-container">
            <input
              type="file"
              id="file-input"
              onChange={handleFileChange}
              accept=".pdf,.jpg,.jpeg,.png,.bmp,.tiff,.xlsx,.xls,.csv,.txt"
              className="file-input"
            />
            <label htmlFor="file-input" className="file-input-label">
              <span className="upload-icon">📁</span>
              Choose File
            </label>
          </div>

          {selectedFile && (
            <div className="file-selected">
              <div className="file-info">
                {getFileIcon(selectedFile)}
                <div className="file-details">
                  <p className="filename">{selectedFile.name}</p>
                  <p className="filesize">{(selectedFile.size / 1024).toFixed(2)} KB</p>
                </div>
              </div>
              
              <button
                onClick={handleUpload}
                disabled={uploading}
                className="upload-btn"
              >
                {uploading ? 'Processing...' : 'Extract Text'}
              </button>
            </div>
          )}

          {uploading && (
            <div className="progress-container">
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <p className="progress-text">{Math.round(progress)}% Complete</p>
            </div>
          )}
        </div>

        {selectedFile && !uploading && (
          <div className="file-preview-container">
            <h3>File Preview</h3>
            {renderFilePreview()}
          </div>
        )}

        <div className="supported-formats">
          <h3>Supported Formats</h3>
          <div className="format-list">
            <div className="format-item">
              <span className="format-icon">🖼️</span>
              <span>Images (JPEG, PNG, BMP, TIFF)</span>
            </div>
            <div className="format-item">
              <span className="format-icon">📄</span>
              <span>PDF (text-based and scanned)</span>
            </div>
            <div className="format-item">
              <span className="format-icon">📊</span>
              <span>Excel (XLS, XLSX)</span>
            </div>
            <div className="format-item">
              <span className="format-icon">📊</span>
              <span>CSV</span>
            </div>
            <div className="format-item">
              <span className="format-icon">📄</span>
              <span>Text files (TXT)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;