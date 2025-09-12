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
You are given text extracted from a PDF that may contain a job description mixed with other content like LinkedIn page elements, navigation, ads, headers, footers, or unrelated text.

Please extract and return ONLY the core job description content, including:
- Job title and company name
- Job responsibilities and duties
- Required qualifications and skills
- Experience requirements
- Education requirements
- Any other job-specific requirements
- Company description (if relevant)

Remove all:
- LinkedIn interface elements
- Navigation menus
- Advertisements
- Page headers/footers
- Unrelated content
- Social media elements
- User interface text

Return only clean, relevant job description text. If no job description is found, return "NO JOB DESCRIPTION FOUND".

Raw text to process:
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a text extraction specialist. Extract only job description content from noisy PDF text."},
                    {"role": "user", "content": f"{prompt}\n\n{raw_text}"}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            extracted_content = response.choices[0].message.content.strip()
            
            if "NO JOB DESCRIPTION FOUND" in extracted_content:
                logger.warning("LLM could not find job description content in PDF text")
                return raw_text  # Fallback to original text
            
            return extracted_content
            
        except Exception as e:
            logger.error(f"Error extracting job description content with LLM: {e}")
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
                    
                    # For job description, use LLM to extract clean content
                    if doc_type == "job_description" and raw_text:
                        with st.spinner("🤖 Extracting job description content..."):
                            processed_text = self.extract_job_description_content(raw_text)
                            processed_texts[doc_type] = processed_text
                            st.success(f"✅ {doc_type} processed and cleaned ({len(processed_text)} characters)")
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
            "processed_texts": processed_texts,  # LLM-cleaned text  
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