"""
AI-Powered Resume Screening System
Main Application File
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

from utils.file_handlers import extract_text_from_file
from utils.groq_client import init_groq_client, parse_resume_with_groq, extract_jd_requirements, match_candidates_with_jd, generate_interview_questions
from utils.preprocessing import automated_pre_screen, save_rejected_to_csv
from utils.scoring import calculate_semantic_score
from config.settings import PAGE_CONFIG, CUSTOM_CSS, OCR_AVAILABLE, TFIDF_AVAILABLE, SHAREPOINT_AVAILABLE
from ui.tabs import render_upload_tab, render_database_tab, render_matching_tab, render_analytics_tab

# Page Configuration
st.set_page_config(**PAGE_CONFIG)

# Custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    """Initialize all session state variables"""
    if 'parsed_resumes' not in st.session_state:
        st.session_state.parsed_resumes = []
    if 'candidates_df' not in st.session_state:
        st.session_state.candidates_df = None
    if 'matched_results' not in st.session_state:
        st.session_state.matched_results = None
    if 'resume_texts' not in st.session_state:
        st.session_state.resume_texts = {}
    if 'jd_requirements' not in st.session_state:
        st.session_state.jd_requirements = None
    if 'rejected_candidates' not in st.session_state:
        st.session_state.rejected_candidates = []
    if 'sharepoint_config' not in st.session_state:
        st.session_state.sharepoint_config = None

def render_sidebar():
    """Render the sidebar with configuration options"""
    with st.sidebar:
        st.title("⚙️ Configuration")
        
        # API Key Input
        groq_api_key = st.text_input(
            "🔑 Groq API Key",
            type="password",
            value=st.session_state.get('groq_api_key', ''),
            help="Get free key: https://console.groq.com"
        )
        
        client = None
        if groq_api_key:
            st.session_state['groq_api_key'] = groq_api_key
            try:
                client = init_groq_client(groq_api_key)
                st.success("✅ Connected")
            except:
                st.error("❌ Invalid Key")
        else:
            st.warning("⚠️ Enter API Key")
        
        st.divider()
        
        # PII Masking Toggle
        st.subheader("🛡️ Privacy Settings")
        mask_pii_enabled = st.checkbox("Enable PII Masking", value=True, 
                                       help="Redact emails and phone numbers before sending to LLM")
        
        st.divider()
        
        # Date Range Filtering
        st.subheader("📅 Date Range Filter")
        st.info("Filter resumes by submission date")
        
        default_start = datetime.now() - timedelta(days=30)
        default_end = datetime.now()
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From", value=default_start)
        with col2:
            end_date = st.date_input("To", value=default_end)
        
        if start_date > end_date:
            st.error("⚠️ Start date must be before end date")
        
        st.divider()
        
        # Top Candidates Selection
        st.subheader("🎚️ Top Candidates")
        top_n = st.select_slider(
            "Select number",
            options=[1, 2, 3, 5, 10, 15, 20],
            value=5
        )
        
        if top_n <= 3:
            st.warning("⚡ Urgent Interview!")
        elif top_n <= 5:
            st.info("📅 Standard - 2 weeks")
        else:
            st.success("🕐 Flexible mode")
        
        # Feature availability status
        st.divider()
        st.subheader("📦 Features Status")
        st.write("✅ Core Features: Active")
        st.write("✅ OCR: Available" if OCR_AVAILABLE else "⚠️ OCR: Not installed")
        st.write("✅ Semantic Scoring: Available" if TFIDF_AVAILABLE else "⚠️ TF-IDF: Not installed")
        st.write("✅ SharePoint: Available" if SHAREPOINT_AVAILABLE else "⚠️ SharePoint: Not installed")
        
        return client, mask_pii_enabled, start_date, end_date, top_n

def render_header():
    """Render application header with logo"""
    import os
    try:
        logo_path = "company_logo.png"
        if os.path.exists(logo_path):
            st.markdown('<div class="logo-container">', unsafe_allow_html=True)
            st.image(logo_path, width=200)
            st.markdown('</div>', unsafe_allow_html=True)
    except:
        pass
    
    st.markdown('<h1 class="main-header">AI Resume Screening System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">⚡ Powered by Groq | Ultra-Fast AI Processing</p>', unsafe_allow_html=True)

def main():
    """Main application function"""
    # Initialize session state
    init_session_state()
    
    # Render header
    render_header()
    
    # Render sidebar and get configuration
    client, mask_pii_enabled, start_date, end_date, top_n = render_sidebar()
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "📊 Database", "🎯 Match", "📈 Analytics"])
    
    # Render tabs
    with tab1:
        render_upload_tab(client, mask_pii_enabled)
    
    with tab2:
        render_database_tab(start_date, end_date)
    
    with tab3:
        render_matching_tab(client, start_date, end_date, top_n)
    
    with tab4:
        render_analytics_tab()
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🚀 AI Resume Screening System | Built with Streamlit & Groq</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()