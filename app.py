import os
import logging
import traceback
import json
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
from services.html_to_pdf import html_to_pdf_converter
from utils.text import TextProcessor, ContentValidator
from utils.style import StyleApplicator
from models.cv_data import CVData, ContactInfo, RoleExperience, ExperienceBullet
from services.template_engine import template_engine

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
        'export_paths': {},
        'sample_cv_content': None,
        'individual_generations': {},
        'structured_cv_data': None,
        'llm_json_responses': {}
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
            ["Cover Letter"],
            help="Individual CV sections and complete CV generation available in Generate tab"
        )
        
    
    tab1, tab2 = st.tabs(["📄 Upload & Process", "🤖 Generate"])
    
    with tab1:
        handle_document_upload()
    
    with tab2:
        if st.session_state.processed_documents:
            handle_generation(generation_mode)
        else:
            st.info("👆 Please upload and process documents first")

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
                
                # Store sample CV content for individual generation functions
                if "sample_cv" in processed_data["texts"]:
                    st.session_state.sample_cv_content = processed_data["texts"]["sample_cv"]
                
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
        
        if st.button("💼 Generate Current Position Summary Top8", help="Create current position summary with 8 high-impact bullets"):
            generate_experience_bullets(llm_service, context_builder)
    
    with gen_cols[1]:
        if st.button("📊 Generate Executive Summary", help="Create a professional executive summary"):
            generate_executive_summary(llm_service, context_builder)
        
        if st.button("📋 Generate Previous Experience Summary", help="Summarize previous work experience"):
            generate_previous_experience_summary(llm_service, context_builder)
    

    # Display all generated individual sections persistently
    st.markdown("---")
    st.subheader("📄 Generated Individual Sections")
    st.markdown("Review and edit your generated content sections")
    
    display_individual_sections()
    
    # Generate Whole CV Section
    st.markdown("---")
    st.subheader("📄 Complete CV Generation")
    st.markdown("Generate a professionally formatted CV using all individual sections created above")
    
    # Check if required sections are available
    required_sections = ['executive_summary', 'top_skills', 'experience_bullets']
    available_sections = [section for section in required_sections if section in st.session_state.individual_generations]
    
    if len(available_sections) >= 2:
        whole_cv_cols = st.columns([2, 1])
        
        with whole_cv_cols[0]:
            # Contact information input
            contact_header_cols = st.columns([3, 1])
            with contact_header_cols[0]:
                st.markdown("##### 📞 Contact Information")
            with contact_header_cols[1]:
                if st.button("🔄 Auto-fill from Sample CV", help="Extract contact info from uploaded Sample CV"):
                    if 'sample_cv_content' not in st.session_state or not st.session_state.sample_cv_content:
                        st.warning("⚠️ Please upload a Sample CV first to auto-fill contact information")
                    else:
                        with st.spinner("📋 Extracting contact information from Sample CV..."):
                            contact_info = extract_contact_info_from_cv(llm_service)
                            if contact_info:
                                # Store in session state to populate form fields
                                st.session_state.auto_contact_info = contact_info
                                st.success("✅ Contact information extracted successfully!")
                                st.rerun()
            
            # Get values from auto-extracted info if available
            auto_info = st.session_state.get('auto_contact_info', {})
            
            contact_cols = st.columns(3)
            with contact_cols[0]:
                name = st.text_input("Full Name", 
                                   value=auto_info.get('name', ''), 
                                   placeholder="John Doe", 
                                   key="cv_name")
                email = st.text_input("Email", 
                                    value=auto_info.get('email', ''), 
                                    placeholder="john.doe@email.com", 
                                    key="cv_email")
            with contact_cols[1]:
                phone = st.text_input("Phone", 
                                    value=auto_info.get('phone', ''), 
                                    placeholder="+1-234-567-8900", 
                                    key="cv_phone")
                location = st.text_input("Location", 
                                       value=auto_info.get('location', ''), 
                                       placeholder="City, Country", 
                                       key="cv_location")
            with contact_cols[2]:
                linkedin = st.text_input("LinkedIn", 
                                        value=auto_info.get('linkedin', ''), 
                                        placeholder="linkedin.com/in/johndoe", 
                                        key="cv_linkedin")
                website = st.text_input("Website/Portfolio", 
                                       value=auto_info.get('website', ''), 
                                       placeholder="johndoe.com", 
                                       key="cv_website")
        
        with whole_cv_cols[1]:
            st.markdown("##### ✅ Available Sections")
            if 'executive_summary' in st.session_state.individual_generations:
                st.success("✅ Executive Summary")
            else:
                st.error("❌ Executive Summary")
            
            if 'top_skills' in st.session_state.individual_generations:
                st.success("✅ Top Skills")
            else:
                st.error("❌ Top Skills")
            
            if 'experience_bullets' in st.session_state.individual_generations:
                st.success("✅ Current Position Summary")
            else:
                st.error("❌ Current Position Summary")
            
            if 'previous_experience' in st.session_state.individual_generations:
                st.success("✅ Previous Experience")
            else:
                st.info("ℹ️ Previous Experience (Optional)")
        
        # Generate button
        generate_whole_cv_cols = st.columns([1, 1, 1])
        with generate_whole_cv_cols[0]:
            if st.button("🎯 Generate Whole CV", type="primary", help="Create complete professional CV"):
                generate_whole_cv(llm_service, context_builder, name, email, phone, location, linkedin, website)
        
        with generate_whole_cv_cols[1]:
            # Remove dependency on whole_cv_content for template-based preview
            if st.session_state.get('whole_cv_contact') and st.session_state.get('individual_generations'):
                preview_cols = st.columns(2)
                
                with preview_cols[0]:
                    if st.button("👁️ Preview Here", help="Preview CV in current page"):
                        show_cv_preview_structured()
                
                with preview_cols[1]:
                    if st.button("🔗 Preview in New Tab", help="Open CV preview in new browser tab"):
                        generate_cv_html_for_new_tab()
        
        with generate_whole_cv_cols[2]:
            # Remove dependency on whole_cv_content for template-based PDF generation
            if st.session_state.get('whole_cv_contact') and st.session_state.get('individual_generations'):
                if st.button("📄 Generate PDF", type="secondary", help="Generate CV as PDF for download"):
                    with st.spinner("📄 Generating PDF..."):
                        pdf_data = generate_cv_pdf_structured()
                        if pdf_data:
                            st.session_state['pdf_data'] = pdf_data
                            st.session_state['pdf_name'] = f"CV_{st.session_state.whole_cv_contact.get('name', 'Document').replace(' ', '_')}.pdf"
                            st.success("✅ PDF generated successfully!")
                            st.rerun()
        
        # Download button (only show if PDF is ready)
        if 'pdf_data' in st.session_state and st.session_state['pdf_data']:
            st.download_button(
                label="💾 Download CV PDF",
                data=st.session_state['pdf_data'],
                file_name=st.session_state.get('pdf_name', 'CV.pdf'),
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
    
    else:
        st.info("📝 Please generate at least 2 individual sections (Executive Summary, Skills, or Experience Bullets) before creating the whole CV")
    
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
        st.info("📝 Use the 'Generate Whole CV' section above to create your complete professional CV")
        
        if generation_mode == "Cover Letter":
            st.subheader("📝 Cover Letter Generation")
            
            company_name = st.text_input("Company Name (optional)", placeholder="e.g., TechCorp Inc.")
            role_title = st.text_input("Role Title (optional)", placeholder="e.g., Senior Software Engineer")
            
            if st.button("🚀 Generate Cover Letter", type="primary"):
                generate_cover_letter(llm_service, context_builder, auto_retry, max_retries, context_preview, company_name, role_title)


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


def apply_cv_styling():
    if not st.session_state.style_profile:
        st.error("❌ No style profile available")
        return
    
    with st.spinner("Applying CV styling..."):
        try:
            style_applicator = StyleApplicator()
            styled_cv = style_applicator.match_sample_style(
                st.session_state.whole_cv_content,
                st.session_state.style_profile.__dict__
            )
            
            st.session_state.whole_cv_content = styled_cv
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
        
        if st.session_state.get('whole_cv_content'):
            if "PDF (.pdf)" in output_formats and st.session_state.style_profile:
                pdf_path = f"outputs/cv_formatted_{timestamp}.pdf"
                pdf_exporter.export_to_pdf(
                    st.session_state.whole_cv_content,
                    st.session_state.style_profile,
                    pdf_path
                )
                st.session_state.export_paths[f"cv_pdf_{timestamp}"] = pdf_path
            
            if "Word (.docx)" in output_formats and st.session_state.style_profile:
                docx_path = f"outputs/cv_formatted_{timestamp}.docx"
                docx_exporter.export_to_docx(
                    st.session_state.whole_cv_content,
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

def clean_generated_content(content: str) -> str:
    """Clean generated content to ensure only headings are bold"""
    
    if not content:
        return ""
    
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        
        # Check if this is a heading (starts with **Two Word Heading** pattern or similar)
        if line.startswith('**') and '**' in line[2:]:
            # This is likely a heading - keep the bold formatting for headings only
            heading_end = line.find('**', 2)
            if heading_end != -1:
                heading = line[2:heading_end]
                rest = line[heading_end + 2:]
                
                # Only keep bold for short headings (likely section headers)
                if len(heading.split()) <= 3:  # Headings are typically 1-3 words
                    cleaned_lines.append(f"**{heading}**{rest}")
                else:
                    # Remove bold from longer content
                    cleaned_lines.append(f"{heading}{rest}")
            else:
                # Malformed bold - remove it
                cleaned_lines.append(line.replace('**', ''))
        else:
            # Remove any remaining bold formatting from non-heading content
            cleaned_line = line.replace('**', '')
            cleaned_lines.append(cleaned_line)
    
    return '\n'.join(cleaned_lines)

def extract_contact_info_from_cv(llm_service):
    """Extract contact information from Sample CV using LLM"""
    
    if 'sample_cv_content' not in st.session_state or not st.session_state.sample_cv_content:
        return None
    
    sample_cv_content = st.session_state.sample_cv_content
    
    contact_extraction_prompt = f"""
You are an expert CV parser. Extract contact information from the following CV content.

CV CONTENT:
{sample_cv_content}

GOAL:
Extract the following contact information from the CV:
1. Full Name (first and last name)
2. Email address
3. Phone number 
4. Location/Address (city, state/country)
5. LinkedIn profile URL
6. Website/Portfolio URL

REQUIREMENTS:
- Look for contact information typically found at the top of CVs
- Extract exact information as written in the CV
- If any field is not found, return "Not found" for that field
- Be precise and extract only what is clearly stated
- For LinkedIn, extract the full profile URL if available, or just the username
- For location, extract city and country/state as written

OUTPUT FORMAT:
Return the information in this exact JSON format:
{{
    "name": "Full Name Here",
    "email": "email@example.com", 
    "phone": "+1-234-567-8900",
    "location": "City, Country",
    "linkedin": "linkedin.com/in/username or full URL",
    "website": "website.com or full URL"
}}

If any field is not found in the CV, use "Not found" as the value.
"""
    
    try:
        response = llm_service.generate_content(contact_extraction_prompt, max_tokens=300)
        
        # Parse JSON response
        import json
        import re
        
        # Extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            contact_info = json.loads(json_str)
            
            # Clean up "Not found" values to empty strings for better UX
            for key, value in contact_info.items():
                if isinstance(value, str) and value.lower() in ['not found', 'n/a', 'none', '']:
                    contact_info[key] = ""
            
            return contact_info
        else:
            st.warning("Could not parse contact information from Sample CV")
            return None
            
    except Exception as e:
        st.error(f"Error extracting contact information: {str(e)}")
        return None

def parse_text_to_json(section_key: str, content: str) -> dict:
    """Parse text content to structured JSON format based on section type"""
    import re
    
    if section_key == 'top_skills':
        # Parse skills from bullet points or numbered lists
        skills = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Remove bullet points, numbers, and markdown formatting
            cleaned = re.sub(r'^[\d\.\-\*\•\#\s]+', '', line).strip()
            cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)  # Remove bold formatting
            if cleaned and not cleaned.startswith('#'):
                skills.append(cleaned)
        
        return {
            "section_type": "skills",
            "skills": skills[:10],  # Top 10 skills
            "total_count": len(skills)
        }
    
    elif section_key == 'experience_bullets':
        # Parse current position summary with role info and SAR bullets
        lines = content.split('\n')
        role_info = {}
        bullets = []
        
        # Extract role information from header
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('**') and line.endswith('**') and i < 3:
                # Position name
                role_info['position_name'] = line.replace('**', '')
            elif line.startswith('*') and line.endswith('*') and '|' in line:
                # Company, location, dates info
                company_info = line.replace('*', '')
                if '|' in company_info:
                    parts = company_info.split('|')
                    role_info['company_location'] = parts[0].strip()
                    role_info['dates'] = parts[1].strip() if len(parts) > 1 else ""
            elif line.startswith('**') and '|' in line:
                # SAR bullet
                if '|' in line:
                    parts = line.split('|', 1)
                    heading = parts[0].strip().replace('**', '')
                    content_part = parts[1].strip()
                    bullets.append({
                        "heading": heading,
                        "content": content_part,
                        "full_text": line
                    })
        
        return {
            "section_type": "current_position_summary",
            "role_info": role_info,
            "bullets": bullets,
            "total_bullets": len(bullets)
        }
    
    elif section_key == 'professional_summary':
        # Parse professional summary
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        word_count = len(content.split())
        
        return {
            "section_type": "professional_summary",
            "summary": content.strip(),
            "word_count": word_count,
            "line_count": len(lines)
        }
    
    elif section_key == 'previous_roles':
        # Parse previous roles and experience
        roles = []
        current_role = {}
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if it's a role header (contains company, title, dates)
            if '|' in line and any(keyword in line.lower() for keyword in ['20', '19', 'present', 'current']):
                if current_role:
                    roles.append(current_role)
                
                parts = line.split('|')
                current_role = {
                    "title": parts[0].strip() if len(parts) > 0 else "",
                    "company_location": parts[1].strip() if len(parts) > 1 else "",
                    "dates": parts[2].strip() if len(parts) > 2 else "",
                    "bullets": []
                }
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # It's a bullet point
                bullet_text = line[1:].strip()
                if current_role:
                    current_role["bullets"].append(bullet_text)
        
        # Add the last role if exists
        if current_role:
            roles.append(current_role)
        
        return {
            "section_type": "previous_roles",
            "roles": roles,
            "total_roles": len(roles)
        }
    
    # Default fallback
    return {
        "section_type": section_key,
        "raw_content": content,
        "word_count": len(content.split()),
        "line_count": len(content.split('\n'))
    }

def display_individual_sections():
    """Display all generated individual sections in persistent expandable format"""
    
    if 'individual_generations' not in st.session_state or not st.session_state.individual_generations:
        st.info("💡 No individual sections generated yet. Use the generation buttons above to create content.")
        return
    
    # Display each generated section with appropriate formatting
    sections_config = {
        'top_skills': {
            'title': '🎯 Top 10 Skills',
            'subtitle': 'JD-aligned technical competencies (≤2 words each)',
            'caption': '🎯 Skills ranked by job description relevance',
            'icon': '🎯'
        },
        'experience_bullets': {
            'title': '💼 Current Position Summary Top8',
            'subtitle': 'Position details with SAR format bullets',
            'caption': '💼 Current role summary with achievement-focused bullets',
            'icon': '⚡'
        },
        'executive_summary': {
            'title': '📊 Executive Summary',
            'subtitle': 'Professional career summary (≤40 words)',
            'caption': '📊 ATS-optimized executive-level summary',
            'icon': '📊'
        },
        'previous_experience': {
            'title': '📋 Previous Experience Summary',
            'subtitle': 'Extracted from Sample CV - Previous roles only (excluding current position)',
            'caption': '🏢 Career progression overview from Sample CV (past roles only)',
            'icon': '📋'
        }
    }
    
    for section_key, config in sections_config.items():
        if section_key in st.session_state.individual_generations:
            content = st.session_state.individual_generations[section_key]
            if content and content.strip():
                with st.expander(f"{config['icon']} {config['title']} - Click to expand", expanded=False):
                    st.markdown(f"### {config['title']}")
                    st.markdown(f"*{config['subtitle']}*")
                    st.markdown("---")
                    
                    # View toggle tabs
                    tab1, tab2 = st.tabs(["📄 Text View", "🔧 JSON View"])
                    
                    with tab1:
                        # Clean content to ensure only headings are bold
                        cleaned_content = clean_generated_content(content)
                        st.markdown(cleaned_content)
                        st.caption(config['caption'])
                    
                    with tab2:
                        # Show JSON structured data if available
                        if section_key in st.session_state.llm_json_responses:
                            json_data = st.session_state.llm_json_responses[section_key]
                            st.json(json_data)
                        else:
                            # Create a structured representation from text content
                            try:
                                structured_data = parse_text_to_json(section_key, content)
                                st.json(structured_data)
                                st.caption("*Auto-generated JSON structure from text response*")
                            except Exception as e:
                                st.warning(f"Could not parse to JSON: {str(e)}")
                                st.code(content, language="text")

def generate_top_skills(llm_service, context_builder):
    """Generate top 10 skills with expandable display using professional ATS-optimized prompt"""
    
    with st.spinner("🛠️ Generating top 10 skills..."):
        try:
            # Get job description context
            job_context = context_builder.retriever.get_jd_specific_context([
                "job description requirements responsibilities qualifications skills",
                "technical skills competencies requirements",
                "qualifications experience needed"
            ])["context"]
            
            # Get experience superset context
            experience_context = context_builder.retriever.get_superset_context(
                "skills technical competencies expertise experience achievements"
            )["context"]
            
            prompt = f"""You are an expert CV writer and ATS optimizer for senior engineering leadership roles.
Read two attached input files (PDFs):
- FILE 1: Job_Description.pdf → complete job description
- FILE 2: CV_ExperienceSummary_Skills_Superset - Google Docs.pdf → my full "experience superset"

JOB DESCRIPTION CONTEXT:
{job_context}

EXPERIENCE SUPERSET CONTEXT:
{experience_context}

GOAL
Produce EXACTLY 10 skills (max two words each) that:
- Are directly derived from the JD's language.
- Are ordered by PRIORITY based on the JD's stated and implied requirements.
- Are present in (or credibly supported by) my Experience Superset to avoid listing skills I don't have.

SKILL RULES
- Each skill must be ≤ 2 words, Title Case, and ideally reuse JD keywords verbatim.
- Prefer JD phrasing over synonyms; only use a close synonym if the exact JD term cannot fit in ≤ 2 words.
- No duplication or near-duplicates (e.g., "Platform Engineering" vs "Platform Ops"—pick one).
- Use international English unless the JD clearly uses US spelling.
- Do NOT add commentary, definitions, or examples.

PRIORITY RULES (ORDER HIGHEST → LOWEST)
1) Mission-critical competencies and leadership scope explicitly required by the JD.
2) Skills/terms repeated or emphasised in the JD (high keyword frequency or prominence).
3) Strategic differentiators likely valued for this role (use your industry knowledge), when also supported by my Superset.

PROCESS (AI internal reasoning; do NOT include in output)
1) Parse Job_Description.pdf → extract competencies, requirements, repeated keywords, leadership scope, domain/tech stack.
2) Parse the Superset PDF → identify which JD skills I can credibly claim.
3) Build a candidate skill list from JD terms (≤ 2 words), mapped to my Superset.
4) Rank candidates using the priority rules; remove overlaps and near-duplicates.
5) Final check for clarity, JD wording fidelity, and ATS friendliness.

OUTPUT FORMAT (strict)
- Output ONLY the 10 skills, one per line, highest priority first.
- No numbering, no bullets, no extra text.
- Each line must be exactly a ≤ 2-word skill in Title Case.

CONSTRAINTS
- Use ONLY skills supported by my Superset (no fabrication).
- Keep every skill ≤ 2 words; compress longer JD phrases while preserving meaning (e.g., "Incident Management," "Vendor Strategy").
- Avoid buzzword noise; each skill must map to a concrete competency in the JD.

QUALITY BAR
- Challenge your first pass: does each skill mirror JD language, reflect priority, and align with my Superset?
- Assume review by both ATS and a CTO—optimise for accuracy, clarity, and relevance.

BEGIN."""
            
            response = llm_service.generate_content(prompt, max_tokens=500)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['top_skills'] = response
            
            st.success("✅ Top 10 Skills generated successfully!")
            st.info("👁️ View your generated content in the 'Generated Individual Sections' below")
            
        except Exception as e:
            st.error(f"❌ Error generating skills: {str(e)}")

def generate_experience_bullets(llm_service, context_builder):
    """Generate current position summary with top 8 bullets including role details"""
    
    with st.spinner("💼 Generating current position summary top8..."):
        try:
            # Get sample CV content to extract current role information
            sample_cv_context = context_builder.retriever.get_superset_context(
                "current role position job title company work experience employment"
            )["context"]
            
            # Get job description context for bullet relevance
            job_context = context_builder.retriever.get_jd_specific_context([
                "job description requirements responsibilities qualifications",
                "technical skills competencies requirements",
                "qualifications experience needed"
            ])["context"]
            
            # First LLM call: Extract current role information from sample CV
            extraction_prompt = f"""You are a CV data extraction specialist. Extract the current/most recent job role information from the provided CV content.

SAMPLE CV CONTENT:
{sample_cv_context}

TASK: Extract the current/most recent position details and format as JSON.

OUTPUT FORMAT (JSON):
{{
    "role_data": {{
        "position_name": "exact job title from CV",
        "company_name": "company name from CV", 
        "location": "work location (city, country)",
        "start_date": "start date (format: MMM YYYY)",
        "end_date": "end date or 'Present' if current",
        "work_duration": "calculated duration (e.g., '2 years 3 months')",
        "key_bullets": [
            "bullet point 1 from CV",
            "bullet point 2 from CV",
            "bullet point 3 from CV",
            "bullet point 4 from CV",
            "bullet point 5 from CV",
            "bullet point 6 from CV",
            "bullet point 7 from CV",
            "bullet point 8 from CV"
        ]
    }}
}}

EXTRACTION RULES:
- Extract ONLY information that exists in the CV
- If any field is not found, use "Not specified" 
- For work_duration, calculate from start_date to end_date
- Extract key achievement bullets exactly as written in CV (each as separate array item)
- Include up to 8 bullet points, each as a separate row in key_bullets array
- Focus on the most recent/current position only

Return ONLY the JSON object, no additional text."""

            # Get structured role data from LLM
            role_extraction = llm_service.generate_content(extraction_prompt, max_tokens=500)
            
            # Parse the JSON response
            try:
                extracted_data = json.loads(role_extraction.strip())
                role_data = extracted_data.get('role_data', extracted_data)  # Handle both formats
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                role_data = {
                    "position_name": "Senior Engineering Manager",
                    "company_name": "Technology Company",
                    "location": "Remote",
                    "start_date": "Jan 2022", 
                    "end_date": "Present",
                    "work_duration": "2+ years",
                    "key_bullets": []
                }
            
            # Second LLM call: Generate optimized SAR bullets as JSON array
            bullet_prompt = f"""You are an expert CV writer. Create 8 high-impact achievement bullets for the current position.

CURRENT ROLE DATA:
Position: {role_data.get('position_name', 'Senior Position')}
Company: {role_data.get('company_name', 'Company')}
Duration: {role_data.get('work_duration', '2+ years')}

JOB DESCRIPTION REQUIREMENTS:
{job_context}

ORIGINAL CV BULLETS (reference):
{chr(10).join(role_data.get('key_bullets', []))}

GOAL: Create EXACTLY 8 achievement-focused bullets that align with the target job requirements.

BULLET FORMAT:
**Two Words** | [Context/challenge] → [Action taken] → [Quantified outcome]

EXAMPLE:
**Platform Migration** | Led critical infrastructure upgrade affecting 50M+ users → Designed zero-downtime migration strategy and coordinated 5 engineering teams → Completed migration 2 weeks early with 99.99% uptime maintained.

CONTENT REQUIREMENTS:
- Each bullet showcases different leadership/technical competencies
- Include specific metrics, numbers, percentages where possible  
- Align with target role requirements from job description
- Demonstrate senior-level impact and decision-making
- Use varied action verbs and technical depth

OUTPUT FORMAT (JSON):
{{
    "optimized_bullets": [
        "**First Bullet** | Achievement bullet 1",
        "**Second Bullet** | Achievement bullet 2",
        "**Third Bullet** | Achievement bullet 3",
        "**Fourth Bullet** | Achievement bullet 4",
        "**Fifth Bullet** | Achievement bullet 5",
        "**Sixth Bullet** | Achievement bullet 6",
        "**Seventh Bullet** | Achievement bullet 7",
        "**Eighth Bullet** | Achievement bullet 8"
    ]
}}

Return ONLY the JSON object with exactly 8 bullets, no additional text."""

            bullets_response = llm_service.generate_content(bullet_prompt, max_tokens=800)
            
            # Clean the response - remove markdown code blocks if present
            cleaned_response = bullets_response.strip()
            if '```json' in cleaned_response:
                # Extract JSON from markdown code block
                start_idx = cleaned_response.find('```json') + 7
                end_idx = cleaned_response.find('```', start_idx)
                if end_idx > start_idx:
                    cleaned_response = cleaned_response[start_idx:end_idx].strip()
            elif '```' in cleaned_response:
                # Remove any markdown code blocks
                cleaned_response = cleaned_response.replace('```', '').strip()
            
            # Parse the bullets JSON response
            try:
                bullets_data = json.loads(cleaned_response)
                optimized_bullets = bullets_data.get('optimized_bullets', [])
            except json.JSONDecodeError:
                # Fallback: treat as plain text and split by lines
                optimized_bullets = [line.strip() for line in bullets_response.strip().split('\n') if line.strip()]
            
            # Format bullets for display
            formatted_bullets = '\n'.join([f"• {bullet}" for bullet in optimized_bullets])
            
            # Combine role info and bullets into formatted output
            formatted_output = f"""**{role_data.get('position_name', 'Current Position')}**
*{role_data.get('company_name', 'Company')}, {role_data.get('location', 'Location')} | {role_data.get('start_date', 'Start')} - {role_data.get('end_date', 'Present')} ({role_data.get('work_duration', 'Duration')})*

{formatted_bullets}"""
            
            # Store both formatted output and structured data
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            if 'llm_json_responses' not in st.session_state:
                st.session_state.llm_json_responses = {}
                
            st.session_state.individual_generations['experience_bullets'] = formatted_output
            st.session_state.llm_json_responses['experience_bullets'] = {
                "role_data": role_data,
                "optimized_bullets": optimized_bullets,
                "bullets_text": bullets_response,
                "formatted_output": formatted_output
            }
            
            st.success("✅ Current Position Summary Top8 generated successfully!")
            st.info("👁️ View your generated content in the 'Generated Individual Sections' below")
            
        except Exception as e:
            st.error(f"❌ Error generating current position summary: {str(e)}")

def generate_executive_summary(llm_service, context_builder):
    """Generate executive summary with expandable display using professional ATS-optimized prompt"""
    
    with st.spinner("📊 Generating executive summary..."):
        try:
            # Get job description context
            job_context = context_builder.retriever.get_jd_specific_context([
                "job description requirements responsibilities qualifications leadership",
                "job requirements duties role expectations",
                "qualifications experience needed preferred"
            ])["context"]
            
            # Get experience superset context
            experience_context = context_builder.retriever.get_superset_context(
                "professional summary career experience background achievements leadership"
            )["context"]
            
            prompt = f"""You are an expert CV writer and ATS optimizer for senior engineering leadership roles.

GOAL
Read two attached input files (PDFs):
- FILE 1: Job_Description.pdf → complete job description
- FILE 2: CV_ExperienceSummary_Skills_Superset - Google Docs.pdf → my full "experience superset"

JOB DESCRIPTION CONTEXT:
{job_context}

EXPERIENCE SUPERSET CONTEXT:
{experience_context}

Produce ONE high-impact **Career Summary** (≤40 words) that:
- Is written in a polished, executive tone.
- Directly aligns with the JD using keywords naturally.
- Demonstrates leadership scope, technical expertise, and business impact.
- Prioritises mission-critical competencies stated or implied in the JD.
- Is concise, powerful, and ATS-friendly.

SUMMARY RULES
- ≤40 words, single paragraph.
- No first-person pronouns, fluff, or vague adjectives.
- Integrate the highest-priority keywords from the JD.
- Highlight leadership scale, strategic contributions, and technical breadth.
- Use international English unless the JD uses US spelling.

PRIORITY RULES
1. Core leadership and engineering competencies the JD emphasises.
2. High-frequency JD keywords and themes.
3. Strategic differentiators (e.g., AI adoption, vendor mgmt, cloud cost optimisation) supported by my Superset.

PROCESS (internal, do NOT include in output)
1. Parse the JD → extract repeated competencies, seniority level, domain focus, and business goals.
2. Parse the Superset → map accomplishments and skills.
3. Select only the highest-priority elements.
4. Craft a concise, impactful executive summary using JD language.
5. Final pass: tighten wording to ≤40 words; ensure ATS optimisation.

OUTPUT FORMAT (strict)
- Output ONLY the single summary text in one paragraph, ≤40 words.
- No labels, no headings, no commentary.

QUALITY BAR
- Pretend this will sit at the top of a CTO-level CV and be scanned by ATS and executive recruiters.
- Ensure clarity, measurable leadership impact, and keyword relevance.

BEGIN."""
            
            response = llm_service.generate_content(prompt, max_tokens=200)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['executive_summary'] = response
            
            st.success("✅ Executive Summary generated successfully!")
            st.info("👁️ View your generated content in the 'Generated Individual Sections' below")
            
        except Exception as e:
            st.error(f"❌ Error generating executive summary: {str(e)}")

def generate_previous_experience_summary(llm_service, context_builder):
    """Generate previous experience summary with structured JSON format for multiple positions"""
    
    with st.spinner("📋 Generating previous experience summary..."):
        try:
            # Check if sample CV is available
            if 'sample_cv_content' not in st.session_state or not st.session_state.sample_cv_content:
                st.warning("⚠️ Sample CV not available. Please upload a Sample CV to generate previous experience summary.")
                return
            
            # Get sample CV content for experience extraction
            sample_cv_content = st.session_state.sample_cv_content
            
            # First LLM call: Extract previous roles data in JSON format with strict guardrails
            extraction_prompt = f"""You are a CV data extraction specialist. Extract ONLY previous/past work experiences from the CV (exclude current/most recent role).

CV CONTENT:
{sample_cv_content}

CRITICAL EXTRACTION RULES:
1. EXTRACT ONLY - Do not create, generate, or hallucinate any information
2. Include ONLY previous/past positions (exclude current/most recent role)
3. Extract exact job titles, company names, and dates as written in CV
4. Calculate work duration for each role (e.g., "2 years 3 months")
5. Extract 2-4 key achievements/responsibilities per role EXACTLY as written
6. If no previous roles exist, return {{"previous_roles_data": []}}
7. Preserve original wording and content from CV

STRICT GUARDRAILS:
❌ Do NOT create fictional positions
❌ Do NOT add achievements not in the CV
❌ Do NOT rephrase or improve content
❌ Do NOT include current/most recent role
❌ Do NOT infer information not explicitly stated

✅ DO extract exact text from CV
✅ DO maintain original company names
✅ DO preserve exact job titles
✅ DO calculate accurate work durations

OUTPUT FORMAT (JSON):
{{
  "previous_roles_data": [
    {{
      "position_name": "exact job title from CV",
      "company_name": "exact company name from CV",
      "location": "work location from CV (city, state/country)",
      "start_date": "start date (format: MMM YYYY)",
      "end_date": "end date (format: MMM YYYY)",
      "work_duration": "calculated duration (e.g., '2 years 3 months')",
      "key_bullets": [
        "achievement/responsibility 1 exactly as written",
        "achievement/responsibility 2 exactly as written",
        "achievement/responsibility 3 exactly as written"
      ]
    }}
  ]
}}

VALIDATION CHECK: Ensure every field comes directly from the CV content. Do not fabricate any information."""
            
            # Generate structured role data
            roles_response = llm_service.generate_content(extraction_prompt, max_tokens=3500)
            
            # Parse JSON and validate
            try:
                import json
                roles_data = json.loads(roles_response)
                
                # Validate structure
                if 'previous_roles_data' not in roles_data:
                    st.warning("⚠️ Invalid JSON structure returned by LLM")
                    return
                
                previous_roles = roles_data['previous_roles_data']
                
                if not previous_roles:
                    st.info("ℹ️ No previous roles found in sample CV")
                    return
                
                # Second LLM call: Generate optimized bullets for each role
                optimized_roles = []
                
                for role in previous_roles:
                    role_name = role.get('position_name', 'Unknown Position')
                    company = role.get('company_name', 'Unknown Company')
                    bullets = role.get('key_bullets', [])
                    
                    if bullets:
                        # For previous positions, use original bullets from sample CV as-is
                        # No SAR formatting or pipe symbols needed
                        role['key_bullets'] = bullets
                    
                    optimized_roles.append(role)
                
                # Create formatted output for display
                formatted_sections = []
                for role in optimized_roles:
                    role_header = f"**{role.get('position_name', 'Unknown Position')}** | {role.get('company_name', 'Unknown Company')}, {role.get('location', 'Unknown Location')} | {role.get('start_date', '')} - {role.get('end_date', '')} ({role.get('work_duration', '')})"
                    formatted_sections.append(role_header)
                    
                    for bullet in role.get('key_bullets', []):
                        formatted_sections.append(f"• {bullet}")
                    formatted_sections.append("")  # Add spacing
                
                formatted_response = '\n'.join(formatted_sections).strip()
                
                # Store both formatted text and structured JSON
                if 'individual_generations' not in st.session_state:
                    st.session_state.individual_generations = {}
                if 'llm_json_responses' not in st.session_state:
                    st.session_state.llm_json_responses = {}
                
                st.session_state.individual_generations['previous_experience'] = formatted_response
                st.session_state.llm_json_responses['previous_experience'] = {'previous_roles_data': optimized_roles}
                
                st.success(f"✅ Previous Experience Summary generated successfully! ({len(optimized_roles)} roles processed)")
                st.info("👁️ View your generated content in the 'Generated Individual Sections' below")
                
            except json.JSONDecodeError as e:
                st.error(f"❌ Failed to parse LLM JSON response: {str(e)}")
                st.warning("🔧 Falling back to text extraction method")
                
                # Fallback: use original text extraction
                fallback_response = llm_service.generate_content(
                    f"Extract previous work experience from CV (exclude current role): {sample_cv_content}",
                    max_tokens=2000
                )
                
                if 'individual_generations' not in st.session_state:
                    st.session_state.individual_generations = {}
                st.session_state.individual_generations['previous_experience'] = fallback_response
                
        except Exception as e:
            st.error(f"❌ Error generating previous experience summary: {str(e)}")

def generate_whole_cv(llm_service, context_builder, name, email, phone, location, linkedin, website):
    """Generate a complete, professionally formatted CV using individual sections"""
    
    with st.spinner("🎯 Generating complete professional CV..."):
        try:
            # Validate required information
            if not name or not email:
                st.error("❌ Please provide at least Name and Email to generate CV")
                return
            
            # Validate that we have sufficient content sections
            required_sections = ['executive_summary', 'top_skills', 'experience_bullets']
            available_sections = [section for section in required_sections 
                                if section in st.session_state.individual_generations 
                                and st.session_state.individual_generations[section].strip()]
            
            if len(available_sections) < 2:
                st.error("❌ Please generate at least 2 individual sections with content before creating whole CV")
                st.info("💡 Required: Executive Summary, Top Skills, or Experience Bullets")
                return
            
            # Build contact information section
            contact_info = build_contact_section(name, email, phone, location, linkedin, website)
            
            # Get individual sections from session state
            executive_summary = st.session_state.individual_generations.get('executive_summary', '').strip()
            top_skills = st.session_state.individual_generations.get('top_skills', '').strip()
            experience_bullets = st.session_state.individual_generations.get('experience_bullets', '').strip()
            previous_experience = st.session_state.individual_generations.get('previous_experience', '').strip()
            
            # Validate content is not empty
            content_validation = validate_cv_content(executive_summary, top_skills, experience_bullets)
            if not content_validation['valid']:
                st.error(f"❌ Content validation failed: {content_validation['message']}")
                return
            
            # Process and format sections
            formatted_summary = format_executive_summary(executive_summary)
            formatted_skills = format_skills_section(top_skills)
            formatted_current_experience = format_current_experience(experience_bullets)
            formatted_previous_experience = format_previous_experience(previous_experience) if previous_experience else ""
            
            # Generate additional information section
            additional_info = generate_additional_info_section(llm_service, context_builder)
            
            # Combine all sections into complete CV
            complete_cv = assemble_complete_cv(
                contact_info, formatted_summary, formatted_skills, 
                formatted_current_experience, formatted_previous_experience, additional_info
            )
            
            # Final validation of complete CV
            if not complete_cv or len(complete_cv.strip()) < 100:
                st.error("❌ Generated CV content is too short or empty. Please regenerate individual sections.")
                return
            
            # Store in session state
            st.session_state.whole_cv_content = complete_cv
            st.session_state.whole_cv_contact = {
                'name': name, 'email': email, 'phone': phone, 
                'location': location, 'linkedin': linkedin, 'website': website
            }
            
            # Log content summary for debugging
            content_summary = {
                'total_chars': len(complete_cv),
                'sections_count': len([s for s in [formatted_summary, formatted_skills, formatted_current_experience, formatted_previous_experience] if s.strip()]),
                'has_contact': bool(contact_info.strip()),
                'has_summary': bool(formatted_summary.strip()),
                'has_skills': bool(formatted_skills.strip()),
                'has_experience': bool(formatted_current_experience.strip()),
                'experience_length': len(formatted_current_experience) if formatted_current_experience else 0,
                'raw_bullets_length': len(experience_bullets) if experience_bullets else 0
            }
            
            st.success("✅ Complete CV generated successfully!")
            st.info("👁️ Click 'Preview CV' to review before downloading PDF")
            
            # Add debug info for troubleshooting
            with st.expander("🐛 Debug Info (Content Summary)", expanded=False):
                st.json(content_summary)
                if experience_bullets:
                    st.markdown("**Raw Experience Bullets:**")
                    st.text(experience_bullets[:200] + "..." if len(experience_bullets) > 200 else experience_bullets)
                if formatted_current_experience:
                    st.markdown("**Formatted Current Experience:**")
                    st.text(formatted_current_experience[:300] + "..." if len(formatted_current_experience) > 300 else formatted_current_experience)
            
        except Exception as e:
            st.error(f"❌ Error generating complete CV: {str(e)}")
            logger.error(f"CV generation error: {e}")



def validate_cv_content(executive_summary, top_skills, experience_bullets):
    """Validate that CV content sections have sufficient content"""
    
    issues = []
    
    # Check executive summary
    if executive_summary and len(executive_summary.split()) < 3:
        issues.append("Executive summary is too short (minimum 3 words)")
    
    # Check skills
    if top_skills:
        skills_lines = [line.strip() for line in top_skills.split('\n') if line.strip()]
        if len(skills_lines) < 3:
            issues.append("Skills section needs at least 3 skills")
    
    # Check experience bullets (no minimum restriction needed)
    # Previous experience can have any number of bullet points
    
    # Check that we have meaningful content overall
    total_content = f"{executive_summary} {top_skills} {experience_bullets}"
    if len(total_content.strip()) < 50:
        issues.append("Overall content is too short (minimum 50 characters)")
    
    return {
        'valid': len(issues) == 0,
        'message': '; '.join(issues) if issues else 'Content validation passed',
        'issues': issues
    }

def build_contact_section(name, email, phone, location, linkedin, website):
    """Build single-line contact information section"""
    contact_parts = [name]
    
    if email:
        contact_parts.append(f"📧 {email}")
    if phone:
        contact_parts.append(f"📞 {phone}")
    if location:
        contact_parts.append(f"📍 {location}")
    if linkedin:
        linkedin_clean = linkedin.replace("linkedin.com/in/", "").replace("https://", "").replace("http://", "")
        contact_parts.append(f"💼 linkedin.com/in/{linkedin_clean}")
    if website:
        website_clean = website.replace("https://", "").replace("http://", "")
        contact_parts.append(f"🌐 {website_clean}")
    
    return " | ".join(contact_parts)

def format_executive_summary(summary_text):
    """Format executive summary section"""
    if not summary_text:
        return ""
    
    # Clean and ensure ≤30 words
    cleaned = clean_generated_content(summary_text)
    words = cleaned.split()
    if len(words) > 30:
        cleaned = " ".join(words[:30]) + "..."
    
    return f"**PROFESSIONAL SUMMARY**\n\n{cleaned}"

def format_skills_section(skills_text):
    """Format skills section with visual boxes (4 per row)"""
    if not skills_text:
        return ""
    
    # Extract skills from the generated text
    skills = extract_skills_list(skills_text)
    
    # Format as 4 skills per row
    skills_rows = []
    for i in range(0, len(skills), 4):
        row_skills = skills[i:i+4]
        formatted_row = " | ".join([f"**{skill}**" for skill in row_skills])
        skills_rows.append(formatted_row)
    
    skills_formatted = "\n".join(skills_rows)
    return f"**CORE SKILLS**\n\n{skills_formatted}"

def format_current_experience(experience_text):
    """Format current role experience with detailed 8 bullets"""
    if not experience_text or not experience_text.strip():
        return ""
    
    # Extract and format the 8 SAR bullets
    bullets = extract_experience_bullets(experience_text)
    
    if not bullets:
        # If extraction failed, try to use the raw text as bullets
        lines = [line.strip() for line in experience_text.split('\n') if line.strip()]
        bullets = [line for line in lines if len(line) > 10][:8]
    
    formatted_bullets = []
    for bullet in bullets[:8]:  # Ensure exactly 8 bullets
        if ":" in bullet and not bullet.startswith("**"):
            # Format SAR bullets with two-word headings
            heading, description = bullet.split(":", 1)
            # Clean heading of any existing formatting
            heading = heading.replace("**", "").strip()
            formatted_bullets.append(f"• **{heading}**: {description.strip()}")
        elif ":" in bullet and bullet.startswith("**"):
            # Already formatted heading
            formatted_bullets.append(f"• {bullet}")
        else:
            # Simple bullet without heading
            formatted_bullets.append(f"• {bullet}")
    
    bullets_formatted = "\n".join(formatted_bullets)
    
    # Ensure we have content
    if not bullets_formatted.strip():
        return f"**PROFESSIONAL EXPERIENCE**\n\n**Current Role** | Present\n\n• Experience details will be added here"
    
    # Add professional experience section header
    return f"**PROFESSIONAL EXPERIENCE**\n\n**Current Role** | Present\n\n{bullets_formatted}"

def extract_previous_experience_from_cv(cv_content):
    """Extract the complete Previous Roles section from the whole CV content"""
    if not cv_content:
        return ""
    
    lines = cv_content.split('\n')
    in_previous_section = False
    previous_content = []
    
    for line in lines:
        line_upper = line.upper().strip()
        
        # Look for "Previous Roles" section header
        if 'PREVIOUS ROLES' in line_upper or 'PREVIOUS EXPERIENCE' in line_upper:
            in_previous_section = True
            continue
            
        # Stop when we hit another major section
        elif in_previous_section and any(section in line_upper for section in [
            'ADDITIONAL INFORMATION', 'CERTIFICATIONS', 'EDUCATION', 
            'AWARDS', 'LANGUAGES', 'REFERENCES', '---'
        ]):
            break
            
        # Collect content if we're in the previous section
        elif in_previous_section:
            previous_content.append(line)
    
    # Join and clean the content
    result = '\n'.join(previous_content).strip()
    return result

def format_previous_experience(prev_exp_text):
    """Format previous experience section (concise, 3-4 bullets per role)"""
    if not prev_exp_text:
        return ""
    
    # This would parse the previous experience and format it concisely
    cleaned = clean_generated_content(prev_exp_text)
    
    return f"\n\n**Previous Roles**\n\n{cleaned}"

def generate_additional_info_section(llm_service, context_builder):
    """Generate additional information table (certifications, awards, etc.)"""
    try:
        # Get context for additional information
        additional_context = context_builder.retriever.get_superset_context(
            "certifications awards achievements education training courses"
        )["context"]
        
        if not additional_context.strip():
            return ""
        
        prompt = f"""
Extract and organize additional professional information into a compact 2-column table format.

CONTEXT:
{additional_context}

GOAL:
- Create a professional 2-column table: Category | Details
- Include: Certifications, Awards, Education, Training, Languages, etc.
- Keep entries concise and impactful
- Maximum 8 rows

OUTPUT FORMAT:
| Category | Details |
|----------|---------|
| Certifications | List relevant certifications |
| Awards | Notable achievements |
| Education | Degrees/qualifications |
| Training | Key training programs |

Return only the table, no additional text.
"""
        
        additional_info = llm_service.generate_content(prompt, max_tokens=500)
        return f"\n\n**ADDITIONAL INFORMATION**\n\n{additional_info}"
        
    except Exception as e:
        logger.error(f"Error generating additional info: {e}")
        return ""

def extract_skills_list(skills_text):
    """Extract clean skills list from generated text"""
    import re
    
    if not skills_text:
        return []
    
    # Handle pipe-separated format: **Skill1** | **Skill2** | **Skill3**
    if '|' in skills_text:
        skills = []
        parts = skills_text.split('|')
        for part in parts:
            # Clean each skill: remove ** and whitespace
            clean_skill = part.strip().replace('**', '').replace('*', '').strip()
            if clean_skill and len(clean_skill.split()) <= 3:  # Allow up to 3 words per skill
                skills.append(clean_skill)
        return skills[:10]
    
    # Handle line-by-line format
    cleaned = clean_generated_content(skills_text)
    skills = []
    lines = cleaned.split('\n')
    
    for line in lines:
        line = line.strip()
        if line:
            # Remove bullet points, numbers, and markdown formatting
            line = re.sub(r'^[\d\.\-\•\*\+]\s*', '', line)
            line = line.replace('**', '').replace('*', '').strip()
            
            # Skip headers and empty lines
            if line and not line.startswith('#') and len(line.split()) <= 3:
                skills.append(line)
    
    return skills[:10]

def extract_experience_bullets(experience_text):
    """Extract experience bullets from generated text"""
    import re
    
    if not experience_text or not experience_text.strip():
        return []
    
    cleaned = clean_generated_content(experience_text)
    lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
    
    bullets = []
    for line in lines:
        # Look for bullets with two-word headings (SAR format)
        if ':' in line and len(line.split(':')[0].strip().split()) <= 3:
            # Remove existing bullet points and clean
            line = re.sub(r'^[\-\•\*\+\d\.]\s*', '', line).strip()
            if line and not line.startswith('#'):  # Skip headers
                bullets.append(line)
        # Also catch any line that looks like a bullet point
        elif re.match(r'^[\-\•\*\+]?\s*\**\w+.*?:', line):
            line = re.sub(r'^[\-\•\*\+]\s*', '', line).strip()
            if line and not line.startswith('#'):  # Skip headers
                bullets.append(line)
    
    # If we still don't have bullets, be more lenient
    if not bullets:
        for line in lines:
            if line and not line.startswith('#') and len(line) > 10:
                line = re.sub(r'^[\-\•\*\+\d\.]\s*', '', line).strip()
                bullets.append(line)
    
    return bullets[:8]  # Ensure max 8 bullets

def assemble_complete_cv(contact, summary, skills, current_exp, previous_exp, additional_info):
    """Assemble all sections into complete CV format"""
    
    cv_sections = [
        contact,
        summary,
        skills,
        current_exp
    ]
    
    if previous_exp.strip():
        cv_sections.append(previous_exp)
    
    if additional_info.strip():
        cv_sections.append(additional_info)
    
    return "\n\n---\n\n".join([section for section in cv_sections if section.strip()])

def show_cv_preview():
    """Display CV preview using template engine for consistent formatting"""
    
    # Check if we have the necessary data for template engine
    if ('individual_generations' not in st.session_state or 
        'whole_cv_contact' not in st.session_state):
        st.warning("⚠️ No CV data available for preview")
        return
    
    try:
        # Use template engine to generate consistent preview content
        cv_data = convert_session_to_cvdata()
        preview_content = template_engine.render_cv_preview(cv_data)
        
        # Show CV preview with toggle for expanded view  
        expanded_view = st.checkbox("📖 Show full-width CV preview", value=False, help="Check to see CV preview in full page width")
        
        if expanded_view:
            # Full width preview
            st.markdown("### 📄 Generated CV Preview (Full Width)")
            st.markdown("*Review your complete CV before downloading as PDF*")
            st.markdown("---")
            
            # Display the template-generated content
            st.markdown(preview_content)
            
            st.markdown("---")
            st.caption("🎯 Professional CV preview")
        else:
            # Compact expander view  
            with st.expander("👁️ Complete CV Preview - Click to expand", expanded=True):
                st.markdown("### 📄 Generated CV Preview")
                st.markdown("*Review your complete CV before downloading as PDF*")
                st.markdown("---")
                
                # Display the template-generated content
                st.markdown(preview_content)
                
                st.markdown("---")
                st.caption("🎯 Professional CV preview")
                
    except Exception as e:
        st.error(f"❌ Error generating CV preview: {str(e)}")
        # Fallback to old content if available
        if 'whole_cv_content' in st.session_state and st.session_state.whole_cv_content:
            st.warning("⚠️ Using fallback content format")
            st.markdown(st.session_state.whole_cv_content)

def generate_cv_pdf():
    """Generate CV as PDF and return the PDF data"""
    try:
        # Validate that CV content exists and is not empty
        if 'whole_cv_content' not in st.session_state or not st.session_state.whole_cv_content:
            st.error("❌ No CV content available. Please generate CV first.")
            return None
        
        if 'whole_cv_contact' not in st.session_state or not st.session_state.whole_cv_contact:
            st.error("❌ No contact information available. Please generate CV first.")
            return None
        
        cv_content = st.session_state.whole_cv_content.strip()
        contact_info = st.session_state.whole_cv_contact
        
        # Validate content length and quality
        if len(cv_content) < 100:
            st.error("❌ CV content is too short to generate a meaningful PDF. Please regenerate the CV.")
            return None
        
        # Check that we have essential contact information
        if not contact_info.get('name') or not contact_info.get('email'):
            st.error("❌ Missing essential contact information (name/email). Please regenerate CV.")
            return None
        
        # Validate that CV has structured sections
        sections_check = validate_cv_structure(cv_content)
        if not sections_check['valid']:
            st.error(f"❌ CV structure validation failed: {sections_check['message']}")
            st.info("💡 Please regenerate individual sections and try again.")
            
            # Show debug info to understand what's in the CV
            with st.expander("🔍 Debug: CV Content Analysis", expanded=False):
                st.text("First 1000 characters of CV:")
                st.text(cv_content[:1000])
                st.text("---")
                st.text("Lines containing common section words:")
                lines = cv_content.split('\n')
                for i, line in enumerate(lines):
                    line_upper = line.upper()
                    if any(word in line_upper for word in ['SUMMARY', 'SKILLS', 'EXPERIENCE', 'PROFESSIONAL', 'EXECUTIVE']):
                        st.text(f"Line {i+1}: {line}")
            
            return None
        
        # Generate PDF with teal color scheme using individual sections
        pdf_exporter = get_pdf_exporter()
        
        # Get individual sections from session state with fallback to whole CV content
        individual_sections = {}
        
        if 'individual_generations' in st.session_state and st.session_state.individual_generations:
            # Extract complete previous experience from whole CV content to avoid truncation
            complete_previous_experience = extract_previous_experience_from_cv(cv_content)
            
            individual_sections = {
                'executive_summary': st.session_state.individual_generations.get('executive_summary', ''),
                'top_skills': st.session_state.individual_generations.get('top_skills', ''),
                'experience_bullets': st.session_state.individual_generations.get('experience_bullets', ''),
                'previous_experience': complete_previous_experience
            }
        else:
            # Fallback: parse sections from whole CV content
            st.warning("⚠️ Individual sections not found. Using whole CV content with parsed sections.")
            individual_sections = {
                'executive_summary': '',
                'top_skills': '',
                'experience_bullets': cv_content,
                'previous_experience': ''
            }
        
        # Use the new direct method that matches preview CV logic
        try:
            pdf_path = pdf_exporter.create_direct_cv_pdf(
                contact_info, cv_content, color_scheme="teal"
            )
        except AttributeError:
            # Method not available (cache issue), clear cache and try again
            st.cache_resource.clear()
            pdf_exporter = get_pdf_exporter()
            
            try:
                pdf_path = pdf_exporter.create_direct_cv_pdf(
                    contact_info, cv_content, color_scheme="teal"
                )
            except AttributeError:
                # Still not available, use fallback method
                st.warning("⚠️ Using fallback PDF generation method.")
                pdf_path = pdf_exporter.create_professional_cv_pdf(
                    cv_content, contact_info, color_scheme="teal"
                )
        
        # Validate PDF was created and has content
        if not os.path.exists(pdf_path):
            raise Exception("PDF file was not created")
        
        file_size = os.path.getsize(pdf_path)
        if file_size < 1000:  # PDF should be at least 1KB
            raise Exception(f"PDF file is too small ({file_size} bytes), likely empty")
        
        # Read and return PDF data
        with open(pdf_path, "rb") as file:
            pdf_data = file.read()
            
            if len(pdf_data) < 1000:
                raise Exception("PDF data is too small, likely corrupted or empty")
            
            return pdf_data
            
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        st.error(f"❌ Error generating PDF: {str(e)}")
        return None

def validate_cv_structure(cv_content):
    """Validate that the CV has proper structure and sections"""
    
    issues = []
    sections_found = 0
    
    # Check for required section markers (with alternatives and various formats)
    required_sections = [
        {
            'alternatives': [
                'PROFESSIONAL SUMMARY', 'EXECUTIVE SUMMARY', 'CAREER SUMMARY', 'SUMMARY',
                '**PROFESSIONAL SUMMARY**', '**EXECUTIVE SUMMARY**', '**CAREER SUMMARY**', '**SUMMARY**',
                '# PROFESSIONAL SUMMARY', '# EXECUTIVE SUMMARY', '# CAREER SUMMARY', '# SUMMARY',
                '## PROFESSIONAL SUMMARY', '## EXECUTIVE SUMMARY', '## CAREER SUMMARY', '## SUMMARY'
            ],
            'name': 'Summary Section'
        },
        {
            'alternatives': [
                'CORE SKILLS', 'SKILLS', 'TECHNICAL SKILLS', 'KEY SKILLS',
                '**CORE SKILLS**', '**SKILLS**', '**TECHNICAL SKILLS**', '**KEY SKILLS**',
                '# CORE SKILLS', '# SKILLS', '# TECHNICAL SKILLS', '# KEY SKILLS',
                '## CORE SKILLS', '## SKILLS', '## TECHNICAL SKILLS', '## KEY SKILLS'
            ],
            'name': 'Skills Section'  
        },
        {
            'alternatives': [
                'PROFESSIONAL EXPERIENCE', 'WORK EXPERIENCE', 'EXPERIENCE', 'EMPLOYMENT HISTORY',
                '**PROFESSIONAL EXPERIENCE**', '**WORK EXPERIENCE**', '**EXPERIENCE**', '**EMPLOYMENT HISTORY**',
                '# PROFESSIONAL EXPERIENCE', '# WORK EXPERIENCE', '# EXPERIENCE', '# EMPLOYMENT HISTORY',
                '## PROFESSIONAL EXPERIENCE', '## WORK EXPERIENCE', '## EXPERIENCE', '## EMPLOYMENT HISTORY'
            ],
            'name': 'Experience Section'
        }
    ]
    
    content_upper = cv_content.upper()
    
    # Debug: log what sections we're checking against
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"CV Content (first 500 chars): {cv_content[:500]}")
    
    for section_group in required_sections:
        found = False
        matched_section = None
        
        # First try exact matches
        for alternative in section_group['alternatives']:
            if alternative.upper() in content_upper:
                sections_found += 1
                found = True
                matched_section = alternative
                break
        
        # If not found, try partial matches for more flexibility
        if not found:
            section_keywords = {
                'Summary Section': ['SUMMARY', 'EXECUTIVE', 'PROFESSIONAL', 'CAREER'],
                'Skills Section': ['SKILLS', 'TECHNICAL', 'COMPETENCIES', 'CORE'],
                'Experience Section': ['EXPERIENCE', 'EMPLOYMENT', 'WORK', 'PROFESSIONAL']
            }
            
            keywords = section_keywords.get(section_group['name'], [])
            for keyword in keywords:
                if keyword in content_upper:
                    sections_found += 1
                    found = True
                    matched_section = f"(partial match: {keyword})"
                    break
        
        if found:
            logger.info(f"Found {section_group['name']}: '{matched_section}'")
        else:
            logger.warning(f"Missing {section_group['name']} - checked {len(section_group['alternatives'])} alternatives")
            # For now, let's not block PDF generation on missing sections
            # issues.append(f"Missing section: {section_group['name']}")
    
    # Check for contact information
    if '📧' not in cv_content and '@' not in cv_content:
        issues.append("No email contact information found")
    
    # Check for meaningful content (not just headers)
    content_lines = [line.strip() for line in cv_content.split('\n') if line.strip()]
    non_header_lines = [line for line in content_lines if not line.startswith('**') and not line == '---']
    
    if len(non_header_lines) < 5:
        issues.append("Insufficient content lines (need at least 5 non-header lines)")
    
    # Check for bullet points or structured content
    has_bullets = any('•' in line for line in content_lines)
    has_structured_content = any(':' in line for line in content_lines)
    
    if not has_bullets and not has_structured_content:
        issues.append("No structured content (bullets or formatted text) found")
    
    return {
        'valid': len(issues) == 0 and sections_found >= 2,
        'message': '; '.join(issues) if issues else 'CV structure validation passed',
        'issues': issues,
        'sections_found': sections_found
    }

def convert_session_to_cvdata() -> CVData:
    """Convert session state data to structured CVData format"""
    from datetime import datetime
    import json
    
    # Get contact information
    contact_data = st.session_state.get('whole_cv_contact', {})
    contact = ContactInfo(
        name=contact_data.get('name', ''),
        email=contact_data.get('email', ''),
        phone=contact_data.get('phone', ''),
        location=contact_data.get('location', ''),
        linkedin=contact_data.get('linkedin'),
        website=contact_data.get('website')
    )
    
    # Get individual sections
    individual_sections = st.session_state.get('individual_generations', {})
    llm_json_responses = st.session_state.get('llm_json_responses', {})
    
    # Extract professional summary
    professional_summary = individual_sections.get('executive_summary', '')
    if professional_summary:
        # Clean summary and limit to 40 words
        words = professional_summary.split()
        if len(words) > 40:
            professional_summary = ' '.join(words[:40])
    
    # Extract skills from top_skills section
    skills = []
    top_skills = individual_sections.get('top_skills', '')
    if top_skills:
        skills = extract_skills_list(top_skills)
    if len(skills) > 10:
        skills = skills[:10]  # Limit to max 10 skills
    
    # Extract current role from experience_bullets JSON data
    current_role = None
    experience_json = llm_json_responses.get('experience_bullets')
    
    if experience_json:
        try:
            # Get structured data from the new format
            role_data = experience_json.get('role_data', {})
            optimized_bullets = experience_json.get('optimized_bullets', [])
            
            # Create bullets from optimized JSON data  
            bullets = []
            for bullet_text in optimized_bullets[:8]:  # Max 8 bullets
                if '|' in bullet_text:
                    # Handle SAR format: **Heading** | Content
                    parts = bullet_text.split('|', 1)
                    heading = parts[0].strip().replace('**', '').replace('•', '').strip()
                    content = parts[1].strip() if len(parts) > 1 else bullet_text
                    # Take first two words as heading
                    heading_words = heading.split()[:2]
                    heading = ' '.join(heading_words)
                    bullets.append(ExperienceBullet(heading=heading, content=content))
                elif ':' in bullet_text:
                    # Handle colon format: **Heading**: Content
                    heading = bullet_text.split(':', 1)[0].strip().replace('**', '').replace('•', '').strip()
                    content = bullet_text.split(':', 1)[1].strip()
                    # Take first two words as heading
                    heading_words = heading.split()[:2]
                    heading = ' '.join(heading_words)
                    bullets.append(ExperienceBullet(heading=heading, content=content))
                else:
                    # Use first two words as heading
                    clean_text = bullet_text.replace('•', '').replace('**', '').strip()
                    words = clean_text.split()
                    if len(words) >= 2:
                        heading = ' '.join(words[:2])
                        content = ' '.join(words[2:]) if len(words) > 2 else bullet_text
                        bullets.append(ExperienceBullet(heading=heading, content=content))
                    else:
                        bullets.append(ExperienceBullet(heading="Action", content=bullet_text))
            
            current_role = RoleExperience(
                job_title=role_data.get('position_name', 'Current Position'),
                company=role_data.get('company_name', 'Company'),
                location=role_data.get('location', 'Location'),
                start_date=role_data.get('start_date', 'Present'),
                end_date=role_data.get('end_date', 'Present'),
                bullets=bullets
            )
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning(f"Could not parse experience_bullets JSON: {e}")
            # Fallback: create basic current role from text
            experience_text = individual_sections.get('experience_bullets', '')
            bullets = []
            if experience_text:
                lines = [line.strip() for line in experience_text.split('\n') if line.strip() and ('•' in line or ':' in line)]
                for line in lines[:8]:
                    clean_line = line.replace('•', '').strip()
                    if ':' in clean_line:
                        heading = clean_line.split(':', 1)[0].strip().replace('**', '')
                        content = clean_line.split(':', 1)[1].strip()
                        heading_words = heading.split()[:2]
                        heading = ' '.join(heading_words)
                        bullets.append(ExperienceBullet(heading=heading, content=content))
            
            current_role = RoleExperience(
                job_title='Current Position',
                company='Company',
                location='Location',
                start_date='Present',
                end_date='Present',
                bullets=bullets
            )
    
    if not current_role:
        # Create empty current role if none exists
        current_role = RoleExperience(
            job_title='Position Title',
            company='Company Name',
            location='City, Country',
            start_date='MMM YYYY',
            end_date='Present',
            bullets=[]
        )
    
    # Extract previous roles from previous_experience JSON data
    previous_roles = []
    previous_experience_json = llm_json_responses.get('previous_experience')
    
    if previous_experience_json:
        try:
            # Get structured data from previous roles JSON format
            previous_roles_data = previous_experience_json.get('previous_roles_data', [])
            
            for role_data in previous_roles_data:
                optimized_bullets = role_data.get('optimized_bullets', role_data.get('key_bullets', []))
                
                # Create bullets from optimized JSON data  
                bullets = []
                for bullet_text in optimized_bullets[:6]:  # Max 6 bullets for previous roles
                    if '|' in bullet_text:
                        # Handle SAR format: **Heading** | Content
                        parts = bullet_text.split('|', 1)
                        heading = parts[0].strip().replace('**', '').replace('•', '').strip()
                        content = parts[1].strip() if len(parts) > 1 else bullet_text
                        # Take first two words as heading
                        heading_words = heading.split()[:2]
                        heading = ' '.join(heading_words)
                        bullets.append(ExperienceBullet(heading=heading, content=content))
                    elif ':' in bullet_text:
                        # Handle colon format: **Heading**: Content
                        heading = bullet_text.split(':', 1)[0].strip().replace('**', '').replace('•', '').strip()
                        content = bullet_text.split(':', 1)[1].strip()
                        # Take first two words as heading
                        heading_words = heading.split()[:2]
                        heading = ' '.join(heading_words)
                        bullets.append(ExperienceBullet(heading=heading, content=content))
                    else:
                        # Use first two words as heading
                        clean_text = bullet_text.replace('•', '').replace('**', '').strip()
                        words = clean_text.split()
                        if len(words) >= 2:
                            heading = ' '.join(words[:2])
                            content = ' '.join(words[2:]) if len(words) > 2 else bullet_text
                            bullets.append(ExperienceBullet(heading=heading, content=content))
                        else:
                            bullets.append(ExperienceBullet(heading="Action", content=bullet_text))
                
                previous_role = RoleExperience(
                    job_title=role_data.get('position_name', 'Previous Position'),
                    company=role_data.get('company_name', 'Company'),
                    location=role_data.get('location', 'Location'),
                    start_date=role_data.get('start_date', 'YYYY'),
                    end_date=role_data.get('end_date', 'YYYY'),
                    bullets=bullets
                )
                previous_roles.append(previous_role)
                
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning(f"Could not parse previous_experience JSON: {e}")
            # Fallback: try to parse from text
            previous_experience_text = individual_sections.get('previous_experience', '')
            if previous_experience_text and '###' in previous_experience_text:
                # Try basic parsing of structured previous experience text
                pass  # Keep empty for now as text parsing is complex
    
    # Get additional info
    additional_info = individual_sections.get('additional_info', '')
    
    # Create CVData structure
    cv_data = CVData(
        contact=contact,
        professional_summary=professional_summary,
        skills=skills,
        current_role=current_role,
        previous_roles=previous_roles,
        additional_info=additional_info,
        generated_at=datetime.now().isoformat()
    )
    
    return cv_data

def show_cv_preview_structured():
    """Display CV preview using Jinja2 template engine"""
    
    # Check if we have sufficient data
    if not st.session_state.get('whole_cv_contact') or not st.session_state.get('individual_generations'):
        st.warning("⚠️ No CV content available for preview. Please generate individual sections first.")
        return
    
    try:
        # Option 1: Use structured CVData if available
        try:
            cv_data = convert_session_to_cvdata()
            formatted_cv = template_engine.render_cv_preview(cv_data)
            template_source = "CVData + Jinja2 Template"
        except Exception as cvdata_error:
            logger.warning(f"CVData conversion failed: {cvdata_error}, using session data directly")
            # Option 2: Fallback to session data rendering
            contact_info = st.session_state.get('whole_cv_contact', {})
            session_data = {
                'llm_json_responses': st.session_state.get('llm_json_responses', {}),
                'individual_generations': st.session_state.get('individual_generations', {})
            }
            formatted_cv = template_engine.render_cv_from_session_data(session_data, contact_info)
            template_source = "Session Data + Jinja2 Template"
        
        with st.expander("👁️ Complete CV Preview (Template Engine) - Click to expand", expanded=True):
            st.markdown("### 📄 Generated CV Preview")
            st.markdown(f"*Professional CV rendered using {template_source}*")
            st.markdown("---")
            
            # Display the template-rendered CV
            st.markdown(formatted_cv)
            
            st.markdown("---")
            st.caption("🎯 Professional CV preview using Jinja2 templating engine")
            
            # Add structured data view toggle
            with st.expander("🔍 View Structured Data (JSON)", expanded=False):
                try:
                    cv_data = convert_session_to_cvdata()
                    st.json(cv_data.to_dict())
                except:
                    st.json({
                        'contact': st.session_state.get('whole_cv_contact', {}),
                        'llm_responses': st.session_state.get('llm_json_responses', {}),
                        'individual_generations': st.session_state.get('individual_generations', {})
                    })
            
            # Add template view toggle for developers
            with st.expander("🔧 Template Engine Debug", expanded=False):
                st.text(f"Template Source: {template_source}")
                st.text("Available Templates:")
                st.code("templates/cv_preview.md", language="text")
                
    except Exception as e:
        logger.error(f"Error in templated CV preview: {e}")
        st.error(f"❌ Error generating templated preview: {str(e)}")
        # Fallback to simple error message instead of broken old system
        st.error("❌ Unable to generate CV preview. Please ensure all sections are generated first.")

def generate_cv_html_for_new_tab():
    """Generate CV HTML content and create downloadable link for new tab viewing"""
    import base64
    import uuid
    
    try:
        # Check if we have sufficient data
        if not st.session_state.get('whole_cv_contact') or not st.session_state.get('individual_generations'):
            st.error("❌ No CV content available. Please generate individual sections first.")
            return
        
        # Convert to structured format and generate CV markdown
        cv_data = convert_session_to_cvdata()
        markdown_content = template_engine.render_cv_preview(cv_data)
        
        # Convert markdown to HTML with the same styling as our HTML-to-PDF converter
        import markdown
        html_body = markdown.markdown(
            markdown_content, 
            extensions=['tables', 'fenced_code', 'nl2br']
        )
        
        # Create complete HTML document with professional styling
        full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CV Preview - {cv_data.contact.name}</title>
    <style>
        {html_to_pdf_converter.css_styles}
        
        /* Additional styles for web viewing */
        body {{
            max-width: 8.5in;
            margin: 20px auto;
            padding: 40px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            background: white;
        }}
        
        @media print {{
            body {{
                box-shadow: none;
                margin: 0;
                padding: 0.5in;
            }}
        }}
    </style>
</head>
<body>
    <div class="cv-container">
        {html_body}
    </div>
    
    <script>
        // Add print functionality
        document.addEventListener('keydown', function(e) {{
            if (e.ctrlKey && e.key === 'p') {{
                window.print();
                e.preventDefault();
            }}
        }});
    </script>
</body>
</html>
"""
        
        # Create a unique filename
        timestamp = uuid.uuid4().hex[:8]
        filename = f"cv_preview_{cv_data.contact.name.replace(' ', '_')}_{timestamp}.html"
        
        # Convert to base64 for download
        html_bytes = full_html.encode('utf-8')
        b64_html = base64.b64encode(html_bytes).decode()
        
        # Create download link that opens in new tab
        download_link = f'<a href="data:text/html;base64,{b64_html}" download="{filename}" target="_blank">📄 Download & Open CV Preview</a>'
        
        st.success("✅ CV HTML preview generated successfully!")
        st.markdown(
            f"🔗 **Preview Options:**\n\n"
            f"1. {download_link} (Downloads HTML file and opens in new tab)\n"
            f"2. Right-click the link above and select 'Open in new tab'\n"
            f"3. Use Ctrl+P in the new tab to print",
            unsafe_allow_html=True
        )
        
        # Also provide a preview of the content length
        word_count = len(markdown_content.split())
        st.info(f"📊 Generated HTML preview: {word_count} words, {len(full_html)} characters")
        
    except Exception as e:
        logger.error(f"HTML generation for new tab error: {e}")
        st.error(f"❌ Error generating HTML preview: {str(e)}")

def generate_cv_pdf_structured():
    """Generate CV PDF using HTML-to-PDF converter to match CV preview exactly"""
    try:
        # Check if we have sufficient data
        if not st.session_state.get('whole_cv_contact') or not st.session_state.get('individual_generations'):
            st.error("❌ No CV content available. Please generate individual sections first.")
            return None
        
        # Convert to structured format
        cv_data = convert_session_to_cvdata()
        
        # Validate the structured data
        if not cv_data.contact.name or not cv_data.contact.email:
            st.error("❌ Missing essential contact information (name/email). Please check your contact details.")
            return None
        
        # Generate CV preview markdown content (same as what user sees)
        markdown_content = template_engine.render_cv_preview(cv_data)
        
        # Validate that we have actual content
        if not markdown_content or len(markdown_content.strip()) < 100:
            st.error("❌ CV preview content is empty or too short. Please regenerate sections.")
            return None
        
        # Convert markdown preview to PDF using HTML-to-PDF converter
        # This ensures the PDF matches exactly what the user sees in preview
        pdf_data = html_to_pdf_converter.convert_markdown_to_pdf(markdown_content)
        
        # Validate PDF data
        if not pdf_data or len(pdf_data) < 1000:
            raise Exception("Generated PDF is empty or too small")
        
        logger.info(f"✅ Successfully generated CV PDF using HTML-to-PDF converter ({len(pdf_data)} bytes)")
        return pdf_data
            
    except Exception as e:
        logger.error(f"HTML-to-PDF generation error: {e}")
        st.error(f"❌ Error generating PDF from CV preview: {str(e)}")
        
        # Fallback to original broken method as last resort
        st.warning("⚠️ Attempting fallback PDF generation method...")
        return generate_cv_pdf()

if __name__ == "__main__":
    main()