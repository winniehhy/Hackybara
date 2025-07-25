from flask import Flask, request, jsonify
from flask_cors import CORS
import pytesseract
from PIL import Image
import os
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def extract_text_from_image(image_path):
    """
    Extract text from an image using Tesseract OCR
    """
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"Error processing image: {e}")
        return None

def save_output_to_file(content, filename="output.txt"):
    """
    Save content to a text file
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error saving to file: {e}")
        return False

@app.route('/ocr', methods=['POST'])
def perform_ocr():
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        # Save the uploaded file
        file.save(file_path)
        
        # Process with OCR
        extracted_text = extract_text_from_image(file_path)
        
        # Prepare output content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output_content = f"OCR Processing Report\n"
        output_content += f"Timestamp: {timestamp}\n"
        output_content += f"Original filename: {file.filename}\n"
        output_content += f"Processed file: {unique_filename}\n"
        output_content += "="*50 + "\n\n"
        
        if extracted_text:
            output_content += "EXTRACTED TEXT:\n"
            output_content += "="*50 + "\n"
            output_content += extracted_text + "\n"
            output_content += "="*50 + "\n"
            
            # Save output to file
            output_filename = f"ocr_output_{uuid.uuid4().hex[:8]}.txt"
            save_output_to_file(output_content, output_filename)
            
            # Clean up uploaded file (optional)
            os.remove(file_path)
            
            return jsonify({
                'success': True,
                'text': extracted_text,
                'filename': file.filename,
                'output_file': output_filename,
                'timestamp': timestamp
            })
        else:
            output_content += "No text could be extracted from the image.\n"
            save_output_to_file(output_content, f"ocr_output_{uuid.uuid4().hex[:8]}.txt")
            
            # Clean up uploaded file
            os.remove(file_path)
            
            return jsonify({
                'success': False,
                'message': 'No text could be extracted from the image',
                'filename': file.filename
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)