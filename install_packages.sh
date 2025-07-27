#!/bin/bash

echo "🚀 Installing packages for multi-format text extraction..."

# Activate virtual environment
echo "📦 Activating virtual environment..."
source backend/ocr_env/bin/activate

# Install Python packages
echo "🐍 Installing Python packages..."
pip install -r requirements.txt

echo "✅ Installation complete!"

echo "📋 Installed packages:"
echo "   - Flask & Flask-CORS (API framework)"
echo "   - pytesseract & OpenCV (Image OCR)"
echo "   - pdfplumber & pdf2image (PDF processing)"
echo "   - pandas & openpyxl (Excel/CSV processing)"
echo "   - python-magic (File type detection)"

echo ""
echo "🎯 Usage:"
echo "   1. Start backend: cd backend && source ocr_env/bin/activate && python multi_file_api.py"
echo "   2. Start frontend: cd frontend && npm start"

echo ""
echo "📁 Supported file types:"
echo "   - Images: JPEG, PNG, BMP, TIFF (OCR)"
echo "   - PDF: Text-based and scanned (OCR fallback)"
echo "   - Excel: XLS, XLSX"
echo "   - CSV files"
