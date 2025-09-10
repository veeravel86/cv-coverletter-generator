import pytest
import os
from unittest.mock import MagicMock, patch
from langchain.schema import Document
from langchain_community.vectorstores import FAISS

from services.rag import RAGRetriever, ContextBuilder, RetrievalConfig

class TestRAGRetriever:
    
    @pytest.fixture
    def mock_vector_store(self):
        mock_store = MagicMock(spec=FAISS)
        
        sample_docs = [
            (Document(page_content="Software engineer with 5 years experience", 
                     metadata={"source": "job_description", "chunk_id": 0}), 0.9),
            (Document(page_content="Python, Java, React development skills", 
                     metadata={"source": "superset", "chunk_id": 1}), 0.8),
            (Document(page_content="Led team of 10 developers on major project", 
                     metadata={"source": "superset", "chunk_id": 2}), 0.7)
        ]
        
        mock_store.similarity_search_with_score.return_value = sample_docs
        return mock_store
    
    @pytest.fixture
    def retriever(self, mock_vector_store):
        config = RetrievalConfig(k=10, score_threshold=0.7)
        return RAGRetriever(mock_vector_store, config)
    
    def test_retrieve_context_basic(self, retriever):
        result = retriever.retrieve_context("software engineer skills")
        
        assert "context" in result
        assert "source_docs" in result
        assert "total_retrieved" in result
        assert result["total_retrieved"] == 3
        assert len(result["source_docs"]) == 3
    
    def test_retrieve_context_with_doc_type_filter(self, retriever):
        result = retriever.retrieve_context("software engineer", doc_types=["superset"])
        
        assert len(result["source_docs"]) == 2
        for doc, score in result["source_docs"]:
            assert doc.metadata["source"] == "superset"
    
    def test_filter_by_relevance(self, retriever, mock_vector_store):
        # Test that low-scoring documents are filtered out
        low_score_docs = [
            (Document(page_content="test", metadata={"source": "test"}), 0.9),
            (Document(page_content="test", metadata={"source": "test"}), 0.5),
            (Document(page_content="test", metadata={"source": "test"}), 0.3)
        ]
        mock_vector_store.similarity_search_with_score.return_value = low_score_docs
        
        filtered = retriever._filter_by_relevance(low_score_docs)
        assert len(filtered) == 2
        assert all(score >= 0.5 for _, score in filtered)
    
    def test_ensure_diversity(self, retriever):
        duplicate_docs = [
            (Document(page_content="Same content here", metadata={"source": "test"}), 0.9),
            (Document(page_content="Same content here", metadata={"source": "test"}), 0.8),
            (Document(page_content="Different content", metadata={"source": "test"}), 0.7)
        ]
        
        diverse_docs = retriever._ensure_diversity(duplicate_docs)
        assert len(diverse_docs) == 2
        
        contents = [doc.page_content for doc, _ in diverse_docs]
        assert len(set(contents)) == 2
    
    def test_build_context_string(self, retriever):
        docs_with_scores = [
            (Document(page_content="First content", 
                     metadata={"source": "job_description"}), 0.9),
            (Document(page_content="Second content", 
                     metadata={"source": "superset"}), 0.8)
        ]
        
        context = retriever._build_context_string(docs_with_scores)
        
        assert "First content" in context
        assert "Second content" in context
        assert "job_description" in context
        assert "superset" in context
        assert "---" in context
    
    def test_get_source_distribution(self, retriever):
        docs_with_scores = [
            (Document(page_content="content1", metadata={"source": "job_description"}), 0.9),
            (Document(page_content="content2", metadata={"source": "job_description"}), 0.8),
            (Document(page_content="content3", metadata={"source": "superset"}), 0.7)
        ]
        
        distribution = retriever._get_source_distribution(docs_with_scores)
        
        assert distribution["job_description"] == 2
        assert distribution["superset"] == 1
    
    def test_get_targeted_context_career_summary(self, retriever):
        result = retriever.get_targeted_context("career_summary")
        
        assert "context" in result
        assert "queries_used" in result
        assert len(result["queries_used"]) == 3
        assert "professional summary" in result["queries_used"][0]
    
    def test_get_jd_specific_context(self, retriever):
        result = retriever.get_jd_specific_context()
        
        assert "context" in result
        assert "queries_used" in result
        assert "final_count" in result
        
        retriever.vector_store.similarity_search_with_score.assert_called()
    
    def test_get_superset_context(self, retriever):
        result = retriever.get_superset_context("Python programming")
        
        assert "context" in result
        assert "queries_used" in result
        assert result["queries_used"][0] == "Python programming"

class TestContextBuilder:
    
    @pytest.fixture
    def mock_retriever(self):
        mock_retriever = MagicMock(spec=RAGRetriever)
        
        mock_retriever.get_jd_specific_context.return_value = {
            "context": "Job requires Python and React skills",
            "source_docs": [],
            "queries_used": ["job requirements"],
            "final_count": 1
        }
        
        mock_retriever.get_superset_context.return_value = {
            "context": "Candidate has 5 years Python experience", 
            "source_docs": [],
            "queries_used": ["technical skills"],
            "final_count": 1
        }
        
        return mock_retriever
    
    @pytest.fixture
    def context_builder(self, mock_retriever):
        return ContextBuilder(mock_retriever)
    
    def test_build_cv_generation_context(self, context_builder, mock_retriever):
        context = context_builder.build_cv_generation_context()
        
        assert "JOB DESCRIPTION ANALYSIS:" in context
        assert "CANDIDATE EXPERIENCE & SKILLS SUPERSET:" in context
        assert "Job requires Python and React skills" in context
        assert "Candidate has 5 years Python experience" in context
        
        mock_retriever.get_jd_specific_context.assert_called_once()
        mock_retriever.get_superset_context.assert_called_once()
    
    def test_build_cover_letter_context(self, context_builder, mock_retriever):
        context = context_builder.build_cover_letter_context("TechCorp")
        
        assert "TARGET JOB & COMPANY:" in context
        assert "RELEVANT CANDIDATE BACKGROUND:" in context
        
        # Verify that company-specific query was used
        mock_retriever.get_jd_specific_context.assert_called()
        args = mock_retriever.get_jd_specific_context.call_args[0]
        assert "TechCorp" in args[0][1]
    
    def test_get_context_summary(self, context_builder):
        test_context = """This is a test context.
        
        It has multiple paragraphs.
        (Source: test1)
        (Source: test2)
        
        And some more content here."""
        
        summary = context_builder.get_context_summary(test_context)
        
        assert summary["total_chars"] == len(test_context)
        assert summary["total_words"] > 0
        assert summary["paragraphs"] >= 2
        assert summary["sources"] == 2

class TestRetrievalConfig:
    
    def test_default_config(self):
        config = RetrievalConfig()
        
        assert config.k == 10
        assert config.score_threshold == 0.7
        assert config.diversity_threshold == 0.8
        assert config.max_context_length == 8000
    
    def test_custom_config(self):
        config = RetrievalConfig(
            k=5,
            score_threshold=0.8,
            max_context_length=5000
        )
        
        assert config.k == 5
        assert config.score_threshold == 0.8
        assert config.max_context_length == 5000

@pytest.mark.integration
class TestRAGIntegration:
    """Integration tests that require actual FAISS setup"""
    
    @pytest.fixture
    def sample_documents(self):
        return [
            Document(
                page_content="Software engineer position requires Python and Java skills",
                metadata={"source": "job_description", "chunk_id": 0}
            ),
            Document(
                page_content="5 years experience developing web applications with React",
                metadata={"source": "superset", "chunk_id": 1}  
            ),
            Document(
                page_content="Led development team of 8 engineers on microservices project",
                metadata={"source": "superset", "chunk_id": 2}
            )
        ]
    
    @pytest.mark.skip(reason="Requires actual embedding model")
    def test_full_rag_pipeline(self, sample_documents):
        """Test complete RAG pipeline with real embeddings"""
        # This test would require setting up actual FAISS with embeddings
        # Skip for now unless running with full environment
        pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])