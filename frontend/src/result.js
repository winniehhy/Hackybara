import React, { useState, useEffect } from 'react';
import './result.css';

function PIIDetectionPage({ fileId, piiData: initialPiiData, extractedText, onBack }) {
  const [piiData, setPiiData] = useState(initialPiiData);
  const [loading, setLoading] = useState(!initialPiiData);
  const [error, setError] = useState(null);
  const [selectedMatches, setSelectedMatches] = useState(new Set());
  const [originalText, setOriginalText] = useState(extractedText || '');

  	// New state for tracking changes and save status
	const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
	const [lastSavedState, setLastSavedState] = useState(null);
	const [showEncryptButton, setShowEncryptButton] = useState(false);
	const [isEncrypted, setIsEncrypted] = useState(false);
	const [showKeyModal, setShowKeyModal] = useState(false);
	const [decryptionKey, setDecryptionKey] = useState('');

  // audit log state

  const [showAuditModal, setShowAuditModal] = useState(false);
const [auditLogs, setAuditLogs] = useState([]);
const [auditLoading, setAuditLoading] = useState(false);
const [auditError, setAuditError] = useState(null);
const [auditFilters, setAuditFilters] = useState({
  file_id: '',
  activity_type: '',
  limit: 50,
  offset: 0
});

  // Fetch PII data from backend if not provided
  useEffect(() => {
    const fetchPiiData = async () => {
      if (initialPiiData) {
        // Initialize with provided data
        if (initialPiiData.pii_summary && initialPiiData.pii_summary.matches) {
					const initialSelection = new Set(initialPiiData.pii_summary.matches.map((_, index) => index));
					setSelectedMatches(initialSelection);
					setLastSavedState(initialSelection);        }
        // Get original text if not provided
        if (!extractedText) {
          try {
            const docResponse = await fetch(
              process.env.NODE_ENV === 'production' 
                ? `/api/document/${fileId}` 
                : `http://127.0.0.1:5000/document/${fileId}`
            );
            if (docResponse.ok) {
              const docData = await docResponse.json();
              setOriginalText(docData.extracted_text || '');
            }
          } catch (err) {
            console.error('Error fetching original text:', err);
          }
        }
        return;
      }

      if (!fileId) {
        setError('No file ID provided');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const apiUrl = process.env.NODE_ENV === 'production' 
            ? `/api/document/${fileId}/pii` 
            : `http://127.0.0.1:5000/document/${fileId}/pii`;
          
        const response = await fetch(apiUrl);
        
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('PII data not found for this file');
          } else {
            throw new Error(`Server error: ${response.status}`);
          }
        }

        const data = await response.json();
        
        // Get original text from document endpoint
        const docResponse = await fetch(
          process.env.NODE_ENV === 'production' 
            ? `/api/document/${fileId}` 
            : `http://127.0.0.1:5000/document/${fileId}`
        );
        
        if (docResponse.ok) {
          const docData = await docResponse.json();
          setOriginalText(docData.extracted_text || '');
        }

        // Transform data to match expected format
        const transformedData = {
          ...data,
          pii_summary: {
            total_pii_found: data.pii_matches?.length || 0,
            high_confidence_count: data.pii_matches?.filter(m => m.confidence >= 0.9).length || 0,
            pii_types: {},
            matches: data.pii_matches?.map(match => ({
              text: match.text,
              type: match.type,
              position: [match.start_pos, match.end_pos],
              confidence: match.confidence
            })) || []
          }
        };

        // Calculate pii_types
        if (data.pii_matches) {
          data.pii_matches.forEach(match => {
            transformedData.pii_summary.pii_types[match.type] = 
              (transformedData.pii_summary.pii_types[match.type] || 0) + 1;
          });
        }

        setPiiData(transformedData);
        
        // Initialize selected matches with all matches selected by default
        if (transformedData.pii_summary.matches) {
					const initialSelection = new Set(transformedData.pii_summary.matches.map((_, index) => index));
					setSelectedMatches(initialSelection);
					setLastSavedState(initialSelection);
				}
        
      } catch (err) {
        console.error('Error fetching PII data:', err);
        setError(err.message || 'Failed to load PII data');
      } finally {
        setLoading(false);
      }
    };

    fetchPiiData();
  }, [fileId, initialPiiData, extractedText]);

  	// Function to check if there are unsaved changes
	const checkForUnsavedChanges = (currentSelection, currentMatches) => {
		if (!lastSavedState) return false;

		// Compare current selection with last saved state
		if (currentSelection.size !== lastSavedState.size) return true;

		for (let item of currentSelection) {
			if (!lastSavedState.has(item)) return true;
		}

		// Also check if new matches were added (length changed)
		if (currentMatches && piiData?.pii_summary?.matches) {
			if (currentMatches.length !== piiData.pii_summary.matches.length) return true;
		}

		return false;
	};

  // Handle text selection and word clicking
  const [selectedText, setSelectedText] = useState('');
  const [showPiiModal, setShowPiiModal] = useState(false);

  // Get PII type color
  const getPiiTypeColor = (type) => {
    const colors = {
      name: '#3b82f6',      // Blue
      phone: '#10b981',     // Green
      address: '#f59e0b',   // Yellow
      email: '#ef4444',     // Red
      ic: '#8b5cf6',        // Purple
      credit_card: '#f97316', // Orange
      date_of_birth: '#06b6d4', // Cyan
      driver_license: '#84cc16', // Lime
      passport: '#ec4899',  // Pink
      bank_account: '#6366f1', // Indigo
      ip_address: '#14b8a6', // Teal
      religion: '#a855f7',  // Violet
      ethnicity: '#f43f5e', // Rose
      other: '#6b7280'      // Gray
    };
    return colors[type] || colors.other;
  };

  // Get PII type icon
  const getPiiTypeIcon = (type) => {
    const icons = {
      name: '👤',
      phone: '📞',
      address: '📍',
      email: '📧',
      ic: '🆔',
      credit_card: '💳',
      date_of_birth: '🎂',
      driver_license: '🚗',
      passport: '📘',
      bank_account: '🏦',
      ip_address: '🌐',
      religion: '🕊️',
      ethnicity: '🌍',
      other: '📋'
    };
    return icons[type] || icons.other;
  };

  // Toggle PII match selection
  const togglePiiMatch = (matchIndex) => {
    const newSelected = new Set(selectedMatches);
    if (newSelected.has(matchIndex)) {
      newSelected.delete(matchIndex);
    } else {
      newSelected.add(matchIndex);
    }
    setSelectedMatches(newSelected);

	// Check for unsaved changes
	const hasChanges = checkForUnsavedChanges(newSelected, piiData.pii_summary.matches);
	setHasUnsavedChanges(hasChanges);
	if (hasChanges) {
		setShowEncryptButton(false);
	}
    
    // Update PII data
    updatePiiData(newSelected);
  };

  // Update PII data based on selected matches
  const updatePiiData = (selectedSet, matchesArray = null) => {
    const currentMatches = matchesArray || piiData.pii_summary.matches;
    const selectedMatchesArray = currentMatches.filter((_, index) => 
      selectedSet.has(index)
    );
    
    // Recalculate pii_types
    const piiTypes = {};
    selectedMatchesArray.forEach(match => {
      piiTypes[match.type] = (piiTypes[match.type] || 0) + 1;
    });
    
    const updatedData = {
      ...piiData,
      pii_summary: {
        ...piiData.pii_summary,
        total_pii_found: selectedMatchesArray.length,
        pii_types: piiTypes,
        high_confidence_count: selectedMatchesArray.filter(m => m.confidence >= 0.9).length,
        matches: matchesArray || piiData.pii_summary.matches
      }
    };
    
    setPiiData(updatedData);
  };

  const handleTextSelection = (event) => {
    const selection = window.getSelection();
    const selectedTextValue = selection.toString().trim();
    
    if (selectedTextValue && selectedTextValue.length >= 2) {
      setSelectedText(selectedTextValue);
      setShowPiiModal(true);
    }
  };

  const addNewPiiMatch = (piiType) => {
    const text = originalText;
    const selectedTextValue = selectedText;
    
    // Find the position of the selected text in the original text
    const startPos = text.indexOf(selectedTextValue);
    if (startPos === -1) {
      alert('Selected text not found in original document. Please try selecting the text again.');
      setShowPiiModal(false);
      setSelectedText('');
      window.getSelection().removeAllRanges();
      return;
    }
    
    const endPos = startPos + selectedTextValue.length;
    
    // Check if this text overlaps with existing matches
    const existingMatch = piiData.pii_summary.matches.find(match => {
      const [existingStart, existingEnd] = match.position;
      return (startPos < existingEnd && endPos > existingStart);
    });
    
    if (existingMatch) {
      alert('This text overlaps with an existing PII match. Please select different text.');
      setShowPiiModal(false);
      setSelectedText('');
      window.getSelection().removeAllRanges();
      return;
    }
    
    // Create new PII match
    const newMatch = {
      text: selectedTextValue,
      type: piiType,
      position: [startPos, endPos],
      confidence: 0.80 // Default confidence for manually added PII
    };
    
    // Add to matches array
    const updatedMatches = [...piiData.pii_summary.matches, newMatch];
    const newMatchIndex = updatedMatches.length - 1;
    
    // Update selected matches
    const newSelected = new Set(selectedMatches);
    newSelected.add(newMatchIndex);
    setSelectedMatches(newSelected);
    
	// Check for unsaved changes
	const hasChanges = checkForUnsavedChanges(newSelected, updatedMatches);
	setHasUnsavedChanges(hasChanges);
	if (hasChanges) {
		setShowEncryptButton(false);
	}

    // Update PII data
    const updatedData = {
      ...piiData,
      pii_summary: {
        ...piiData.pii_summary,
        matches: updatedMatches
      }
    };
    
    setPiiData(updatedData);
    updatePiiData(newSelected, updatedMatches);
    
    // Close modal and clear selection
    setShowPiiModal(false);
    setSelectedText('');
    window.getSelection().removeAllRanges();
  };

  // Render text with highlighted PII and clickable words
  const renderHighlightedText = () => {
    if (!originalText || !piiData?.pii_summary?.matches) {
      return <span>No text available for highlighting</span>;
    }
    
    const text = originalText;
    const matches = piiData.pii_summary.matches;
    
    // Sort matches by position to process them in order
    const sortedMatches = matches
      .map((match, index) => ({ ...match, originalIndex: index }))
      .sort((a, b) => a.position[0] - b.position[0]);
    
    let result = [];
    let lastIndex = 0;
    
    sortedMatches.forEach((match) => {
      const [start, end] = match.position;
      const isSelected = selectedMatches.has(match.originalIndex);
      
      // Add text before this match (make it selectable)
      if (start > lastIndex) {
        const textBefore = text.substring(lastIndex, start);
        result.push(
          <span key={`text-${lastIndex}`} className="selectable-text">
            {textBefore}
          </span>
        );
      }
      
      // Add the highlighted match
      result.push(
        <span
          key={`match-${match.originalIndex}`}
          className={`pii-highlight ${isSelected ? 'selected' : 'deselected'}`}
          style={{
            backgroundColor: isSelected ? getPiiTypeColor(match.type) + '30' : '#f3f4f6',
            borderBottom: isSelected ? `2px solid ${getPiiTypeColor(match.type)}` : '2px solid #d1d5db',
            color: isSelected ? getPiiTypeColor(match.type) : '#6b7280'
          }}
          onClick={() => togglePiiMatch(match.originalIndex)}
          title={`${match.type.replace('_', ' ').toUpperCase()} (${Math.round(match.confidence * 100)}% confidence) - Click to ${isSelected ? 'deselect' : 'select'}`}
        >
          {match.text}
        </span>
      );
      
      lastIndex = end;
    });
    
    // Add remaining text (make it selectable)
    if (lastIndex < text.length) {
      const remainingText = text.substring(lastIndex);
      result.push(
        <span key={`text-${lastIndex}`} className="selectable-text">
          {remainingText}
        </span>
      );
    }
    
    return result;
  };

  // Group PII types for summary
  const getGroupedPiiTypes = () => {
    if (!piiData?.pii_summary?.pii_types) return [];
    
    const types = piiData.pii_summary.pii_types;
    return Object.entries(types).map(([type, count]) => ({
      type,
      count,
      color: getPiiTypeColor(type),
      icon: getPiiTypeIcon(type)
    })).sort((a, b) => b.count - a.count);
  };

  // Save changes to backend
  const saveChanges = async () => {
    if (!fileId) {
      alert('No file ID available for saving changes');
      return;
    }

    try {
      const selectedMatchesArray = piiData.pii_summary.matches.filter((_, index) => 
        selectedMatches.has(index)
      );

      const saveData = {
        file_id: fileId,
        pii_matches: selectedMatchesArray.map(match => ({
          text: match.text,
          type: match.type,
          start_pos: match.position[0],
          end_pos: match.position[1],
          confidence: match.confidence
        })),
        pii_summary: {
          total_pii_found: selectedMatchesArray.length,
          high_confidence_count: selectedMatchesArray.filter(m => m.confidence >= 0.9).length,
          pii_types: piiData.pii_summary.pii_types
        },
		original_text: originalText
      };

    //   const response = await fetch(
    //     process.env.NODE_ENV === 'production' 
    //       ? `/api/document/${fileId}/pii` 
    //       : `http://127.0.0.1:5000/document/${fileId}/pii`,
    //     {
    //       method: 'PUT',
    //       headers: {
    //         'Content-Type': 'application/json',
    //       },
    //       body: JSON.stringify(saveData)
    //     }
    //   );

	// UPDATED ENDPOINT AND METHOD
	const apiUrl = process.env.NODE_ENV === 'production'
		? '/api/pii/save'
		: 'http://127.0.0.1:5000/api/pii/save';

	const response = await fetch(apiUrl, {
		method: 'PUT',  // Use PUT method for updates
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(saveData)
	});

	const responseData = await response.json();

			if (response.ok) {
				alert(responseData.message || 'PII changes saved successfully!');

				// Update the saved state and show encrypt button
				setLastSavedState(new Set(selectedMatches));
				setHasUnsavedChanges(false);
				setShowEncryptButton(true);

				// Update local PII data with new selection
				const updatedData = {
					...piiData,
					pii_summary: {
						...piiData.pii_summary,
						matches: saveData.pii_matches.map(m => ({
							...m,
							position: [m.start_pos, m.end_pos]
						}))
					}
				};
				setPiiData(updatedData);
			} else {
				throw new Error(responseData.error || `Failed to save changes: ${response.status}`);
			}
		} catch (error) {
			console.error('Error saving PII changes:', error);
			alert(error.message || 'Failed to save changes. Please try again.');
		}
	};

  // Export results
  const exportResults = async () => {
    const selectedMatchesArray = piiData.pii_summary.matches.filter((_, index) =>
      selectedMatches.has(index)
    );

    const exportData = {
      file_id: fileId,
      processing_timestamp: new Date().toISOString(),
      pii_summary: {
        total_pii_found: selectedMatchesArray.length,
        high_confidence_count: selectedMatchesArray.filter(m => m.confidence >= 0.9).length,
        pii_types: piiData.pii_summary.pii_types
      },
      pii_matches: selectedMatchesArray,
      original_text_length: originalText.length
    };

    try {
      const response = await fetch('http://localhost:5000/api/pii/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(exportData)
      });

      if (!response.ok) throw new Error('Failed to save results');
      alert('PII results saved to database successfully!');
    } catch (err) {
      console.error(err);
      alert('Error saving PII results.');
    }
  };

  // const exportResults = () => {
  //   const selectedMatchesArray = piiData.pii_summary.matches.filter((_, index) => 
  //     selectedMatches.has(index)
  //   );

  //   const exportData = {
  //     file_id: fileId,
  //     processing_timestamp: new Date().toISOString(),
  //     pii_summary: {
  //       total_pii_found: selectedMatchesArray.length,
  //       high_confidence_count: selectedMatchesArray.filter(m => m.confidence >= 0.9).length,
  //       pii_types: piiData.pii_summary.pii_types
  //     },
  //     pii_matches: selectedMatchesArray,
  //     original_text_length: originalText.length
  //   };

  //   const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  //   const url = URL.createObjectURL(blob);
  //   const a = document.createElement('a');
  //   a.href = url;
  //   a.download = `pii_results_${fileId}_${new Date().toISOString().split('T')[0]}.json`;
  //   document.body.appendChild(a);
  //   a.click();
  //   document.body.removeChild(a);
  //   URL.revokeObjectURL(url);
  // };

  const encryptNow = async () => {
		if (!fileId) {
			alert('No file ID available for encryption');
			return;
		}

		try {
			// Step 1: Trigger backend encryption
			const response = await fetch('http://localhost:5000/encrypt_pii', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ file_id: fileId })
			});

			if (!response.ok) throw new Error('Failed to trigger encryption');

			const result = await response.json();
			
			// Show decryption key to user
			if (result.decryption_key) {
				setDecryptionKey(result.decryption_key);
				setShowKeyModal(true);
				setIsEncrypted(true);
			} else {
				alert('Encryption successful!');
				setIsEncrypted(true);
			}

			// Step 2: Trigger file download
			const downloadUrl = `http://localhost:5000/get_tokenized_text?file_id=${fileId}`;
			const downloadResponse = await fetch(downloadUrl);

			if (!downloadResponse.ok) throw new Error('Failed to download tokenized file');

			const blob = await downloadResponse.blob();
			const url = window.URL.createObjectURL(blob);

			const link = document.createElement('a');
			link.href = url;
			link.download = `${fileId}_tokenized.txt`;
			document.body.appendChild(link);
			link.click();
			link.remove();
			window.URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Encryption or download error:', err);
			alert('Failed to encrypt or download. Please try again.');
		}
	};

	const copyToClipboard = async (text) => {
		try {
			await navigator.clipboard.writeText(text);
			alert('Decryption key copied to clipboard!');
		} catch (err) {
			console.error('Failed to copy to clipboard:', err);
			alert('Failed to copy to clipboard. Please select and copy the key manually.');
		}
	};

	const decryptText = async () => {
		if (!fileId) {
			alert('No file ID available for decryption');
			return;
		}

		// Prompt user for decryption key
		const decryptionKey = prompt('Enter your decryption key:');
		if (!decryptionKey) {
			alert('Decryption key is required');
			return;
		}

		try {
			const response = await fetch('http://localhost:5000/decrypt_pii', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ 
					file_id: fileId,
					decryption_key: decryptionKey
				})
			});

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || 'Decryption failed');
			}

			const result = await response.json();
			
			// Show decrypted text in a modal or download it
			const decryptedText = result.decrypted_text;
			
			// Create download link for decrypted text
			const blob = new Blob([decryptedText], { type: 'text/plain' });
			const url = window.URL.createObjectURL(blob);
			
			const link = document.createElement('a');
			link.href = url;
			link.download = `${fileId}_decrypted.txt`;
			document.body.appendChild(link);
			link.click();
			link.remove();
			window.URL.revokeObjectURL(url);
			
			alert(`✅ Decryption successful!\n\nDecrypted text (${result.text_length} characters) has been downloaded as "${fileId}_decrypted.txt"`);
			
		} catch (err) {
			console.error('Decryption error:', err);
			alert(`Decryption failed: ${err.message}`);
		}
	};

  // Reset to original
  	const resetToOriginal = () => {
		if (piiData?.pii_summary?.matches) {
			const originalSelection = new Set(piiData.pii_summary.matches.map((_, index) => index));
			setSelectedMatches(originalSelection);
			updatePiiData(originalSelection);

			// Check for unsaved changes
			const hasChanges = checkForUnsavedChanges(originalSelection, piiData.pii_summary.matches);
			setHasUnsavedChanges(hasChanges);
			if (hasChanges) {
				setShowEncryptButton(false);
			}
		}
	};

  // Fetch Audit Logs  ---- new add
const fetchAuditLogs = async (filters = auditFilters) => {
  setAuditLoading(true);
  setAuditError(null);
  
  try {
    const params = new URLSearchParams();
    if (filters.file_id) params.append('file_id', filters.file_id);
    if (filters.activity_type) params.append('activity_type', filters.activity_type);
    params.append('limit', filters.limit.toString());
    params.append('offset', filters.offset.toString());

    const apiUrl = process.env.NODE_ENV === 'production' 
      ? `/api/audit/logs?${params.toString()}` 
      : `http://127.0.0.1:5000/audit/logs?${params.toString()}`;

    const response = await fetch(apiUrl);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch audit logs: ${response.status}`);
    }

    const data = await response.json();
    setAuditLogs(data.logs || []);
  } catch (err) {
    console.error('Error fetching audit logs:', err);
    setAuditError(err.message || 'Failed to load audit logs');
  } finally {
    setAuditLoading(false);
  }
};

// Open audit log modal
const openAuditModal = () => {
  setShowAuditModal(true);
  setAuditFilters(prev => ({ ...prev, file_id: fileId })); // Set current file ID as default filter
  fetchAuditLogs({ ...auditFilters, file_id: fileId });
};

// Handle filter changes
const handleAuditFilterChange = (key, value) => {
  const newFilters = { ...auditFilters, [key]: value, offset: 0 }; // Reset offset when changing filters
  setAuditFilters(newFilters);
  fetchAuditLogs(newFilters);
};

// Handle pagination
const handleAuditPagination = (newOffset) => {
  const newFilters = { ...auditFilters, offset: newOffset };
  setAuditFilters(newFilters);
  fetchAuditLogs(newFilters);
};

// Format timestamp
const formatTimestamp = (timestamp) => {
  return new Date(timestamp).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

// Get activity type color
const getActivityTypeColor = (activityType) => {
  const colors = {
    'file_upload': '#10b981', // Green
    'pii_detection': '#3b82f6', // Blue
    'pii_modification': '#f59e0b', // Yellow
    'encryption': '#ef4444', // Red
    'decryption': '#8b5cf6', // Purple
    'export': '#06b6d4', // Cyan
    'error': '#f87171' // Light red
  };
  return colors[activityType] || '#6b7280'; // Gray default
};

// Get activity type icon
const getActivityTypeIcon = (activityType) => {
  const icons = {
    'file_upload': '📤',
    'pii_detection': '🔍',
    'pii_modification': '✏️',
    'encryption': '🔐',
    'decryption': '🔓',
    'export': '📥',
    'error': '❌'
  };
  return icons[activityType] || '📋';
};

  // Loading state
  if (loading) {
    return (
      <div className="pii-detection-container">
        <div className="pii-detection-content">
          <div className="pii-detection-header">
            <h1 className="pii-detection-title">PII Detection & Editing</h1>
            <p className="pii-detection-subtitle">Loading PII data...</p>
          </div>
          <div className="loading-container" style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            height: '400px',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              border: '4px solid #f3f4f6',
              borderTop: '4px solid #3b82f6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }}></div>
            <p style={{ color: '#6b7280' }}>Loading PII analysis...</p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="pii-detection-container">
        <div className="pii-detection-content">
          <div className="pii-detection-header">
            <h1 className="pii-detection-title">PII Detection & Editing</h1>
            <p className="pii-detection-subtitle">Error loading data</p>
          </div>
          <div className="error-container" style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '400px',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            <div style={{
              fontSize: '3rem',
              color: '#ef4444'
            }}>❌</div>
            <h3 style={{ color: '#ef4444', margin: 0 }}>Failed to Load PII Data</h3>
            <p style={{ color: '#6b7280', textAlign: 'center' }}>{error}</p>
            <button 
              onClick={() => window.location.reload()} 
              className="action-button primary"
              style={{ marginTop: '1rem' }}
            >
              🔄 Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // No data state
  if (!piiData || !piiData.pii_summary) {
    return (
      <div className="pii-detection-container">
        <div className="pii-detection-content">
          <div className="pii-detection-header">
            <h1 className="pii-detection-title">PII Detection & Editing</h1>
            <p className="pii-detection-subtitle">No data available</p>
          </div>
          <div className="no-data-container" style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '400px',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            <div style={{
              fontSize: '3rem',
              color: '#6b7280'
            }}>📄</div>
            <h3 style={{ color: '#6b7280', margin: 0 }}>No PII Data Found</h3>
            <p style={{ color: '#6b7280', textAlign: 'center' }}>
              No PII analysis data is available for this file.
            </p>
          </div>
        </div>
      </div>
    );
  }

  			return (
			<>
				<div className="pii-detection-container">
					<div className="pii-detection-content">
						{/* Header */}
						<div className="pii-detection-header">
							{onBack && (
								<button className="back-button" onClick={onBack}>
									← Back to Upload
								</button>
							)}
							<h1 className="pii-detection-title">PII Detection & Editing</h1>
							<p className="pii-detection-subtitle">Review and modify detected personally identifiable information (PII)</p>
							{hasUnsavedChanges && (
								<div style={{
									backgroundColor: '#fef3c7',
									color: '#92400e',
									padding: '0.5rem 1rem',
									borderRadius: '0.5rem',
									fontSize: '0.9rem',
									marginTop: '0.5rem'
								}}>
									⚠️ You have unsaved changes. Click "Save Changes" to save your modifications.
								</div>
							)}
						</div>

						<div className="pii-detection-grid">
							{/* Left Panel - Document with PII Highlights */}
							<div className="document-panel">
								<div className="panel-header">
									<h2 className="panel-title">
										📄 Document Text
										<span className="panel-subtitle">
											(Click on highlighted text to toggle PII detection)
										</span>
									</h2>
								</div>

								<div className="panel-content">
									<div className="document-text-area">
										<pre
											className="document-text"
											onMouseUp={handleTextSelection}
										>
											{renderHighlightedText()}
										</pre>
									</div>

									{/* PII Type Selection Modal */}
									{showPiiModal && (
										<>
											<div
												className="pii-modal-overlay"
												onClick={() => {
													setShowPiiModal(false);
													setSelectedText('');
													window.getSelection().removeAllRanges();
												}}
											/>
											<div
												className="pii-modal fixed-modal"
											>
												<div className="pii-modal-title">
													Categorize "{selectedText.length > 20 ? selectedText.substring(0, 20) + '...' : selectedText}" as:
												</div>
												<div className="pii-modal-options">
													{[
														{ type: 'name', icon: '👤', label: 'Name' },
														{ type: 'phone', icon: '📞', label: 'Phone Number' },
														{ type: 'address', icon: '📍', label: 'Address' },
														{ type: 'email', icon: '📧', label: 'Email' },
														{ type: 'ic', icon: '🆔', label: 'IC/NRIC' },
														{ type: 'credit_card', icon: '💳', label: 'Credit Card' },
														{ type: 'date_of_birth', icon: '🎂', label: 'Date of Birth' },
														{ type: 'passport', icon: '📘', label: 'Passport' },
														{ type: 'religion', icon: '🕊️', label: 'Religion' },
														{ type: 'ethnicity', icon: '🌍', label: 'Ethnicity' },
														{ type: 'other', icon: '📋', label: 'Other PII' }
													].map(({ type, icon, label }) => (
														<button
															key={type}
															onClick={() => addNewPiiMatch(type)}
															className="pii-modal-option"
															style={{ color: getPiiTypeColor(type) }}
														>
															<span>{icon}</span>
															<span>{label}</span>
														</button>
													))}
												</div>
											</div>
										</>
									)}

									{/* Instructions */}
									<div className="instructions-panel">
										<h4 className="instructions-title">How to use:</h4>
										<div className="instructions-list">
											<div>• <span style={{ textDecoration: 'underline' }}>Underlined text</span> = Selected as PII (will be processed)</div>
											<div>• <span style={{ textDecoration: 'line-through', color: '#6b7280' }}>Strikethrough text</span> = Deselected (will be ignored)</div>
											<div>• Click on highlighted text to toggle selection</div>
											<div>• <strong>Select any text </strong> to categorize it as new PII</div>
										</div>
									</div>
								</div>
							</div>

							{/* Right Panel - PII Summary */}
							<div className="summary-panel">
								{/* Summary Stats */}
								<div className="summary-card">
									<div className="panel-header">
										<h2 className="panel-title">
											📊 PII Summary
										</h2>
									</div>

									<div className="summary-stats">
										<div className="stats-grid">
											<div className="stat-card blue">
												<div className="stat-number blue">
													{piiData.pii_summary.total_pii_found}
												</div>
												<div className="stat-label blue">Total PII Found</div>
											</div>

											<div className="stat-card green">
												<div className="stat-number green">
													{piiData.pii_summary.high_confidence_count}
												</div>
												<div className="stat-label green">High Confidence</div>
											</div>
										</div>

										{/* PII Types Breakdown */}
										<div className="pii-types-section">
											<h3 className="pii-types-title">PII Types:</h3>
											{getGroupedPiiTypes().length > 0 ? getGroupedPiiTypes().map(({ type, count, color, icon }) => (
												<div key={type} className="pii-type-item"
													style={{ borderColor: color + '40', backgroundColor: color + '10' }}>
													<div className="pii-type-left">
														<span className="pii-type-icon">{icon}</span>
														<span className="pii-type-name" style={{ color }}>
															{type.replace('_', ' ').toUpperCase()}
														</span>
													</div>
													<div className="pii-type-right">
														<span className="pii-type-count" style={{ color }}>
															{count}
														</span>
														<span className="pii-type-found">found</span>
													</div>
												</div>
											)) : (
												<div style={{ padding: '1rem', textAlign: 'center', color: '#6b7280' }}>
													No PII types selected
												</div>
											)}
										</div>
									</div>
								</div>

								{/* Processing Details */}
								<div className="summary-card">
									<div className="panel-header">
										<h3 className="panel-title">Processing Details</h3>
									</div>

									<div className="processing-details">
										<div className="processing-item">
											<span className="processing-label">File ID:</span>
											<span className="processing-value mono">
												{fileId}
											</span>
										</div>

										<div className="processing-item">
											<span className="processing-label">Processing Time:</span>
											<span className="processing-value">
												{piiData.processing_duration?.toFixed(2) || 'N/A'}s
											</span>
										</div>

										<div className="processing-item">
											<span className="processing-label">Timestamp:</span>
											<span className="processing-value">
												{piiData.processing_timestamp
													? new Date(piiData.processing_timestamp).toLocaleString()
													: 'N/A'
												}
											</span>
										</div>
									</div>
								</div>

								{/* Actions */}
								<div className="summary-card">
									<div className="actions-panel">
										<button
											className={`action-button ${hasUnsavedChanges ? 'primary' : 'secondary'}`}
											onClick={saveChanges}
											style={{
												backgroundColor: hasUnsavedChanges ? '#3b82f6' : undefined,
												color: hasUnsavedChanges ? 'white' : undefined
											}}
										>
											💾 Save Changes {hasUnsavedChanges && '*'}
										</button>

										<button className="action-button outline" onClick={resetToOriginal}>
											🔄 Reset to Original
										</button>

										{showEncryptButton && (
											<button className="action-button danger" onClick={encryptNow}>
												🔐 Encrypt Now
											</button>
										)}

										{/* <button className="action-button outline" onClick={decryptText}>
											🔓 Decrypt Text
										</button> */}

                    <button className="action-button outline" onClick={openAuditModal}>
                        📋 View Audit Log
                    </button>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>

				{/* Decryption Key Modal */}
				{showKeyModal && (
					<div className="key-modal-overlay" onClick={() => setShowKeyModal(false)}>
						<div className="key-modal" onClick={(e) => e.stopPropagation()}>
							<div className="key-modal-header">
								<h3>🔐 Encryption Completed!</h3>
								<button 
									className="key-modal-close" 
									onClick={() => setShowKeyModal(false)}
								>
									
								</button>
							</div>
							
							<div className="key-modal-content">
								<div className="key-warning">
									⚠️ <strong>IMPORTANT:</strong> Save this decryption key securely!
								</div>
								
								<div className="key-section">
									<label>Decryption Key:</label>
									<div className="key-display">
										<input 
											type="text" 
											value={decryptionKey} 
											readOnly 
											className="key-input"
											onClick={(e) => e.target.select()}
										/>
										<button 
											className="copy-key-btn"
											onClick={() => copyToClipboard(decryptionKey)}
										>
											📋 Copy
										</button>
									</div>
								</div>
								
								<div className="key-note">
									You will need this key to decrypt the text later.
								</div>
							</div>
							
							<div className="key-modal-footer">
								<button 
									className="key-modal-ok"
									onClick={() => setShowKeyModal(false)}
								>
									OK
								</button>
							</div>
						</div>
					</div>
				)}

        {/* Audit Log Modal */}
{showAuditModal && (
  <div className="audit-modal-overlay" onClick={() => setShowAuditModal(false)}>
    <div className="audit-modal" onClick={(e) => e.stopPropagation()}>
      <div className="audit-modal-header">
        <h3>📋 Audit Log</h3>
        <button 
          className="audit-modal-close" 
          onClick={() => setShowAuditModal(false)}
        >
          ×
        </button>
      </div>
      
      {/* Filters */}
      <div className="audit-filters">
        <div className="audit-filter-row">
          <div className="audit-filter-group">
            <label>File ID:</label>
            <input
              type="text"
              value={auditFilters.file_id}
              onChange={(e) => handleAuditFilterChange('file_id', e.target.value)}
              placeholder="Filter by file ID"
              className="audit-filter-input"
            />
          </div>
          
          <div className="audit-filter-group">
            <label>Activity Type:</label>
            <select
              value={auditFilters.activity_type}
              onChange={(e) => handleAuditFilterChange('activity_type', e.target.value)}
              className="audit-filter-select"
            >
              <option value="">All Activities</option>
              {/* <option value="file_upload">File Upload</option>
              <option value="pii_detection">PII Detection</option>
              <option value="pii_modification">PII Modification</option>
              <option value="encryption">Encryption</option>
              <option value="decryption">Decryption</option>
              <option value="export">Export</option>
              <option value="error">Error</option> */}
            </select>
          </div>
          
          <div className="audit-filter-group">
            <label>Limit:</label>
            <select
              value={auditFilters.limit}
              onChange={(e) => handleAuditFilterChange('limit', parseInt(e.target.value))}
              className="audit-filter-select"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
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
                  <div className="audit-logs-container">
                    {auditLogs.map((log, index) => (
                      <div key={index} className="audit-log-item">
                        <div className="audit-log-header">
                          <div className="audit-log-type">
                            <span 
                              className="audit-type-icon"
                              style={{ color: getActivityTypeColor(log.activity_type) }}
                            >
                              {getActivityTypeIcon(log.activity_type)}
                            </span>
                            <span 
                              className="audit-type-text"
                              style={{ color: getActivityTypeColor(log.activity_type) }}
                            >
                              {log.activity_type.replace('_', ' ').toUpperCase()}
                            </span>
                          </div>
                          <div className="audit-log-timestamp">
                            {formatTimestamp(log.timestamp)}
                          </div>
                        </div>
                        
                        <div className="audit-log-details">
                          <div className="audit-log-row">
                            <strong>File ID:</strong> 
                            <span className="audit-file-id">{log.file_id}</span>
                          </div>
                          
                          {log.user_id && (
                            <div className="audit-log-row">
                              <strong>User ID:</strong> {log.user_id}
                            </div>
                          )}
                          
                          {log.details && (
                            <div className="audit-log-row">
                              <strong>Details:</strong>
                              <div className="audit-details-json">
                                {typeof log.details === 'object' ? (
                                  <pre>{JSON.stringify(log.details, null, 2)}</pre>
                                ) : (
                                  <span>{log.details}</span>
                                )}
                              </div>
                            </div>
                          )}
                          
                          {log.metadata && (
                            <div className="audit-log-row">
                              <strong>Metadata:</strong>
                              <div className="audit-metadata-json">
                                {typeof log.metadata === 'object' ? (
                                  <pre>{JSON.stringify(log.metadata, null, 2)}</pre>
                                ) : (
                                  <span>{log.metadata}</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {/* Pagination */}
                  <div className="audit-pagination">
                    <button
                      className="audit-page-btn"
                      onClick={() => handleAuditPagination(Math.max(0, auditFilters.offset - auditFilters.limit))}
                      disabled={auditFilters.offset === 0}
                    >
                      ← Previous
                    </button>
                    
                    <span className="audit-page-info">
                      Showing {auditFilters.offset + 1} - {auditFilters.offset + auditLogs.length}
                    </span>
                    
                    <button
                      className="audit-page-btn"
                      onClick={() => handleAuditPagination(auditFilters.offset + auditFilters.limit)}
                      disabled={auditLogs.length < auditFilters.limit}
                    >
                      Next →
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

			</>
		);
	}

export default PIIDetectionPage;