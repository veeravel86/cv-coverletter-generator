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
        'generated_cv': None,
        'generated_cover_letter': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

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
        
        generation_type = st.radio(
            "What to Generate",
            ["CV", "Cover Letter", "Both"],
            help="Choose what to generate"
        )
    
    tab1, tab2, tab3 = st.tabs(["📄 Upload", "🤖 Generate", "💾 Download"])
    
    with tab1:
        handle_document_upload()
    
    with tab2:
        if st.session_state.processed_documents:
            handle_generation(generation_type)
        else:
            st.info("👆 Please upload and process documents first")
    
    with tab3:
        if st.session_state.generated_cv or st.session_state.generated_cover_letter:
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
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Chunks", len(processed_data["documents"]))
                with col2:
                    doc_summary = ingestor.get_document_summary(processed_data["processed_texts"])
                    total_words = sum(doc_summary.values())
                    st.metric("Total Words", f"{total_words:,}")
                with col3:
                    st.metric("Vector Embeddings", len(processed_data["documents"]))
                
                # Display cleaned job description (if uploaded)
                if "job_description" in processed_data["processed_texts"]:
                    st.divider()
                    st.subheader("📄 Cleaned Job Description")
                    
                    # Show the LLM-cleaned version
                    cleaned_jd = processed_data["processed_texts"].get("job_description", "")
                    if cleaned_jd:
                        st.text_area(
                            "Job Description Content (Cleaned by AI)",
                            cleaned_jd,
                            height=300,
                            help="This is the cleaned job description content extracted by AI, removing LinkedIn elements and irrelevant content"
                        )
                        st.info(f"📊 Cleaned Job Description: {len(cleaned_jd.split())} words, {len(cleaned_jd)} characters")
                        
                        # Option to view original raw text
                        with st.expander("🔍 View Original Raw PDF Text"):
                            raw_jd = processed_data["texts"].get("job_description", "")
                            st.text_area(
                                "Original Raw Text",
                                raw_jd,
                                height=200,
                                help="This is the original text extracted directly from the PDF"
                            )
                            st.caption(f"Raw text: {len(raw_jd.split())} words, {len(raw_jd)} characters")
                
                # Display structured Sample CV content (if uploaded)
                if "sample_cv" in processed_data["processed_texts"]:
                    st.divider()
                    st.subheader("📋 Structured Sample CV")
                    
                    sample_cv_text = processed_data["processed_texts"].get("sample_cv", "")
                    if sample_cv_text:
                        st.text_area(
                            "Sample CV Content (Structured by AI)",
                            sample_cv_text,
                            height=400,
                            help="This is the sample CV content structured by AI with proper headings and formatting"
                        )
                        st.info(f"📊 Structured Sample CV: {len(sample_cv_text.split())} words, {len(sample_cv_text)} characters")
                        
                        # Option to view original raw text
                        with st.expander("🔍 View Original Raw Sample CV Text"):
                            raw_sample = processed_data["texts"].get("sample_cv", "")
                            st.text_area(
                                "Original Sample CV Text",
                                raw_sample,
                                height=200,
                                help="This is the original text extracted directly from the sample CV PDF"
                            )
                            st.caption(f"Raw sample CV: {len(raw_sample.split())} words, {len(raw_sample)} characters")
                
                # Display structured Skills Superset content (if uploaded)
                if "skills_superset" in processed_data["processed_texts"]:
                    st.divider()
                    st.subheader("🛠️ Structured Skills Superset")
                    
                    skills_text = processed_data["processed_texts"].get("skills_superset", "")
                    if skills_text:
                        st.text_area(
                            "Skills Superset Content (Structured by AI)",
                            skills_text,
                            height=400,
                            help="This is the skills superset content structured by AI with proper headings and formatting"
                        )
                        st.info(f"📊 Structured Skills Superset: {len(skills_text.split())} words, {len(skills_text)} characters")
                        
                        # Option to view original raw text
                        with st.expander("🔍 View Original Raw Skills Superset Text"):
                            raw_skills = processed_data["texts"].get("skills_superset", "")
                            st.text_area(
                                "Original Skills Superset Text",
                                raw_skills,
                                height=200,
                                help="This is the original text extracted directly from the skills superset PDF"
                            )
                            st.caption(f"Raw skills: {len(raw_skills.split())} words, {len(raw_skills)} characters")
                
                # Display structured Experience Superset content (if uploaded)
                if "experience_superset" in processed_data["processed_texts"]:
                    st.divider()
                    st.subheader("💼 Structured Experience Superset")
                    
                    experience_text = processed_data["processed_texts"].get("experience_superset", "")
                    if experience_text:
                        st.text_area(
                            "Experience Superset Content (Structured by AI)",
                            experience_text,
                            height=400,
                            help="This is the experience superset content structured by AI with proper headings and formatting - preserves existing headings and focuses only on experience content"
                        )
                        st.info(f"📊 Structured Experience Superset: {len(experience_text.split())} words, {len(experience_text)} characters")
                        
                        # Option to view original raw text
                        with st.expander("🔍 View Original Raw Experience Superset Text"):
                            raw_experience = processed_data["texts"].get("experience_superset", "")
                            st.text_area(
                                "Original Experience Superset Text",
                                raw_experience,
                                height=200,
                                help="This is the original text extracted directly from the experience superset PDF"
                            )
                            st.caption(f"Raw experience: {len(raw_experience.split())} words, {len(raw_experience)} characters")
                
            except Exception as e:
                st.error(f"❌ **Document Processing Failed**")
                st.error(f"**Error Details:** {str(e)}")
                with st.expander("🔍 **Full Error Details**"):
                    st.code(traceback.format_exc())

def handle_generation(generation_type):
    st.header("🤖 Content Generation")
    
    llm_service = get_llm_service()
    retriever = create_rag_retriever(st.session_state.vector_store)
    context_builder = ContextBuilder(retriever)
    
    if generation_type in ["CV", "Both"]:
        st.subheader("📄 CV Generation")
        
        if st.button("🚀 Generate CV", type="primary"):
            generate_cv(llm_service, context_builder)
    
    if generation_type in ["Cover Letter", "Both"]:
        st.subheader("📝 Cover Letter Generation")
        
        company_name = st.text_input("Company Name (optional)", placeholder="e.g., TechCorp Inc.")
        role_title = st.text_input("Role Title (optional)", placeholder="e.g., Senior Software Engineer")
        
        if st.button("🚀 Generate Cover Letter", type="primary"):
            generate_cover_letter(llm_service, context_builder, company_name, role_title)

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
            
            # Phase 3: Generate complete CV with optimized components
            st.divider()
            
            # Build context for CV generation
            context = context_builder.build_cv_generation_context()
            
            # Create comprehensive CV prompt with generated components
            formatted_skills = skills_generator.format_skills_for_cv(skills_result["skills"], "bullet")
            
            formatted_experience = ""
            if experience_result and experience_result["bullets"]:
                formatted_experience = experience_generator.format_bullets_for_cv(
                    experience_result["bullets"], "standard"
                )
            
            generated_summary = ""
            if summary_result and summary_result["summary"]:
                generated_summary = summary_result["summary"]
            
            cv_prompt = f"""You are a professional CV writer creating an ATS-optimized resume for a senior engineering role.

TASK: Create a complete, professional CV using the provided context and pre-generated optimized components.

REQUIRED SECTIONS:
1. **CONTACT INFORMATION** - Name, email, phone, location (placeholder format)

2. **PROFESSIONAL SUMMARY** - {"Use this exact pre-generated executive summary:" if generated_summary else "Create 2-3 lines highlighting key qualifications and value proposition"}
{generated_summary if generated_summary else ""}

3. **CORE SKILLS** - Use EXACTLY these optimized skills:
{formatted_skills}

4. **PROFESSIONAL EXPERIENCE** - {"Use these pre-generated SAR format experience bullets:" if formatted_experience else "3-4 most relevant roles with achievement-focused bullets"}
{formatted_experience if formatted_experience else "   - Company, job title, dates (MM/YYYY - MM/YYYY format)\n   - 3-4 achievement-focused bullet points per role\n   - Quantified results where possible\n   - Keywords from job description"}

5. **EDUCATION** - Degree, institution, year (extract from context)

FORMATTING REQUIREMENTS:
- Use ALL CAPS for section headings
- Use • for bullet points
- Use MM/YYYY - MM/YYYY for date formats
- Keep professional summary under 50 words
- Focus on achievements, not responsibilities
- Mirror job description language
- Ensure ATS compatibility

QUALITY STANDARDS:
- Tailor content specifically to the target role
- Highlight relevant achievements and impact
- Use strong action verbs and job description keywords
- Ensure consistency in formatting and style
- Create a cohesive, professional document

Generate a complete, professional CV that will pass ATS scanning and impress hiring managers."""
            
            with st.spinner("📝 Generating complete CV..."):
                result = llm_service.generate_cv_package(cv_prompt, context)
                
                # Store results in session state
                st.session_state.generated_cv = result["content"]
                st.session_state.generated_skills = skills_result
                if experience_result:
                    st.session_state.generated_experience = experience_result
                if summary_result:
                    st.session_state.generated_summary = summary_result
                
                st.success("✅ Complete ATS-optimized CV generated successfully!")
                
                # Display final CV
                st.subheader("📄 Complete Generated CV")
                
                # Final stats and CV display
                final_col1, final_col2 = st.columns([3, 1])
                
                with final_col1:
                    st.text_area("CV Content", result["content"], height=600, key="cv_preview")
                
                with final_col2:
                    st.subheader("📊 Generation Summary")
                    
                    # Component counts
                    st.metric("Skills Generated", skills_result["skill_count"])
                    if experience_result:
                        st.metric("Experience Bullets", experience_result["bullet_count"])
                    if summary_result:
                        st.metric("Summary Words", f"{summary_result['word_count']}/30")
                    st.metric("Total Word Count", len(result["content"].split()))
                    
                    # Quality indicators
                    st.divider()
                    st.subheader("🎯 Quality Indicators")
                    
                    if skills_result["valid"]:
                        st.success("✅ Skills ATS-Optimized")
                    else:
                        st.warning("⚠️ Skills Partial")
                        
                    if experience_result and experience_result["valid"]:
                        st.success("✅ Experience SAR Format")
                    elif experience_result:
                        st.warning("⚠️ Experience Partial")
                    else:
                        st.info("ℹ️ Basic Experience Used")
                    
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

def generate_cover_letter(llm_service, context_builder, company_name, role_title):
    with st.spinner("Generating cover letter..."):
        try:
            context = context_builder.build_cover_letter_context(company_name)
            
            # Simple prompt for cover letter
            cover_letter_prompt = f"""Generate a professional cover letter for the job application.
            Company: {company_name or '[Company Name]'}
            Role: {role_title or '[Job Title]'}
            
            Make it engaging, professional, and tailored to the job requirements.
            Keep it concise and impactful."""
            
            result = llm_service.generate_cover_letter(cover_letter_prompt, context)
            
            st.session_state.generated_cover_letter = result["content"]
            st.success("✅ Cover Letter generated successfully!")
            
            st.subheader("📝 Generated Cover Letter")
            st.text_area("Cover Letter Content", result["content"], height=300, key="cover_letter_preview")
            
        except Exception as e:
            st.error(f"❌ **Cover Letter Generation Failed**")
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
        
        if st.session_state.generated_cover_letter:
            if st.button("📝 Download Cover Letter as PDF"):
                with st.spinner("Generating PDF..."):
                    pdf_path = f"outputs/cover_letter_{timestamp}.pdf"
                    
                    pdf_exporter.export_cover_letter_to_pdf(
                        st.session_state.generated_cover_letter,
                        pdf_path,
                        "Professional Application"
                    )
                    
                    # Provide download button
                    with open(pdf_path, 'rb') as f:
                        st.download_button(
                            label="⬇️ Download Cover Letter PDF",
                            data=f.read(),
                            file_name=f"cover_letter_{timestamp}.pdf",
                            mime="application/pdf"
                        )
                    
                    st.success("✅ Cover Letter PDF generated successfully!")
    
    except Exception as e:
        st.error(f"❌ **PDF Generation Failed**")
        st.error(f"**Error Details:** {str(e)}")
        with st.expander("🔍 **Full Error Details**"):
            st.code(traceback.format_exc())

if __name__ == "__main__":
    main()