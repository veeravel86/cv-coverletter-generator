import os
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import streamlit as st
from openai import OpenAI

logger = logging.getLogger(__name__)

@dataclass
class ExperienceGenerationConfig:
    max_bullets: int = 8
    min_words_per_bullet: int = 22
    max_words_per_bullet: int = 35
    temperature: float = 0.1
    max_tokens: int = 1500
    model: str = "gpt-4o-mini"  # Can be gpt-4o-mini, gpt-4o, or gpt-5

@dataclass
class ExperienceBullet:
    heading: str
    content: str
    full_bullet: str
    word_count: int
    has_two_word_heading: bool

class ExperienceGenerator:
    def __init__(self, config: ExperienceGenerationConfig = None):
        self.config = config or ExperienceGenerationConfig()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def generate_experience_summary(self, job_description: str, experience_superset: str) -> Dict[str, Any]:
        """Generate 8 high-impact experience summary bullets using SAR format"""
        
        try:
            system_prompt = self._create_experience_system_prompt()
            user_prompt = self._create_experience_user_prompt(job_description, experience_superset)
            
            response = self.openai_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            raw_response = response.choices[0].message.content.strip()
            processed_bullets = self._process_experience_response(raw_response)
            
            return {
                "bullets": processed_bullets["bullets"],
                "raw_response": raw_response,
                "bullet_count": len(processed_bullets["bullets"]),
                "valid": processed_bullets["valid"],
                "validation_message": processed_bullets["message"],
                "two_word_headings_count": processed_bullets["two_word_count"]
            }
            
        except Exception as e:
            logger.error(f"Error generating experience summary: {e}")
            return {
                "bullets": [],
                "raw_response": "",
                "bullet_count": 0,
                "valid": False,
                "validation_message": f"Error generating experience summary: {str(e)}",
                "two_word_headings_count": 0
            }
    
    def _create_experience_system_prompt(self) -> str:
        return """You are an expert CV writer and ATS optimizer specializing in senior engineering leadership roles.

Your ONLY task is to generate exactly 8 high-impact experience summary bullets using SAR (Situation-Action-Result) format.

CRITICAL RULES:
- Output ONLY the 8 bullets, nothing else
- Format: **Two Word Heading | SAR statement showing measurable impact**
- Each bullet must be 22-35 words
- Two-word headings using job description language
- SAR structure in one concise sentence
- Priority order (most relevant first)
- Include metrics when available from experience
- No fabrication or vague content"""
    
    def _create_experience_user_prompt(self, job_description: str, experience_superset: str) -> str:
        return f"""ANALYZE the job description and experience superset to generate EXACTLY 8 experience bullets.

JOB DESCRIPTION:
{job_description}

EXPERIENCE SUPERSET:
{experience_superset}

REQUIREMENTS:
- Create exactly 8 bullets using SAR format (Situation-Action-Result)
- Start each bullet with TWO-WORD HEADING using job description keywords
- Each bullet: 22-35 words in one concise sentence
- Show measurable impact, leadership depth, business relevance
- Use job description keywords naturally
- Include quantifiable results when present in experience
- No abbreviations in headings

PRIORITY ORDER:
1. Mission-critical competencies and leadership scope from JD
2. Skills and themes repeated/emphasized in job description  
3. Emerging differentiators likely valued for this role

OUTPUT FORMAT:
**Two Word Heading | SAR statement showing measurable impact and business outcomes**

Example format (not content):
**Cloud Migration | Inherited aging on-prem infrastructure; led comprehensive AWS migration with team restructuring; achieved 20% cost reduction and improved deployment cycles**

QUALITY STANDARDS:
- Each bullet must be JD-aligned and SAR-structured
- Focus on outcomes and quantified results
- Use strong action verbs and ATS-friendly keywords
- Ensure bullets show progression and increasing responsibility
- No duplicated content or similar achievements"""
    
    def _process_experience_response(self, raw_response: str) -> Dict[str, Any]:
        """Process and validate the experience bullets response"""
        lines = [line.strip() for line in raw_response.split('\n') if line.strip()]
        
        bullets = []
        for line in lines:
            if '|' in line and ('**' in line or line.strip().startswith(('•', '-', '*'))):
                # Clean the line
                clean_line = line.strip()
                
                # Remove common prefixes
                prefixes = ['•', '-', '*']
                for prefix in prefixes:
                    if clean_line.startswith(prefix):
                        clean_line = clean_line[1:].strip()
                
                # Extract heading and content
                if '|' in clean_line:
                    parts = clean_line.split('|', 1)
                    if len(parts) == 2:
                        heading_part = parts[0].strip()
                        content_part = parts[1].strip()
                        
                        # Extract heading (remove ** formatting)
                        heading = re.sub(r'\*+', '', heading_part).strip()
                        
                        # Count words in content
                        word_count = len(content_part.split())
                        
                        # Check if heading has exactly 2 words
                        heading_words = heading.split()
                        has_two_word_heading = len(heading_words) == 2
                        
                        bullet = ExperienceBullet(
                            heading=heading,
                            content=content_part,
                            full_bullet=f"**{heading}** | {content_part}",
                            word_count=word_count,
                            has_two_word_heading=has_two_word_heading
                        )
                        
                        bullets.append(bullet)
                        
                        if len(bullets) >= self.config.max_bullets:
                            break
        
        # Validation
        valid_bullets = len(bullets) == self.config.max_bullets
        two_word_count = sum(1 for b in bullets if b.has_two_word_heading)
        
        # Word count validation
        word_count_valid = all(
            self.config.min_words_per_bullet <= b.word_count <= self.config.max_words_per_bullet 
            for b in bullets
        )
        
        validation_msg = f"Generated {len(bullets)}/{self.config.max_bullets} bullets"
        if two_word_count < len(bullets):
            validation_msg += f", {two_word_count}/{len(bullets)} with two-word headings"
        
        return {
            "bullets": bullets,
            "valid": valid_bullets and word_count_valid,
            "message": validation_msg,
            "two_word_count": two_word_count
        }
    
    def format_bullets_for_cv(self, bullets: List[ExperienceBullet], format_style: str = "standard") -> str:
        """Format experience bullets for CV display"""
        if not bullets:
            return ""
        
        if format_style == "standard":
            return '\n'.join(f"• {bullet.full_bullet}" for bullet in bullets)
        elif format_style == "clean":
            return '\n'.join(bullet.full_bullet for bullet in bullets)
        elif format_style == "numbered":
            return '\n'.join(f"{i+1}. {bullet.full_bullet}" for i, bullet in enumerate(bullets))
        else:
            return '\n'.join(bullet.full_bullet for bullet in bullets)
    
    def get_bullets_summary(self, bullets: List[ExperienceBullet]) -> Dict[str, Any]:
        """Get summary statistics for generated bullets"""
        if not bullets:
            return {
                "total_bullets": 0,
                "two_word_headings": 0,
                "avg_word_count": 0,
                "word_count_range": "N/A"
            }
        
        word_counts = [b.word_count for b in bullets]
        two_word_count = sum(1 for b in bullets if b.has_two_word_heading)
        
        return {
            "total_bullets": len(bullets),
            "two_word_headings": two_word_count,
            "avg_word_count": round(sum(word_counts) / len(word_counts), 1),
            "word_count_range": f"{min(word_counts)}-{max(word_counts)}"
        }

@st.cache_resource
def get_experience_generator():
    return ExperienceGenerator()