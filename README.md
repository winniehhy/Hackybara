<img width="347" height="288" alt="image" src="https://github.com/user-attachments/assets/1cfcbb2b-e536-471c-9008-c81c5f5de749" />

---

# Anonybara

## 📝 Problem Statement: Data Privacy Protector

Unstructured documents such as PDFs, images, spreadsheets, and text files frequently contain sensitive Personally Identifiable Information (PII). Organizations face significant challenges in detecting and redacting this data automatically. Manual review and redaction are not only time-consuming and costly, but also prone to human error and inconsistency. As regulations around data privacy become stricter, there is a growing need for reliable, automated solutions to protect sensitive information before documents are shared with third parties.

---

## 💡 Solution Overview

Anonybara is an all-in-one platform designed to streamline the process of extracting, detecting, and redacting PII from a wide range of document formats. Inspired by the simplicity and utility of platforms like iLovePDF, Anonybara empowers users to upload their files and receive automated, privacy-protected outputs in just a few steps.

**Key Features:**

- **Multi-format Support:** Users can upload images (JPEG, PNG, BMP, TIFF), PDFs (text-based and scanned), Excel spreadsheets, CSVs, and plain text files.
  
- **Automated Text Extraction:** The system leverages OCR (Optical Character Recognition) for images and scanned PDFs, and direct parsing for text-based documents and spreadsheets, ensuring accurate extraction of textual content from any supported file.
  
- **PII Detection:** Using LLM Gemma3 model and Regex, Anonybara automatically scans the extracted text for a wide range of PII types, including names, addresses, phone numbers, emails, identification numbers, and more.
  
- **Redaction Workflow:** Detected PII is highlighted for user review. Users can accept, reject, or manually adjust detected PII before finalizing the document, ensuring both automation and human oversight.
  
- **Audit Logging:** Every action, from file upload to PII review, is logged for transparency and compliance, supporting organizational data governance needs.
- **User-Friendly Interface:** The React-based frontend provides a clean, intuitive workflow, making it easy for users of all technical backgrounds to protect sensitive data.

Anonybara reduces the risk of accidental data leaks, saves time, and helps organizations comply with data privacy regulations by automating the most tedious parts of the document privacy workflow.

---

## 🛠️ Tech Stack

- **Frontend:** React (JavaScript)
- **Backend API:** Flask (Python)
- **OCR & Document Processing:** pytesseract, OpenCV, pdfplumber, pdf2image, pandas, openpyxl, python-magic
- **PII Detection:** Ollama Gemma3
- **Database:** SQLite
- **Encryption** aes-gcm

  <img width="938" height="492" alt="image" src="https://github.com/user-attachments/assets/bff8a65b-2459-4092-8059-96e7bb0ff245" />


## Presentation
- **Link for Slides :** https://www.canva.com/design/DAGugv5LxqU/1FzVIqDKnh7kTit_8Cfpyw/edit?utm_content=DAGugv5LxqU&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton
-  **Link for Demo Video :**


---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/winniehhy/Hackybara.git
cd Hackybara
```

### 2. Install Backend & Frontend Dependencies

```bash
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

#### Pull and Run a Model (gemma3)

```bash
docker exec -it ollama ollama run gemma3
```

> For more models and details, see: [Ollama Library](https://ollama.com/library) and [Ollama GitHub](https://github.com/ollama/ollama)

---

### 4. Start the Application

**Backend (Terminal 1):**
```bash
cd backend
source ocr_env/bin/activate
python3 multi_file_api.py
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

## 👤 Team Members

- Winnie Heng Han Yee
- Tay Qi Ter
- Adya Zahila



