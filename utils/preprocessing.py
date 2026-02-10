"""
Preprocessing and Data Filtering Utilities
"""

import re
import pandas as pd
from datetime import datetime
import io

def mask_pii(text):
    """Redacts PII before sending to LLM"""
    text = re.sub(r'\S+@\S+', '[EMAIL_MASKED]', text)
    text = re.sub(r'\+?\d[\d -]{8,12}\d', '[PHONE_MASKED]', text)
    return text

def automated_pre_screen(df, jd_requirements, start_date=None, end_date=None):
    """Pre-screen candidates automatically based on JD requirements"""
    if df is None or df.empty or jd_requirements is None:
        return df, pd.DataFrame()
    
    filtered_df = df.copy()
    rejection_tracker = []
    
    # Date filtering
    if start_date and end_date and 'parsed_date' in filtered_df.columns:
        try:
            filtered_df['parsed_date_dt'] = pd.to_datetime(filtered_df['parsed_date'], errors='coerce')
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # Track rejected by date
            date_rejected = filtered_df[
                (filtered_df['parsed_date_dt'] < start_dt) | 
                (filtered_df['parsed_date_dt'] > end_dt)
            ].copy()
            if not date_rejected.empty:
                date_rejected['rejection_reason'] = 'Outside selected date range'
                date_rejected['rejection_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rejection_tracker.append(date_rejected)
            
            filtered_df = filtered_df[
                (filtered_df['parsed_date_dt'] >= start_dt) & 
                (filtered_df['parsed_date_dt'] <= end_dt)
            ]
        except Exception as e:
            import streamlit as st
            st.warning(f"Date filtering skipped: {str(e)}")
    
    # Experience filtering
    min_experience = jd_requirements.get('min_experience', 0)
    if min_experience > 0:
        try:
            filtered_df['experience_years'] = pd.to_numeric(filtered_df['experience_years'], errors='coerce')
            
            # Track rejected by experience
            exp_rejected = filtered_df[filtered_df['experience_years'] < min_experience].copy()
            if not exp_rejected.empty:
                exp_rejected['rejection_reason'] = f'Insufficient experience (Required: {min_experience}+ years)'
                exp_rejected['rejection_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rejection_tracker.append(exp_rejected)
            
            filtered_df = filtered_df[filtered_df['experience_years'] >= min_experience]
        except:
            pass
    
    # Skills filtering
    required_skills = jd_requirements.get('required_skills', [])
    if required_skills:
        def has_required_skills(tech_stack):
            if pd.isna(tech_stack):
                return False
            tech_stack_lower = str(tech_stack).lower()
            matched_skills = sum(1 for skill in required_skills if skill.lower() in tech_stack_lower)
            return matched_skills >= len(required_skills) * 0.5  # At least 50% match
        
        # Track rejected by skills
        skills_rejected = filtered_df[~filtered_df['tech_stack'].apply(has_required_skills)].copy()
        if not skills_rejected.empty:
            skills_rejected['rejection_reason'] = f'Missing required skills: {", ".join(required_skills)}'
            skills_rejected['rejection_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rejection_tracker.append(skills_rejected)
        
        filtered_df = filtered_df[filtered_df['tech_stack'].apply(has_required_skills)]
    
    # Combine all rejected candidates
    rejected_df = pd.DataFrame()
    if rejection_tracker:
        rejected_df = pd.concat(rejection_tracker, ignore_index=True)
        # Remove duplicates (keep first rejection reason)
        rejected_df = rejected_df.drop_duplicates(subset=['name'], keep='first')
    
    return filtered_df, rejected_df

def save_rejected_to_csv(rejected_df):
    """Save rejected candidates to CSV file"""
    if rejected_df.empty:
        return None
    
    filename = f"rejected_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    csv_buffer = io.StringIO()
    rejected_df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue(), filename