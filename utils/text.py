import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TextStats:
    word_count: int
    char_count: int
    sentence_count: int
    paragraph_count: int
    bullet_count: int

class TextProcessor:
    def __init__(self):
        self.bullet_patterns = [
            r'^\s*[•\-\*○▪]\s+',
            r'^\s*\d+\.\s+', 
            r'^\s*[a-zA-Z]\.\s+'
        ]
    
    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        
        text = re.sub(r'\x00', '', text)
        
        text = re.sub(r'\s+', ' ', text)
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.isspace():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def extract_bullets(self, text: str) -> List[str]:
        bullets = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            for pattern in self.bullet_patterns:
                if re.match(pattern, line):
                    bullet_text = re.sub(pattern, '', line).strip()
                    if bullet_text:
                        bullets.append(bullet_text)
                    break
        
        return bullets
    
    def format_bullets(self, bullets: List[str], bullet_style: str = "•") -> str:
        if not bullets:
            return ""
        
        formatted_bullets = []
        for bullet in bullets:
            if not bullet.strip():
                continue
            formatted_bullets.append(f"{bullet_style} {bullet.strip()}")
        
        return '\n'.join(formatted_bullets)
    
    def extract_sar_bullets(self, text: str) -> List[Dict[str, str]]:
        sar_bullets = []
        lines = text.split('\n')
        
        sar_pattern = r'^\s*[•\-\*]?\s*(\w+\s+\w+):\s*(.+)$'
        
        for line in lines:
            match = re.match(sar_pattern, line.strip())
            if match:
                heading = match.group(1).strip()
                content = match.group(2).strip()
                
                if len(heading.split()) == 2:
                    sar_bullets.append({
                        "heading": heading,
                        "content": content,
                        "full_text": line.strip()
                    })
        
        return sar_bullets
    
    def validate_sar_format(self, bullets: List[str]) -> Dict[str, Any]:
        sar_bullets = []
        two_word_headings = 0
        
        for bullet in bullets:
            sar_match = re.match(r'^\s*[•\-\*]?\s*(\w+\s+\w+):\s*(.+)', bullet.strip())
            if sar_match:
                heading = sar_match.group(1).strip()
                content = sar_match.group(2).strip()
                
                sar_bullets.append({
                    "heading": heading,
                    "content": content,
                    "is_two_word": len(heading.split()) == 2
                })
                
                if len(heading.split()) == 2:
                    two_word_headings += 1
        
        return {
            "total_bullets": len(bullets),
            "sar_formatted": len(sar_bullets),
            "two_word_headings": two_word_headings,
            "valid": len(sar_bullets) == 8 and two_word_headings == 8,
            "sar_bullets": sar_bullets
        }
    
    def extract_skills(self, text: str, max_skills: int = 10, max_words_per_skill: int = 2) -> List[str]:
        skills = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            if any(re.match(pattern, line) for pattern in self.bullet_patterns):
                skill = re.sub(r'^\s*[•\-\*○▪]\s*', '', line).strip()
                if skill and len(skill.split()) <= max_words_per_skill:
                    skills.append(skill)
            
            elif ',' in line:
                line_skills = [s.strip() for s in line.split(',')]
                for skill in line_skills:
                    if skill and len(skill.split()) <= max_words_per_skill:
                        skills.append(skill)
            
            elif '|' in line:
                line_skills = [s.strip() for s in line.split('|')]
                for skill in line_skills:
                    if skill and len(skill.split()) <= max_words_per_skill:
                        skills.append(skill)
            
            elif line and len(line.split()) <= max_words_per_skill:
                skills.append(line)
        
        unique_skills = []
        seen = set()
        for skill in skills:
            skill_lower = skill.lower()
            if skill_lower not in seen:
                unique_skills.append(skill)
                seen.add(skill_lower)
                if len(unique_skills) >= max_skills:
                    break
        
        return unique_skills
    
    def count_words(self, text: str) -> int:
        if not text:
            return 0
        
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        words = clean_text.split()
        return len([word for word in words if word.strip()])
    
    def get_text_stats(self, text: str) -> TextStats:
        if not text:
            return TextStats(0, 0, 0, 0, 0)
        
        word_count = self.count_words(text)
        char_count = len(text.strip())
        
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        paragraphs = text.split('\n\n')
        paragraph_count = len([p for p in paragraphs if p.strip()])
        
        bullets = self.extract_bullets(text)
        bullet_count = len(bullets)
        
        return TextStats(
            word_count=word_count,
            char_count=char_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            bullet_count=bullet_count
        )
    
    def truncate_text(self, text: str, max_words: int, add_ellipsis: bool = True) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        
        truncated = ' '.join(words[:max_words])
        if add_ellipsis:
            truncated += "..."
        
        return truncated
    
    def extract_section_content(self, text: str, section_name: str) -> Optional[str]:
        section_patterns = [
            rf'#{1,3}\s*{re.escape(section_name)}\s*\n(.*?)(?=\n#{1,3}\s|\Z)',
            rf'{re.escape(section_name.upper())}\s*\n(.*?)(?=\n[A-Z\s]+\n|\Z)',
            rf'{re.escape(section_name)}\s*:?\s*\n(.*?)(?=\n\w+.*?:\s*\n|\Z)'
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def normalize_spacing(self, text: str, line_spacing: str = "single") -> str:
        if line_spacing == "single":
            text = re.sub(r'\n\s*\n', '\n\n', text)
        elif line_spacing == "double":
            text = re.sub(r'\n\s*\n', '\n\n\n\n', text)
        
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n[ \t]+', '\n', text)
        
        return text.strip()
    
    def apply_emphasis(self, text: str, emphasis_style: str = "**") -> str:
        if emphasis_style == "**":
            text = re.sub(r'\*\*(.*?)\*\*', r'**\1**', text)
        elif emphasis_style == "*":
            text = re.sub(r'\*(.*?)\*', r'*\1*', text)
        elif emphasis_style.upper() == "UPPERCASE":
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            text = text.upper()
        
        return text

class ContentValidator:
    def __init__(self):
        self.text_processor = TextProcessor()
    
    def validate_career_summary(self, text: str, max_words: int = 40) -> Dict[str, Any]:
        stats = self.text_processor.get_text_stats(text)
        
        return {
            "valid": stats.word_count <= max_words,
            "word_count": stats.word_count,
            "max_words": max_words,
            "message": f"Career summary: {stats.word_count}/{max_words} words",
            "text": text
        }
    
    def validate_skills_list(self, skills: List[str], required_count: int = 10, 
                           max_words_per_skill: int = 2) -> Dict[str, Any]:
        valid_skills = [s for s in skills if len(s.split()) <= max_words_per_skill]
        
        return {
            "valid": len(valid_skills) == required_count,
            "skill_count": len(valid_skills),
            "required_count": required_count,
            "invalid_skills": [s for s in skills if len(s.split()) > max_words_per_skill],
            "message": f"Skills: {len(valid_skills)}/{required_count} valid skills",
            "skills": valid_skills
        }
    
    def validate_cover_letter(self, text: str, max_words: int = 250, 
                            min_paragraphs: int = 3, max_paragraphs: int = 4) -> Dict[str, Any]:
        stats = self.text_processor.get_text_stats(text)
        
        return {
            "valid": (stats.word_count <= max_words and 
                     min_paragraphs <= stats.paragraph_count <= max_paragraphs),
            "word_count": stats.word_count,
            "max_words": max_words,
            "paragraph_count": stats.paragraph_count,
            "min_paragraphs": min_paragraphs,
            "max_paragraphs": max_paragraphs,
            "message": f"Cover letter: {stats.word_count}/{max_words} words, {stats.paragraph_count} paragraphs",
            "text": text
        }