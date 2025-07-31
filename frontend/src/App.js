import React, { useState, useEffect } from 'react';
import './App.css';
import PIIDetectionPage from './result';
import hackybaraLogo from './hackybara_logo.png'; 

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
  const [showPiiEditor, setShowPiiEditor] = useState(false);
  
  // New state for main navigation
  const [currentMode, setCurrentMode] = useState('main'); // 'main', 'encrypt', 'decrypt'
  const [decryptFileId, setDecryptFileId] = useState('');
  const [decryptKey, setDecryptKey] = useState('');
  const [decryptResult, setDecryptResult] = useState(null);
  const [decryptLoading, setDecryptLoading] = useState(false);
  const [encryptionCompleted, setEncryptionCompleted] = useState(false);

  // Audit summary state
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState(null);
  const [showAuditSummaryTable, setShowAuditSummaryTable] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [auditFilters, setAuditFilters] = useState({
    file_id: '',
    activity_type: '',
    limit: 500,
    offset: 0
  });

  // State to control visibility of "View Audit Log" button
  const [showAuditButton, setShowAuditButton] = useState(false);

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

  const pollPiiResults = async (fileId) => {
    const maxAttempts = 60;
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
          attempts++;
          if (attempts < maxAttempts) {
            console.log(`PII results not ready, will retry in 2 seconds (${attempts}/${maxAttempts})`);
            setTimeout(poll, 2000);
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

    poll();
  };

  const fetchAuditLogs = async (filters = auditFilters) => {
    setAuditLoading(true);
    setAuditError(null);
    try {
      const params = new URLSearchParams({
        file_id: filters.file_id,
        activity_type: filters.activity_type,
        limit: filters.limit,
        offset: filters.offset
      });
      const response = await fetch(`http://localhost:5000/audit/logs?${params}`);
      if (!response.ok) throw new Error('Failed to fetch audit logs');
      const data = await response.json();
      setAuditLogs(data.logs || []);
    } catch (err) {
      setAuditError(err.message || 'Failed to load audit logs');
    } finally {
      setAuditLoading(false);
    }
  };

  // Handle filter changes
  const handleAuditFilterChange = (field, value) => {
    const newFilters = { ...auditFilters, [field]: value, offset: 0 };
    setAuditFilters(newFilters);
    fetchAuditLogs(newFilters);
  };

  // Handle pagination
  const handleAuditPagination = (newOffset) => {
    const newFilters = { ...auditFilters, offset: newOffset };
    setAuditFilters(newFilters);
    fetchAuditLogs(newFilters);
  };

  // Open modal and fetch logs for current file
  const openAuditModal = () => {
    setShowAuditModal(true);
    setAuditFilters({
      file_id: decryptFileId || '',
      activity_type: '',
      limit: 1000,
      offset: 0
    });
    fetchAuditLogs({
      file_id: decryptFileId || '',
      activity_type: '',
      limit: 1000,
      offset: 0
    });
  };

  const handleDecrypt = async () => {
    if (!decryptFileId || !decryptKey) {
      alert('Please enter both File ID and Decryption Key');
      return;
    }

    setDecryptLoading(true);
    setDecryptResult(null);
    setShowAuditSummaryTable(false);

    try {
      const response = await fetch('http://localhost:5000/decrypt_pii', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          file_id: decryptFileId,
          decryption_key: decryptKey
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Decryption failed');
      }

      const result = await response.json();
      setDecryptResult(result);

      // Download the decrypted text
      const blob = new Blob([result.decrypted_text], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${decryptFileId}_decrypted.txt`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      // Fetch audit logs after successful decryption
      fetchAuditLogs(decryptFileId);

      // Show the audit button after decryption attempt
      setShowAuditButton(true);

    } catch (err) {
      console.error('Decryption error:', err);
      alert(`Decryption failed: ${err.message}`);
      // Still show the audit button even if decryption fails
      setShowAuditButton(true);
    } finally {
      setDecryptLoading(false);
    }
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
            onClick={() => {
              setShowPiiResults(false);
              setShowPiiEditor(true);
            }}
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
  
  if (showPiiEditor && piiResults && result) {
    return (
      <PIIDetectionPage
        fileId={result.fileId}
        piiData={piiResults}
        extractedText={result.text}
      />
    );
  }

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
          </div>
        </div>

        <div className="results-content">
          <div className="document-panel">
            <div className="panel-header">
              <span className="panel-icon">📄</span>
              <h2>Original Document</h2>
            </div>
            <div className="panel-content">
              {renderFilePreview()}
            </div>
          </div>

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

        {renderPiiModal()}
      </div>
    );
  }

  const renderAuditSummary = () => {
    if (!showAuditSummaryTable) {
      return (
        <button
          className="audit-summary-btn"
          style={{ marginTop: '1rem' }}
          onClick={() => setShowAuditSummaryTable(true)}
          disabled={auditLoading || auditLogs.length === 0}
        >
          📋 View Audit Summary
        </button>
      );
    }
    if (auditLoading) return <div>Loading audit summary...</div>;
    if (auditError) return <div style={{ color: 'red' }}>Error: {auditError}</div>;
    if (!auditLogs.length) return <div>No audit logs found for this file.</div>;

    return (
      <div className="audit-summary">
        <h3>📋 Audit Summary for File</h3>
        <button
          className="audit-summary-btn"
          style={{ float: 'right', marginBottom: '0.5rem' }}
          onClick={() => setShowAuditSummaryTable(false)}
        >
          Close
        </button>
        <table className="audit-table">
          <thead>
            <tr>
              <th>Activity</th>
              <th>Status</th>
              <th>Timestamp</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {auditLogs.map((log, idx) => (
              <tr key={idx}>
                <td>{log.activity_type}</td>
                <td>{log.status || '-'}</td>
                <td>{log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}</td>
                <td>
                  {log.details && typeof log.details === 'object'
                    ? <pre style={{ maxWidth: 200, whiteSpace: 'pre-wrap' }}>{JSON.stringify(log.details, null, 1)}</pre>
                    : (log.details || '-')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  // Main navigation component
  const renderMainMenu = () => {
    return (
      <div className="main-menu">
        <div className="main-header">
          <div className="logo-container">
            <img src={hackybaraLogo} alt="Hackybara Logo" className="main-logo" />
          </div>
          <h1>Anonybara</h1>
          <p>Privacy Shouldn't Be Optional</p>
        </div>
        
        <div className="menu-options">
          <div className="menu-option" onClick={() => setCurrentMode('encrypt')}>
            <div className="option-icon">🔒</div>
            <div className="option-content">
              <h3>Encrypt Text</h3>
              <p>Upload a document, detect PII, and encrypt sensitive information</p>
              <ul>
                <li>Upload PDF, images, or text files</li>
                <li>AI-powered PII detection</li>
                <li>Select which PII to encrypt</li>
                <li>Get encrypted file and decryption key</li>
              </ul>
            </div>
          </div>
          
          <div className="menu-option" onClick={() => setCurrentMode('decrypt')}>
            <div className="option-icon">🔓</div>
            <div className="option-content">
              <h3>Decrypt Text</h3>
              <p>Decrypt previously encrypted text using your decryption key</p>
              <ul>
                <li>Enter File ID and decryption key</li>
                <li>Restore original text with PII</li>
                <li>Download decrypted file</li>
                <li>Secure and fast decryption</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderAuditModal = () => {
    if (!showAuditModal) return null;
    return (
      <div className="audit-modal-overlay" onClick={() => setShowAuditModal(false)}>
        <div className="audit-modal" onClick={e => e.stopPropagation()}>
          <div className="audit-modal-header">
            <h3>📋 Audit Log</h3>
            <button className="audit-modal-close" onClick={() => setShowAuditModal(false)}>×</button>
          </div>
          {/* Filters */}
          <div className="audit-filters">
            <div className="audit-filter-row">
              <div className="audit-filter-group">
                <label>File ID:</label>
                <input
                  type="text"
                  value={auditFilters.file_id}
                  onChange={e => handleAuditFilterChange('file_id', e.target.value)}
                  placeholder="Filter by file ID"
                  className="audit-filter-input"
                />
              </div>
              <div className="audit-filter-group">
                <label>Activity Type:</label>
                <select
                  value={auditFilters.activity_type}
                  onChange={e => handleAuditFilterChange('activity_type', e.target.value)}
                  className="audit-filter-select"
                >
                  <option value="">All Activities</option>
                </select>
              </div>
              <div className="audit-filter-group">
                <label>Limit:</label>
                <select
                  value={auditFilters.limit}
                  onChange={e => handleAuditFilterChange('limit', parseInt(e.target.value))}
                  className="audit-filter-select"
                >
                  <option value={500}>500</option>
                  <option value={1000}>1000</option>
                  <option value={5000}>5000</option>
                </select>
              </div>
            </div>
          </div>
          <div className="audit-modal-content">
            {auditLoading ? (
              <div className="audit-loading">
                <div className="loading-spinner"></div>
                <p>Loading audit logs...</p>
              </div>
            ) : auditError ? (
              <div className="audit-error">
                <p>❌ {auditError}</p>
                <button onClick={() => fetchAuditLogs()} className="retry-btn">
                  🔄 Retry
                </button>
              </div>
            ) : auditLogs.length === 0 ? (
              <div className="audit-empty">
                <p>📭 No audit logs found</p>
              </div>
            ) : (
              <>
                <div className="audit-logs-container" style={{ maxHeight: 400, overflowY: 'auto' }}>
                  {auditLogs.map((log, index) => (
                    <div key={index} className="audit-log-item" style={{
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      marginBottom: '1rem',
                      padding: '1rem',
                      background: '#fff'
                    }}>
                      <div className="audit-log-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div>
                          <strong style={{ color: '#2563eb' }}>{log.activity_type.replace('_', ' ').toUpperCase()}</strong>
                        </div>
                        <div style={{ color: '#6b7280', fontSize: '0.9em' }}>
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}
                        </div>
                      </div>
                      <div className="audit-log-details" style={{ marginTop: '0.5rem' }}>
                        <div><strong>File ID:</strong> {log.file_id}</div>
                        {log.details && (
                          <div>
                            <strong>Details:</strong>
                            <pre style={{ background: '#f3f4f6', borderRadius: 4, padding: 8, margin: 0 }}>
                              {typeof log.details === 'object'
                                ? JSON.stringify(log.details, null, 2)
                                : log.details}
                            </pre>
                          </div>
                        )}
                        {log.metadata && (
                          <div>
                            <strong>Metadata:</strong>
                            <pre style={{ background: '#f3f4f6', borderRadius: 4, padding: 8, margin: 0 }}>
                              {typeof log.metadata === 'object'
                                ? JSON.stringify(log.metadata, null, 2)
                                : log.metadata}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                {/* Pagination */}
                <div className="audit-pagination" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <span className="audit-page-info">
                      Showing {auditLogs.length === 0 ? 0 : auditFilters.offset + 1} - {auditFilters.offset + auditLogs.length}
                    </span>
                
                  </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  // Decryption interface component
  // Only show "View Audit Log" button after decryption attempt
  const renderDecryptInterface = () => {
    return (
      <div className="decrypt-interface">
        <div className="decrypt-header">
          <button className="back-button" onClick={() => setCurrentMode('main')}>
            ← Back to Main Menu
          </button>
          <h2>🔓 Decrypt Text</h2>
          <p>Enter your File ID and decryption key to restore the original text</p>
        </div>
        
        <div className="decrypt-form-fields">
          <div className="form-group">
            <label htmlFor="decrypt-file-id">File ID</label>
            <input
              id="decrypt-file-id"
              type="text"
              value={decryptFileId}
              onChange={e => setDecryptFileId(e.target.value)}
              placeholder="Enter the File ID (e.g., 32-617f-48b0-8f5a-7960e6b69a8)"
              className="decrypt-input"
              autoComplete="off"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="decrypt-key">Decryption Key</label>
            <input
              id="decrypt-key"
              type="password"
              value={decryptKey}
              onChange={e => setDecryptKey(e.target.value)}
              placeholder="Enter your decryption key"
              className="decrypt-input"
              autoComplete="off"
            />
          </div>
          
          <button
            className="decrypt-btn"
            onClick={handleDecrypt}
            disabled={decryptLoading || !decryptFileId || !decryptKey}
          >
            {decryptLoading ? (
              <>
                <div className="loading-spinner" style={{ width: '16px', height: '16px' }}></div>
                Decrypting...
              </>
            ) : (
              <>
                🔓 Decrypt Text
              </>
            )}
          </button>
        </div>

        {/* Secondary Actions - Only show after decryption attempt */}
        {showAuditButton && (
          <div className="decrypt-secondary-actions">
            <button
              className="audit-summary-btn"
              onClick={openAuditModal}
              disabled={auditLoading}
            >
              📋 View Audit Log
            </button>
          </div>
        )}

        {/* Decrypt Result - if exists */}
        {decryptResult && (
          <div className="decrypt-result">
            <h3>✅ Decryption Successful</h3>
            <div className="result-details">
              <p><strong>File ID:</strong> {decryptResult.file_id}</p>
              <p><strong>Characters:</strong> {decryptResult.character_count?.toLocaleString()}</p>
              <p><strong>File Downloaded:</strong> {decryptResult.file_id}_decrypted.txt</p>
            </div>
            
            {decryptResult.decrypted_text && (
              <div className="decrypted-preview">
                <h4>Preview (first 500 characters):</h4>
                <div className="preview-text">
                  {decryptResult.decrypted_text.substring(0, 500)}
                  {decryptResult.decrypted_text.length > 500 && '...'}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Audit Modal */}
        {renderAuditModal()}
      </div>
    );
  };

  if (currentMode === 'main') {
    return renderMainMenu();
  } else if (currentMode === 'decrypt') {
    return renderDecryptInterface();
  } else if (showPiiEditor && piiResults) {
    return (
      <PIIDetectionPage 
        fileId={result?.file_id} 
        piiData={piiResults} 
        extractedText={fileContent}
        onBack={() => {
          setShowPiiEditor(false);
          setCurrentMode('encrypt');
        }}
      />
    );
  }

  return (
    <div className="App">
      <div className="upload-container">
        <div className="upload-header">
          <button className="back-button" onClick={() => setCurrentMode('main')}>
            ← Back to Main Menu
          </button>
          <h1>🔒 Encrypt Text - Anonybara Extractor</h1>
          <p>Upload documents to extract text, detect PII, and encrypt sensitive information</p>
        </div>

        <div className="upload-section">
          <div className="file-input-container">
            <input
              type="file"
              id="file-input"
              onChange={handleFileChange}
              accept=".pdf,.jpg,.jpeg,.png,.txt"
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
              <span>Images (JPEG, PNG)</span>
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