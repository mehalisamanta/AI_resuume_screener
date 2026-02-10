"""
File Handling Utilities
"""

import streamlit as st
import PyPDF2
import docx2txt
from config.settings import OCR_AVAILABLE

if OCR_AVAILABLE:
    import pytesseract
    from PIL import Image

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def extract_text_from_docx(docx_file):
    """Extract text from DOCX file"""
    try:
        text = docx2txt.process(docx_file)
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {str(e)}")
        return ""

def extract_text_from_image(image_file):
    """Extracts text from images using OCR"""
    if not OCR_AVAILABLE:
        st.error("OCR not available. Install with: pip install pytesseract pillow")
        return ""
    
    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        st.error(f"Error reading image with OCR: {str(e)}")
        return ""

def extract_text_from_file(uploaded_file):
    """Extract text from PDF, DOCX, or Images"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if file_ext == 'pdf':
        return extract_text_from_pdf(uploaded_file)
    elif file_ext in ['docx', 'doc']:
        return extract_text_from_docx(uploaded_file)
    elif file_ext in ['png', 'jpg', 'jpeg']:
        if OCR_AVAILABLE:
            return extract_text_from_image(uploaded_file)
        else:
            st.warning(f"OCR not available for {uploaded_file.name}. Skipping...")
            return ""
    else:
        st.error(f"Unsupported file type: {file_ext}")
        return ""