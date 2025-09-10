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
from exporters.markdown_export import get_markdown_exporter
from exporters.docx_export import get_docx_exporter
from exporters.pdf_export import get_pdf_exporter
from utils.text import TextProcessor, ContentValidator
from utils.style import StyleApplicator

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="CV & Cover Letter Generator",
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
        'generated_cover_letter': None,
        'validation_results': {},
        'export_paths': {}
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def main():
    initialize_session_state()
    
    st.title("🎯 CV & Cover Letter Generator")
    st.markdown("**Upload PDFs → Generate ATS-Optimized CV Package → Export in Multiple Formats**")
    
    with st.sidebar:
        st.header("📋 Configuration")
        
        if not os.getenv("OPENAI_API_KEY"):
            st.error("⚠️ OpenAI API key not found!")
            st.info("Please set OPENAI_API_KEY in your .env file")
            st.stop()
        else:
            st.success("✅ OpenAI API key loaded")
        
        st.divider()
        
        generation_mode = st.radio(
            "Generation Mode",
            ["CV Package", "Cover Letter", "Both"],
            help="Choose what to generate"
        )
        
        output_format = st.multiselect(
            "Export Formats",
            ["PDF (.pdf)", "Word (.docx)"],
            default=["PDF (.pdf)", "Word (.docx)"],
            help="Select output formats for download"
        )
    
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Upload & Process", "🤖 Generate", "📊 Validate", "💾 Export"])
    
    with tab1:
        handle_document_upload()
    
    with tab2:
        if st.session_state.processed_documents:
            handle_generation(generation_mode)
        else:
            st.info("👆 Please upload and process documents first")
    
    with tab3:
        if st.session_state.generated_cv or st.session_state.generated_cover_letter:
            handle_validation()
        else:
            st.info("👆 Please generate content first")
    
    with tab4:
        if st.session_state.generated_cv or st.session_state.generated_cover_letter:
            handle_export(output_format)
        else:
            st.info("👆 Please generate content first")

def handle_document_upload():
    st.header("📄 Document Upload & Processing")
    
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
                sample_text = processed_data["texts"]["sample_cv"]
                style_profile = style_extractor.extract_style_from_text(sample_text)
                st.session_state.style_profile = style_profile
                
                st.success(f"✅ Processed {processed_data['doc_count']} documents successfully!")
                
                st.subheader("📈 Processing Summary")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Chunks", len(processed_data["documents"]))
                
                with col2:
                    doc_summary = ingestor.get_document_summary(processed_data["texts"])
                    total_words = sum(doc_summary.values())
                    st.metric("Total Words", f"{total_words:,}")
                
                with col3:
                    st.metric("Vector Embeddings", len(processed_data["documents"]))
                
                with st.expander("📋 Style Profile Detected"):
                    st.code(style_extractor.get_style_summary(style_profile))
                
            except Exception as e:
                error_msg = str(e)
                st.error(f"❌ **Document Processing Failed**")
                st.error(f"**Error Details:** {error_msg}")
                
                # Show full error in an expandable section for easy copying
                with st.expander("🔍 **Full Error Details (Click to Copy)**"):
                    full_error = f"""
ERROR TYPE: {type(e).__name__}
ERROR MESSAGE: {error_msg}
STACK TRACE: 
{traceback.format_exc()}
                    """
                    st.code(full_error)
                
                logger.error(f"Document processing error: {e}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                
                # Show troubleshooting tips
                st.info("""
                **Troubleshooting Tips:**
                1. Ensure all PDFs are not password protected
                2. Check that PDF files are not corrupted
                3. Verify sufficient disk space is available
                4. Try uploading smaller PDF files if they are very large
                """)
                
                return None

def handle_generation(generation_mode):
    st.header("🤖 Content Generation")
    
    if not st.session_state.vector_store:
        st.error("❌ No processed documents found")
        return
    
    llm_service = get_llm_service()
    retriever = create_rag_retriever(st.session_state.vector_store)
    context_builder = ContextBuilder(retriever)
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("⚙️ Generation Settings")
        
        auto_retry = st.checkbox(
            "Auto-retry on validation failure",
            value=True,
            help="Automatically retry generation if validation fails"
        )
        
        max_retries = st.slider("Max Retries", 1, 5, 3)
        
        context_preview = st.checkbox("Show context preview", value=False)
    
    with col1:
        if generation_mode in ["CV Package", "Both"]:
            st.subheader("📄 CV Package Generation")
            
            if st.button("🚀 Generate CV Package", type="primary"):
                generate_cv_package(llm_service, context_builder, auto_retry, max_retries, context_preview)
        
        if generation_mode in ["Cover Letter", "Both"]:
            st.subheader("📝 Cover Letter Generation")
            
            company_name = st.text_input("Company Name (optional)", placeholder="e.g., TechCorp Inc.")
            role_title = st.text_input("Role Title (optional)", placeholder="e.g., Senior Software Engineer")
            
            if st.button("🚀 Generate Cover Letter", type="primary"):
                generate_cover_letter(llm_service, context_builder, auto_retry, max_retries, context_preview, company_name, role_title)

def generate_cv_package(llm_service, context_builder, auto_retry, max_retries, context_preview):
    with st.spinner("Generating CV package..."):
        try:
            context = context_builder.build_cv_generation_context()
            
            if context_preview:
                with st.expander("📋 Context Preview"):
                    st.text_area("Generated Context", context[:2000] + "..." if len(context) > 2000 else context, height=200)
            
            cv_prompt = load_prompt4()
            
            for attempt in range(max_retries + 1):
                try:
                    result = llm_service.generate_cv_package(cv_prompt, context)
                    
                    if result["valid"] or not auto_retry or attempt == max_retries:
                        break
                    
                    st.warning(f"⚠️ Attempt {attempt + 1} failed validation. Retrying...")
                    result = llm_service.improve_response(
                        result["content"], result["validation"], cv_prompt, context
                    )
                except Exception as retry_error:
                    st.error(f"❌ Error on attempt {attempt + 1}: {str(retry_error)}")
                    if attempt == max_retries:
                        raise retry_error
                    st.info(f"🔄 Retrying... ({attempt + 2}/{max_retries + 1})")
                    continue
            
            st.session_state.generated_cv = result["content"]
            st.session_state.validation_results["cv"] = result["validation"]
            
            if result["valid"]:
                st.success("✅ CV Package generated successfully!")
            else:
                st.warning("⚠️ CV Package generated but validation failed")
            
            st.subheader("📄 Generated CV Package")
            st.text_area("CV Content", result["content"], height=400, key="cv_preview")
            
            with st.expander("🔍 Validation Details"):
                for section, validation in result["validation"].items():
                    color = "🟢" if validation.get("valid", False) else "🔴"
                    st.write(f"{color} {validation.get('message', section)}")
            
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ **CV Package Generation Failed**")
            st.error(f"**Error Details:** {error_msg}")
            
            # Show full error in an expandable section for easy copying
            with st.expander("🔍 **Full Error Details (Click to Copy)**"):
                full_error = f"""
ERROR TYPE: {type(e).__name__}
ERROR MESSAGE: {error_msg}
STACK TRACE: 
{traceback.format_exc()}
                """
                st.code(full_error)
            
            # Also log the error
            logger.error(f"CV generation error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Show troubleshooting tips
            st.info("""
            **Troubleshooting Tips:**
            1. Check your OpenAI API key is valid and has credits
            2. Try switching to a different model (GPT-4o vs GPT-4o-mini)
            3. Ensure all three PDFs were uploaded and processed correctly
            4. Try regenerating with different settings
            """)
            
            return None

def generate_cover_letter(llm_service, context_builder, auto_retry, max_retries, context_preview, company_name, role_title):
    with st.spinner("Generating cover letter..."):
        try:
            context = context_builder.build_cover_letter_context(company_name)
            
            if context_preview:
                with st.expander("📋 Context Preview"):
                    st.text_area("Generated Context", context[:2000] + "..." if len(context) > 2000 else context, height=200)
            
            cover_letter_prompt = load_prompt5(company_name, role_title)
            
            for attempt in range(max_retries + 1):
                result = llm_service.generate_cover_letter(cover_letter_prompt, context)
                
                if result["valid"] or not auto_retry or attempt == max_retries:
                    break
                
                st.warning(f"⚠️ Attempt {attempt + 1} failed validation. Retrying...")
            
            st.session_state.generated_cover_letter = result["content"]
            st.session_state.validation_results["cover_letter"] = result["validation"]
            
            if result["valid"]:
                st.success("✅ Cover Letter generated successfully!")
            else:
                st.warning("⚠️ Cover Letter generated but exceeded word limit")
            
            st.subheader("📝 Generated Cover Letter")
            st.text_area("Cover Letter Content", result["content"], height=300, key="cover_letter_preview")
            
            with st.expander("🔍 Validation Details"):
                validation = result["validation"]["word_count"]
                color = "🟢" if validation.get("valid", False) else "🔴"
                st.write(f"{color} {validation.get('message', 'Word count check')}")
            
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ **Cover Letter Generation Failed**")
            st.error(f"**Error Details:** {error_msg}")
            
            # Show full error in an expandable section for easy copying
            with st.expander("🔍 **Full Error Details (Click to Copy)**"):
                full_error = f"""
ERROR TYPE: {type(e).__name__}
ERROR MESSAGE: {error_msg}
STACK TRACE: 
{traceback.format_exc()}
                """
                st.code(full_error)
            
            # Also log the error
            logger.error(f"Cover letter generation error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Show troubleshooting tips
            st.info("""
            **Troubleshooting Tips:**
            1. Check your OpenAI API key is valid and has credits
            2. Try switching to a different model (GPT-4o vs GPT-4o-mini)
            3. Ensure all three PDFs were uploaded and processed correctly
            4. Try regenerating with different settings
            """)
            
            return None

def handle_validation():
    st.header("📊 Content Validation & Analysis")
    
    text_processor = TextProcessor()
    validator = ContentValidator()
    
    if st.session_state.generated_cv:
        st.subheader("📄 CV Package Analysis")
        
        cv_content = st.session_state.generated_cv
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            stats = text_processor.get_text_stats(cv_content)
            st.metric("Total Words", stats.word_count)
            st.metric("Bullets Found", stats.bullet_count)
        
        with col2:
            career_summary = text_processor.extract_section_content(cv_content, "CAREER SUMMARY")
            if career_summary:
                summary_validation = validator.validate_career_summary(career_summary)
                color = "🟢" if summary_validation["valid"] else "🔴"
                st.metric(
                    "Career Summary",
                    f"{summary_validation['word_count']}/40 words",
                    delta=None if summary_validation["valid"] else f"+{summary_validation['word_count'] - 40}"
                )
        
        with col3:
            bullets = text_processor.extract_bullets(cv_content)
            sar_validation = text_processor.validate_sar_format(bullets)
            st.metric("SAR Bullets", f"{sar_validation['sar_formatted']}/8")
            st.metric("Two-Word Headings", f"{sar_validation['two_word_headings']}/8")
    
    if st.session_state.generated_cover_letter:
        st.subheader("📝 Cover Letter Analysis")
        
        cover_letter_content = st.session_state.generated_cover_letter
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            stats = text_processor.get_text_stats(cover_letter_content)
            st.metric("Word Count", f"{stats.word_count}/250")
        
        with col2:
            st.metric("Paragraphs", stats.paragraph_count)
        
        with col3:
            validation = validator.validate_cover_letter(cover_letter_content)
            color = "🟢" if validation["valid"] else "🔴"
            st.metric("Validation", "✅ Pass" if validation["valid"] else "❌ Fail")

def handle_export(output_formats):
    st.header("💾 Export & Download")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    
    if st.session_state.generated_cv:
        st.subheader("📄 CV Package Export")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📝 Apply Sample CV Style", help="Format CV to match Sample CV style"):
                apply_cv_styling()
        
        with col2:
            if st.button("🔄 Regenerate Exports"):
                generate_all_exports(timestamp, output_formats)
        
        download_exports("cv", timestamp, output_formats)
    
    if st.session_state.generated_cover_letter:
        st.subheader("📝 Cover Letter Export")
        download_exports("cover_letter", timestamp, output_formats)

def apply_cv_styling():
    if not st.session_state.style_profile:
        st.error("❌ No style profile available")
        return
    
    with st.spinner("Applying CV styling..."):
        try:
            style_applicator = StyleApplicator()
            styled_cv = style_applicator.match_sample_style(
                st.session_state.generated_cv,
                st.session_state.style_profile.__dict__
            )
            
            st.session_state.generated_cv = styled_cv
            st.success("✅ CV styled to match sample format!")
            st.rerun()
            
        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ **Style Application Failed**")
            st.error(f"**Error Details:** {error_msg}")
            
            # Show full error in an expandable section for easy copying
            with st.expander("🔍 **Full Error Details (Click to Copy)**"):
                full_error = f"""
ERROR TYPE: {type(e).__name__}
ERROR MESSAGE: {error_msg}
STACK TRACE: 
{traceback.format_exc()}
                """
                st.code(full_error)
            
            logger.error(f"Style application error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            st.info("""
            **Troubleshooting Tips:**
            1. Ensure Sample CV was uploaded and processed correctly
            2. Try regenerating the CV content first
            3. Check that the style profile was extracted successfully
            """)

def generate_all_exports(timestamp, output_formats):
    try:
        docx_exporter = get_docx_exporter()
        pdf_exporter = get_pdf_exporter()
        
        if st.session_state.generated_cv:
            if "PDF (.pdf)" in output_formats and st.session_state.style_profile:
                pdf_path = f"outputs/cv_formatted_{timestamp}.pdf"
                pdf_exporter.export_to_pdf(
                    st.session_state.generated_cv,
                    st.session_state.style_profile,
                    pdf_path
                )
                st.session_state.export_paths[f"cv_pdf_{timestamp}"] = pdf_path
            
            if "Word (.docx)" in output_formats and st.session_state.style_profile:
                docx_path = f"outputs/cv_formatted_{timestamp}.docx"
                docx_exporter.export_to_docx(
                    st.session_state.generated_cv,
                    st.session_state.style_profile,
                    docx_path
                )
                st.session_state.export_paths[f"cv_docx_{timestamp}"] = docx_path
        
        if st.session_state.generated_cover_letter:
            if "PDF (.pdf)" in output_formats:
                pdf_path = f"outputs/cover_letter_{timestamp}.pdf"
                pdf_exporter.export_cover_letter_to_pdf(
                    st.session_state.generated_cover_letter,
                    pdf_path
                )
                st.session_state.export_paths[f"cover_pdf_{timestamp}"] = pdf_path
            
            if "Word (.docx)" in output_formats:
                docx_path = f"outputs/cover_letter_{timestamp}.docx"
                docx_exporter.export_cover_letter_to_docx(
                    st.session_state.generated_cover_letter,
                    docx_path
                )
                st.session_state.export_paths[f"cover_docx_{timestamp}"] = docx_path
        
        st.success("✅ All exports generated successfully!")
        
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ **Export Failed**")
        st.error(f"**Error Details:** {error_msg}")
        
        # Show full error in an expandable section for easy copying
        with st.expander("🔍 **Full Error Details (Click to Copy)**"):
            full_error = f"""
ERROR TYPE: {type(e).__name__}
ERROR MESSAGE: {error_msg}
STACK TRACE: 
{traceback.format_exc()}
            """
            st.code(full_error)
        
        logger.error(f"Export error: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Show troubleshooting tips
        st.info("""
        **Troubleshooting Tips:**
        1. Ensure outputs/ directory is writable
        2. Check available disk space
        3. Verify all dependencies are installed correctly
        4. Try exporting in a different format
        """)

def download_exports(content_type, timestamp, output_formats):
    for format_name in output_formats:
        format_key = format_name.split()[0].lower()
        export_key = f"{content_type}_{format_key}_{timestamp}"
        
        if export_key in st.session_state.export_paths:
            file_path = st.session_state.export_paths[export_key]
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    st.download_button(
                        label=f"⬇️ Download {format_name}",
                        data=f.read(),
                        file_name=os.path.basename(file_path),
                        mime=get_mime_type(format_name),
                        key=f"download_{export_key}"
                    )
            else:
                st.error(f"❌ File not found: {file_path}")

def get_mime_type(format_name):
    if "Word" in format_name:
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif "PDF" in format_name:
        return "application/pdf"
    else:
        return "application/octet-stream"

def load_prompt4():
    try:
        with open("prompts/prompt4_combined.txt", 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return """Generate a professional CV package with:
        
        1. CAREER SUMMARY (≤40 words exactly)
        2. EXACTLY 8 SAR bullets with two-word headings (e.g., "Project Leadership: Led team of 5...")
        3. EXACTLY 10 skills (≤2 words each)
        
        Use the job description and candidate superset to create targeted, ATS-optimized content."""

def load_prompt5(company_name=None, role_title=None):
    try:
        with open("prompts/prompt5_coverletter.txt", 'r', encoding='utf-8') as f:
            prompt = f.read()
    except FileNotFoundError:
        prompt = """Generate an ATS-optimized cover letter (≤250 words, 3-4 paragraphs) that:
        
        1. Opens with enthusiasm for the specific role
        2. Highlights 2-3 relevant achievements with metrics
        3. Shows knowledge of company/role requirements
        4. Closes with clear next steps
        
        Use professional tone, avoid clichés, include keywords from job description."""
    
    if company_name:
        prompt = prompt.replace("[COMPANY_NAME]", company_name)
    if role_title:
        prompt = prompt.replace("[ROLE_TITLE]", role_title)
    
    return prompt

if __name__ == "__main__":
    main()