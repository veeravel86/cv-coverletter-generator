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
        
        for doc_type, file in uploaded_files.items():
            if file is not None:
                with st.spinner(f"Processing {doc_type}..."):
                    text = self.extract_text_from_pdf(file)
                    texts[doc_type] = text
                    st.success(f"✅ {doc_type} processed ({len(text)} characters)")
        
        if not texts:
            raise ValueError("No valid PDFs were processed")
        
        with st.spinner("Creating vector embeddings..."):
            documents = self.create_documents(texts)
            vector_store = self.create_vector_store(documents)
            st.success(f"✅ Vector store created with {len(documents)} chunks")
        
        return {
            "texts": texts,
            "documents": documents,
            "vector_store": vector_store,
            "doc_count": len([t for t in texts.values() if t])
        }
    
    def get_document_summary(self, texts: Dict[str, str]) -> Dict[str, int]:
        summary = {}
        for doc_type, text in texts.items():
            summary[doc_type] = len(text.split()) if text else 0
        return summary

@st.cache_resource
def get_pdf_ingestor():
    return PDFIngestor()