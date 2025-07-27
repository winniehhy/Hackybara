# Hackybara

## 🚀 Quick Start

### 1. Install Dependencies (Local)

```bash
# Make installation script executable
chmod +x install_packages.sh

# Install all required packages
bash install_packages.sh
```

### 2. Test Installation

```bash
python test_packages.py
```

### 3. Run the Application (Local)

**Backend (Terminal 1):**
```bash
cd backend
source ocr_env/bin/activate
python multi_file_api.py
```

**Frontend (Terminal 2):**
```bash
cd frontend
npm install
npm start
```

### 4. Access the Application

Open your browser and go to [http://localhost:3000](http://localhost:3000)

---

## 🐳 Running with Docker

### Backend

```bash
cd backend
docker build -t hackybara-backend .
docker run -d -p 5000:5000 --name hackybara-backend hackybara-backend
```

### Frontend

You can use a simple Node-based container, or run locally as above.  
For development, it's common to run the frontend locally with `npm start`.

---

## 📦 Required Packages

### Python (Backend)
- **Flask & Flask-CORS**: Web API framework
- **pytesseract & OpenCV**: Image OCR processing
- **pdfplumber & pdf2image**: PDF text extraction
- **pandas & openpyxl**: Excel/CSV processing
- **python-magic**: File type detection
- **PIL/Pillow**: Image processing

### Node.js (Frontend)
- **React**: Frontend framework
- **Standard React dependencies**

---

## 🔧 How It Works

1. **File Upload**: Users can upload images, PDFs, Excel files, or CSV files
2. **File Type Detection**: The system automatically detects the file type
3. **Smart Processing**:
   - **Images**: Direct OCR using pytesseract + OpenCV preprocessing
   - **Text PDFs**: Direct text extraction using pdfplumber
   - **Scanned PDFs**: OCR fallback using pdf2image + pytesseract
   - **Excel**: Data extraction using pandas + openpyxl
   - **CSV**: Data parsing using pandas
4. **Results**: Extracted text is displayed with processing details

---

## 🛠️ API Endpoints

- `POST /extract`: Upload and process file
- `GET /health`: Service health check

---

## 📁 Project Structure

```
Hackybara/
├── backend/
│   ├── multi_file_api.py      # Main API with multi-format support
│   ├── flask_api.py           # Original image-only API
│   ├── ocr_env/               # Python virtual environment
│   ├── uploads/               # Temporary file storage
│   └── Dockerfile             # Backend Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.js             # Updated React app
│   │   └── App.css            # Styling
│   └── public/
│   └── package.json           # Frontend dependencies
├── requirements.txt           # Python dependencies
├── install_packages.sh        # Installation script
└── test_packages.py           # Package verification script
```