import os
import logging
import time
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import streamlit as st
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

class ModelType(Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"

@dataclass
class LLMConfig:
    model: ModelType
    temperature: float = 0.2
    max_tokens: int = 4000
    retry_attempts: int = 3
    retry_delay: float = 1.0

class CVPackageValidator:
    @staticmethod
    def validate_career_summary(summary: str) -> Dict[str, Any]:
        words = summary.split()
        return {
            "valid": len(words) <= 40,
            "word_count": len(words),
            "message": f"Career summary: {len(words)}/40 words"
        }
    
    @staticmethod
    def validate_sar_bullets(text: str) -> Dict[str, Any]:
        bullet_patterns = [
            r'^\s*[\•\-\*]\s*\w+\s+\w+:',
            r'^\s*\w+\s+\w+:',
        ]
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        bullets = []
        
        for line in lines:
            for pattern in bullet_patterns:
                if re.match(pattern, line):
                    bullets.append(line)
                    break
        
        two_word_headings = []
        for bullet in bullets:
            heading_match = re.match(r'^\s*[\•\-\*]?\s*(\w+\s+\w+):', bullet)
            if heading_match:
                heading = heading_match.group(1)
                if len(heading.split()) == 2:
                    two_word_headings.append(heading)
        
        return {
            "valid": len(bullets) == 8 and len(two_word_headings) == 8,
            "bullet_count": len(bullets),
            "two_word_headings_count": len(two_word_headings),
            "bullets": bullets,
            "message": f"SAR bullets: {len(bullets)}/8 found, {len(two_word_headings)}/8 with two-word headings"
        }
    
    @staticmethod
    def validate_skills(text: str) -> Dict[str, Any]:
        skill_patterns = [
            r'^\s*[\•\-\*]\s*(\w+(?:\s+\w+)?)\s*$',
            r'^(\w+(?:\s+\w+)?)\s*[,\|]?',
        ]
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        skills = []
        
        for line in lines:
            for pattern in skill_patterns:
                matches = re.findall(pattern, line)
                for match in matches:
                    skill = match.strip().strip(',|')
                    if skill and len(skill.split()) <= 2:
                        skills.append(skill)
        
        skills = list(set(skills))[:10]
        valid_skills = [s for s in skills if len(s.split()) <= 2]
        
        return {
            "valid": len(valid_skills) == 10,
            "skill_count": len(valid_skills),
            "skills": valid_skills,
            "message": f"Skills: {len(valid_skills)}/10 found (≤2 words each)"
        }

class OpenAILLMService:
    def __init__(self, api_key: str, config: LLMConfig = None):
        self.client = OpenAI(api_key=api_key)
        self.config = config or LLMConfig(model=ModelType.GPT_4O_MINI)
        self.validator = CVPackageValidator()
        
        self.langchain_llm = ChatOpenAI(
            model=self.config.model.value,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            openai_api_key=api_key
        )
    
    def _make_request_with_retry(self, messages: List[Dict[str, str]], system_prompt: str = None) -> str:
        for attempt in range(self.config.retry_attempts):
            try:
                formatted_messages = []
                if system_prompt:
                    formatted_messages.append({"role": "system", "content": system_prompt})
                
                formatted_messages.extend(messages)
                
                response = self.client.chat.completions.create(
                    model=self.config.model.value,
                    messages=formatted_messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                logger.warning(f"API request attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise e
    
    def generate_cv_package(self, prompt: str, context: str) -> Dict[str, Any]:
        system_prompt = """You are a professional CV writer specializing in creating ATS-optimized resumes. 
        You must follow the exact specifications provided in the prompt regarding word counts and formatting requirements."""
        
        messages = [
            {
                "role": "user", 
                "content": f"{prompt}\n\nContext:\n{context}"
            }
        ]
        
        response = self._make_request_with_retry(messages, system_prompt)
        
        validation_results = self._validate_cv_package(response)
        
        return {
            "content": response,
            "validation": validation_results,
            "model_used": self.config.model.value,
            "valid": all(v.get("valid", False) for v in validation_results.values())
        }
    
    def generate_cover_letter(self, prompt: str, context: str) -> Dict[str, Any]:
        system_prompt = """You are a professional cover letter writer. Create compelling, ATS-optimized cover letters 
        that are concise and targeted. Follow the word count limits strictly."""
        
        messages = [
            {
                "role": "user",
                "content": f"{prompt}\n\nContext:\n{context}"
            }
        ]
        
        response = self._make_request_with_retry(messages, system_prompt)
        
        word_count = len(response.split())
        
        return {
            "content": response,
            "word_count": word_count,
            "valid": word_count <= 250,
            "model_used": self.config.model.value,
            "validation": {
                "word_count": {
                    "valid": word_count <= 250,
                    "count": word_count,
                    "message": f"Cover letter: {word_count}/250 words"
                }
            }
        }
    
    def _validate_cv_package(self, content: str) -> Dict[str, Any]:
        sections = self._extract_sections(content)
        results = {}
        
        if "career_summary" in sections:
            results["career_summary"] = self.validator.validate_career_summary(
                sections["career_summary"]
            )
        
        if "experience" in sections:
            results["sar_bullets"] = self.validator.validate_sar_bullets(
                sections["experience"]
            )
        
        if "skills" in sections:
            results["skills"] = self.validator.validate_skills(
                sections["skills"]
            )
        
        return results
    
    def _extract_sections(self, content: str) -> Dict[str, str]:
        sections = {}
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            line_upper = line.upper().strip()
            
            if any(keyword in line_upper for keyword in ['CAREER SUMMARY', 'PROFESSIONAL SUMMARY', 'SUMMARY']):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "career_summary"
                current_content = []
                
            elif any(keyword in line_upper for keyword in ['EXPERIENCE', 'WORK EXPERIENCE', 'PROFESSIONAL EXPERIENCE']):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "experience"
                current_content = []
                
            elif any(keyword in line_upper for keyword in ['SKILLS', 'TECHNICAL SKILLS', 'CORE COMPETENCIES']):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = "skills"
                current_content = []
                
            else:
                if current_section:
                    current_content.append(line)
        
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def improve_response(self, original_response: str, validation_results: Dict[str, Any], 
                        original_prompt: str, context: str) -> Dict[str, Any]:
        
        improvement_prompt = self._create_improvement_prompt(validation_results)
        
        system_prompt = """You are tasked with fixing a CV that doesn't meet the specified requirements. 
        Make the minimum necessary changes to meet all validation criteria."""
        
        messages = [
            {
                "role": "user",
                "content": f"{improvement_prompt}\n\nOriginal Response:\n{original_response}\n\nOriginal Prompt:\n{original_prompt}\n\nContext:\n{context}"
            }
        ]
        
        improved_response = self._make_request_with_retry(messages, system_prompt)
        new_validation = self._validate_cv_package(improved_response)
        
        return {
            "content": improved_response,
            "validation": new_validation,
            "model_used": self.config.model.value,
            "valid": all(v.get("valid", False) for v in new_validation.values())
        }
    
    def _create_improvement_prompt(self, validation_results: Dict[str, Any]) -> str:
        issues = []
        
        for section, result in validation_results.items():
            if not result.get("valid", True):
                issues.append(result.get("message", f"{section} validation failed"))
        
        return f"Please fix the following issues:\n" + "\n".join(f"- {issue}" for issue in issues)

@st.cache_resource
def create_llm_service(model_choice: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OpenAI API key not found. Please set OPENAI_API_KEY in your environment.")
        st.stop()
    
    config = LLMConfig(
        model=ModelType(model_choice),
        temperature=0.2,
        max_tokens=4000
    )
    
    return OpenAILLMService(api_key, config)

def get_llm_service():
    model_choice = st.sidebar.selectbox(
        "Select Model",
        options=[ModelType.GPT_4O_MINI.value, ModelType.GPT_4O.value],
        index=0,
        help="gpt-4o-mini is faster and cheaper, gpt-4o is higher quality"
    )
    
    return create_llm_service(model_choice)