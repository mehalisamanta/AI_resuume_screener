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

    prompt = f"""You are an expert AI resume parser. Extract structured data from this resume.

IMPORTANT: Look carefully for email addresses and phone numbers in the resume text.
Email format: name@domain.com
Phone format: (XXX) XXX-XXXX or XXX-XXX-XXXX or similar variations

Return valid JSON with this exact structure:
{{
    "name": "full name",
    "email": "email@example.com or null if not found",
    "phone": "phone number or null if not found",
    "experience_years": numeric value (e.g., 5.5),
    "tech_stack": "comma-separated skills (Python, AWS, Docker, etc)",
    "current_role": "most recent job title",
    "education": "highest degree",
    "key_projects": "brief summary of top achievements",
    "certifications": "certifications or null",
    "domain_expertise": "industry domain"
}}

Resume:
{processed_text[:6000]}

Return ONLY JSON, no markdown or extra text."""

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

    prompt = f"""Analyze this job description and extract the requirements.

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON with this structure:
{{
    "minimum_experience_years": <number or 0 if not specified>,
    "required_technical_skills": ["skill1", "skill2", "skill3"],
    "preferred_skills": ["skill1", "skill2"],
    "job_title": "extracted job title",
    "seniority_level": "Entry/Mid/Senior/Lead"
}}

Extract actual technical skills (Python, AWS, Docker, etc), not soft skills.
Return ONLY the JSON object, no extra text."""

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