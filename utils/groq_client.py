"""
Groq LLM Client and Processing Functions
"""

import streamlit as st
import json
from groq import Groq
from datetime import datetime
from config.settings import GROQ_MODEL, GROQ_TEMPERATURE_PARSING, GROQ_TEMPERATURE_MATCHING, GROQ_TEMPERATURE_QUESTIONS
from utils.preprocessing import mask_pii
from utils.scoring import calculate_semantic_score

@st.cache_resource
def init_groq_client(api_key):
    """Initialize Groq client"""
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize Groq: {str(e)}")
        return None

def parse_resume_with_groq(client, resume_text, filename, mask_pii_enabled=False):
    """Parse resume using Groq LLM"""
    processed_text = mask_pii(resume_text) if mask_pii_enabled else resume_text
    
    prompt = f"""You are an expert AI resume parser. Extract structured data from this resume.

Return valid JSON with this exact structure:
{{
    "name": "full name",
    "email": "email or null",
    "phone": "phone or null",
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
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a precise resume parser. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=GROQ_TEMPERATURE_PARSING,
            max_tokens=1500
        )
        
        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            parsed_data = json.loads(response[json_start:json_end])
            parsed_data['filename'] = filename
            parsed_data['parsed_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return parsed_data
        return None
            
    except Exception as e:
        st.error(f"Error parsing {filename}: {str(e)}")
        return None

def extract_jd_requirements(client, job_description):
    """Extract skills and experience requirements from JD automatically"""
    prompt = f"""Analyze this job description and extract key requirements.

JOB DESCRIPTION:
{job_description}

Return valid JSON with this exact structure:
{{
    "min_experience": numeric value (e.g., 3, 5, 0 if not specified),
    "required_skills": ["skill1", "skill2", "skill3"],
    "preferred_skills": ["skill1", "skill2"],
    "role_title": "job title"
}}

Extract only skills explicitly mentioned. Return ONLY JSON."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a precise job requirement analyzer. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=GROQ_TEMPERATURE_PARSING,
            max_tokens=1000
        )
        
        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            requirements = json.loads(response[json_start:json_end])
            return requirements
        return None
            
    except Exception as e:
        st.error(f"Error extracting JD requirements: {str(e)}")
        return None

def match_candidates_with_jd(client, candidates_df, job_description, top_n=5):
    """Match candidates against job description"""
    if candidates_df.empty:
        return []
    
    candidates_summary = ""
    for idx, row in candidates_df.iterrows():
        candidates_summary += f"""
Candidate {idx + 1}:
- Name: {row.get('name', 'N/A')}
- Experience: {row.get('experience_years', 'N/A')} years
- Tech Stack: {row.get('tech_stack', 'N/A')}
- Role: {row.get('current_role', 'N/A')}
- Projects: {row.get('key_projects', 'N/A')}
"""
    
    prompt = f"""You are an expert HR recruiter. Rank top {top_n} candidates for this job.

JOB DESCRIPTION:
{job_description}

CANDIDATES:
{candidates_summary}

Evaluate on: Technical skills (40%), Experience (30%), Projects (20%), Domain fit (10%)

IMPORTANT: Format strengths and gaps as clear bullet points.

Return JSON array:
[
  {{
    "rank": 1,
    "name": "Name",
    "match_percentage": 88,
    "strengths": "• Strength 1\\n• Strength 2\\n• Strength 3",
    "gaps": "• Gap 1\\n• Gap 2",
    "recommendation": "Strongly Recommended/Recommended/Consider/Not Recommended",
    "interview_priority": "High/Medium/Low"
  }}
]

Return ONLY JSON array."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Expert technical recruiter AI."},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=GROQ_TEMPERATURE_MATCHING,
            max_tokens=3000
        )
        
        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        
        if json_start != -1:
            results = json.loads(response[json_start:json_end])
            
            # Add TF-IDF semantic scores
            for result in results:
                candidate_name = result.get('name', '')
                resume_text = st.session_state.resume_texts.get(candidate_name, '')
                if resume_text:
                    semantic_score = calculate_semantic_score(resume_text, job_description)
                    result['keyword_match_score'] = semantic_score  
                    llm_score = result.get('match_percentage', 0)
                    result['ai_analysis_score'] = llm_score  
                    # Blend AI Analysis (70%) + Keyword Match (30%)
                    result['final_score'] = round(llm_score * 0.7 + semantic_score * 0.3, 2)
                else:
                    result['keyword_match_score'] = 0
                    result['ai_analysis_score'] = result.get('match_percentage', 0)
                    result['final_score'] = result.get('match_percentage', 0)
            
            return results
        return []
            
    except Exception as e:
        st.error(f"Matching error: {str(e)}")
        return []

def generate_interview_questions(client, candidate_data, job_description):
    """Generate targeted interview questions"""
    prompt = f"""Generate 8 targeted interview questions for this candidate.

CANDIDATE:
- Name: {candidate_data.get('name')}
- Experience: {candidate_data.get('experience_years')} years
- Tech: {candidate_data.get('tech_stack')}
- Role: {candidate_data.get('current_role')}

JOB: {job_description[:1000]}

Generate:
- 3 technical questions
- 2 behavioral (STAR format)
- 2 scenario-based
- 1 culture fit

Return JSON:
[{{"category": "Technical", "question": "...", "why_asking": "..."}}]"""

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Interview question generator."},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=GROQ_TEMPERATURE_QUESTIONS,
            max_tokens=2000
        )
        
        text = response.choices[0].message.content.strip()
        json_start = text.find('[')
        json_end = text.rfind(']') + 1
        
        if json_start != -1:
            return json.loads(text[json_start:json_end])
        return []
    except:
        return []