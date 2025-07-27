#!/usr/bin/env python3

import sys
import importlib

def test_package(package_name, import_name=None):
    """Test if a package can be imported"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        print(f"✅ {package_name}")
        return True
    except ImportError as e:
        print(f"❌ {package_name} - {e}")
        return False

def main():
    print("🧪 Testing package installations...\n")
    
    packages = [
        ("Flask", "flask"),
        ("Flask-CORS", "flask_cors"),
        ("pytesseract", "pytesseract"),
        ("OpenCV", "cv2"),
        ("PIL/Pillow", "PIL"),
        ("NumPy", "numpy"),
        ("pdfplumber", "pdfplumber"),
        ("pdf2image", "pdf2image"),
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("python-magic", "magic"),
    ]
    
    results = []
    for package_name, import_name in packages:
        results.append(test_package(package_name, import_name))
    
    print(f"\n📊 Results: {sum(results)}/{len(results)} packages installed successfully")
    
    if all(results):
        print("🎉 All packages are ready! You can start the application.")
    else:
        print("⚠️  Some packages are missing. Run the installation script first.")
        print("   Command: bash install_packages.sh")

if __name__ == "__main__":
    main()
