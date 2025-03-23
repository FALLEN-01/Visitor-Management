from flask import Flask
import sys
import os

# Add parent directory to path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the Flask app instance
from app import app as flask_app

# This is required for Vercel serverless functions
app = flask_app

# This is the handler Vercel will invoke

