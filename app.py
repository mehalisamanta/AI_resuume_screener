import streamlit as st
import pandas as pd
import json
import os
import re
import io
import requests
from groq import Groq
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
import PyPDF2
import docx2txt
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --------------------------------------------------
# ENV CONFIG (Streamlit Cloud / GitHub Secrets)
# --------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SITE_ID = os.getenv("SITE_ID")
DRIVE_ID = os.getenv("DRIVE_ID")

GRAPH_API = "https://graph.microsoft.com/v1.0"

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="AI Resume Screening System",
    page_icon="🎯",
    layout="wide"
)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def ensure_bullets(text):
    if not text:
        return "- Not specified"
    if "\n" in text:
        return text
    return "\n".join([f"- {i.strip()}" for i in text.split(",")])

@st.cache_resource
def init_groq_client():
    return Groq(api_key=GROQ_API_KEY)

def mask_pii(text):
    text = re.sub(r'\S+@\S+', '[EMAIL]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE]', text)
    return text

def extract_text_from_file(file_bytes, filename):
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    if ext == "docx":
        return docx2txt.process(io.BytesIO(file_bytes))
    return ""

def semantic_score(resume, jd):
    try:
        vec = TfidfVectorizer(stop_words="english")
        tfidf = vec.fit_transform([resume, jd])
        return round(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0] * 100, 2)
    except:
        return 0

# --------------------------------------------------
# SHAREPOINT AUTH
# --------------------------------------------------
def get_graph_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def list_sharepoint_files(folder_path):
    token = get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_API}/sites/{SITE_ID}/drives/{DRIVE_ID}/root:/{folder_path}:/children"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["value"]

def download_sharepoint_file(file_id):
    token = get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_API}/drives/{DRIVE_ID}/items/{file_id}/content"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.content

def extract_folder_from_url(sp_url):
    parsed = urlparse(sp_url)
    path = unquote(parsed.path)
    if "Shared Documents/" in path:
        return path.split("Shared Documents/")[1]
    return ""

# --------------------------------------------------
# GROQ PARSING
# --------------------------------------------------
def parse_resume(client, text, filename):
    prompt = f"""
Extract JSON:
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
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    data = json.loads(res.choices[0].message.content)
    data["filename"] = filename
    return data

# --------------------------------------------------
# MAIN APP
# --------------------------------------------------
def main():
    st.title("🎯 AI Resume Screening System")

    client = init_groq_client()

    source = st.radio(
        "Resume Source",
        ["Local Upload", "SharePoint Folder"],
        horizontal=True
    )

    resumes = []

    if source == "Local Upload":
        files = st.file_uploader(
            "Upload Resumes (PDF/DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True
        )

        if st.button("Process Resumes") and files:
            for f in files:
                text = extract_text_from_file(f.read(), f.name)
                resumes.append(parse_resume(client, mask_pii(text), f.name))

    else:
        sp_url = st.text_input("SharePoint Folder URL")
        st.caption("🔒 Access via backend credentials")

        if st.button("Process Resumes") and sp_url:
            folder = extract_folder_from_url(sp_url)
            files = list_sharepoint_files(folder)

            for f in files:
                if f["name"].endswith((".pdf", ".docx")):
                    content = download_sharepoint_file(f["id"])
                    text = extract_text_from_file(content, f["name"])
                    resumes.append(parse_resume(client, mask_pii(text), f["name"]))

    if resumes:
        df = pd.DataFrame(resumes)
        st.success(f"Processed {len(df)} resumes")
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "candidates.csv", "text/csv")

        jd = st.text_area("Job Description")
        if st.button("Rank Candidates") and jd:
            df["match_score"] = df["filename"].apply(
                lambda x: semantic_score(df[df["filename"] == x]["tech_stack"].iloc[0], jd)
            )
            st.dataframe(df.sort_values("match_score", ascending=False))

if __name__ == "__main__":
    main()
