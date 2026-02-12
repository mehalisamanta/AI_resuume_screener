"""
Candidate scoring and matching utilities - UPDATED WITH FLEXIBLE SCREENING
"""

import streamlit as st
import pandas as pd
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from utils.groq_client import create_groq_completion


def calculate_semantic_score(resume_text, jd_text):
    """Calculate objective similarity score using TF-IDF."""
    try:
        vectorizer = TfidfVectorizer(max_features=500)
        vectors = vectorizer.fit_transform([resume_text, jd_text])
        score = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        return round(score * 100, 2)
    except:
        return 0


def auto_pre_screen_candidates(df, jd_requirements):
    """
    Flexible pre-screening with OR logic and scoring system.
    Candidates need to pass EITHER experience OR skills (not both).
    """
    if df is None or df.empty or jd_requirements is None:
        return df, []

    filtered_candidates = []
    min_exp = jd_requirements.get('minimum_experience_years', 0)
    required_skills = jd_requirements.get('required_technical_skills', [])

    experience_pass_count = 0
    skills_pass_count = 0

    for idx, row in df.iterrows():
        candidate_score = 0
        reasons = []

        # Experience check
        try:
            candidate_exp = float(row.get('experience_years', 0))
            if min_exp > 0:
                exp_threshold = min_exp * 0.8
                if candidate_exp >= min_exp:
                    candidate_score += 50
                    reasons.append(f"Meets experience requirement ({candidate_exp} >= {min_exp} years)")
                    experience_pass_count += 1
                elif candidate_exp >= exp_threshold:
                    candidate_score += 35
                    reasons.append(f"Close to experience requirement ({candidate_exp} years, preferred {min_exp}+)")
                    experience_pass_count += 1
                else:
                    reasons.append(f"Below experience threshold ({candidate_exp} < {exp_threshold} years)")
            else:
                candidate_score += 25
        except:
            pass

        # Skills check
        if required_skills:
            tech_stack = str(row.get('tech_stack', '')).lower()
            matched_skills = []

            for skill in required_skills:
                skill_lower = skill.lower()
                if (skill_lower in tech_stack or
                        (skill_lower == 'scikit-learn' and ('sklearn' in tech_stack or 'scikit' in tech_stack)) or
                        (skill_lower == 'tensorflow' and 'tensor' in tech_stack) or
                        (skill_lower == 'pytorch' and 'torch' in tech_stack) or
                        (skill_lower == 'numpy' and 'np' in tech_stack) or
                        (skill_lower == 'pandas' and 'pd' in tech_stack)):
                    matched_skills.append(skill)

            if len(required_skills) > 0:
                skill_match_ratio = len(matched_skills) / len(required_skills)
                if skill_match_ratio >= 0.6:
                    candidate_score += 50
                    reasons.append(f"Strong skill match ({len(matched_skills)}/{len(required_skills)} required skills)")
                    skills_pass_count += 1
                elif skill_match_ratio >= 0.3:
                    candidate_score += 35
                    reasons.append(f"Partial skill match ({len(matched_skills)}/{len(required_skills)} required skills)")
                    skills_pass_count += 1
                elif len(matched_skills) > 0:
                    candidate_score += 20
                    reasons.append(f"Some relevant skills ({len(matched_skills)} matched)")
                    skills_pass_count += 1
                else:
                    reasons.append(f"Limited skill match (0/{len(required_skills)} required skills)")
        else:
            candidate_score += 25

        if candidate_score >= 40:
            filtered_candidates.append(row)

    filtered_df = pd.DataFrame(filtered_candidates) if filtered_candidates else pd.DataFrame()

    screening_summary = []
    if min_exp > 0:
        screening_summary.append(
            f"✓ Experience: {min_exp}+ years preferred (flexible: {min_exp * 0.8:.1f}+ accepted) → {experience_pass_count}/{len(df)} candidates"
        )
    if required_skills:
        screening_summary.append(
            f"✓ Skills: {', '.join(required_skills[:3])}{'...' if len(required_skills) > 3 else ''} → {skills_pass_count}/{len(df)} candidates"
        )
    if screening_summary:
        screening_summary.insert(0, f"📊 Pre-screening weighs in both experience and skillset as per JD requirements")
        screening_summary.append(f"✅ {len(filtered_df)}/{len(df)} candidates passed pre-screening")

    return filtered_df, screening_summary


def match_candidates_with_jd(client, candidates_df, job_description, top_n=5):
    """
    Optimized hybrid matching: 70% LLM + 30% TF-IDF.
    Uses fallback Groq client when available.
    """
    if candidates_df.empty:
        return []

    fallback_client = st.session_state.get('fallback_client')
    actual_top_n = min(top_n, len(candidates_df))

    candidates_summary = ""
    for idx, row in candidates_df.iterrows():
        candidates_summary += f"""
Candidate {idx + 1}:
- Name: {row.get('name', 'N/A')}
- Email: {row.get('email', 'N/A')}
- Experience: {row.get('experience_years', 'N/A')} years
- Tech Stack: {row.get('tech_stack', 'N/A')}
- Role: {row.get('current_role', 'N/A')}
- Projects: {row.get('key_projects', 'N/A')}
"""

    prompt = f"""You are an expert HR recruiter. Rank the top {actual_top_n} candidates for this job.

JOB DESCRIPTION:
{job_description}

CANDIDATES:
{candidates_summary}

CRITICAL: You MUST return EXACTLY {actual_top_n} candidates, no more, no less.

Evaluate on: Technical skills (40%), Experience (30%), Projects (20%), Domain fit (10%)

IMPORTANT: Format strengths and gaps as comma-separated points that are clear and HR-friendly.

Return JSON array with EXACTLY {actual_top_n} candidates:
[
  {{
    "rank": 1,
    "name": "Name",
    "email": "Email",
    "match_percentage": 88,
    "strengths": "Strong Python expertise, Extensive AWS experience, Led 5+ successful projects",
    "gaps": "Limited experience with Kubernetes, No mention of CI/CD pipelines",
    "recommendation": "Strongly Recommended/Recommended/Consider/Not Recommended",
    "interview_priority": "High/Medium/Low"
  }}
]

Return ONLY JSON array with EXACTLY {actual_top_n} candidates."""

    try:
        chat_completion = create_groq_completion(
            client,
            fallback_client,
            messages=[
                {"role": "system", "content": f"Expert technical recruiter AI. You MUST return exactly {actual_top_n} candidates."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=3000
        )

        response = chat_completion.choices[0].message.content.strip()
        json_start = response.find('[')
        json_end = response.rfind(']') + 1

        if json_start != -1:
            results = json.loads(response[json_start:json_end])
            results = results[:actual_top_n]

            for result in results:
                candidate_name = result.get('name', '')
                resume_text = st.session_state.resume_texts.get(candidate_name, '')
                if resume_text:
                    semantic_score = calculate_semantic_score(resume_text, job_description)
                    result['semantic_score'] = semantic_score
                    llm_score = result.get('match_percentage', 0)
                    result['final_score'] = round(llm_score * 0.7 + semantic_score * 0.3, 2)
                else:
                    result['semantic_score'] = 0
                    result['final_score'] = result.get('match_percentage', 0)

            results.sort(key=lambda x: x['final_score'], reverse=True)
            for idx, result in enumerate(results, 1):
                result['rank'] = idx

            return results[:actual_top_n]
        return []

    except Exception as e:
        st.error(f"Matching error: {str(e)}")
        return []


def generate_interview_questions(client, candidate_data, job_description):
    """Generate personalized interview questions. Uses fallback Groq client when available."""
    fallback_client = st.session_state.get('fallback_client')

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
        response = create_groq_completion(
            client,
            fallback_client,
            messages=[
                {"role": "system", "content": "Interview question generator."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
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


def format_strengths_weaknesses(text):
    """Convert comma-separated text to list items."""
    if not text or text == "None" or text == "N/A":
        return []
    items = [item.strip() for item in text.split(',') if item.strip()]
    return items


def format_dataframe_for_display(df, columns_to_display):
    """Format dataframe with proper naming conventions."""
    from config.settings import COLUMN_DISPLAY_NAMES
    display_df = df[columns_to_display].copy()
    display_df = display_df.rename(columns=COLUMN_DISPLAY_NAMES)
    return display_df