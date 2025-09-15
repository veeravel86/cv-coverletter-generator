import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import streamlit as st
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from openai import OpenAI

logger = logging.getLogger(__name__)

class PDFIngestor:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        self.vector_store: Optional[FAISS] = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def _get_compatible_temperature(self, model: str, desired_temperature: float) -> float:
        """Get temperature value compatible with the model"""
        # GPT-5 only supports default temperature (1.0)
        if model == "gpt-5":
            return 1.0
        return desired_temperature
    
    def _get_model_compatible_params(self, model: str, max_tokens: int) -> Dict[str, Any]:
        """Get model-compatible parameters for OpenAI API calls"""
        # GPT-5 and newer models use max_completion_tokens
        if model in ["gpt-5"]:
            return {"max_completion_tokens": max_tokens}
        else:
            return {"max_tokens": max_tokens}
        
    def extract_text_from_pdf(self, pdf_file) -> str:
        try:
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""
    
    def clean_text(self, text: str) -> str:
        text = text.replace('\x00', '')
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.isspace():
                cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)
    
    def extract_job_description_content(self, raw_text: str) -> str:
        """Use LLM to extract only job description content from potentially noisy PDF text"""
        try:
            prompt = """
CRITICAL TASK: You are a specialized text extraction expert. You must extract ONLY the pure job description content from a PDF that contains a LinkedIn page export with lots of noise.

EXTRACT ONLY these job description elements:
- Job title and company name
- Job location (city, state, remote/hybrid options)
- Employment type (full-time, part-time, contract)
- Job responsibilities and key duties
- Required qualifications and skills
- Preferred qualifications and skills
- Experience requirements (years, specific experience)
- Education requirements
- Technical requirements and tools
- Company description and culture information
- Benefits and compensation (if mentioned)
- Application instructions

STRICTLY REMOVE all LinkedIn page noise including:
- LinkedIn interface elements (buttons, links, navigation)
- "Sign in", "Join now", "Apply", "Save job" buttons
- Social sharing buttons and links
- LinkedIn user interface text
- Navigation menus and breadcrumbs
- Advertisement content
- Page headers, footers, and metadata
- "Show more", "See less" text
- LinkedIn-specific formatting artifacts
- User profile suggestions
- Related job suggestions
- Page loading elements
- Cookie notices and privacy text
- "Connect with" or networking suggestions
- View counts, application numbers
- LinkedIn branding text

FORMATTING REQUIREMENTS:
- Return clean, readable job description text
- Use proper paragraph breaks
- Maintain bullet points for responsibilities and requirements
- Keep section headings (like "Requirements:", "Responsibilities:")
- Remove excessive whitespace and formatting artifacts

If no clear job description is found, return "NO JOB DESCRIPTION FOUND".

Raw LinkedIn export text to process:
"""

            model = "gpt-4o-mini"
            token_params = self._get_model_compatible_params(model, 4000)
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a specialized text extraction expert. Your job is to extract ONLY pure job description content from noisy LinkedIn page exports. Be extremely thorough in removing LinkedIn interface noise while preserving all job-relevant information."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=self._get_compatible_temperature(model, 0.0),  # Use 0.0 for more consistent extraction
                **token_params
            )
            
            extracted_content = response.choices[0].message.content.strip()
            
            if "NO JOB DESCRIPTION FOUND" in extracted_content:
                logger.warning("LLM could not find job description content in PDF text")
                return raw_text  # Fallback to original text
            
            return extracted_content
            
        except Exception as e:
            logger.error(f"Error extracting job description content with LLM: {e}")
            return raw_text  # Fallback to original text
    
    def structure_sample_cv_content(self, raw_text: str) -> str:
        """Use LLM to structure sample CV content with proper headings"""
        try:
            prompt = """
CRITICAL INSTRUCTIONS: You are a formatting assistant. Your ONLY job is to organize existing content under proper headings. 

STRICT RULES:
- DO NOT remove, delete, or omit ANY information from the original text
- DO NOT change the meaning or content of any sentences
- DO NOT summarize or paraphrase any content
- DO NOT add new information that wasn't in the original
- PRESERVE all dates, numbers, company names, achievements, and details exactly as written
- Your job is ONLY to organize and format, not to edit content

TASK: Take all the text provided and organize it under appropriate headings:
- CONTACT INFORMATION (name, email, phone, location, LinkedIn)
- PROFESSIONAL SUMMARY or CAREER SUMMARY
- SKILLS or TECHNICAL SKILLS 
- WORK EXPERIENCE or PROFESSIONAL EXPERIENCE
- EDUCATION
- CERTIFICATIONS (if present)
- PROJECTS (if present)
- ACHIEVEMENTS or AWARDS (if present)

FORMATTING:
- Use ALL CAPS for section headings
- Use • for bullet points
- Keep all original content exactly as provided
- Only remove obvious PDF artifacts (repeated characters, page numbers)
- If unsure where content belongs, create an "ADDITIONAL INFORMATION" section

VERIFICATION: After formatting, ensure every piece of information from the original text is included somewhere in your output.

Raw CV text to process:
"""

            model = "gpt-4o-mini"
            token_params = self._get_model_compatible_params(model, 4000)
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a formatting assistant. Your only job is to organize content under headings without changing, removing, or modifying any information. Preserve all content exactly as provided."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=self._get_compatible_temperature(model, 0.0),  # Reduced for more consistent formatting
                **token_params
            )
            
            structured_content = response.choices[0].message.content.strip()
            
            if "NO CV CONTENT FOUND" in structured_content:
                logger.warning("LLM could not structure CV content")
                return raw_text  # Fallback to original text
            
            return structured_content
            
        except Exception as e:
            logger.error(f"Error structuring CV content with LLM: {e}")
            return raw_text  # Fallback to original text
    
    def structure_experience_superset_content(self, raw_text: str) -> str:
        """Use LLM to structure experience superset content with proper headings"""
        try:
            prompt = """
CRITICAL INSTRUCTIONS: You are a formatting assistant. Your ONLY job is to organize existing content under proper headings while PRESERVING ALL existing headings and content EXACTLY as written.

ABSOLUTE REQUIREMENTS - NO EXCEPTIONS:
- DO NOT remove, delete, or omit ANY information from the original text
- DO NOT change the meaning or content of any sentences  
- DO NOT summarize, paraphrase, or rewrite any content
- DO NOT add new information that wasn't in the original
- PRESERVE ALL existing headings exactly as they appear in the original
- PRESERVE all dates, numbers, company names, project names, achievements, and details EXACTLY as written
- PRESERVE all quantified achievements (percentages, numbers, metrics) exactly as stated
- If there are existing headings in the document, KEEP them exactly as they are
- Your job is ONLY to organize and format, not to edit or improve content
- If there are multiple similar entries, keep ALL of them - do not consolidate or merge

TASK: Take ALL the text provided and organize it. Focus ONLY on experience-related content:
- If the document already has headings, preserve them exactly
- If content needs organization, use these headings ONLY if no existing headings are present:
  - WORK EXPERIENCE  
  - PROFESSIONAL EXPERIENCE
  - KEY PROJECTS
  - PROJECT EXPERIENCE

DO NOT CREATE sections for:
- Awards, recognition, achievements (unless specifically about work experience)
- Education or certifications 
- Skills or technical competencies
- Personal information

FORMATTING GUIDELINES:
- Keep ALL original headings exactly as they appear
- Use ALL CAPS only if original headings were in ALL CAPS
- Use • for bullet points only if not already formatted
- Keep all original content exactly as provided
- Only remove obvious PDF artifacts (repeated characters, page numbers, footers)
- Maintain original date formats exactly as written
- Preserve original formatting structure as much as possible

MANDATORY VERIFICATION: After formatting, verify that EVERY single piece of experience information, project detail, achievement, date, and detail from the original text appears exactly as it was written. Nothing should be missing or changed.

Raw experience text to process:
"""

            model = "gpt-4o-mini"
            token_params = self._get_model_compatible_params(model, 4000)
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a formatting assistant. Your ONLY job is to organize content while preserving ALL existing headings and content EXACTLY as written. Do not change, remove, or modify any content - only organize it while maintaining original structure and headings."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=self._get_compatible_temperature(model, 0.0),  # Set to 0 for maximum consistency
                **token_params
            )
            
            structured_content = response.choices[0].message.content.strip()
            
            if "NO EXPERIENCE CONTENT FOUND" in structured_content:
                logger.warning("LLM could not structure experience content")
                return raw_text  # Fallback to original text
            
            return structured_content
            
        except Exception as e:
            logger.error(f"Error structuring experience content with LLM: {e}")
            return raw_text  # Fallback to original text
    
    def structure_skills_superset_content(self, raw_text: str) -> str:
        """Use LLM to structure skills superset content with proper headings"""
        try:
            prompt = """
CRITICAL INSTRUCTIONS: You are a formatting assistant. Your ONLY job is to organize existing content under proper headings.

STRICT RULES - ABSOLUTE REQUIREMENTS:
- DO NOT remove, delete, or omit ANY information from the original text
- DO NOT change the meaning or content of any sentences
- DO NOT summarize, paraphrase, or rewrite any content
- DO NOT add new information that wasn't in the original
- PRESERVE all skill names, technologies, proficiency levels, and details EXACTLY as written
- Your job is ONLY to organize and format, not to edit or improve content
- If there are multiple similar entries, keep ALL of them - do not consolidate or merge

TASK: Take ALL the text provided and organize it under appropriate headings:
- PROGRAMMING LANGUAGES
- FRAMEWORKS AND LIBRARIES
- DATABASES
- CLOUD PLATFORMS
- TOOLS AND TECHNOLOGIES
- SOFT SKILLS
- CERTIFICATIONS (if present)
- ADDITIONAL SKILLS (for content that doesn't fit other categories)

FORMATTING GUIDELINES:
- Use ALL CAPS for section headings
- Use • for bullet points
- Keep all original content exactly as provided
- Only remove obvious PDF artifacts (repeated characters, page numbers, footers)
- If you're unsure where something belongs, put it in "ADDITIONAL SKILLS"
- Group similar skills together but preserve all individual entries

MANDATORY VERIFICATION: After formatting, verify that EVERY single skill, technology, tool, and detail from the original text appears somewhere in your organized output. Nothing should be missing.

Raw skills text to process:
"""

            model = "gpt-4o-mini"
            token_params = self._get_model_compatible_params(model, 4000)
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a formatting assistant. Your ONLY job is to organize content under headings. You must preserve ALL information exactly as provided. Do not change, remove, or modify any content - only organize it under appropriate headings."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=self._get_compatible_temperature(model, 0.0),  # Set to 0 for maximum consistency
                **token_params
            )
            
            structured_content = response.choices[0].message.content.strip()
            
            if "NO SKILLS CONTENT FOUND" in structured_content:
                logger.warning("LLM could not structure skills content")
                return raw_text  # Fallback to original text
            
            return structured_content
            
        except Exception as e:
            logger.error(f"Error structuring skills content with LLM: {e}")
            return raw_text  # Fallback to original text
    
    def structure_experience_content(self, raw_text: str) -> str:
        """Use LLM to structure experience document content with proper headings"""
        try:
            prompt = """
CRITICAL INSTRUCTIONS: You are a formatting assistant. Your ONLY job is to organize existing work experience content under proper headings.

STRICT RULES:
- DO NOT remove, delete, or omit ANY information from the original text
- DO NOT change the meaning or content of any sentences
- DO NOT summarize or paraphrase any content
- DO NOT add new information that wasn't in the original
- PRESERVE all dates, numbers, company names, achievements, and details exactly as written
- Your job is ONLY to organize and format, not to edit content

TASK: Take all the text provided and organize it under appropriate headings for work experience:
- WORK EXPERIENCE or PROFESSIONAL EXPERIENCE
- PROJECT EXPERIENCE (if applicable)
- INTERNSHIPS (if applicable)
- CONSULTING EXPERIENCE (if applicable)

FORMATTING:
- Use ALL CAPS for section headings
- Use • for bullet points
- Keep all original content exactly as provided
- Only remove obvious PDF artifacts (repeated characters, page numbers)
- Focus only on work-related experience content

Raw experience text to process:
"""

            model = "gpt-4o-mini"
            token_params = self._get_model_compatible_params(model, 4000)
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a formatting assistant. Organize work experience content under headings without changing any information. Preserve all content exactly as provided."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=self._get_compatible_temperature(model, 0.0),
                **token_params
            )
            
            structured_content = response.choices[0].message.content.strip()
            return structured_content
            
        except Exception as e:
            logger.error(f"Error structuring experience content with LLM: {e}")
            return raw_text  # Fallback to original text
    
    def structure_skills_content(self, raw_text: str) -> str:
        """Use LLM to structure skills document content with proper headings"""
        try:
            prompt = """
CRITICAL INSTRUCTIONS: You are a formatting assistant. Your ONLY job is to organize existing skills content under proper headings.

STRICT RULES:
- DO NOT remove, delete, or omit ANY information from the original text
- DO NOT change the meaning or content of any sentences
- DO NOT summarize or paraphrase any content
- DO NOT add new information that wasn't in the original
- PRESERVE all skill names, technologies, and details exactly as written
- Your job is ONLY to organize and format, not to edit content

TASK: Take all the text provided and organize it under appropriate headings for skills:
- TECHNICAL SKILLS
- PROGRAMMING LANGUAGES
- FRAMEWORKS & LIBRARIES
- TOOLS & TECHNOLOGIES
- SOFT SKILLS
- CERTIFICATIONS (if applicable)
- LANGUAGES (if applicable)

FORMATTING:
- Use ALL CAPS for section headings
- Use • for bullet points or keep original formatting
- Keep all original content exactly as provided
- Only remove obvious PDF artifacts (repeated characters, page numbers)
- Focus only on skills-related content

Raw skills text to process:
"""

            model = "gpt-4o-mini"
            token_params = self._get_model_compatible_params(model, 4000)
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a formatting assistant. Organize skills content under headings without changing any information. Preserve all content exactly as provided."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=self._get_compatible_temperature(model, 0.0),
                **token_params
            )
            
            structured_content = response.choices[0].message.content.strip()
            return structured_content
            
        except Exception as e:
            logger.error(f"Error structuring skills content with LLM: {e}")
            return raw_text  # Fallback to original text
    
    def create_documents(self, texts: Dict[str, str]) -> List[Document]:
        documents = []
        for doc_type, text in texts.items():
            if text:
                cleaned_text = self.clean_text(text)
                chunks = self.text_splitter.split_text(cleaned_text)
                for i, chunk in enumerate(chunks):
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "source": doc_type,
                            "chunk_id": i,
                            "total_chunks": len(chunks)
                        }
                    )
                    documents.append(doc)
        return documents
    
    def create_vector_store(self, documents: List[Document]) -> FAISS:
        if not documents:
            raise ValueError("No documents provided for vector store creation")
        
        self.vector_store = FAISS.from_documents(documents, self.embeddings)
        return self.vector_store
    
    def ingest_pdfs(self, uploaded_files: Dict[str, Any]) -> Dict[str, Any]:
        texts = {}
        processed_texts = {}
        
        for doc_type, file in uploaded_files.items():
            if file is not None:
                with st.spinner(f"Processing {doc_type}..."):
                    raw_text = self.extract_text_from_pdf(file)
                    
                    # Use LLM to process and structure content based on document type
                    if doc_type == "job_description" and raw_text:
                        with st.spinner("🧹 Cleaning LinkedIn page noise from job description..."):
                            processed_text = self.extract_job_description_content(raw_text)
                            processed_texts[doc_type] = processed_text
                            # Show the cleaning effectiveness
                            original_length = len(raw_text)
                            cleaned_length = len(processed_text)
                            noise_removed = original_length - cleaned_length
                            st.success(f"✅ Job description cleaned: {noise_removed} characters of LinkedIn noise removed ({cleaned_length} clean characters retained)")
                    
                    elif doc_type == "sample_cv" and raw_text:
                        with st.spinner("🤖 Structuring sample CV content..."):
                            processed_text = self.structure_sample_cv_content(raw_text)
                            processed_texts[doc_type] = processed_text
                            st.success(f"✅ {doc_type} structured with proper headings ({len(processed_text)} characters)")
                    
                    elif doc_type == "experience_doc" and raw_text:
                        with st.spinner("🤖 Structuring experience document content..."):
                            processed_text = self.structure_experience_content(raw_text)
                            processed_texts[doc_type] = processed_text
                            st.success(f"✅ Experience document structured with proper headings ({len(processed_text)} characters)")
                    
                    elif doc_type == "skills_doc" and raw_text:
                        with st.spinner("🤖 Structuring skills document content..."):
                            processed_text = self.structure_skills_content(raw_text)
                            processed_texts[doc_type] = processed_text
                            st.success(f"✅ Skills document structured with proper headings ({len(processed_text)} characters)")
                    
                    else:
                        processed_texts[doc_type] = raw_text
                        st.success(f"✅ {doc_type} processed ({len(raw_text)} characters)")
                    
                    texts[doc_type] = raw_text  # Keep original for reference
        
        if not processed_texts:
            raise ValueError("No valid PDFs were processed")
        
        with st.spinner("Creating vector embeddings..."):
            documents = self.create_documents(processed_texts)
            vector_store = self.create_vector_store(documents)
            st.success(f"✅ Vector store created with {len(documents)} chunks")
        
        return {
            "texts": texts,  # Original extracted text
            "processed_texts": processed_texts,  # LLM-structured text  
            "documents": documents,
            "vector_store": vector_store,
            "doc_count": len([t for t in processed_texts.values() if t])
        }
    
    def get_document_summary(self, texts: Dict[str, str]) -> Dict[str, int]:
        summary = {}
        for doc_type, text in texts.items():
            summary[doc_type] = len(text.split()) if text else 0
        return summary

@st.cache_resource
def get_pdf_ingestor():
    return PDFIngestor()