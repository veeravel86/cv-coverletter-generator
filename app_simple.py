import os
import logging
import traceback
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from services.ingest import get_pdf_ingestor
from services.rag import create_rag_retriever, ContextBuilder
from services.llm import get_llm_service
from services.style_extract import get_style_extractor
from services.skills_generator import get_skills_generator
from services.experience_generator import get_experience_generator
from services.summary_generator import get_summary_generator
from exporters.pdf_export import get_pdf_exporter

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="CV Generator",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

def initialize_session_state():
    defaults = {
        'processed_documents': None,
        'vector_store': None,
        'style_profile': None,
        'generated_cv': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def extract_contact_info_from_sample_cv(sample_cv_text):
    """Extract contact information from sample CV"""
    if not sample_cv_text:
        return None, "JOHN DOE"
    
    lines = sample_cv_text.split('\n')
    name = None
    contact_info = []
    
    # Look for name (usually first non-empty line or after contact/header sections)
    for i, line in enumerate(lines[:10]):  # Check first 10 lines for name
        line = line.strip()
        if line and not any(keyword in line.lower() for keyword in [
            'email', 'phone', 'linkedin', 'address', 'contact', '@', '+', 'www', 'http'
        ]):
            # This might be the name
            if len(line.split()) <= 4 and not line.startswith(('##', '#', '**', '•', '-')):
                name = line.upper()  # Use uppercase for consistency
                break
    
    # Extract contact information
    for line in lines:
        line = line.strip()
        if any(keyword in line.lower() for keyword in [
            'email', 'phone', 'linkedin', 'address', 'location', '@', '+1', 'tel:', 'mobile'
        ]):
            # Clean up the contact line
            clean_line = line.replace('**', '').replace('*', '').strip()
            if clean_line and not clean_line.startswith(('#', '##')):
                contact_info.append(clean_line)
    
    # If we found contact info, format it
    if contact_info:
        # Join multiple contact lines with ' | '
        formatted_contact = ' | '.join(contact_info[:4])  # Limit to 4 contact items
        return formatted_contact, name or "JOHN DOE"
    
    return None, name or "JOHN DOE"

def extract_previous_experiences_from_sample_cv(sample_cv_text):
    """Extract previous work experiences from sample CV (excluding most recent)"""
    if not sample_cv_text:
        return []
    
    lines = sample_cv_text.split('\n')
    experiences = []
    current_job = None
    current_bullets = []
    in_experience_section = False
    
    for line in lines:
        line = line.strip()
        
        # Detect experience section
        if any(keyword in line.lower() for keyword in [
            'experience', 'work experience', 'professional experience', 'employment'
        ]) and line.startswith(('##', '#', '**')):
            in_experience_section = True
            continue
        
        # Exit experience section if we hit another section
        if in_experience_section and line.startswith(('##', '#')) and not any(
            keyword in line.lower() for keyword in ['experience', 'employment']
        ):
            # Save current job before exiting
            if current_job and current_bullets:
                experiences.append({
                    'job_title': current_job,
                    'bullets': current_bullets.copy()
                })
            break
        
        if in_experience_section and line:
            # Check if this is a job title line (contains company, dates, title)
            if ('|' in line and any(keyword in line.lower() for keyword in [
                'inc', 'corp', 'company', 'ltd', 'llc', 'technologies', 'solutions', 'systems'
            ])) or (any(char in line for char in ['2019', '2020', '2021', '2022', '2023', '2024']) and '|' in line):
                # Save previous job if exists
                if current_job and current_bullets:
                    experiences.append({
                        'job_title': current_job,
                        'bullets': current_bullets.copy()
                    })
                
                # Start new job
                current_job = line
                current_bullets = []
            
            # Check if this is a bullet point
            elif line.startswith(('•', '-', '*', '○', '▪')) and current_job:
                bullet_text = line[1:].strip()
                if bullet_text:
                    current_bullets.append(bullet_text)
    
    # Don't forget the last job
    if current_job and current_bullets:
        experiences.append({
            'job_title': current_job,
            'bullets': current_bullets.copy()
        })
    
    # Return all but the first (most recent) experience
    return experiences[1:] if len(experiences) > 1 else []

def assemble_cv_from_components(skills_result, experience_result, summary_result, processed_texts):
    """Assemble CV using sample CV contact info and previous experiences, with LLM current experience"""
    
    cv_sections = []
    
    # Extract sample CV information
    sample_cv_text = processed_texts.get("sample_cv", "")
    contact_info, name = extract_contact_info_from_sample_cv(sample_cv_text)
    previous_experiences = extract_previous_experiences_from_sample_cv(sample_cv_text)
    
    # Name and Contact Information from Sample CV
    cv_sections.append(f"# {name}")
    cv_sections.append("")
    cv_sections.append("## CONTACT INFORMATION")
    
    if contact_info:
        cv_sections.append(contact_info)
    else:
        # Fallback contact info
        cv_sections.append("john.doe@email.com | +1-555-123-4567 | Location: New York, NY | LinkedIn: linkedin.com/in/johndoe")
    cv_sections.append("")
    
    # Professional Summary (from LLM) - Use "CAREER SUMMARY" for PDF compatibility
    if summary_result and summary_result["summary"]:
        cv_sections.append("## CAREER SUMMARY")
        cv_sections.append(summary_result["summary"])
        cv_sections.append("")
    
    # Core Skills (from LLM) - Use "SKILLS" for PDF compatibility
    if skills_result and skills_result["skills"]:
        cv_sections.append("## SKILLS")
        for skill in skills_result["skills"]:
            cv_sections.append(f"• {skill}")
        cv_sections.append("")
    
    # Professional Experience - Use "EXPERIENCE" for PDF compatibility
    cv_sections.append("## EXPERIENCE")
    cv_sections.append("")
    
    # Current Experience (from LLM - use generated bullets)
    if experience_result and experience_result["bullets"]:
        # Use first few bullets for current role
        current_role_bullets = experience_result["bullets"][:4] if len(experience_result["bullets"]) > 4 else experience_result["bullets"]
        
        cv_sections.append("**Senior Engineering Manager** | TechCorp Inc. | 01/2020 - Present")
        for bullet in current_role_bullets:
            cv_sections.append(f"• {bullet.full_bullet}")
        cv_sections.append("")
    
    # Previous Experiences (from Sample CV)
    for exp in previous_experiences:
        cv_sections.append(exp['job_title'])
        for bullet in exp['bullets'][:4]:  # Limit to 4 bullets per role
            cv_sections.append(f"• {bullet}")
        cv_sections.append("")
    
    # Education (extract from sample CV or other processed texts)
    cv_sections.append("## EDUCATION")
    
    education_found = False
    # First try sample CV
    if sample_cv_text:
        lines = sample_cv_text.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ["bachelor", "master", "degree", "university", "college", "phd", "doctorate"]):
                clean_line = line.replace('**', '').replace('*', '').strip()
                if clean_line and not clean_line.startswith(('#', '##')):
                    cv_sections.append(f"• {clean_line}")
                    education_found = True
                    break
    
    # Try other processed texts if not found in sample CV
    if not education_found:
        for doc_type, text in processed_texts.items():
            if doc_type != "sample_cv" and any(word in text.lower() for word in ["bachelor", "master", "degree", "university", "college"]):
                lines = text.split('\n')
                for line in lines:
                    if any(word in line.lower() for word in ["bachelor", "master", "degree", "university", "college"]):
                        cv_sections.append(f"• {line.strip()}")
                        education_found = True
                        break
                if education_found:
                    break
    
    if not education_found:
        cv_sections.append("• Bachelor of Science in Computer Science | University Name | 2016")
    
    cv_sections.append("")
    
    # Join all sections
    return "\n".join(cv_sections)

def main():
    initialize_session_state()
    
    st.title("🎯 Simple CV Generator")
    st.markdown("**Upload PDFs → Generate CV → Download PDF**")
    
    with st.sidebar:
        st.header("📋 Configuration")
        
        if not os.getenv("OPENAI_API_KEY"):
            st.error("⚠️ OpenAI API key not found!")
            st.info("Please set OPENAI_API_KEY in your environment")
            st.stop()
        else:
            st.success("✅ OpenAI API key loaded")
        
        st.divider()
        
        # Model selection dropdown
        model_choice = st.selectbox(
            "Select Model",
            options=["gpt-4o-mini", "gpt-4o", "gpt-5"],
            index=0,
            help="gpt-4o-mini is fastest and cheapest, gpt-4o is high quality, gpt-5 is the most advanced"
        )
        
        # Store model choice in session state
        st.session_state['selected_model'] = model_choice
    
    tab1, tab2, tab3 = st.tabs(["📄 Upload", "🤖 Generate", "💾 Download"])
    
    with tab1:
        handle_document_upload()
    
    with tab2:
        if st.session_state.processed_documents:
            handle_generation()
        else:
            st.info("👆 Please upload and process documents first")
    
    with tab3:
        if st.session_state.generated_cv:
            handle_download()
        else:
            st.info("👆 Please generate content first")

def handle_document_upload():
    st.header("📄 Document Upload")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Job Description")
        job_description = st.file_uploader(
            "Upload Job_Description.pdf",
            type=['pdf'],
            key="job_description",
            help="The target job description PDF"
        )
        
        st.subheader("Skills Superset")
        skills_superset = st.file_uploader(
            "Upload Skills_Superset.pdf", 
            type=['pdf'],
            key="skills_superset",
            help="Your comprehensive skills and technologies document"
        )
    
    with col2:
        st.subheader("Experience Superset")
        experience_superset = st.file_uploader(
            "Upload Experience_Superset.pdf", 
            type=['pdf'],
            key="experience_superset",
            help="Your comprehensive work experience and projects document"
        )
        
        st.subheader("Sample CV Style")
        sample_cv = st.file_uploader(
            "Upload Sample_CV.pdf",
            type=['pdf'],
            key="sample_cv",
            help="CV to mimic the formatting style from"
        )
    
    if st.button("🔄 Process Documents", type="primary"):
        # Check if at least one document is uploaded
        uploaded_docs = [job_description, skills_superset, experience_superset, sample_cv]
        if not any(uploaded_docs):
            st.error("❌ Please upload at least one PDF file")
            return
        
        with st.spinner("Processing documents..."):
            try:
                ingestor = get_pdf_ingestor()
                
                # Only include uploaded files
                uploaded_files = {}
                if job_description:
                    uploaded_files["job_description"] = job_description
                if skills_superset:
                    uploaded_files["skills_superset"] = skills_superset
                if experience_superset:
                    uploaded_files["experience_superset"] = experience_superset
                if sample_cv:
                    uploaded_files["sample_cv"] = sample_cv
                
                processed_data = ingestor.ingest_pdfs(uploaded_files)
                st.session_state.processed_documents = processed_data
                st.session_state.vector_store = processed_data["vector_store"]
                
                # Only extract style if sample CV was uploaded
                if "sample_cv" in processed_data["processed_texts"]:
                    style_extractor = get_style_extractor()
                    sample_text = processed_data["processed_texts"]["sample_cv"]
                    style_profile = style_extractor.extract_style_from_text(sample_text)
                    st.session_state.style_profile = style_profile
                else:
                    st.session_state.style_profile = None
                
                st.success(f"✅ Processed {processed_data['doc_count']} documents successfully!")
                
                # Processing summary with expandable metrics
                with st.expander("📊 **Processing Summary**", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Chunks", len(processed_data["documents"]))
                    with col2:
                        doc_summary = ingestor.get_document_summary(processed_data["processed_texts"])
                        total_words = sum(doc_summary.values())
                        st.metric("Total Words", f"{total_words:,}")
                    with col3:
                        st.metric("Vector Embeddings", len(processed_data["documents"]))
                
                # Progressive disclosure for all processed documents
                st.divider()
                st.subheader("📋 Processed Documents")
                
                # Display cleaned job description (if uploaded)
                if "job_description" in processed_data["processed_texts"]:
                    cleaned_jd = processed_data["processed_texts"].get("job_description", "")
                    if cleaned_jd:
                        with st.expander(f"📄 **Job Description** ({len(cleaned_jd.split())} words)", expanded=False):
                            st.text_area(
                                "Cleaned Job Description (AI Processed)",
                                cleaned_jd,
                                height=300,
                                help="AI-cleaned content with LinkedIn elements and irrelevant content removed",
                                key="cleaned_jd_display"
                            )
                            
                            # Original raw text option
                            with st.expander("🔍 View Original Raw PDF Text"):
                                raw_jd = processed_data["texts"].get("job_description", "")
                                st.text_area(
                                    "Original Raw Text",
                                    raw_jd,
                                    height=200,
                                    help="Direct PDF extraction without processing",
                                    key="raw_jd_display"
                                )
                                st.caption(f"Raw text: {len(raw_jd.split())} words, {len(raw_jd)} characters")
                
                # Display structured Sample CV content (if uploaded)
                if "sample_cv" in processed_data["processed_texts"]:
                    sample_cv_text = processed_data["processed_texts"].get("sample_cv", "")
                    if sample_cv_text:
                        with st.expander(f"📋 **Sample CV** ({len(sample_cv_text.split())} words)", expanded=False):
                            st.text_area(
                                "Structured Sample CV (AI Processed)",
                                sample_cv_text,
                                height=400,
                                help="AI-structured content with proper headings and formatting",
                                key="sample_cv_display"
                            )
                            
                            # Original raw text option
                            with st.expander("🔍 View Original Raw Sample CV Text"):
                                raw_sample = processed_data["texts"].get("sample_cv", "")
                                st.text_area(
                                    "Original Sample CV Text",
                                    raw_sample,
                                    height=200,
                                    help="Direct PDF extraction without processing",
                                    key="raw_sample_display"
                                )
                                st.caption(f"Raw sample CV: {len(raw_sample.split())} words, {len(raw_sample)} characters")
                
                # Display structured Skills Superset content (if uploaded)
                if "skills_superset" in processed_data["processed_texts"]:
                    skills_text = processed_data["processed_texts"].get("skills_superset", "")
                    if skills_text:
                        with st.expander(f"🛠️ **Skills Superset** ({len(skills_text.split())} words)", expanded=False):
                            st.text_area(
                                "Structured Skills Superset (AI Processed)",
                                skills_text,
                                height=400,
                                help="AI-structured skills content with proper headings and formatting",
                                key="skills_superset_display"
                            )
                            
                            # Original raw text option
                            with st.expander("🔍 View Original Raw Skills Superset Text"):
                                raw_skills = processed_data["texts"].get("skills_superset", "")
                                st.text_area(
                                    "Original Skills Superset Text",
                                    raw_skills,
                                    height=200,
                                    help="Direct PDF extraction without processing",
                                    key="raw_skills_display"
                                )
                                st.caption(f"Raw skills: {len(raw_skills.split())} words, {len(raw_skills)} characters")
                
                # Display structured Experience Superset content (if uploaded)
                if "experience_superset" in processed_data["processed_texts"]:
                    experience_text = processed_data["processed_texts"].get("experience_superset", "")
                    if experience_text:
                        with st.expander(f"💼 **Experience Superset** ({len(experience_text.split())} words)", expanded=False):
                            st.text_area(
                                "Structured Experience Superset (AI Processed)",
                                experience_text,
                                height=400,
                                help="AI-structured experience content preserving existing headings and focusing on experience content",
                                key="experience_superset_display"
                            )
                            
                            # Original raw text option
                            with st.expander("🔍 View Original Raw Experience Superset Text"):
                                raw_experience = processed_data["texts"].get("experience_superset", "")
                                st.text_area(
                                    "Original Experience Superset Text",
                                    raw_experience,
                                    height=200,
                                    help="Direct PDF extraction without processing",
                                    key="raw_experience_display"
                                )
                                st.caption(f"Raw experience: {len(raw_experience.split())} words, {len(raw_experience)} characters")
                
            except Exception as e:
                st.error(f"❌ **Document Processing Failed**")
                st.error(f"**Error Details:** {str(e)}")
                with st.expander("🔍 **Full Error Details**"):
                    st.code(traceback.format_exc())

def handle_generation():
    st.header("🤖 CV Generation")
    
    # Get the LLM service with the selected model
    model_choice = st.session_state.get('selected_model', 'gpt-4o-mini')
    from services.llm import create_llm_service
    llm_service = create_llm_service(model_choice)
    
    retriever = create_rag_retriever(st.session_state.vector_store)
    context_builder = ContextBuilder(retriever)
    
    st.subheader("📄 CV Generation")
    st.info(f"Using model: **{model_choice}**")
    
    if st.button("🚀 Generate CV", type="primary"):
        generate_cv(llm_service, context_builder)

def generate_cv(llm_service, context_builder):
    with st.spinner("Generating CV..."):
        try:
            # Get processed documents from session state
            processed_texts = st.session_state.processed_documents["processed_texts"]
            
            # Initialize generators
            skills_generator = get_skills_generator()
            experience_generator = get_experience_generator()
            summary_generator = get_summary_generator()
            
            job_description = processed_texts.get("job_description", "")
            experience_superset = processed_texts.get("experience_superset", "")
            skills_superset = processed_texts.get("skills_superset", "")
            
            # Phase 1: Generate optimized skills
            with st.spinner("🎯 Generating optimized skills..."):
                skills_result = skills_generator.generate_top_skills(
                    job_description, experience_superset, skills_superset
                )
                
                if skills_result["valid"]:
                    st.success(f"✅ Generated {skills_result['skill_count']} optimized skills")
                else:
                    st.warning(f"⚠️ Skills generation: {skills_result['validation_message']}")
            
            # Phase 2: Generate experience summary bullets
            experience_result = None
            if experience_superset and job_description:
                with st.spinner("📋 Generating experience summary bullets..."):
                    experience_result = experience_generator.generate_experience_summary(
                        job_description, experience_superset
                    )
                    
                    if experience_result["valid"]:
                        st.success(f"✅ Generated {experience_result['bullet_count']} experience bullets")
                    else:
                        st.warning(f"⚠️ Experience generation: {experience_result['validation_message']}")
            
            # Phase 3: Generate professional summary
            summary_result = None
            if job_description and (experience_superset or skills_superset):
                with st.spinner("📝 Generating executive professional summary..."):
                    summary_result = summary_generator.generate_professional_summary(
                        job_description, experience_superset, skills_superset
                    )
                    
                    if summary_result["valid"]:
                        st.success(f"✅ Generated professional summary ({summary_result['word_count']}/30 words)")
                    else:
                        st.warning(f"⚠️ Summary generation: {summary_result['validation_message']}")
            
            # Show generated content in expandable UI
            st.subheader("🔍 Generated Content Preview")
            
            # Professional Summary at the top (full width if generated)
            if summary_result and summary_result["summary"]:
                with st.expander("📝 **Generated Professional Summary**", expanded=True):
                    st.markdown(f"**Executive Summary (≤30 words):**")
                    st.info(f"📋 {summary_result['summary']}")
                    
                    # Summary analysis
                    analysis = summary_generator.get_summary_analysis(
                        summary_generator._process_summary_response(summary_result['summary'], job_description),
                        job_description
                    )
                    
                    col_s1, col_s2, col_s3 = st.columns(3)
                    with col_s1:
                        st.metric("Word Count", f"{analysis['word_count']}/{analysis['max_words']}")
                        st.caption(analysis['compliance'])
                    with col_s2:
                        st.metric("JD Keywords", "Present" if summary_result['has_keywords'] else "Limited")
                        st.caption(analysis['keyword_integration'])
                    with col_s3:
                        st.metric("Tone Score", analysis['tone_score'])
                        st.caption(analysis['tone_assessment'])
                    
                    if analysis['executive_ready']:
                        st.success("🎯 Executive-ready summary")
                    else:
                        st.warning("⚠️ May need refinement")
            
            col1, col2 = st.columns(2)
            
            with col1:
                with st.expander("🎯 **Generated Skills (Top 10)**", expanded=True):
                    if skills_result["skills"]:
                        st.write("**Priority Order (Job Description Aligned):**")
                        for i, skill in enumerate(skills_result["skills"], 1):
                            st.write(f"**{i}.** {skill}")
                        
                        # Skills statistics
                        st.divider()
                        skill_col1, skill_col2 = st.columns(2)
                        with skill_col1:
                            st.metric("Skills Count", skills_result["skill_count"])
                        with skill_col2:
                            st.metric("Validation", "✅ Pass" if skills_result["valid"] else "⚠️ Partial")
                    else:
                        st.warning("No skills generated")
            
            with col2:
                with st.expander("📋 **Generated Experience Bullets (Top 8)**", expanded=True):
                    if experience_result and experience_result["bullets"]:
                        st.write("**SAR Format (Situation-Action-Result):**")
                        for i, bullet in enumerate(experience_result["bullets"], 1):
                            st.write(f"**{i}.** {bullet.full_bullet}")
                            st.caption(f"   Heading: {bullet.heading} | Words: {bullet.word_count}")
                        
                        # Experience statistics
                        st.divider()
                        exp_col1, exp_col2 = st.columns(2)
                        with exp_col1:
                            st.metric("Bullets Count", experience_result["bullet_count"])
                            st.metric("Two-Word Headings", experience_result["two_word_headings_count"])
                        with exp_col2:
                            if experience_result["bullets"]:
                                summary = experience_generator.get_bullets_summary(experience_result["bullets"])
                                st.metric("Avg Words", summary["avg_word_count"])
                                st.metric("Word Range", summary["word_count_range"])
                    else:
                        st.info("Experience superset needed for bullet generation")
            
            # Phase 4: Assemble complete CV from optimized components
            st.divider()
            
            with st.spinner("📝 Assembling complete CV from optimized components..."):
                # Get processed texts for basic info extraction
                processed_texts = st.session_state.processed_documents["processed_texts"]
                
                # Assemble CV directly from components
                cv_content = assemble_cv_from_components(
                    skills_result, experience_result, summary_result, processed_texts
                )
                
                # Debug information with progressive disclosure
                with st.expander("🔍 **CV Assembly Debug**", expanded=False):
                    st.write("**Component Assembly Status:**")
                    debug_col1, debug_col2, debug_col3 = st.columns(3)
                    
                    with debug_col1:
                        st.metric("Skills Added", len(skills_result["skills"]) if skills_result["skills"] else 0)
                    with debug_col2:
                        st.metric("Experience Bullets", len(experience_result["bullets"]) if experience_result and experience_result["bullets"] else 0)
                    with debug_col3:
                        st.metric("Summary Words", summary_result["word_count"] if summary_result else 0)
                    
                    # Show sample CV extraction info
                    st.divider()
                    st.write("**Sample CV Extraction:**")
                    sample_cv_text = processed_texts.get("sample_cv", "")
                    
                    if sample_cv_text:
                        # Extract info for debugging
                        contact_info, name = extract_contact_info_from_sample_cv(sample_cv_text)
                        previous_experiences = extract_previous_experiences_from_sample_cv(sample_cv_text)
                        
                        extract_col1, extract_col2 = st.columns(2)
                        with extract_col1:
                            st.write(f"**Name Extracted:** {name}")
                            st.write(f"**Contact Info:** {'✅ Found' if contact_info else '❌ Not found'}")
                        with extract_col2:
                            st.write(f"**Previous Experiences:** {len(previous_experiences)} found")
                            if previous_experiences:
                                for i, exp in enumerate(previous_experiences[:2], 1):
                                    st.write(f"  {i}. {exp['job_title'][:50]}...")
                    else:
                        st.warning("No sample CV provided - using placeholder data")
                    
                    st.write(f"**Final CV Length:** {len(cv_content):,} characters")
                
                # Create result structure similar to LLM service
                result = {
                    "content": cv_content,
                    "model_used": "Direct Assembly",
                    "valid": True
                }
                
                # Store results in session state
                st.session_state.generated_cv = result["content"]
                st.session_state.generated_skills = skills_result
                if experience_result:
                    st.session_state.generated_experience = experience_result
                if summary_result:
                    st.session_state.generated_summary = summary_result
                
                st.success("✅ Complete ATS-optimized CV assembled successfully from specialized components!")
                
                # Display final CV with progressive disclosure
                st.subheader("📄 Generated CV Output")
                
                # CV Content in expandable section
                with st.expander("📋 **Complete Generated CV**", expanded=True):
                    st.text_area("CV Content", result["content"], height=600, key="cv_preview")
                
                # Generation Summary in expandable section
                with st.expander("📊 **Generation Summary & Metrics**", expanded=True):
                    # Component counts
                    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
                    
                    with stats_col1:
                        st.metric("Skills Generated", skills_result["skill_count"])
                    with stats_col2:
                        if experience_result:
                            st.metric("Experience Bullets", experience_result["bullet_count"])
                        else:
                            st.metric("Experience Bullets", "N/A")
                    with stats_col3:
                        if summary_result:
                            st.metric("Summary Words", f"{summary_result['word_count']}/30")
                        else:
                            st.metric("Summary Words", "N/A")
                    with stats_col4:
                        st.metric("Total Word Count", len(result["content"].split()))
                    
                    # Quality indicators
                    st.divider()
                    st.subheader("🎯 Quality Indicators")
                    
                    quality_col1, quality_col2, quality_col3 = st.columns(3)
                    
                    with quality_col1:
                        if skills_result["valid"]:
                            st.success("✅ Skills ATS-Optimized")
                        else:
                            st.warning("⚠️ Skills Partial")
                    
                    with quality_col2:
                        if experience_result and experience_result["valid"]:
                            st.success("✅ Experience SAR Format")
                        elif experience_result:
                            st.warning("⚠️ Experience Partial")
                        else:
                            st.info("ℹ️ Basic Experience Used")
                    
                    with quality_col3:
                        if summary_result and summary_result["valid"]:
                            st.success("✅ Executive Summary")
                        elif summary_result:
                            st.warning("⚠️ Summary Needs Review")
                        else:
                            st.info("ℹ️ Basic Summary Used")
            
        except Exception as e:
            st.error(f"❌ **CV Generation Failed**")
            st.error(f"**Error Details:** {str(e)}")
            with st.expander("🔍 **Full Error Details**"):
                st.code(traceback.format_exc())


def handle_download():
    st.header("💾 Download PDF")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    
    try:
        pdf_exporter = get_pdf_exporter()
        
        if st.session_state.generated_cv:
            if st.button("📄 Download CV as PDF", type="primary"):
                with st.spinner("Generating PDF..."):
                    pdf_path = f"outputs/cv_{timestamp}.pdf"
                    
                    # Debug CV content for PDF export
                    st.write("🔍 **PDF Export Debug:**")
                    st.write(f"CV content length: {len(st.session_state.generated_cv):,} characters")
                    
                    # Parse sections to see what PDF exporter will find
                    from exporters.pdf_export import PDFExporter
                    temp_exporter = PDFExporter()
                    parsed_sections = temp_exporter._parse_markdown_cv(st.session_state.generated_cv)
                    
                    debug_pdf_col1, debug_pdf_col2 = st.columns(2)
                    with debug_pdf_col1:
                        st.write("**Sections Found by PDF Parser:**")
                        for section_key in parsed_sections.keys():
                            st.write(f"  ✅ {section_key}")
                    
                    with debug_pdf_col2:
                        st.write("**Expected Sections:**")
                        expected_sections = ['contact_information', 'career_summary', 'skills', 'experience', 'education']
                        for section in expected_sections:
                            status = "✅" if section in parsed_sections else "❌"
                            st.write(f"  {status} {section}")
                    
                    with st.expander("📄 **CV Content for PDF**", expanded=False):
                        st.text_area("CV Content Being Exported", st.session_state.generated_cv, height=200, key="pdf_debug_content")
                    
                    with st.expander("🔍 **Parsed Sections Content**", expanded=False):
                        for section_key, content in parsed_sections.items():
                            st.write(f"**{section_key}:**")
                            st.text_area(f"Content for {section_key}", content[:500] + "..." if len(content) > 500 else content, height=100, key=f"debug_{section_key}")
                    
                    if st.session_state.style_profile:
                        pdf_exporter.export_to_pdf(
                            st.session_state.generated_cv,
                            st.session_state.style_profile,
                            pdf_path,
                            "Professional CV"
                        )
                    else:
                        # Create a default style profile if none exists
                        from services.style_extract import StyleProfile
                        default_style = StyleProfile(
                            section_order=["Contact", "Summary", "Experience", "Skills", "Education"],
                            bullet_style="•",
                            spacing_pattern="single_line",
                            heading_format="ALL_CAPS",
                            contact_format="horizontal",
                            date_format="MM/YYYY - MM/YYYY",
                            font_style="professional",
                            margins={"top": "1in", "bottom": "1in", "left": "0.75in", "right": "0.75in"},
                            line_spacing="1.15",
                            emphasis_markers=["**"]
                        )
                        pdf_exporter.export_to_pdf(
                            st.session_state.generated_cv,
                            default_style,
                            pdf_path,
                            "Professional CV"
                        )
                    
                    # Provide download button
                    with open(pdf_path, 'rb') as f:
                        st.download_button(
                            label="⬇️ Download CV PDF",
                            data=f.read(),
                            file_name=f"cv_{timestamp}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                    
                    st.success("✅ CV PDF generated successfully!")
        
    
    except Exception as e:
        st.error(f"❌ **PDF Generation Failed**")
        st.error(f"**Error Details:** {str(e)}")
        with st.expander("🔍 **Full Error Details**"):
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()