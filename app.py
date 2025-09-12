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
    st.markdown("Upload four separate documents for comprehensive CV generation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 Job Description")
        job_description = st.file_uploader(
            "Upload Job Description PDF",
            type=['pdf'],
            key="job_description",
            help="The target job description you're applying for"
        )
        
        st.subheader("💼 Experience Superset") 
        experience_doc = st.file_uploader(
            "Upload Experience Superset PDF",
            type=['pdf'],
            key="experience_doc",
            help="Document containing all your work experience and achievements"
        )
    
    with col2:
        st.subheader("🛠️ Skills Superset")
        skills_doc = st.file_uploader(
            "Upload Skills Superset PDF",
            type=['pdf'],
            key="skills_doc", 
            help="Document containing all your technical and soft skills"
        )
        
        st.subheader("📋 Sample CV")
        sample_cv = st.file_uploader(
            "Upload Sample CV PDF",
            type=['pdf'],
            key="sample_cv",
            help="CV whose formatting style you want to mimic"
        )
    
    # Show upload status
    uploaded_files = [job_description, experience_doc, skills_doc, sample_cv]
    file_names = ["Job Description", "Experience Superset", "Skills Superset", "Sample CV"]
    
    st.markdown("### Upload Status:")
    upload_cols = st.columns(4)
    for i, (file, name) in enumerate(zip(uploaded_files, file_names)):
        with upload_cols[i]:
            if file:
                st.success(f"✅ {name}")
            else:
                st.error(f"❌ {name}")
    
    if st.button("🔄 Process Documents", type="primary"):
        if not any(uploaded_files):
            st.error("❌ Please upload at least one PDF file")
            return
        
        with st.spinner("Processing documents..."):
            try:
                ingestor = get_pdf_ingestor()
                
                uploaded_files = {
                    "job_description": job_description,
                    "experience_doc": experience_doc,
                    "skills_doc": skills_doc,
                    "sample_cv": sample_cv
                }
                
                processed_data = ingestor.ingest_pdfs(uploaded_files)
                st.session_state.processed_documents = processed_data
                st.session_state.vector_store = processed_data["vector_store"]
                
                # Extract style profile only if sample CV is available
                if "sample_cv" in processed_data["texts"]:
                    style_extractor = get_style_extractor()
                    sample_text = processed_data["texts"]["sample_cv"]
                    style_profile = style_extractor.extract_style_from_text(sample_text)
                    st.session_state.style_profile = style_profile
                
                st.success(f"✅ Processed {processed_data['doc_count']} documents successfully!")
                
                # Show extracted content with progressive disclosure
                st.markdown("---")
                st.subheader("📄 Extracted Content Preview")
                
                display_extracted_content(processed_data)
                
                st.markdown("---")
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
                
                # Show style profile only if available
                if st.session_state.get('style_profile'):
                    with st.expander("📋 Style Profile Detected"):
                        style_extractor = get_style_extractor()
                        st.code(style_extractor.get_style_summary(st.session_state.style_profile))
                
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
    
    # New individual generation options
    st.markdown("---")
    st.subheader("🎯 Individual Content Generation")
    st.markdown("Generate specific components for targeted CV customization")
    
    gen_cols = st.columns(2)
    
    with gen_cols[0]:
        if st.button("🛠️ Generate Top 10 Skills", help="Extract and rank the top 10 most relevant skills"):
            generate_top_skills(llm_service, context_builder)
        
        if st.button("💼 Generate Top 8 Experience Bullets", help="Create 8 high-impact experience bullets"):
            generate_experience_bullets(llm_service, context_builder)
    
    with gen_cols[1]:
        if st.button("📊 Generate Executive Summary", help="Create a professional executive summary"):
            generate_executive_summary(llm_service, context_builder)
        
        if st.button("📋 Generate Previous Experience Summary", help="Summarize previous work experience"):
            generate_previous_experience_summary(llm_service, context_builder)
    
    # Original generation section
    st.markdown("---")
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
            st.subheader("📄 Complete CV Package Generation")
            
            if st.button("🚀 Generate Full CV Package", type="primary"):
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

def display_extracted_content(processed_data):
    """Display extracted content with progressive disclosure"""
    
    processed_texts = processed_data.get("processed_texts", {})
    document_titles = {
        "job_description": "🎯 Job Description (Cleaned)",
        "experience_doc": "💼 Experience Superset",
        "skills_doc": "🛠️ Skills Superset", 
        "sample_cv": "📋 Sample CV"
    }
    
    for doc_type, content in processed_texts.items():
        if content and content.strip():
            title = document_titles.get(doc_type, doc_type.replace('_', ' ').title())
            
            with st.expander(f"{title} - Click to expand", expanded=False):
                # Format content with proper structure
                formatted_content = format_content_with_structure(content, doc_type)
                st.markdown(formatted_content)
                
                # Show word count
                word_count = len(content.split())
                st.caption(f"📊 Word count: {word_count:,} words")

def format_content_with_structure(content: str, doc_type: str) -> str:
    """Format content with proper headings and bullet points"""
    
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append("")
            continue
            
        # Detect headings (all caps, short lines, or specific patterns)
        if (line.isupper() and len(line) < 50 and not line.startswith('•')) or \
           line.endswith(':') or \
           any(header in line.upper() for header in ['EXPERIENCE', 'SKILLS', 'EDUCATION', 'SUMMARY', 'OBJECTIVE', 'REQUIREMENTS', 'RESPONSIBILITIES', 'QUALIFICATIONS']):
            # Format as heading
            formatted_lines.append(f"### {line}")
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            # Format as bullet point
            clean_line = line.lstrip('•-* ').strip()
            formatted_lines.append(f"• {clean_line}")
        elif line and not line.startswith(' ') and len(line.split()) < 10:
            # Potential subheading
            formatted_lines.append(f"**{line}**")
        else:
            # Regular content
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

def generate_top_skills(llm_service, context_builder):
    """Generate top 10 skills with expandable display"""
    
    with st.spinner("🛠️ Generating top 10 skills..."):
        try:
            # Get relevant context from vector store
            context = context_builder.build_context("skills technical competencies expertise")
            
            prompt = f"""
Based on the following context, extract and rank the top 10 most relevant and marketable skills.

Context:
{context}

Requirements:
- Extract exactly 10 skills
- Each skill should be 1-3 words maximum
- Prioritize technical skills and in-demand competencies
- Include both hard and soft skills where relevant
- Format as a numbered list
- Consider current market demand and relevance

Return format:
1. Skill Name
2. Skill Name
...
10. Skill Name
"""
            
            response = llm_service.generate_content(prompt, max_tokens=500)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['top_skills'] = response
            
            # Display with expander
            with st.expander("🛠️ Top 10 Skills - Click to expand", expanded=True):
                st.markdown("### Generated Skills")
                st.write(response)
                st.caption("💡 These skills were extracted from your documents and ranked by relevance")
            
        except Exception as e:
            st.error(f"❌ Error generating skills: {str(e)}")

def generate_experience_bullets(llm_service, context_builder):
    """Generate top 8 experience bullets with expandable display using professional ATS-optimized prompt"""
    
    with st.spinner("💼 Generating top 8 experience bullets..."):
        try:
            # Get job description context
            job_context = context_builder.build_context("job description requirements responsibilities qualifications")
            
            # Get experience context  
            experience_context = context_builder.build_context("work experience achievements projects accomplishments results")
            
            prompt = f"""You are an expert CV writer and ATS optimizer for senior engineering leadership roles. Read the below mentioned guidelines and accomplish the task from the provided context.

GOAL:
Read the provided context containing:
- Job Description: Complete job requirements and expectations
- Experience Superset: All possible experience points and achievements

From these, create EXACTLY 8 high-impact experience summary bullets that are:
- Directly aligned with the job description
- Ordered by PRIORITY based on job requirements and implied expectations
- Polished for both ATS scanning and human decision-makers

JOB DESCRIPTION CONTEXT:
{job_context}

EXPERIENCE SUPERSET CONTEXT:
{experience_context}

BULLET REQUIREMENTS:
- Start with a TWO-WORD HEADING (no abbreviations), ideally using language from the job description
- Each bullet must follow SAR (Situation–Action–Result) in one concise sentence (~22–35 words)
- Use job description keywords naturally and accurately
- Include metrics or quantifiable results ONLY if present in the experience context; otherwise, use qualitative outcomes
- No fabrication or vague fluff
- Use international English unless the job clearly uses US spelling
- Each bullet should show measurable impact, leadership depth, and business relevance

PRIORITY RULES:
- Rank bullets strictly by relevance to the job description:
  1. Mission-critical competencies, leadership scope, and business outcomes the job emphasizes
  2. Skills and themes repeated or highlighted in job description wording
  3. Emerging themes or differentiators likely valued for this role
- Highest-priority achievements appear first
- No duplicated content or similar bullets

PROCESS:
1. Parse job description context → extract competencies, themes, leadership scope, hard skills, and keyword frequencies
2. Parse experience context → shortlist all relevant achievements
3. Rank shortlist bullets against job requirements and implied role impact
4. Rewrite top 8 bullets in SAR style with job keywords and two-word headings
5. Sequence bullets in order of job relevance (highest priority first)
6. Final polish: ensure conciseness, ATS optimization, and strong action verbs

OUTPUT FORMAT (strict):
- Output ONLY the 8 bullets, nothing else
- Format: **Two Word Heading** | SAR statement showing measurable impact
- Example format (not content): **Cloud Migration** | Inherited aging on-prem infra; led phased AWS migration with team restructure; cut costs 20%, boosted uptime, and accelerated deployment cycles.

QUALITY BAR:
- Each bullet must be job-aligned, SAR-structured, outcome-focused, and priority-ranked
- Optimize for clarity, keywords, and quantified results as if reviewed by an ATS and a CTO in a competitive search

BEGIN."""
            
            response = llm_service.generate_content(prompt, max_tokens=1000)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['experience_bullets'] = response
            
            # Display with expander
            with st.expander("💼 Top 8 Experience Bullets - Click to expand", expanded=True):
                st.markdown("### Generated Experience Bullets")
                st.markdown("*ATS-optimized bullets aligned with job requirements and prioritized by relevance*")
                st.markdown("---")
                st.markdown(response)
                st.caption("🎯 Professional SAR-format bullets optimized for ATS and hiring managers")
            
        except Exception as e:
            st.error(f"❌ Error generating experience bullets: {str(e)}")

def generate_executive_summary(llm_service, context_builder):
    """Generate executive summary with expandable display"""
    
    with st.spinner("📊 Generating executive summary..."):
        try:
            # Get relevant context from vector store
            context = context_builder.build_context("professional summary career objective experience background")
            
            prompt = f"""
Based on the following context, create a powerful executive summary (30-40 words maximum).

Context:
{context}

Requirements:
- Maximum 40 words
- Executive-level, results-oriented tone
- Highlight key value proposition and expertise
- Include years of experience if apparent
- Use impactful, professional language
- No first-person pronouns
- Focus on what you bring to an organization
- Include industry or functional expertise

The summary should capture the essence of a senior professional's career value.
"""
            
            response = llm_service.generate_content(prompt, max_tokens=200)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['executive_summary'] = response
            
            # Display with expander
            with st.expander("📊 Executive Summary - Click to expand", expanded=True):
                st.markdown("### Generated Executive Summary")
                st.markdown(f"*{response.strip()}*")
                word_count = len(response.split())
                st.caption(f"📝 Word count: {word_count} words (target: ≤40 words)")
            
        except Exception as e:
            st.error(f"❌ Error generating executive summary: {str(e)}")

def generate_previous_experience_summary(llm_service, context_builder):
    """Generate previous experience summary with expandable display"""
    
    with st.spinner("📋 Generating previous experience summary..."):
        try:
            # Get relevant context from vector store
            context = context_builder.build_context("previous roles work history career progression past positions")
            
            prompt = f"""
Based on the following context, create a comprehensive summary of previous work experience.

Context:
{context}

Requirements:
- Summarize previous roles and positions chronologically
- Include key companies, job titles, and time periods where available
- Highlight major achievements and responsibilities for each role
- Use 3-5 bullet points per significant role
- Focus on career progression and skill development
- Include quantified achievements where possible
- Professional tone and clear formatting
- Group similar or related roles together if needed

Format as a structured summary with clear role sections.
"""
            
            response = llm_service.generate_content(prompt, max_tokens=1000)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['previous_experience'] = response
            
            # Display with expander
            with st.expander("📋 Previous Experience Summary - Click to expand", expanded=True):
                st.markdown("### Generated Previous Experience Summary")
                st.markdown(response)
                st.caption("🏢 Comprehensive overview of career progression and key roles")
            
        except Exception as e:
            st.error(f"❌ Error generating previous experience summary: {str(e)}")

if __name__ == "__main__":
    main()