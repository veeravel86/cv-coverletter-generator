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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Job Description")
        job_description = st.file_uploader(
            "Upload Job_Description.pdf",
            type=['pdf'],
            key="job_description",
            help="The target job description PDF"
        )
    
    with col2:
        st.subheader("Experience Superset")
        superset = st.file_uploader(
            "Upload CV_ExperienceSummary_Skills_Superset.pdf", 
            type=['pdf'],
            key="superset",
            help="Your comprehensive experience and skills document"
        )
    
    with col3:
        st.subheader("Sample CV Style")
        sample_cv = st.file_uploader(
            "Upload Sample_CV.pdf",
            type=['pdf'],
            key="sample_cv",
            help="CV to mimic the formatting style from"
        )
    
    if st.button("🔄 Process Documents", type="primary"):
        if not all([job_description, superset, sample_cv]):
            st.error("❌ Please upload all three PDF files")
            return
        
        with st.spinner("Processing documents..."):
            try:
                ingestor = get_pdf_ingestor()
                
                uploaded_files = {
                    "job_description": job_description,
                    "superset": superset,
                    "sample_cv": sample_cv
                }
                
                processed_data = ingestor.ingest_pdfs(uploaded_files)
                st.session_state.processed_documents = processed_data
                st.session_state.vector_store = processed_data["vector_store"]
                
                style_extractor = get_style_extractor()
                sample_text = processed_data["processed_texts"]["sample_cv"]
                style_profile = style_extractor.extract_style_from_text(sample_text)
                st.session_state.style_profile = style_profile
                
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
                
                # Display cleaned job description
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
                else:
                    st.warning("No job description text was extracted")
                
                # Display structured Sample CV content
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
                else:
                    st.warning("No sample CV text was extracted")
                
                # Display structured Experience Superset content
                st.divider()
                st.subheader("📚 Structured Experience Superset")
                
                superset_text = processed_data["processed_texts"].get("superset", "")
                if superset_text:
                    st.text_area(
                        "Experience Superset Content (Structured by AI)",
                        superset_text,
                        height=400,
                        help="This is the experience superset content structured by AI with proper headings and formatting"
                    )
                    st.info(f"📊 Structured Experience Superset: {len(superset_text.split())} words, {len(superset_text)} characters")
                    
                    # Option to view original raw text
                    with st.expander("🔍 View Original Raw Experience Superset Text"):
                        raw_superset = processed_data["texts"].get("superset", "")
                        st.text_area(
                            "Original Experience Superset Text",
                            raw_superset,
                            height=200,
                            help="This is the original text extracted directly from the experience superset PDF"
                        )
                        st.caption(f"Raw superset: {len(raw_superset.split())} words, {len(raw_superset)} characters")
                else:
                    st.warning("No experience superset text was extracted")
                
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
            context = context_builder.build_cv_generation_context()
            
            # Simple prompt for CV generation
            cv_prompt = """Generate a professional CV based on the job description and candidate experience provided. 
            Include:
            - Contact information
            - Professional summary
            - Work experience with achievements
            - Skills section
            - Education
            
            Make it professional and tailored to the job requirements."""
            
            result = llm_service.generate_cv_package(cv_prompt, context)
            
            st.session_state.generated_cv = result["content"]
            st.success("✅ CV generated successfully!")
            
            st.subheader("📄 Generated CV")
            st.text_area("CV Content", result["content"], height=400, key="cv_preview")
            
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