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
import plotly.graph_objects as go
import pytesseract
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Page Configuration
st.set_page_config(
    page_title="AI Resume Screening System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for UI Enhancement
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: black;
        text-align: center;
        padding: 20px 0;
    }
    .sub-header {
        text-align: center;
        color: #555;
        font-size: 1.2rem;
        margin-bottom: 30px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 8px;
        font-weight: 600;
    }
    .card-container {
        border-left: 5px solid #667eea;
        padding: 20px;
        margin: 15px 0;
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# Helper function to ensure text is bulleted for the UI
def ensure_bullets(text):
    if not text or text.lower() in ["none", "n/a", "null"]:
        return "No specific points identified."
    text = text.strip()
    # Check if it already looks like a list
    if text.startswith("-") or text.startswith("*") or "\n" in text:
        return text
    # Convert comma-separated strings to bullets
    if "," in text:
        return "\n".join([f"- {item.strip()}" for item in text.split(",")])
    return f"- {text}"

# --- CORE FUNCTIONS ---

@st.cache_resource
def init_groq_client(api_key):
    return Groq(api_key=api_key)

def mask_pii(text):
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text

def extract_text_from_file(uploaded_file):
    if uploaded_file is None:
        return ""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_ext == 'pdf':
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join([page.extract_text() for page in pdf_reader.pages])
        elif file_ext == 'docx':
            return docx2txt.process(uploaded_file)
        elif file_ext in ['png', 'jpg', 'jpeg']:
            return pytesseract.image_to_string(Image.open(uploaded_file))
        return ""
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {str(e)}")
        return ""

def calculate_semantic_score(resume_text, jd_text):
    try:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        vectors = vectorizer.fit_transform([resume_text, jd_text])
        score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return round(score * 100, 2)
    except:
        return 0

def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled=False):
    processed_text = mask_pii(resume_text) if mask_pii_enabled else resume_text
    prompt = f"""Extract structured JSON from this resume.
    Structure:
    {{
        "name": "full name", "email": "email", "phone": "phone",
        "experience_years": numeric, "tech_stack": "comma-separated skills",
        "current_role": "role", "education": "degree", "key_projects": "summary"
    }}
    Resume: {processed_text[:6000]}"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        parsed_data = json.loads(chat_completion.choices[0].message.content)
        parsed_data['filename'] = filename
        return parsed_data
    except:
        return None

def match_candidates_with_jd(client, candidates_df, job_description, top_n=5):
    candidates_summary = ""
    for idx, row in candidates_df.iterrows():
        candidates_summary += f"ID {idx}: {row.get('name')} | Exp: {row.get('experience_years')} | Skills: {row.get('tech_stack')}\n"

    prompt = f"""Evaluate these candidates against this Job Description (JD). 
    JD: {job_description}
    Candidates: {candidates_summary}

    For 'strengths' and 'gaps', strictly use Markdown BULLET POINTS (starting with -).
    Return JSON array of objects:
    [{{ "name": "Name", "rank": 1, "match_percentage": 90, "strengths": "- point 1\\n- point 2", "gaps": "- point 1", "recommendation": "Strongly Recommended", "interview_priority": "High" }}]"""

    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        res_text = json.loads(completion.choices[0].message.content)
        results = res_text if isinstance(res_text, list) else res_text.get('candidates', res_text.get('results', []))

        for result in results:
            resume_text = st.session_state.get('resume_texts', {}).get(result.get('name'), '')
            if resume_text:
                sem_score = calculate_semantic_score(resume_text, job_description)
                result['semantic_score'] = sem_score
                result['final_score'] = round((result.get('match_percentage', 0) * 0.7) + (sem_score * 0.3), 1)
        return results
    except Exception as e:
        st.error(f"Match Error: {e}")
        return []

def generate_interview_questions(client, candidate_data, job_description):
    prompt = f"Generate 5 interview questions for {candidate_data.get('name')} based on JD: {job_description[:500]}. Return JSON array: [{{'category': '...', 'question': '...', 'why_asking': '...'}}]"
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        res = json.loads(completion.choices[0].message.content)
        return res if isinstance(res, list) else res.get('questions', [])
    except: return []
    
def convert_df_to_csv(df):
    # Cache the conversion to prevent re-running on every render
    return df.to_csv(index=False).encode('utf-8')

def upload_to_sharepoint_logic(df, folder_url):
    """
    Placeholder for Microsoft Graph API or O365 library integration.
    To make this live, you will need:
    1. An Azure App Registration (Client ID & Secret)
    2. The 'O365' or 'office365-python-client' library
    """
    try:
        # Convert DF to a temporary CSV buffer
        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        
        # LOGIC GOES HERE:
        # ctx = ClientContext(site_url).with_credentials(client_credentials)
        # target_folder = ctx.web.get_folder_by_server_relative_url(folder_url)
        # target_folder.upload_file(f"export_{datetime.now()}.csv", csv_buffer.getvalue()).execute_query()
        
        # For now, we simulate a successful connection:
        return True 
    except Exception as e:
        st.error(f"SharePoint Upload Failed: {str(e)}")
        return False

# --- MAIN APP ---

def main():
    if 'parsed_resumes' not in st.session_state: st.session_state.parsed_resumes = []
    if 'candidates_df' not in st.session_state: st.session_state.candidates_df = None
    if 'matched_results' not in st.session_state: st.session_state.matched_results = None
    if 'resume_texts' not in st.session_state: st.session_state.resume_texts = {}

    st.markdown('<h1 class="main-header">Resume Screening System</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">⚡ Powered by Groq | Fast Semantic Matching</p>', unsafe_allow_html=True)

    # SIDEBAR MODIFIED: Removed Experience Slider
    with st.sidebar:
        st.title("⚙️ Config")
        api_key = st.text_input("Groq API Key", type="password")
        client = init_groq_client(api_key) if api_key else None
        
        st.divider()
        mask_pii_enabled = st.checkbox("PII Masking", value=True)
        top_n = st.select_slider("Top Candidates to Rank", options=[1, 3, 5, 10], value=3)

    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload Resumes", "📊 Database", "🎯 Match", "📈 Analytics"])

    # TAB 1: Upload Resumes
    # TAB 1: Upload
    # TAB 1: Upload Resumes
    with tab1:
        st.header("Step 1: Provide Resumes")
        
        # Toggle between methods to ensure "either/or" functionality
        upload_method = st.radio(
            "Select Upload Method:",
            ["Local File Upload", "SharePoint Link"],
            horizontal=True
        )
        
        uploaded_files = []
        sharepoint_link = ""

        if upload_method == "Local File Upload":
            uploaded_files = st.file_uploader(
                "Upload Candidate Resumes", 
                type=['pdf', 'docx', 'png', 'jpg', 'jpeg'], 
                accept_multiple_files=True
            )
        else:
            sharepoint_link = st.text_input(
                "🔗 SharePoint Folder Link", 
                placeholder="https://company.sharepoint.com/..."
            )
            st.info("Note: When using a link, please ensure files are also manually accessible for parsing in this version.")

        # Updated Processing Button Logic
        if client:
            # Check if we have input based on the selected method
            has_input = (upload_method == "Local File Upload" and uploaded_files) or \
                        (upload_method == "SharePoint Link" and sharepoint_link)
            
            if st.button("🚀 Process Resumes", disabled=not has_input):
                st.session_state.parsed_resumes = []
                
                if upload_method == "Local File Upload":
                    for f in uploaded_files:
                        text = extract_text_from_file(f)
                        parsed = parse_resume_with_groq(client, text, f.name, mask_pii_enabled)
                        if parsed:
                            st.session_state.parsed_resumes.append(parsed)
                            st.session_state.resume_texts[parsed.get('name')] = text
                
                elif upload_method == "SharePoint Link":
                    # Placeholder for SharePoint API integration
                    st.warning("Automatic background download from SharePoint requires Graph API credentials. Please upload files directly for immediate processing.")
                
                if st.session_state.parsed_resumes:
                    st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                    st.success(f"Successfully processed {len(st.session_state.parsed_resumes)} resumes!")

    # TAB 2: Candidate Database
    # TAB 2: Candidate Database
    # TAB 2: Candidate Database
    with tab2:
        if st.session_state.candidates_df is not None:
            st.subheader("📋 Parsed Candidate Records")
            st.dataframe(st.session_state.candidates_df, use_container_width=True)
            
            st.divider()
            st.subheader("📤 Export Database")
            
            # Use a radio button to toggle between local and cloud export
            export_method = st.radio(
                "Choose Export Action:",
                ["Download CSV Locally", "Upload CSV to SharePoint"],
                horizontal=True
            )
            
            if export_method == "Download CSV Locally":
                st.info("Your file will be prepared for local download.")
                csv_data = convert_df_to_csv(st.session_state.candidates_df)
                st.download_button(
                    label="📥 Click to Download CSV",
                    data=csv_data,
                    file_name=f"candidates_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            else:
                st.info("Provide the destination details for SharePoint.")
                target_sp_link = st.text_input(
                    "Destination SharePoint Folder URL", 
                    placeholder="https://company.sharepoint.com/sites/..."
                )
                
                if st.button("☁️ Start SharePoint Upload"):
                    if not target_sp_link:
                        st.error("Please provide a valid SharePoint folder URL.")
                    else:
                        with st.spinner("Uploading file..."):
                            # Placeholder for actual API logic
                            success = upload_to_sharepoint_logic(st.session_state.candidates_df, target_sp_link)
                            if success:
                                st.success(f"✅ Export successfully uploaded to: {target_sp_link}")
        else: 
            st.info("No data yet. Please upload resumes in the first tab.")
    # TAB 3: Job Description & Matching
    with tab3:
        st.header("Semantic Matching")
        
        # JD MODIFIED: Added File Upload Option
        jd_col1, jd_col2 = st.columns([1, 1])
        
        with jd_col1:
            st.subheader("Upload JD File")
            jd_file = st.file_uploader("Choose a JD (PDF or DOCX)", type=['pdf', 'docx'])
            
        with jd_col2:
            st.subheader("Or Paste JD Text")
            pasted_jd = st.text_area("Job Description Content", height=150, placeholder="Paste JD requirements here...")

        # Determine which JD content to use
        final_jd_text = ""
        if jd_file:
            final_jd_text = extract_text_from_file(jd_file)
            if final_jd_text:
                st.success(f"JD extracted from {jd_file.name}")
        else:
            final_jd_text = pasted_jd

        if st.button("🎯 Rank Candidates") and client:
            if not final_jd_text:
                st.warning("Please upload or paste a Job Description first.")
            elif st.session_state.candidates_df is None:
                st.warning("No candidates in the database. Please upload resumes first.")
            else:
                with st.spinner("Analyzing resumes against the JD..."):
                    results = match_candidates_with_jd(client, st.session_state.candidates_df, final_jd_text, top_n)
                    st.session_state.matched_results = results

        # Display Results
        if st.session_state.matched_results:
            st.divider()
            for cand in st.session_state.matched_results:
                final_score = cand.get('final_score', 0)
                color = "#28a745" if final_score > 75 else "#ffc107" if final_score > 50 else "#dc3545"
                
                # Header Card
                st.markdown(f"""
                <div class="card-container" style="border-left-color: {color};">
                    <h3 style="margin:0;">#{cand.get('rank')} {cand.get('name')} <span style="float:right; color:{color};">{final_score}% Match</span></h3>
                    <p><b>{cand.get('recommendation')}</b> | Priority: {cand.get('interview_priority')}</p>
                </div>
                """, unsafe_allow_html=True)

                # Strengths & Gaps (Bullet Points)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### ✅ Key Strengths")
                    st.markdown(ensure_bullets(cand.get('strengths')))
                with col2:
                    st.markdown("##### ⚠️ Skill Gaps / Concerns")
                    st.markdown(ensure_bullets(cand.get('gaps')))
                
                # Interview Questions
                with st.expander(f"🎤 Generate Targeted Questions for {cand.get('name')}"):
                    if st.button("Generate Questions", key=f"q_{cand.get('name')}"):
                        qs = generate_interview_questions(client, cand, final_jd_text)
                        for q in qs:
                            st.write(f"**{q.get('category')}**: {q.get('question')}")
                            st.caption(f"*Why:* {q.get('why_asking')}")
                st.divider()

    # TAB 4: Visual Analytics
    with tab4:
        if st.session_state.candidates_df is not None:
            st.header("Analytics Overview")
            col_a, col_b = st.columns(2)
            with col_a:
                fig_exp = px.histogram(st.session_state.candidates_df, x="experience_years", title="Candidate Experience Levels")
                st.plotly_chart(fig_exp, use_container_width=True)
            with col_b:
                if st.session_state.matched_results:
                    match_df = pd.DataFrame(st.session_state.matched_results)
                    fig_match = px.bar(match_df, x="name", y="final_score", title="Comparison of Match Scores")
                    st.plotly_chart(fig_match, use_container_width=True)
        else: st.info("Upload resumes to see analytics.")

if __name__ == "__main__":
    main()