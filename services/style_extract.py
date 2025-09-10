import json
import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

import streamlit as st

logger = logging.getLogger(__name__)

@dataclass
class StyleProfile:
    section_order: List[str]
    bullet_style: str
    spacing_pattern: str
    heading_format: str
    contact_format: str
    date_format: str
    font_style: str
    margins: Dict[str, str]
    line_spacing: str
    emphasis_markers: List[str]

class StyleExtractor:
    def __init__(self):
        self.default_profile = StyleProfile(
            section_order=["Contact", "Career Summary", "Skills", "Experience", "Education"],
            bullet_style="•",
            spacing_pattern="single_line",
            heading_format="ALL_CAPS",
            contact_format="horizontal",
            date_format="MM/YYYY - MM/YYYY",
            font_style="professional",
            margins={"top": "1in", "bottom": "1in", "left": "0.75in", "right": "0.75in"},
            line_spacing="1.15",
            emphasis_markers=["**", "*", "**bold**"]
        )
    
    def extract_style_from_text(self, sample_cv_text: str) -> StyleProfile:
        try:
            profile = self._analyze_structure(sample_cv_text)
            return profile
        except Exception as e:
            logger.error(f"Error extracting style: {e}")
            return self.default_profile
    
    def _analyze_structure(self, text: str) -> StyleProfile:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        section_order = self._extract_section_order(lines)
        bullet_style = self._detect_bullet_style(lines)
        heading_format = self._detect_heading_format(lines)
        contact_format = self._detect_contact_format(lines)
        date_format = self._detect_date_format(lines)
        emphasis_markers = self._detect_emphasis_markers(lines)
        
        return StyleProfile(
            section_order=section_order,
            bullet_style=bullet_style,
            spacing_pattern="single_line",
            heading_format=heading_format,
            contact_format=contact_format,
            date_format=date_format,
            font_style="professional",
            margins=self.default_profile.margins,
            line_spacing="1.15",
            emphasis_markers=emphasis_markers
        )
    
    def _extract_section_order(self, lines: List[str]) -> List[str]:
        common_sections = [
            "CONTACT", "SUMMARY", "CAREER SUMMARY", "PROFESSIONAL SUMMARY",
            "SKILLS", "TECHNICAL SKILLS", "CORE COMPETENCIES",
            "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE",
            "EDUCATION", "ACADEMIC BACKGROUND", "QUALIFICATIONS",
            "CERTIFICATIONS", "PROJECTS", "ACHIEVEMENTS"
        ]
        
        found_sections = []
        for line in lines:
            line_upper = line.upper()
            for section in common_sections:
                if section in line_upper and section not in found_sections:
                    found_sections.append(section)
        
        if not found_sections:
            return self.default_profile.section_order
        
        return found_sections[:5]
    
    def _detect_bullet_style(self, lines: List[str]) -> str:
        bullet_patterns = {
            '•': r'^\s*•',
            '○': r'^\s*○',
            '-': r'^\s*-\s',
            '*': r'^\s*\*\s',
            '→': r'^\s*→',
            '▪': r'^\s*▪'
        }
        
        bullet_counts = {}
        for line in lines:
            for bullet, pattern in bullet_patterns.items():
                if re.match(pattern, line):
                    bullet_counts[bullet] = bullet_counts.get(bullet, 0) + 1
        
        if bullet_counts:
            return max(bullet_counts, key=bullet_counts.get)
        return self.default_profile.bullet_style
    
    def _detect_heading_format(self, lines: List[str]) -> str:
        heading_patterns = []
        potential_headings = [line for line in lines if len(line) < 50 and line.isupper()]
        
        if len(potential_headings) > 2:
            return "ALL_CAPS"
        
        title_case_headings = [line for line in lines if line.istitle() and len(line.split()) <= 4]
        if len(title_case_headings) > 2:
            return "Title_Case"
        
        return "ALL_CAPS"
    
    def _detect_contact_format(self, lines: List[str]) -> str:
        top_lines = lines[:10]
        
        for line in top_lines:
            if '@' in line and ('|' in line or '•' in line or len(line.split()) > 4):
                return "horizontal"
        
        email_line = -1
        phone_line = -1
        for i, line in enumerate(top_lines):
            if '@' in line:
                email_line = i
            if re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', line):
                phone_line = i
        
        if email_line != -1 and phone_line != -1 and abs(email_line - phone_line) <= 2:
            return "vertical"
        
        return "horizontal"
    
    def _detect_date_format(self, lines: List[str]) -> str:
        date_patterns = {
            "MM/YYYY - MM/YYYY": r'\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{4}',
            "Mon YYYY - Mon YYYY": r'[A-Za-z]{3,9}\s+\d{4}\s*-\s*[A-Za-z]{3,9}\s+\d{4}',
            "YYYY-YYYY": r'\d{4}\s*-\s*\d{4}',
            "MM.YYYY - MM.YYYY": r'\d{1,2}\.\d{4}\s*-\s*\d{1,2}\.\d{4}'
        }
        
        for line in lines:
            for format_name, pattern in date_patterns.items():
                if re.search(pattern, line):
                    return format_name
        
        return self.default_profile.date_format
    
    def _detect_emphasis_markers(self, lines: List[str]) -> List[str]:
        emphasis_patterns = []
        
        for line in lines:
            if '**' in line:
                emphasis_patterns.append('**')
            if re.search(r'\*[^*]+\*', line):
                emphasis_patterns.append('*')
            if line.isupper() and len(line.split()) <= 6:
                emphasis_patterns.append('UPPERCASE')
        
        return list(set(emphasis_patterns)) if emphasis_patterns else ["**"]
    
    def save_style_profile(self, profile: StyleProfile, file_path: str) -> None:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(profile), f, indent=2, ensure_ascii=False)
            logger.info(f"Style profile saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving style profile: {e}")
    
    def load_style_profile(self, file_path: str) -> StyleProfile:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return StyleProfile(**data)
        except Exception as e:
            logger.error(f"Error loading style profile: {e}")
            return self.default_profile
    
    def get_style_summary(self, profile: StyleProfile) -> str:
        return f"""
Style Profile Summary:
• Sections: {', '.join(profile.section_order[:3])}...
• Bullets: {profile.bullet_style}
• Headers: {profile.heading_format}
• Contact: {profile.contact_format}
• Dates: {profile.date_format}
        """.strip()

@st.cache_resource
def get_style_extractor():
    return StyleExtractor()