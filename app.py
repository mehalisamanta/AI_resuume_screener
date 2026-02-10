import streamlit as st
import pandas as pd
import json
import os
import re
from groq import Groq
from datetime import datetime
import io
from typing import List, Dict
import PyPDF2
import docx2txt
import plotly.express as px
import pytesseract
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from urllib.parse import urlparse, unquote
import pytesseract
from PIL import Image


# --------------------------------------------------
# ENV CONFIG (BACKEND ONLY)
# --------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SITE_ID = os.getenv("SITE_ID")
DRIVE_ID = os.getenv("DRIVE_ID")

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
.main-header {
    font-size: 3rem;
    font-weight: bold;
    text-align: center;
    padding: 20px 0;
}
.sub-header {
    text-align: center;
    color: #555;
    font-size: 1.2rem;
    margin-bottom: 30px;
}
.card-container {
    border-left: 5px solid #667eea;
    padding: 20px;
    margin: 15px 0;
    background: white;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def ensure_bullets(text):
    if not text or text.lower() in ["none", "n/a", "null"]:
        return "No specific points identified."
    if text.startswith("-") or "\n" in text:
        return text
    if "," in text:
        return "\n".join([f"- {i.strip()}" for i in text.split(",")])
    return f"- {text}"

@st.cache_resource
def init_groq_client():
    return Groq(api_key=GROQ_API_KEY)

def mask_pii(text):
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text

def extract_text_from_file(uploaded_file):
    if uploaded_file is None:
        return ""
    ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if ext == "pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        if ext == "docx":
            return docx2txt.process(uploaded_file)
        if ext in ["png", "jpg", "jpeg"]:
            return pytesseract.image_to_string(Image.open(uploaded_file))
    except Exception as e:
        st.error(f"File error: {e}")
    return ""

def calculate_semantic_score(resume_text, jd_text):
    try:
        vec = TfidfVectorizer(stop_words="english", max_features=1000)
        tfidf = vec.fit_transform([resume_text, jd_text])
        return round(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0] * 100, 2)
    except:
        return 0

def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled):
    text = mask_pii(resume_text) if mask_pii_enabled else resume_text
    prompt = f"""
Extract structured JSON:
{{
"name": "", "email": "", "phone": "",
"experience_years": 0,
"tech_stack": "",
"current_role": "",
"education": "",
"key_projects": ""
}}
Resume:
{text[:6000]}
"""
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        data["filename"] = filename
        return data
    except:
        return None

def match_candidates_with_jd(client, df, jd_text, top_n):
    summary = ""
    for i, r in df.iterrows():
        summary += f"{i}: {r['name']} | {r['experience_years']} yrs | {r['tech_stack']}\n"

    prompt = f"""
JD:
{jd_text}

Candidates:
{summary}

Return ranked JSON list with strengths & gaps as bullet points.
"""
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content)
    except:
        return []

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

# --------------------------------------------------
# SHAREPOINT HELPERS (PLACEHOLDER)
# --------------------------------------------------
def extract_sharepoint_folder_path(sp_url):
    parsed = urlparse(sp_url)
    path = unquote(parsed.path)
    if "Shared Documents" in path:
        return path.split("Shared Documents/")[-1]
    return ""

def list_sharepoint_files(folder_path):
    # TODO: Replace with Graph API call
    return []

def download_sharepoint_file(file_id):
    # TODO: Replace with Graph API call
    return None

# --------------------------------------------------
# MAIN APP
# --------------------------------------------------
def main():
    if "parsed_resumes" not in st.session_state:
        st.session_state.parsed_resumes = []
    if "candidates_df" not in st.session_state:
        st.session_state.candidates_df = None
    if "matched_results" not in st.session_state:
        st.session_state.matched_results = None
    if "resume_texts" not in st.session_state:
        st.session_state.resume_texts = {}

    st.markdown('<h1 class="main-header">AI Resume Screening System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Powered by Groq</p>', unsafe_allow_html=True)

    # ---------------- SIDEBAR ----------------
    with st.sidebar:
        st.title("⚙️ System Status")

        if GROQ_API_KEY:
            client = init_groq_client()
            st.success("Groq Connected")
        else:
            client = None
            st.error("Groq API Key missing")

        st.divider()
        mask_pii_enabled = st.checkbox("PII Masking", value=True)
        top_n = st.select_slider("Top Candidates", [1, 3, 5, 10], 3)

        st.divider()
        if all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, SITE_ID, DRIVE_ID]):
            st.success("SharePoint Config Loaded")
        else:
            st.warning("SharePoint Config Missing")

    tabs = st.tabs(["📤 Upload", "📊 Database", "🎯 Match", "📈 Analytics"])

    # ---------------- UPLOAD ----------------
    with tabs[0]:
        st.subheader("Resume Source")

        source = st.radio(
            "Choose resume source",
            ["Local Upload", "SharePoint Folder"],
            horizontal=True
        )

        files = None
        sharepoint_url = None

        if source == "Local Upload":
            files = st.file_uploader(
                "Upload Resumes",
                type=["pdf", "docx", "png", "jpg"],
                accept_multiple_files=True
            )
        else:
            sharepoint_url = st.text_input(
                "SharePoint Folder URL",
                placeholder="https://company.sharepoint.com/sites/HR/Shared Documents/Resumes"
            )
            st.caption("🔒 Access handled securely using backend credentials")

            if sharepoint_url and "sharepoint.com" not in sharepoint_url:
                st.error("Please enter a valid SharePoint URL")

        if st.button("Process Resumes") and client:
            st.session_state.parsed_resumes.clear()

            if source == "Local Upload" and files:
                for f in files:
                    txt = extract_text_from_file(f)
                    parsed = parse_resume_with_groq(client, txt, f.name, mask_pii_enabled)
                    if parsed:
                        st.session_state.parsed_resumes.append(parsed)
                        st.session_state.resume_texts[parsed["name"]] = txt

            elif source == "SharePoint Folder" and sharepoint_url:
                folder_path = extract_sharepoint_folder_path(sharepoint_url)
                st.info(f"Reading resumes from SharePoint folder: {folder_path}")
                st.warning("SharePoint file fetching not implemented yet")

            if st.session_state.parsed_resumes:
                st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                st.success("Resumes processed")
            else:
                st.warning("No resumes processed")

    # ---------------- DATABASE ----------------
    with tabs[1]:
        if st.session_state.candidates_df is not None:
            st.dataframe(st.session_state.candidates_df, use_container_width=True)
            csv = convert_df_to_csv(st.session_state.candidates_df)
            st.download_button("Download CSV", csv, "candidates.csv", "text/csv")

    # ---------------- MATCH ----------------
    with tabs[2]:
        jd_text = st.text_area("Paste Job Description")
        if st.button("Rank Candidates") and client and st.session_state.candidates_df is not None:
            st.session_state.matched_results = match_candidates_with_jd(
                client, st.session_state.candidates_df, jd_text, top_n
            )

        if st.session_state.matched_results:
            for c in st.session_state.matched_results:
                st.markdown(f"### {c.get('name')}")
                st.markdown("**Strengths**")
                st.markdown(ensure_bullets(c.get("strengths")))
                st.markdown("**Gaps**")
                st.markdown(ensure_bullets(c.get("gaps")))

    # ---------------- ANALYTICS ----------------
    with tabs[3]:
        if st.session_state.candidates_df is not None:
            fig = px.histogram(st.session_state.candidates_df, x="experience_years")
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
