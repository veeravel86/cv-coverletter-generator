import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import streamlit as st
from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class SkillsGenerationConfig:
    max_skills: int = 10
    max_words_per_skill: int = 2
    temperature: float = 0.1
    max_tokens: int = 1000
    model: str = "gpt-4o-mini"  # Can be gpt-4o-mini, gpt-4o, or gpt-5

class SkillsGenerator:
    def __init__(self, config: SkillsGenerationConfig = None):
        self.config = config or SkillsGenerationConfig()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate_top_skills(self, job_description: str, experience_superset: str, 
                           skills_superset: str = None) -> Dict[str, Any]:
        """Generate top 10 ATS-optimized skills based on job description and candidate experience"""
        
        try:
            # Combine experience and skills superset
            candidate_background = experience_superset
            if skills_superset:
                candidate_background += f"\n\nSKILLS SUPERSET:\n{skills_superset}"
            
            system_prompt = self._create_skills_system_prompt()
            user_prompt = self._create_skills_user_prompt(job_description, candidate_background)
            
            response = self.openai_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            raw_skills = response.choices[0].message.content.strip()
            processed_skills = self._process_skills_response(raw_skills)
            
            return {
                "skills": processed_skills["skills"],
                "raw_response": raw_skills,
                "skill_count": len(processed_skills["skills"]),
                "valid": processed_skills["valid"],
                "validation_message": processed_skills["message"]
            }
            
        except Exception as e:
            logger.error(f"Error generating skills: {e}")
            return {
                "skills": [],
                "raw_response": "",
                "skill_count": 0,
                "valid": False,
                "validation_message": f"Error generating skills: {str(e)}"
            }
    
    def _create_skills_system_prompt(self) -> str:
        return """You are an expert CV writer and ATS optimizer specializing in senior engineering roles.

Your ONLY task is to generate exactly 10 skills for a CV that will pass both ATS scanning and human review.

CRITICAL RULES:
- Output ONLY the 10 skills, one per line
- No numbering, no bullets, no extra text, no explanations
- Each skill must be ≤ 2 words in Title Case
- Skills must be derived from job description language
- Skills must be supported by candidate's experience
- Order by priority (most important first)
- No duplicates or near-duplicates"""
    
    def _create_skills_user_prompt(self, job_description: str, candidate_background: str) -> str:
        return f"""ANALYZE the job description and candidate background to generate EXACTLY 10 skills.

JOB DESCRIPTION:
{job_description}

CANDIDATE BACKGROUND (Experience & Skills Superset):
{candidate_background}

REQUIREMENTS:
- Extract skills directly from the Job Description's language
- Ensure each skill is supported by the candidate's background
- Maximum 2 words per skill, Title Case format
- Order by priority based on job requirements
- Use Job Description keywords verbatim when possible
- Avoid synonyms unless JD term exceeds 2 words

PRIORITY ORDER:
1. Mission-critical competencies explicitly required
2. Skills repeated/emphasized in job description
3. Strategic differentiators for this role

OUTPUT FORMAT:
- Exactly 10 skills, one per line
- No numbering, bullets, or extra text
- Title Case, ≤2 words each
- Highest priority first"""
    
    def _process_skills_response(self, raw_response: str) -> Dict[str, Any]:
        """Process and validate the skills response"""
        lines = [line.strip() for line in raw_response.split('\n') if line.strip()]
        
        # Filter out any numbered items, bullets, or explanatory text
        skills = []
        for line in lines:
            # Remove common prefixes
            clean_line = line
            prefixes = ['•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.']
            for prefix in prefixes:
                if clean_line.startswith(prefix):
                    clean_line = clean_line[len(prefix):].strip()
            
            # Check if it's a valid skill (≤2 words, not explanatory text)
            words = clean_line.split()
            if len(words) <= self.config.max_words_per_skill and len(words) > 0:
                # Convert to title case
                skill = ' '.join(word.capitalize() for word in words)
                if skill not in skills:  # Avoid duplicates
                    skills.append(skill)
                    
            # Stop at 10 skills
            if len(skills) >= self.config.max_skills:
                break
        
        # Validation
        valid = len(skills) == self.config.max_skills
        message = f"Generated {len(skills)}/{self.config.max_skills} skills"
        
        if len(skills) < self.config.max_skills:
            message += f" (Expected {self.config.max_skills}, got {len(skills)})"
        
        return {
            "skills": skills,
            "valid": valid,
            "message": message
        }
    
    def format_skills_for_cv(self, skills: List[str], format_style: str = "bullet") -> str:
        """Format skills for CV display"""
        if not skills:
            return ""
        
        if format_style == "bullet":
            return '\n'.join(f"• {skill}" for skill in skills)
        elif format_style == "comma":
            return ', '.join(skills)
        elif format_style == "pipe":
            return ' | '.join(skills)
        else:
            return '\n'.join(skills)

@st.cache_resource
def get_skills_generator():
    return SkillsGenerator()