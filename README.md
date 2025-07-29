# Hackybara

## 📝 Problem Statement: Data Privacy Protector

Unstructured documents such as PDFs, images, spreadsheets, and text files frequently contain sensitive Personally Identifiable Information (PII). Organizations face significant challenges in detecting and redacting this data automatically. Manual review and redaction are not only time-consuming and costly, but also prone to human error and inconsistency. As regulations around data privacy become stricter, there is a growing need for reliable, automated solutions to protect sensitive information before documents are shared with third parties.

---

## 💡 Solution Overview

Annoybara is an all-in-one platform designed to streamline the process of extracting, detecting, and redacting PII from a wide range of document formats. Inspired by the simplicity and utility of platforms like iLovePDF, Annoybara empowers users to upload their files and receive automated, privacy-protected outputs in just a few steps.

**Key Features:**

- **Multi-format Support:** Users can upload images (JPEG, PNG, BMP, TIFF), PDFs (text-based and scanned), Excel spreadsheets, CSVs, and plain text files.
- **Automated Text Extraction:** The system leverages OCR (Optical Character Recognition) for images and scanned PDFs, and direct parsing for text-based documents and spreadsheets, ensuring accurate extraction of textual content from any supported file.
- **PII Detection:** Using advanced machine learning models, Annoybara automatically scans the extracted text for a wide range of PII types, including names, addresses, phone numbers, emails, identification numbers, and more.
- **Redaction Workflow:** Detected PII is highlighted for user review. Users can accept, reject, or manually adjust detected PII before finalizing the document, ensuring both automation and human oversight.
- **Audit Logging:** Every action, from file upload to PII review, is logged for transparency and compliance, supporting organizational data governance needs.
- **User-Friendly Interface:** The React-based frontend provides a clean, intuitive workflow, making it easy for users of all technical backgrounds to protect sensitive data.

**How It Works:**

1. **Upload:** Users drag and drop or select files to upload.
2. **Extraction:** The backend automatically extracts text using the best method for the file type (OCR for images, parsing for text-based files).
3. **PII Detection:** Extracted text is analyzed for PII using a dedicated detection module.
4. **Review & Redact:** Users review detected PII, make adjustments, and approve redactions.
5. **Export:** The privacy-protected document is ready for safe sharing, with all actions logged for compliance.

Annoybara reduces the risk of accidental data leaks, saves time, and helps organizations comply with data privacy regulations by automating the most tedious parts of the document privacy workflow.

---

## 🛠️ Tech Stack

- **Frontend:** React (JavaScript)
- **Backend API:** Flask (Python)
- **OCR & Document Processing:** pytesseract, OpenCV, pdfplumber, pdf2image, pandas, openpyxl, python-magic
- **PII Detection:** Ollama Gemma3
- **Database:** SQLite
- **Encryption** aes-gcm

## 🚀 Quick Start: One-Shot Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Hackybara.git
cd Hackybara
```

### 2. Install Backend & Frontend Dependencies

```bash
# Make the install script executable and run it
chmod +x install_packages.sh
bash install_packages.sh
```

### 3. Set Up Ollama (PII Detection Engine)

#### CPU Only

```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

#### Nvidia GPU

```bash
# Install NVIDIA Container Toolkit (Ubuntu/Debian)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use Nvidia runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Start Ollama with GPU support
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

#### AMD GPU

```bash
docker run -d --device /dev/kfd --device /dev/dri -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama:rocm
```

#### Pull and Run a Model (e.g., Llama3)

```bash
docker exec -it ollama ollama run llama3
```

> For more models and details, see: [Ollama Library](https://ollama.com/library) and [Ollama GitHub](https://github.com/ollama/ollama)

---

### 4. Start the Application

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

### 5. Access the App

Open your browser at [http://localhost:3000](http://localhost:3000)

---

