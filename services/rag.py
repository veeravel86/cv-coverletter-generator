import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import streamlit as st
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

logger = logging.getLogger(__name__)

@dataclass
class RetrievalConfig:
    k: int = 10
    score_threshold: float = 0.7
    diversity_threshold: float = 0.8
    max_context_length: int = 8000

class RAGRetriever:
    def __init__(self, vector_store: FAISS, config: RetrievalConfig = None):
        self.vector_store = vector_store
        self.config = config or RetrievalConfig()
        
    def retrieve_context(self, query: str, doc_types: List[str] = None) -> Dict[str, Any]:
        try:
            results = self.vector_store.similarity_search_with_score(
                query, k=self.config.k
            )
            
            filtered_results = self._filter_by_doc_types(results, doc_types)
            
            relevant_docs = self._filter_by_relevance(filtered_results)
            
            diverse_docs = self._ensure_diversity(relevant_docs)
            
            context = self._build_context_string(diverse_docs)
            
            return {
                "context": context,
                "source_docs": diverse_docs,
                "total_retrieved": len(results),
                "after_filtering": len(relevant_docs),
                "final_count": len(diverse_docs),
                "doc_type_distribution": self._get_source_distribution(diverse_docs)
            }
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            return {
                "context": "",
                "source_docs": [],
                "total_retrieved": 0,
                "after_filtering": 0,
                "final_count": 0,
                "doc_type_distribution": {}
            }
    
    def _filter_by_doc_types(self, results: List[Tuple[Document, float]], 
                            doc_types: List[str] = None) -> List[Tuple[Document, float]]:
        if not doc_types:
            return results
        
        filtered = []
        for doc, score in results:
            source = doc.metadata.get("source", "")
            if any(doc_type.lower() in source.lower() for doc_type in doc_types):
                filtered.append((doc, score))
        
        return filtered
    
    def _filter_by_relevance(self, results: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
        if not results:
            return results
        
        max_score = max(score for _, score in results)
        threshold_score = max_score * self.config.score_threshold
        
        relevant = [(doc, score) for doc, score in results if score >= threshold_score]
        
        return relevant[:self.config.k]
    
    def _ensure_diversity(self, results: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
        if len(results) <= 1:
            return results
        
        diverse_docs = []
        used_content_hashes = set()
        
        for doc, score in results:
            content_hash = hash(doc.page_content[:100])
            
            if content_hash not in used_content_hashes:
                diverse_docs.append((doc, score))
                used_content_hashes.add(content_hash)
        
        return diverse_docs
    
    def _build_context_string(self, docs_with_scores: List[Tuple[Document, float]]) -> str:
        context_parts = []
        current_length = 0
        
        for doc, score in docs_with_scores:
            source = doc.metadata.get("source", "unknown")
            chunk_info = f"(Source: {source})"
            
            doc_text = f"{chunk_info}\n{doc.page_content}\n"
            
            if current_length + len(doc_text) > self.config.max_context_length:
                if current_length == 0:
                    truncated = doc_text[:self.config.max_context_length - 100] + "...[truncated]"
                    context_parts.append(truncated)
                break
            
            context_parts.append(doc_text)
            current_length += len(doc_text)
        
        return "\n---\n".join(context_parts)
    
    def _get_source_distribution(self, docs_with_scores: List[Tuple[Document, float]]) -> Dict[str, int]:
        distribution = {}
        for doc, _ in docs_with_scores:
            source = doc.metadata.get("source", "unknown")
            distribution[source] = distribution.get(source, 0) + 1
        return distribution
    
    def get_targeted_context(self, section_type: str, specific_query: str = None) -> Dict[str, Any]:
        section_queries = {
            "career_summary": [
                "professional summary career objective",
                "years experience achievements accomplishments",
                "leadership management skills expertise"
            ],
            "experience": [
                "work experience employment history",
                "job responsibilities achievements results",
                "projects accomplishments impact metrics"
            ],
            "skills": [
                "technical skills competencies",
                "software tools technologies",
                "certifications qualifications expertise"
            ],
            "cover_letter": [
                "job requirements qualifications",
                "company culture values mission",
                "relevant experience achievements match"
            ]
        }
        
        queries = section_queries.get(section_type, [specific_query]) if specific_query else section_queries.get(section_type, [])
        
        all_results = []
        for query in queries:
            if query:
                result = self.retrieve_context(query)
                if result["source_docs"]:
                    all_results.extend(result["source_docs"])
        
        unique_results = self._ensure_diversity(all_results)
        
        context = self._build_context_string(unique_results)
        
        return {
            "context": context,
            "source_docs": unique_results,
            "queries_used": queries,
            "final_count": len(unique_results),
            "doc_type_distribution": self._get_source_distribution(unique_results)
        }
    
    def get_jd_specific_context(self, focus_areas: List[str] = None) -> Dict[str, Any]:
        jd_queries = focus_areas or [
            "job requirements qualifications must have",
            "responsibilities duties role expectations",
            "skills experience needed preferred",
            "company culture values team environment"
        ]
        
        all_docs = []
        for query in jd_queries:
            result = self.retrieve_context(query, doc_types=["job_description"])
            if result["source_docs"]:
                all_docs.extend(result["source_docs"])
        
        unique_docs = self._ensure_diversity(all_docs)
        context = self._build_context_string(unique_docs)
        
        return {
            "context": context,
            "source_docs": unique_docs,
            "queries_used": jd_queries,
            "final_count": len(unique_docs)
        }
    
    def get_superset_context(self, skill_focus: str = None) -> Dict[str, Any]:
        superset_queries = [
            skill_focus or "technical skills experience achievements",
            "projects accomplishments certifications",
            "leadership management experience results"
        ]
        
        all_docs = []
        for query in superset_queries:
            result = self.retrieve_context(query, doc_types=["experience_superset", "skills_superset", "superset", "experience_summary"])
            if result["source_docs"]:
                all_docs.extend(result["source_docs"])
        
        unique_docs = self._ensure_diversity(all_docs)
        context = self._build_context_string(unique_docs)
        
        return {
            "context": context,
            "source_docs": unique_docs,
            "queries_used": superset_queries,
            "final_count": len(unique_docs)
        }

class ContextBuilder:
    def __init__(self, retriever: RAGRetriever):
        self.retriever = retriever
    
    def build_cv_generation_context(self) -> str:
        jd_context = self.retriever.get_jd_specific_context()
        superset_context = self.retriever.get_superset_context()
        
        combined_context = f"""
JOB DESCRIPTION ANALYSIS:
{jd_context['context']}

CANDIDATE EXPERIENCE & SKILLS SUPERSET:
{superset_context['context']}
        """.strip()
        
        return combined_context
    
    def build_cover_letter_context(self, company_focus: str = None) -> str:
        jd_context = self.retriever.get_jd_specific_context([
            "job requirements responsibilities",
            company_focus or "company culture values mission",
            "qualifications experience needed"
        ])
        
        relevant_experience = self.retriever.get_superset_context(
            "relevant projects achievements experience"
        )
        
        combined_context = f"""
TARGET JOB & COMPANY:
{jd_context['context']}

RELEVANT CANDIDATE BACKGROUND:
{relevant_experience['context']}
        """.strip()
        
        return combined_context
    
    def get_context_summary(self, context: str) -> Dict[str, int]:
        return {
            "total_chars": len(context),
            "total_words": len(context.split()),
            "paragraphs": len([p for p in context.split('\n\n') if p.strip()]),
            "sources": len([line for line in context.split('\n') if line.startswith('(Source:')])
        }

@st.cache_resource
def create_rag_retriever(_vector_store: FAISS):
    return RAGRetriever(_vector_store)