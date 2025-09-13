import os
import logging
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

import streamlit as st
from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class SummaryGenerationConfig:
    max_words: int = 30
    temperature: float = 0.1
    max_tokens: int = 300
    model: str = "gpt-4o-mini"  # Can be gpt-4o-mini, gpt-4o, or gpt-5

@dataclass 
class ProfessionalSummary:
    content: str
    word_count: int
    has_keywords: bool
    tone_score: float
    valid: bool

class SummaryGenerator:
    def __init__(self, config: SummaryGenerationConfig = None):
        self.config = config or SummaryGenerationConfig()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def _get_model_compatible_params(self, model: str, max_tokens: int) -> Dict[str, Any]:
        """Get model-compatible parameters for OpenAI API calls"""
        # GPT-5 and newer models use max_completion_tokens
        if model in ["gpt-5"]:
            return {"max_completion_tokens": max_tokens}
        else:
            return {"max_tokens": max_tokens}
    
    def generate_professional_summary(self, job_description: str, experience_superset: str, 
                                    skills_superset: str = None) -> Dict[str, Any]:
        """Generate executive-level professional summary ≤30 words"""
        
        try:
            # Combine experience and skills for full context
            candidate_background = experience_superset
            if skills_superset:
                candidate_background += f"\n\nSKILLS SUPERSET:\n{skills_superset}"
            
            system_prompt = self._create_summary_system_prompt()
            user_prompt = self._create_summary_user_prompt(job_description, candidate_background)
            
            # Get model-compatible parameters
            token_params = self._get_model_compatible_params(self.config.model, self.config.max_tokens)
            
            response = self.openai_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                **token_params
            )
            
            raw_summary = response.choices[0].message.content.strip()
            processed_summary = self._process_summary_response(raw_summary, job_description)
            
            return {
                "summary": processed_summary.content,
                "word_count": processed_summary.word_count,
                "valid": processed_summary.valid,
                "has_keywords": processed_summary.has_keywords,
                "tone_score": processed_summary.tone_score,
                "raw_response": raw_summary,
                "validation_message": self._get_validation_message(processed_summary)
            }
            
        except Exception as e:
            logger.error(f"Error generating professional summary: {e}")
            return {
                "summary": "",
                "word_count": 0,
                "valid": False,
                "has_keywords": False,
                "tone_score": 0.0,
                "raw_response": "",
                "validation_message": f"Error generating summary: {str(e)}"
            }
    
    def _create_summary_system_prompt(self) -> str:
        return """You are an expert CV writer and ATS optimizer for senior technology and engineering leadership roles.

Your ONLY task is to generate ONE high-impact Professional Summary in exactly 30 words or fewer.

CRITICAL RULES:
- Output ONLY the professional summary text, nothing else
- Maximum 30 words, single paragraph
- Executive tone, no first-person pronouns
- No filler words or vague adjectives
- Integrate job description keywords naturally
- Demonstrate leadership scale and business outcomes
- ATS-optimized for senior leadership roles

ANTI-HALLUCINATION GUARD RAILS:
- Use ONLY information directly provided in the candidate background
- Do NOT invent specific percentages, numbers, or metrics not mentioned in the source material
- Do NOT create fictional achievements or outcomes
- Keep all claims factually grounded in the provided context
- If no specific metrics are provided, use qualitative descriptors instead"""
    
    def _create_summary_user_prompt(self, job_description: str, candidate_background: str) -> str:
        return f"""ANALYZE the job description and candidate background to generate ONE executive professional summary.

JOB DESCRIPTION:
{job_description}

CANDIDATE BACKGROUND (Experience & Skills):
{candidate_background}

REQUIREMENTS:
- Maximum 30 words, single paragraph format
- Executive tone suitable for CTO/VP level positions
- Integrate top job description keywords naturally
- Highlight leadership scale, domain expertise, business outcomes
- No first-person pronouns (I, my, me)
- No vague adjectives or filler words
- Demonstrate measurable scope and strategic alignment

IMPORTANT - FACTUAL ACCURACY:
- Use ONLY facts and achievements explicitly stated in the candidate background
- Do NOT invent percentages, dollar amounts, or specific metrics not provided
- If quantitative data isn't available, focus on qualitative achievements and scope
- Keep all statements truthful and verifiable from the source material

PRIORITY ELEMENTS:
1. Core leadership and technology competencies from JD
2. Highest-frequency job description keywords
3. Strategic differentiators from candidate background
4. Business impact and measurable outcomes
5. Technical breadth and industry expertise

TONE:
- Polished and executive-level
- Results-oriented and achievement-focused
- Industry-specific and technically credible
- ATS-optimized with natural keyword integration

OUTPUT FORMAT:
Single paragraph, maximum 30 words, executive tone, integrating JD keywords and demonstrating leadership impact."""
    
    def _process_summary_response(self, raw_summary: str, job_description: str) -> ProfessionalSummary:
        """Process and validate the professional summary response"""
        
        # Clean the response
        clean_summary = raw_summary.strip()
        
        # Remove common prefixes/suffixes that might be added
        prefixes_to_remove = [
            "Professional Summary:", "Summary:", "Here is the professional summary:",
            "The professional summary is:", "Professional summary:"
        ]
        
        for prefix in prefixes_to_remove:
            if clean_summary.lower().startswith(prefix.lower()):
                clean_summary = clean_summary[len(prefix):].strip()
        
        # Remove quotes if present
        if clean_summary.startswith('"') and clean_summary.endswith('"'):
            clean_summary = clean_summary[1:-1].strip()
        
        # Count words
        word_count = len(clean_summary.split())
        
        # Validate
        valid = word_count <= self.config.max_words and word_count > 0
        
        # Check for keywords from job description
        has_keywords = self._check_keyword_presence(clean_summary, job_description)
        
        # Evaluate tone (simple heuristic)
        tone_score = self._evaluate_tone(clean_summary)
        
        return ProfessionalSummary(
            content=clean_summary,
            word_count=word_count,
            has_keywords=has_keywords,
            tone_score=tone_score,
            valid=valid
        )
    
    def _check_keyword_presence(self, summary: str, job_description: str) -> bool:
        """Check if summary contains relevant keywords from job description"""
        
        # Extract key terms from job description (simple approach)
        jd_lower = job_description.lower()
        summary_lower = summary.lower()
        
        # Common senior leadership keywords to look for
        leadership_keywords = [
            "lead", "leader", "leadership", "manage", "director", "vp", "cto", "head",
            "strategy", "strategic", "transform", "scale", "deliver", "drive", "build"
        ]
        
        # Technology keywords
        tech_keywords = [
            "engineering", "technology", "technical", "software", "platform", "architecture",
            "cloud", "data", "ai", "ml", "digital", "innovation", "product", "development"
        ]
        
        # Check for presence of key terms
        keyword_matches = 0
        total_keywords = leadership_keywords + tech_keywords
        
        for keyword in total_keywords:
            if keyword in jd_lower and keyword in summary_lower:
                keyword_matches += 1
        
        # Return True if at least 2 relevant keywords are found
        return keyword_matches >= 2
    
    def _evaluate_tone(self, summary: str) -> float:
        """Simple heuristic to evaluate executive tone (0-1 scale)"""
        
        tone_score = 0.5  # Base score
        
        # Positive indicators
        executive_words = [
            "deliver", "drive", "lead", "transform", "scale", "optimize", "strategic",
            "executive", "senior", "director", "global", "enterprise", "innovative"
        ]
        
        # Negative indicators (reduce score)
        weak_words = [
            "help", "assist", "support", "try", "attempt", "hope", "maybe", "possibly",
            "i", "my", "me", "we", "our"  # first-person pronouns
        ]
        
        summary_lower = summary.lower()
        
        # Add points for executive language
        for word in executive_words:
            if word in summary_lower:
                tone_score += 0.05
        
        # Subtract points for weak language
        for word in weak_words:
            if word in summary_lower:
                tone_score -= 0.1
        
        # Check for metrics/quantification (positive)
        if re.search(r'\d+', summary):
            tone_score += 0.1
        
        # Ensure score stays within bounds
        return max(0.0, min(1.0, tone_score))
    
    def _get_validation_message(self, summary: ProfessionalSummary) -> str:
        """Generate validation message for the summary"""
        
        if summary.valid:
            quality_indicators = []
            if summary.word_count <= 25:
                quality_indicators.append("concise")
            if summary.has_keywords:
                quality_indicators.append("JD-aligned")
            if summary.tone_score > 0.7:
                quality_indicators.append("executive tone")
            
            if quality_indicators:
                return f"✅ Professional summary: {summary.word_count}/{self.config.max_words} words ({', '.join(quality_indicators)})"
            else:
                return f"✅ Professional summary: {summary.word_count}/{self.config.max_words} words"
        else:
            issues = []
            if summary.word_count > self.config.max_words:
                issues.append(f"exceeds {self.config.max_words} words")
            if summary.word_count == 0:
                issues.append("empty content")
            if not summary.has_keywords:
                issues.append("missing JD keywords")
            
            return f"⚠️ Issues: {', '.join(issues)}"
    
    def get_summary_analysis(self, summary: ProfessionalSummary, job_description: str) -> Dict[str, Any]:
        """Get detailed analysis of the generated summary"""
        
        return {
            "word_count": summary.word_count,
            "max_words": self.config.max_words,
            "compliance": "✅ Compliant" if summary.valid else "❌ Non-compliant", 
            "keyword_integration": "✅ Present" if summary.has_keywords else "⚠️ Limited",
            "tone_score": f"{summary.tone_score:.1f}/1.0",
            "tone_assessment": self._get_tone_assessment(summary.tone_score),
            "executive_ready": summary.valid and summary.has_keywords and summary.tone_score > 0.6
        }
    
    def _get_tone_assessment(self, tone_score: float) -> str:
        """Convert tone score to qualitative assessment"""
        if tone_score >= 0.8:
            return "Excellent executive tone"
        elif tone_score >= 0.6:
            return "Good professional tone"
        elif tone_score >= 0.4:
            return "Adequate tone"
        else:
            return "Needs improvement"

@st.cache_resource
def get_summary_generator():
    return SummaryGenerator()