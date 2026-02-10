import streamlit as st
import pandas as pd
import json
import re
import io
from datetime import datetime
from typing import Dict
from groq import Groq

import PyPDF2
import docx2txt
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Import your custom modules
from config import settings
from sharepoint_uploader import SharePointUploader

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="AI Resume Screening System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------------------------------
# STYLES
# --------------------------------------------------
st.markdown("""
<style>
.main-header { font-size: 3rem; font-weight: bold; text-align: center; padding: 20px 0; }
.sub-header { text-align: center; color: #555; font-size: 1.2rem; margin-bottom: 30px; }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# INITIALIZATION
# --------------------------------------------------
@st.cache_resource
def init_groq_client():
    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing in environment/secrets")
    return Groq(api_key=api_key)

@st.cache_resource
def init_sharepoint():
    try:
        settings.validate()
        return SharePointUploader(
            tenant_id=settings.TENANT_ID,
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET
        )
    except Exception as e:
        st.sidebar.error(f"SharePoint Config Error: {e}")
        return None

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def mask_pii(text: str) -> str:
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text

def extract_text_from_file(uploaded_file) -> str:
    if uploaded_file is None: return ""
    ext = uploaded_file.name.split(".")[-1].lower()
    try:
        if ext == "pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        if ext == "docx":
            return docx2txt.process(uploaded_file)
    except Exception as e:
        st.error(f"File read error: {e}")
    return ""

def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled) -> Dict:
    content = mask_pii(resume_text) if mask_pii_enabled else resume_text
    prompt = f"Extract structured JSON:\n{{\"name\": \"\", \"email\": \"\", \"phone\": \"\", \"experience_years\": 0, \"tech_stack\": \"\", \"current_role\": \"\", \"education\": \"\", \"key_projects\": \"\"}}\n\nResume:\n{content[:6000]}"
    try:
        res = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        data["filename"] = filename
        return data
    except Exception:
        return {}

def rank_candidates(client, df, jd_text):
    summary = ""
    for _, r in df.iterrows():
        summary += f"{r['name']} | {r['experience_years']} yrs | {r['tech_stack']}\n"
    prompt = f"Job Description:\n{jd_text}\n\nCandidates:\n{summary}\n\nReturn ranked JSON list with: name, strengths, gaps"
    try:
        res = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content).get("candidates", [])
    except: return []

# --------------------------------------------------
# MAIN APP
# --------------------------------------------------
def main():
    st.markdown('<h1 class="main-header">AI Resume Screening System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Powered by Groq & SharePoint</p>', unsafe_allow_html=True)

    # Sidebar Status
    with st.sidebar:
        st.title("⚙️ System Status")
        client = init_groq_client()
        sp_uploader = init_sharepoint()
        
        if client: st.success("Groq Connected")
        if sp_uploader: st.success("SharePoint Ready")
        else: st.warning("SharePoint Auth Missing")
        
        mask_pii_enabled = st.checkbox("Enable PII Masking", value=True)

    if "df" not in st.session_state:
        st.session_state.df = None

    tabs = st.tabs(["📤 Upload", "📊 Database", "🎯 Match", "📈 Analytics"])

    # 1. UPLOAD TAB
    with tabs[0]:
        files = st.file_uploader("Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)
        if st.button("Process Resumes") and client and files:
            records = []
            progress_bar = st.progress(0)
            for i, f in enumerate(files):
                text = extract_text_from_file(f)
                parsed = parse_resume_with_groq(client, text, f.name, mask_pii_enabled)
                if parsed: records.append(parsed)
                progress_bar.progress((i + 1) / len(files))
            
            if records:
                st.session_state.df = pd.DataFrame(records)
                st.success(f"Processed {len(records)} resumes")

    # 2. DATABASE TAB (Updated with Dynamic SharePoint Link)
    with tabs[1]:
        if st.session_state.df is not None:
            st.dataframe(st.session_state.df, use_container_width=True)
            
            st.divider()
            st.subheader("🌐 Export to SharePoint")
            
            # User inputs the SharePoint URL here
            sp_url = st.text_input(
                "SharePoint Site URL", 
                placeholder="https://yourtenant.sharepoint.com/sites/YourSiteName"
            )
            
            if st.button("🚀 Push to SharePoint"):
                if not sp_url:
                    st.error("Please enter a valid SharePoint Site URL.")
                elif sp_uploader:
                    with st.spinner("Resolving Site IDs and Uploading..."):
                        try:
                            # 1. Resolve IDs from the link provided by user
                            site_id, drive_id = sp_uploader.resolve_site_and_drive(sp_url)
                            
                            # 2. Prepare CSV Buffer
                            csv_buffer = io.BytesIO()
                            st.session_state.df.to_csv(csv_buffer, index=False)
                            csv_buffer.seek(0)
                            
                            # 3. Upload
                            file_name = f"candidates_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                            sp_uploader.upload_csv_to_sharepoint(
                                site_id=site_id,
                                drive_id=drive_id,
                                folder_path="General", # You can make this a text_input too
                                file_name=file_name,
                                csv_buffer=csv_buffer
                            )
                            st.success(f"Successfully uploaded '{file_name}' to SharePoint!")
                        except Exception as e:
                            st.error(f"SharePoint Error: {e}")
                else:
                    st.error("SharePoint uploader not initialized. Check your Secrets.")

            st.divider()
            st.download_button("Download CSV Locally", st.session_state.df.to_csv(index=False), "candidates.csv", "text/csv")

    # 3. MATCH TAB
    with tabs[2]:
        jd_text = st.text_area("Paste Job Description")
        if st.button("Rank Candidates") and client and st.session_state.df is not None:
            results = rank_candidates(client, st.session_state.df, jd_text)
            if results:
                for r in results:
                    with st.expander(f"🎯 {r.get('name')}"):
                        st.write("**Strengths:**", r.get("strengths"))
                        st.write("**Gaps:**", r.get("gaps"))

    # 4. ANALYTICS TAB
    with tabs[3]:
        if st.session_state.df is not None:
            fig = px.histogram(st.session_state.df, x="experience_years", title="Experience Distribution")
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()