"""
UI Tab Rendering Functions
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io
import plotly.express as px

from utils.file_handlers import extract_text_from_file
from utils.groq_client import parse_resume_with_groq, extract_jd_requirements, match_candidates_with_jd, generate_interview_questions
from utils.preprocessing import automated_pre_screen, save_rejected_to_csv
from config.settings import OCR_AVAILABLE, JD_TEMPLATES

def render_upload_tab(client, mask_pii_enabled):
    """Render the Upload & Parse tab"""
    st.header("Step 1: Upload & Parse Resumes")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        file_types = ['pdf', 'docx']
        if OCR_AVAILABLE:
            file_types.extend(['png', 'jpg', 'jpeg'])
        
        uploaded_files = st.file_uploader(
            f"Upload Resumes ({', '.join(file_types).upper()})",
            type=file_types,
            accept_multiple_files=True
        )
    with col2:
        st.metric("📁 Uploaded", len(uploaded_files) if uploaded_files else 0)
        st.metric("✅ Parsed", len(st.session_state.parsed_resumes))
    
    if uploaded_files and client:
        if st.button("🚀 Parse All", type="primary"):
            progress = st.progress(0)
            status = st.empty()
            
            st.session_state.parsed_resumes = []
            st.session_state.resume_texts = {}
            
            for idx, file in enumerate(uploaded_files):
                status.text(f"Processing: {file.name}")
                
                text = extract_text_from_file(file)
                
                if text:
                    parsed = parse_resume_with_groq(client, text, file.name, mask_pii_enabled)
                    if parsed:
                        st.session_state.parsed_resumes.append(parsed)
                        st.session_state.resume_texts[parsed.get('name', '')] = text
                
                progress.progress((idx + 1) / len(uploaded_files))
            
            status.empty()
            progress.empty()
            
            if st.session_state.parsed_resumes:
                st.session_state.candidates_df = pd.DataFrame(st.session_state.parsed_resumes)
                st.success(f"✅ Parsed {len(st.session_state.parsed_resumes)} resumes!")
                
                csv_buffer = io.StringIO()
                st.session_state.candidates_df.to_csv(csv_buffer, index=False)
                
                st.download_button(
                    "💾 Download CSV",
                    csv_buffer.getvalue(),
                    f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )

def render_database_tab(start_date, end_date):
    """Render the Candidate Database tab"""
    st.header("Candidate Database")
    
    if st.session_state.candidates_df is not None:
        total_candidates = len(st.session_state.candidates_df)
        
        # If JD requirements exist, apply automated pre-screening
        if st.session_state.jd_requirements:
            filtered_df, rejected_df = automated_pre_screen(
                st.session_state.candidates_df,
                st.session_state.jd_requirements,
                start_date,
                end_date
            )
            
            # Store rejected candidates in session state
            if not rejected_df.empty:
                st.session_state.rejected_candidates = rejected_df.to_dict('records')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Resumes", total_candidates)
            with col2:
                st.metric("Qualified Candidates", len(filtered_df))
            with col3:
                rate = (len(filtered_df) / total_candidates * 100) if total_candidates > 0 else 0
                st.metric("Qualification Rate", f"{rate:.1f}%")
            
            st.info("✨ Auto-filtered based on Job Description requirements")
            
            # Show rejected candidates info with download option
            if not rejected_df.empty:
                st.warning(f"📁 {len(rejected_df)} candidates were pre-screened out")
                
                csv_data, filename = save_rejected_to_csv(rejected_df)
                if csv_data:
                    st.download_button(
                        "📥 Download Rejected Candidates",
                        csv_data,
                        filename,
                        "text/csv",
                        help="Save rejected candidates for future opportunities"
                    )
        else:
            filtered_df = st.session_state.candidates_df
            st.metric("Total Candidates", total_candidates)
            st.warning("⚠️ Upload Job Description in 'Match' tab for automated pre-screening")
        
        st.divider()
        
        # Display candidates table
        available_cols = list(filtered_df.columns)
        default_cols = [col for col in ['name', 'experience_years', 'tech_stack', 'current_role', 'parsed_date'] 
                       if col in available_cols]
        
        display_cols = st.multiselect(
            "Select Columns to Display",
            available_cols,
            default=default_cols if default_cols else available_cols[:min(4, len(available_cols))]
        )
        
        if display_cols:
            st.dataframe(filtered_df[display_cols], use_container_width=True, height=400)
        
        if not filtered_df.empty:
            csv_buffer = io.StringIO()
            filtered_df.to_csv(csv_buffer, index=False)
            st.download_button(
                "📥 Download Qualified Candidates",
                csv_buffer.getvalue(),
                f"qualified_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )
    else:
        st.info("Upload resumes first in the 'Upload' tab")

def render_matching_tab(client, start_date, end_date, top_n):
    """Render the AI Matching tab"""
    st.header("Step 2: AI-Powered Candidate Matching")
    
    if st.session_state.candidates_df is not None:
        # JD Upload
        st.subheader("📌 Job Description Input")
        jd_input_mode = st.radio(
            "Choose input method:",
            ["Paste Text", "Upload File (PDF/DOCX)"],
            horizontal=True
        )
        
        job_desc = ""
        
        if jd_input_mode == "Upload File (PDF/DOCX)":
            jd_file = st.file_uploader(
                "Upload Job Description",
                type=['pdf', 'docx'],
                key="jd_upload"
            )
            if jd_file:
                jd_text = extract_text_from_file(jd_file)
                if jd_text:
                    job_desc = jd_text
                    st.success("✅ JD loaded successfully!")
                    with st.expander("Preview JD"):
                        st.text(job_desc[:500] + "..." if len(job_desc) > 500 else job_desc)
        else:
            jd_template = st.selectbox(
                "Template",
                ["Custom"] + list(JD_TEMPLATES.keys())
            )
            
            job_desc = st.text_area(
                "Job Description",
                value=JD_TEMPLATES.get(jd_template, ""),
                height=250
            )
        
        if job_desc and client:
            # Extract JD requirements automatically
            if st.button("🎯 Analyze JD & Match Candidates", type="primary"):
                with st.spinner("Extracting job requirements..."):
                    jd_requirements = extract_jd_requirements(client, job_desc)
                    
                    if jd_requirements:
                        st.session_state.jd_requirements = jd_requirements
                        
                        # Display extracted requirements
                        st.success("✅ Job requirements extracted!")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Minimum Experience:** {jd_requirements.get('min_experience', 0)} years")
                        with col2:
                            st.info(f"**Role:** {jd_requirements.get('role_title', 'N/A')}")
                        
                        with st.expander("📋 Required Skills"):
                            required = jd_requirements.get('required_skills', [])
                            if required:
                                st.write(", ".join(required))
                            else:
                                st.write("No specific skills mentioned")
                
                # Apply automated pre-screening
                with st.spinner("Pre-screening candidates based on JD..."):
                    filtered, rejected = automated_pre_screen(
                        st.session_state.candidates_df,
                        st.session_state.jd_requirements,
                        start_date,
                        end_date
                    )
                    
                    # Store rejected candidates
                    if not rejected.empty:
                        st.session_state.rejected_candidates = rejected.to_dict('records')
                    
                    if filtered.empty:
                        st.warning("⚠️ No candidates match the job requirements")
                    else:
                        st.success(f"✅ {len(filtered)} candidates qualified for detailed analysis")
                
                # Match candidates with JD
                if not filtered.empty:
                    with st.spinner("AI is analyzing candidates..."):
                        results = match_candidates_with_jd(
                            client, filtered, job_desc, top_n
                        )
                        
                        if results:
                            st.session_state.matched_results = results
                            st.success(f"🏆 Top {len(results)} candidates ranked!")
        
        if st.session_state.matched_results:
            st.divider()
            st.subheader(f"🏆 Top {len(st.session_state.matched_results)} Candidates")
            
            for cand in st.session_state.matched_results:
                rank = cand.get('rank', 0)
                name = cand.get('name', 'Unknown')
                
                # HR-Friendly Score Labels
                keyword_match = cand.get('keyword_match_score', 0)
                ai_analysis = cand.get('ai_analysis_score', 0)
                final_score = cand.get('final_score', ai_analysis)
                
                strengths = cand.get('strengths', 'N/A')
                gaps = cand.get('gaps', 'N/A')
                rec = cand.get('recommendation', 'N/A')
                priority = cand.get('interview_priority', 'Medium')
                
                color = "#28a745" if final_score >= 80 else "#ffc107" if final_score >= 60 else "#dc3545"
                
                st.markdown(f"""
                <div style="border-left: 5px solid {color}; padding: 20px; margin: 15px 0; background: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h3>#{rank} - {name} <span style="float: right; color: {color};">{final_score}% Overall Match</span></h3>
                    <p><strong>🎯 {rec}</strong> | <strong>⚡ Interview Priority: {priority}</strong></p>
                    <p style="font-size: 0.9em; color: #666;">
                        📊 AI Deep Analysis: {ai_analysis}% | 🔍 Keyword Match: {keyword_match}%
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**✅ Key Strengths:**")
                    st.success(strengths)
                with col2:
                    if gaps and gaps.lower() not in ["none", "n/a", ""]:
                        st.markdown("**⚠️ Areas to Explore:**")
                        st.warning(gaps)
                
                cand_full = st.session_state.candidates_df[
                    st.session_state.candidates_df['name'] == name
                ]
                
                if not cand_full.empty:
                    cand_data = cand_full.iloc[0].to_dict()
                    
                    with st.expander(f"📋 Full Profile - {name}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Email:** {cand_data.get('email')}")
                            st.write(f"**Phone:** {cand_data.get('phone')}")
                            st.write(f"**Experience:** {cand_data.get('experience_years')} years")
                        with col2:
                            st.write(f"**Current Role:** {cand_data.get('current_role')}")
                            st.write(f"**Education:** {cand_data.get('education')}")
                        
                        st.write(f"**Technical Skills:** {cand_data.get('tech_stack')}")
                        st.write(f"**Key Projects:** {cand_data.get('key_projects')}")
                        
                        if st.button(f"🎤 Generate Interview Questions", key=f"q_{rank}"):
                            with st.spinner("Generating personalized questions..."):
                                questions = generate_interview_questions(
                                    client, cand_data, job_desc
                                )
                                
                                if questions:
                                    for q in questions:
                                        st.markdown(f"""
                                        **{q.get('category')}:** {q.get('question')}  
                                        *Why we're asking: {q.get('why_asking')}*
                                        """)
                                        st.divider()
                
                st.divider()
            
            # Download ranking results
            results_df = pd.DataFrame(st.session_state.matched_results)
            csv_buffer = io.StringIO()
            results_df.to_csv(csv_buffer, index=False)
            
            st.download_button(
                "📊 Download Ranking Results",
                csv_buffer.getvalue(),
                f"top_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )
    else:
        st.info("Upload resumes first in the 'Upload' tab")

def render_analytics_tab():
    """Render the Analytics tab"""
    st.header("📈 Recruitment Analytics")
    
    if st.session_state.candidates_df is not None:
        df = st.session_state.candidates_df
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_exp = df['experience_years'].astype(float).mean()
            st.metric("Average Experience", f"{avg_exp:.1f} years")
        with col2:
            st.metric("Total Candidates", len(df))
        with col3:
            if st.session_state.matched_results:
                avg_match = sum(c['final_score'] for c in st.session_state.matched_results) / len(st.session_state.matched_results)
                st.metric("Avg Match Score", f"{avg_match:.1f}%")
            else:
                st.metric("Avg Match Score", "N/A")
        with col4:
            unique_skills = len(set(', '.join(df['tech_stack'].astype(str)).split(', ')))
            st.metric("Unique Skills", unique_skills)
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Experience Distribution")
            exp_bins = pd.cut(df['experience_years'].astype(float), bins=[0, 2, 5, 10, 20], labels=['0-2 yrs', '2-5 yrs', '5-10 yrs', '10+ yrs'])
            exp_counts = exp_bins.value_counts().sort_index()
            
            fig = px.bar(
                x=exp_counts.index, 
                y=exp_counts.values, 
                color=exp_counts.values,
                color_continuous_scale='Blues',
                labels={'x': 'Experience Range', 'y': 'Number of Candidates'}
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if st.session_state.matched_results:
                st.subheader("Match Score Distribution")
                scores = [c['final_score'] for c in st.session_state.matched_results]
                
                fig = px.histogram(
                    x=scores,
                    nbins=10,
                    labels={'x': 'Match Score (%)', 'y': 'Number of Candidates'},
                    color_discrete_sequence=['#667eea']
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Run candidate matching to see score distribution")
        
        st.divider()
        st.subheader("Top Skills in Candidate Pool")
        
        # Skills visualization
        all_skills = ', '.join(df['tech_stack'].astype(str)).lower()
        skills_list = [s.strip() for s in all_skills.split(',') if s.strip()]
        skill_counts = pd.Series(skills_list).value_counts().head(15)
        
        # Create a mapping of skills to candidates
        skill_to_candidates = {}
        for idx, row in df.iterrows():
            tech_stack = str(row.get('tech_stack', '')).lower()
            candidate_name = row.get('name', 'Unknown')
            for skill in skill_counts.index:
                if skill in tech_stack:
                    if skill not in skill_to_candidates:
                        skill_to_candidates[skill] = []
                    skill_to_candidates[skill].append(candidate_name)
        
        # Create hover text
        hover_texts = []
        for skill in skill_counts.index:
            candidates = skill_to_candidates.get(skill, [])
            hover_text = f"<b>{skill.title()}</b><br>Candidates: {', '.join(candidates[:5])}"
            if len(candidates) > 5:
                hover_text += f"<br>and {len(candidates) - 5} more..."
            hover_texts.append(hover_text)
        
        # Create horizontal bar chart
        fig = px.bar(
            x=skill_counts.values,
            y=skill_counts.index,
            orientation='h',
            color=skill_counts.values,
            color_continuous_scale='Viridis',
            labels={'x': 'Number of Candidates', 'y': 'Skill'}
        )
        
        fig.update_traces(
            hovertemplate=hover_texts,
            hoverinfo='text'
        )
        
        fig.update_layout(
            showlegend=False,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("Upload resumes first to see analytics")