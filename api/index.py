from flask import Flask, request, jsonify, send_from_directory
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from flask_api import app

# This is the main entry point for Vercel
if __name__ == "__main__":
    app.run(debug=True)