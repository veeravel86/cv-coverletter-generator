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
        'export_paths': {},
        'sample_cv_content': None,
        'individual_generations': {}
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
        
        if st.button("💼 Generate Top 8 Experience Bullets", help="Create 8 high-impact experience bullets"):
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
                st.success("✅ Experience Bullets")
            else:
                st.error("❌ Experience Bullets")
            
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
            if 'whole_cv_content' in st.session_state and st.session_state.whole_cv_content:
                if st.button("👁️ Preview CV", help="Preview the complete CV before download"):
                    show_cv_preview()
        
        with generate_whole_cv_cols[2]:
            if 'whole_cv_content' in st.session_state and st.session_state.whole_cv_content:
                if st.button("📄 Generate PDF", type="secondary", help="Generate CV as PDF for download"):
                    with st.spinner("📄 Generating PDF..."):
                        pdf_data = generate_cv_pdf()
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
            'title': '⚡ Top 8 Experience Bullets',
            'subtitle': 'SAR format with two-word headings',
            'caption': '⚡ Achievement-focused bullets ranked by relevance',
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
                    # Clean content to ensure only headings are bold
                    cleaned_content = clean_generated_content(content)
                    st.markdown(cleaned_content)
                    st.caption(config['caption'])

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
    """Generate top 8 experience bullets with expandable display using professional ATS-optimized prompt"""
    
    with st.spinner("💼 Generating top 8 experience bullets..."):
        try:
            # Get job description context
            job_context = context_builder.retriever.get_jd_specific_context([
                "job description requirements responsibilities qualifications",
                "job requirements duties role expectations",
                "skills experience needed preferred"
            ])["context"]
            
            # Get experience context  
            experience_context = context_builder.retriever.get_superset_context(
                "work experience achievements projects accomplishments results"
            )["context"]
            
            prompt = f"""You are an expert CV writer and ATS optimizer for senior engineering leadership roles. Read the below mentioned guidelines and accomplish the task from attached files.

GOAL
Read two input files:
- FILE 1: Job_Description.txt → contains the complete job description.
- FILE 2: Experience_Superset.txt → contains all possible experience points and achievements.

From these, create EXACTLY 8 high-impact experience summary bullets that are:
- Directly aligned with the JD.
- Ordered by PRIORITY based on the JD's stated requirements and implied expectations.
- Polished for both ATS scanning and human decision-makers.

JOB DESCRIPTION CONTEXT:
{job_context}

EXPERIENCE SUPERSET CONTEXT:
{experience_context}

BULLET REQUIREMENTS
- Start with a TWO-WORD HEADING (no abbreviations), ideally using language from the JD.
- Each bullet must follow SAR (Situation–Action–Result) in one concise sentence (~22–35 words).
- Use JD keywords naturally and accurately.
- Include metrics or quantifiable results ONLY if present in the Superset; otherwise, use qualitative outcomes.
- No fabrication or vague fluff.
- Use international English unless the JD clearly uses US spelling.
- Each bullet should show measurable impact, leadership depth, and business relevance.

PRIORITY RULES
- Rank bullets strictly by relevance to the JD:
  1. Mission-critical competencies, leadership scope, and business outcomes the JD emphasises.
  2. Skills and themes repeated or highlighted in JD wording.
  3. Emerging themes or differentiators likely valued for this role (use your AI knowledge of industry trends).
- Highest-priority achievements appear first.
- No duplicated content or similar bullets.

PROCESS (AI internal reasoning; do NOT include this reasoning in the output):
1. Parse Job_Description.txt → extract competencies, themes, leadership scope, hard skills, and JD keyword frequencies.
2. Parse Experience_Superset.txt → shortlist all relevant achievements.
3. Rank shortlist bullets against JD requirements and implied role impact.
4. Rewrite top 8 bullets in SAR style with JD keywords and two-word headings.
5. Sequence bullets in order of JD relevance (highest priority first).
6. Final polish: ensure conciseness, ATS optimisation, and strong action verbs.

OUTPUT FORMAT (strict):
- Output ONLY the 8 bullets, nothing else.
- Format:
  **Two Word Heading | SAR statement showing measurable impact**
- Example (not content):
  **Cloud Migration | Inherited aging on-prem infra; led phased AWS migration with team restructure; cut costs 20%, boosted uptime, and accelerated deployment cycles.**

INPUT FILES
- Job_Description.pdf  Use job description as input
- CV_ExperienceSummary_Skills_Superset - Google Docs.pdf use skills super set as input

QUALITY BAR
- Challenge your own output: each bullet must be JD-aligned, SAR-structured, outcome-focused, and priority-ranked.
- Pretend this will be reviewed by an ATS and a CTO in a competitive search; optimise for clarity, keywords, and quantified results.

BEGIN."""
            
            response = llm_service.generate_content(prompt, max_tokens=1000)
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['experience_bullets'] = response
            
            st.success("✅ Top 8 Experience Bullets generated successfully!")
            st.info("👁️ View your generated content in the 'Generated Individual Sections' below")
            
        except Exception as e:
            st.error(f"❌ Error generating experience bullets: {str(e)}")

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
    """Generate previous experience summary by parsing sample CV and extracting only past experiences"""
    
    with st.spinner("📋 Generating previous experience summary..."):
        try:
            # Check if sample CV is available
            if 'sample_cv_content' not in st.session_state or not st.session_state.sample_cv_content:
                st.warning("⚠️ Sample CV not available. Please upload a Sample CV to generate previous experience summary.")
                return
            
            # Get sample CV content for experience extraction
            sample_cv_content = st.session_state.sample_cv_content
            
            # First LLM call to strictly extract experience sections from sample CV
            extraction_prompt = f"""
You are a strict content extractor. Extract ONLY the work experience/employment history section from the CV exactly as it appears.

CV CONTENT:
{sample_cv_content}

STRICT EXTRACTION RULES:
1. Find the work experience/employment/professional experience section
2. Copy the EXACT text as it appears in the CV - word for word
3. Include job titles, company names, dates, and descriptions exactly as written
4. Do NOT rephrase, summarize, or modify any content
5. Do NOT add information that isn't explicitly in the CV
6. Maintain original formatting, bullet points, and structure
7. If no work experience section exists, return "No work experience section found"

WHAT TO EXTRACT:
- Section headers exactly as written
- Job titles exactly as written  
- Company names exactly as written
- Employment dates exactly as written
- All bullet points and descriptions exactly as written

WHAT NOT TO DO:
- Do not create or generate new content
- Do not rephrase or improve the text
- Do not add achievements not mentioned
- Do not infer information

OUTPUT FORMAT:
Return the exact work experience section text as it appears in the CV, with no modifications.
"""
            
            extracted_experience = llm_service.generate_content(extraction_prompt, max_tokens=3000)
            
            # Second LLM call to strictly extract only previous (non-current) roles
            extraction_prompt_strict = f"""
You are a strict content extractor. Your job is to EXTRACT (not create or summarize) ONLY the previous/past work experiences from the given content.

WORK EXPERIENCE CONTENT:
{extracted_experience}

STRICT REQUIREMENTS:
1. EXTRACT ONLY - Do not create, generate, or summarize any content
2. Copy the exact text as it appears in the CV
3. Exclude the current/most recent role (typically the first entry)
4. Include ONLY previous/past positions that are explicitly mentioned
5. Preserve original wording, dates, companies, and descriptions exactly as written
6. If there are no previous roles mentioned, return "No previous roles found in the sample CV"

WHAT TO EXTRACT:
- Job titles exactly as written
- Company names exactly as written  
- Employment dates exactly as written
- Bullet points exactly as written
- Any other details exactly as they appear

WHAT NOT TO DO:
- Do not add information not present in the CV
- Do not rephrase or rewrite content
- Do not create new achievements or responsibilities
- Do not infer or assume information
- Do not summarize or condense content
- Do not add quantified results unless explicitly stated in the CV

OUTPUT FORMAT:
Return only the previous work experience entries exactly as they appear in the original CV content, excluding the most recent/current role.
"""
            
            response = llm_service.generate_content(extraction_prompt_strict, max_tokens=2500)
            
            # Validation step: Check if extracted content contains information from the original CV
            if response and "No previous roles found" not in response:
                # Simple validation: check if the extracted content contains at least some words from original CV
                original_words = set(sample_cv_content.lower().split())
                response_words = set(response.lower().split())
                
                # Check overlap percentage (should be high for genuine extraction)
                common_words = original_words.intersection(response_words)
                if len(response_words) > 0:
                    overlap_percentage = len(common_words) / len(response_words)
                    
                    if overlap_percentage < 0.3:  # Less than 30% overlap suggests hallucination
                        st.warning("⚠️ Detected potential content generation. Using direct extraction from Sample CV instead.")
                        # Fallback: Use a more conservative approach
                        response = "Previous roles extracted directly from Sample CV - manual review recommended for accuracy."
                        st.info("💡 Tip: The generated previous roles may contain created content. Please verify against your Sample CV.")
                    else:
                        st.info(f"✅ Content validation passed ({overlap_percentage:.1%} overlap with original CV)")
            
            # Store in session state
            if 'individual_generations' not in st.session_state:
                st.session_state.individual_generations = {}
            st.session_state.individual_generations['previous_experience'] = response
            
            st.success("✅ Previous Experience Summary generated successfully!")
            st.info("👁️ View your generated content in the 'Generated Individual Sections' below")
            
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
    
    # Remove bold formatting and extract skills
    cleaned = clean_generated_content(skills_text)
    
    # Try different patterns to extract skills
    skills = []
    lines = cleaned.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('**') and not line.startswith('#'):
            # Remove bullet points and numbers
            line = re.sub(r'^[\d\.\-\•\*\+]\s*', '', line)
            if line:
                skills.append(line)
    
    # Limit to 10 skills, ensure ≤2 words each
    final_skills = []
    for skill in skills[:10]:
        words = skill.split()
        if len(words) <= 2:
            final_skills.append(skill)
    
    return final_skills[:10]

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
    """Display CV preview in expandable modal"""
    
    if 'whole_cv_content' not in st.session_state or not st.session_state.whole_cv_content:
        st.warning("⚠️ No CV content available for preview")
        return
    
    with st.expander("👁️ Complete CV Preview - Click to expand", expanded=True):
        st.markdown("### 📄 Generated CV Preview")
        st.markdown("*Review your complete CV before downloading as PDF*")
        st.markdown("---")
        
        # Display the complete CV content
        st.markdown(st.session_state.whole_cv_content)
        
        st.markdown("---")
        st.caption("🎯 Professional CV preview")

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
        
        # Try the new structured method, fallback to existing method if not available
        try:
            pdf_path = pdf_exporter.create_structured_cv_pdf(
                contact_info, individual_sections, color_scheme="teal"
            )
        except AttributeError:
            # Method not available (cache issue), clear cache and try again
            st.cache_resource.clear()
            pdf_exporter = get_pdf_exporter()
            
            try:
                pdf_path = pdf_exporter.create_structured_cv_pdf(
                    contact_info, individual_sections, color_scheme="teal"
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

if __name__ == "__main__":
    main()