"""
Resume preprocessing and parsing utilities
"""

import streamlit as st
import re
import json
from datetime import datetime
from utils.groq_client import create_groq_completion


def mask_pii(text):
    """Redacts PII before sending to LLM."""
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text


def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled=False, upload_date=None):
    """Parse resume with optional PII masking. Uses fallback Groq key when available."""
    fallback_client = st.session_state.get('fallback_client')

    # Extract email and phone BEFORE masking
    email_extracted = None
    phone_extracted = None

    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_matches = re.findall(email_pattern, resume_text)
    if email_matches:
        email_extracted = email_matches[0]

    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phone_matches = re.findall(phone_pattern, resume_text)
    if phone_matches:
        phone_extracted = ''.join(phone_matches[0]) if isinstance(phone_matches[0], tuple) else phone_matches[0]

    processed_text = mask_pii(resume_text) if mask_pii_enabled else resume_text
    #Structured prompting with strict instructions to ensure deterministic output
    prompt = """
ROLE:
You are a deterministic AI resume parsing engine.

PRIMARY OBJECTIVE:
Extract structured data from a resume with maximum accuracy and consistency.

PROCESS (MANDATORY):
1. Identify resume sections:
   - Contact Information
   - Skills
   - Work Experience
   - Education
   - Certifications (if present)
2. Extract information exactly as written.
3. Normalize formats only when clear (dates, job durations).
4. Do NOT infer or guess missing details.

STRICT RULES:
- NEVER invent information.
- NEVER assume company names, dates, or skills.
- If a field is missing → return null.
- Preserve original wording for roles and descriptions.
- Output must be identical for the same input across runs.
-NEVER hallucinate
-Hides personal data if PII masking is enabled, but still extract and return it in separate fields.

OUTPUT FORMAT (STRICT JSON ONLY):

{
  "name": null,
  "contact": {
    "email": null,
    "phone": null,
    "location": null,
    "linkedin": null
  },
  "skills": [],
  "experience": [
    {
      "company": null,
      "job_title": null,
      "start_date": null,
      "end_date": null,
      "description": null
    }
  ],
  "education": [
    {
      "degree": null,
      "institution": null,
      "year": null
    }
  ],
  "certifications": []
}

OUTPUT CONSTRAINTS:
- Return ONLY valid JSON.
- No explanation.
- No markdown.
- No extra text.
"""



    try:
        chat_completion = create_groq_completion(
            client,
            fallback_client,
            messages=[
                {"role": "system", "content": "You are a precise resume parser. Extract ALL contact information including email and phone. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1500
        )

        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            parsed_data = json.loads(response[json_start:json_end])

            if mask_pii_enabled:
                if email_extracted:
                    parsed_data['email'] = email_extracted
                if phone_extracted:
                    parsed_data['phone'] = phone_extracted
            else:
                if not parsed_data.get('email') or parsed_data.get('email') == 'null':
                    parsed_data['email'] = email_extracted if email_extracted else None
                if not parsed_data.get('phone') or parsed_data.get('phone') == 'null':
                    parsed_data['phone'] = phone_extracted if phone_extracted else None

            parsed_data['filename'] = filename
            parsed_data['submission_date'] = upload_date if upload_date else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return parsed_data
        return None

    except Exception as e:
        st.error(f"Error parsing {filename}: {str(e)}")
        return None


def extract_jd_requirements(client, job_description):
    """Extract minimum experience and required skills from JD automatically."""
    fallback_client = st.session_state.get('fallback_client')
#Few shot prompting is used 
    prompt = f"""
You are a deterministic job description parser.

Extract structured hiring requirements.

RULES:
- Extract only technical skills.
- Ignore soft skills and culture statements.
- If unclear → return empty or 0.
- Output JSON only.

EXAMPLE 1

Job Description:
"Junior Data Analyst required. Skills: SQL, Excel, Python."

Output:
{{
  "minimum_experience_years": 0,
  "required_technical_skills": ["SQL","Excel","Python"],
  "preferred_skills": [],
  "job_title": "Data Analyst",
  "seniority_level": "Entry"
}}

EXAMPLE 2

Job Description:
"Looking for Senior DevOps Engineer (7+ years).
Must have AWS, Kubernetes, Terraform.
Preferred: Docker, Jenkins."

Output:
{{
  "minimum_experience_years": 7,
  "required_technical_skills": ["AWS","Kubernetes","Terraform"],
  "preferred_skills": ["Docker","Jenkins"],
  "job_title": "DevOps Engineer",
  "seniority_level": "Senior"
}}

NOW PROCESS:

JOB DESCRIPTION:
['job_description']

Return ONLY:
{{
  "minimum_experience_years": 0,
  "required_technical_skills": [],
  "preferred_skills": [],
  "job_title": "",
  "seniority_level": ""
}}
"""

    try:
        chat_completion = create_groq_completion(
            client,
            fallback_client,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing job descriptions. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=800
        )

        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            return json.loads(response[json_start:json_end])
        return None

    except Exception as e:
        st.error(f"Error extracting JD requirements: {str(e)}")
        return None