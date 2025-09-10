import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class StyleMetrics:
    consistency_score: float
    section_alignment: float
    formatting_uniformity: float
    overall_score: float

class StyleMatcher:
    def __init__(self):
        self.style_templates = {
            "professional": {
                "bullet_style": "•",
                "heading_format": "ALL_CAPS",
                "contact_format": "horizontal",
                "emphasis_style": "**bold**"
            },
            "modern": {
                "bullet_style": "→",
                "heading_format": "Title_Case", 
                "contact_format": "vertical",
                "emphasis_style": "*italic*"
            },
            "classic": {
                "bullet_style": "-",
                "heading_format": "ALL_CAPS",
                "contact_format": "block",
                "emphasis_style": "**BOLD**"
            }
        }
    
    def detect_style_category(self, sample_text: str) -> str:
        scores = {}
        
        for style_name, style_config in self.style_templates.items():
            score = self._calculate_style_match_score(sample_text, style_config)
            scores[style_name] = score
        
        return max(scores, key=scores.get)
    
    def _calculate_style_match_score(self, text: str, style_config: Dict[str, str]) -> float:
        score = 0.0
        
        if style_config["bullet_style"] in text:
            score += 0.25
        
        heading_format = style_config["heading_format"]
        if heading_format == "ALL_CAPS":
            caps_headers = len(re.findall(r'\n[A-Z\s]{3,20}\n', text))
            if caps_headers > 0:
                score += 0.25
        elif heading_format == "Title_Case":
            title_headers = len(re.findall(r'\n[A-Z][a-z]+\s+[A-Z][a-z]+\n', text))
            if title_headers > 0:
                score += 0.25
        
        contact_format = style_config["contact_format"]
        if contact_format == "horizontal" and ('•' in text[:500] or '|' in text[:500]):
            score += 0.25
        elif contact_format == "vertical":
            email_line = text.find('@')
            phone_line = text.find('(') or text.find('-', email_line)
            if email_line != -1 and phone_line != -1 and abs(email_line - phone_line) > 20:
                score += 0.25
        
        emphasis_style = style_config["emphasis_style"]
        if "**" in emphasis_style and "**" in text:
            score += 0.25
        elif "*" in emphasis_style and "*" in text:
            score += 0.25
        
        return score
    
    def extract_formatting_patterns(self, text: str) -> Dict[str, Any]:
        patterns = {
            "bullet_styles": self._extract_bullet_patterns(text),
            "heading_patterns": self._extract_heading_patterns(text),
            "contact_pattern": self._extract_contact_pattern(text),
            "date_patterns": self._extract_date_patterns(text),
            "emphasis_patterns": self._extract_emphasis_patterns(text),
            "spacing_patterns": self._extract_spacing_patterns(text)
        }
        
        return patterns
    
    def _extract_bullet_patterns(self, text: str) -> List[str]:
        bullet_regex = [
            (r'^\s*•\s', '•'),
            (r'^\s*○\s', '○'),
            (r'^\s*-\s', '-'),
            (r'^\s*\*\s', '*'),
            (r'^\s*→\s', '→'),
            (r'^\s*▪\s', '▪')
        ]
        
        found_bullets = []
        lines = text.split('\n')
        
        for line in lines:
            for pattern, bullet_char in bullet_regex:
                if re.match(pattern, line):
                    found_bullets.append(bullet_char)
                    break
        
        return list(set(found_bullets))
    
    def _extract_heading_patterns(self, text: str) -> Dict[str, int]:
        patterns = {
            "all_caps": len(re.findall(r'^[A-Z\s]{3,30}$', text, re.MULTILINE)),
            "title_case": len(re.findall(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', text, re.MULTILINE)),
            "markdown_h2": len(re.findall(r'^## .+$', text, re.MULTILINE)),
            "markdown_h3": len(re.findall(r'^### .+$', text, re.MULTILINE))
        }
        
        return patterns
    
    def _extract_contact_pattern(self, text: str) -> str:
        top_section = text[:500]
        
        if '@' in top_section:
            email_line_idx = top_section.find('@')
            email_line_start = top_section.rfind('\n', 0, email_line_idx)
            email_line_end = top_section.find('\n', email_line_idx)
            
            if email_line_end == -1:
                email_line_end = len(top_section)
            
            email_line = top_section[email_line_start:email_line_end]
            
            if '•' in email_line or '|' in email_line:
                return "horizontal"
            
            phone_indicators = ['(', ')', '-', '+1', 'phone', 'mobile']
            next_lines = top_section[email_line_end:email_line_end+200]
            
            if any(indicator in next_lines.lower() for indicator in phone_indicators):
                return "vertical"
        
        return "block"
    
    def _extract_date_patterns(self, text: str) -> List[str]:
        date_patterns = [
            (r'\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{4}', 'MM/YYYY - MM/YYYY'),
            (r'[A-Za-z]{3,9}\s+\d{4}\s*-\s*[A-Za-z]{3,9}\s+\d{4}', 'Mon YYYY - Mon YYYY'),
            (r'\d{4}\s*-\s*\d{4}', 'YYYY - YYYY'),
            (r'\d{1,2}\.\d{4}\s*-\s*\d{1,2}\.\d{4}', 'MM.YYYY - MM.YYYY')
        ]
        
        found_patterns = []
        for pattern, format_name in date_patterns:
            if re.search(pattern, text):
                found_patterns.append(format_name)
        
        return found_patterns
    
    def _extract_emphasis_patterns(self, text: str) -> List[str]:
        patterns = []
        
        if re.search(r'\*\*[^*]+\*\*', text):
            patterns.append('**bold**')
        
        if re.search(r'\*[^*]+\*(?!\*)', text):
            patterns.append('*italic*')
        
        if re.search(r'[A-Z]{3,}', text):
            patterns.append('UPPERCASE')
        
        return patterns
    
    def _extract_spacing_patterns(self, text: str) -> Dict[str, int]:
        return {
            "single_newlines": text.count('\n') - text.count('\n\n'),
            "double_newlines": text.count('\n\n'),
            "triple_newlines": text.count('\n\n\n'),
            "leading_spaces": len(re.findall(r'^\s+', text, re.MULTILINE))
        }
    
    def calculate_style_consistency(self, text: str) -> StyleMetrics:
        patterns = self.extract_formatting_patterns(text)
        
        bullet_consistency = self._calculate_bullet_consistency(patterns["bullet_styles"])
        heading_consistency = self._calculate_heading_consistency(patterns["heading_patterns"])
        format_consistency = self._calculate_format_consistency(patterns)
        
        overall_score = (bullet_consistency + heading_consistency + format_consistency) / 3
        
        return StyleMetrics(
            consistency_score=bullet_consistency,
            section_alignment=heading_consistency,
            formatting_uniformity=format_consistency,
            overall_score=overall_score
        )
    
    def _calculate_bullet_consistency(self, bullet_styles: List[str]) -> float:
        if not bullet_styles:
            return 1.0
        
        if len(bullet_styles) == 1:
            return 1.0
        
        return 1.0 - (len(bullet_styles) - 1) * 0.2
    
    def _calculate_heading_consistency(self, heading_patterns: Dict[str, int]) -> float:
        total_headings = sum(heading_patterns.values())
        if total_headings == 0:
            return 1.0
        
        max_pattern_count = max(heading_patterns.values())
        consistency = max_pattern_count / total_headings
        
        return consistency
    
    def _calculate_format_consistency(self, patterns: Dict[str, Any]) -> float:
        scores = []
        
        date_patterns = patterns["date_patterns"]
        if date_patterns:
            date_consistency = 1.0 if len(date_patterns) == 1 else 0.5
            scores.append(date_consistency)
        
        emphasis_patterns = patterns["emphasis_patterns"]
        if emphasis_patterns:
            emphasis_consistency = 1.0 if len(emphasis_patterns) <= 2 else 0.5
            scores.append(emphasis_consistency)
        
        return sum(scores) / len(scores) if scores else 1.0

class StyleApplicator:
    def __init__(self):
        self.style_matcher = StyleMatcher()
    
    def apply_style_to_content(self, content: str, target_style: Dict[str, str]) -> str:
        styled_content = content
        
        styled_content = self._apply_bullet_style(styled_content, target_style.get("bullet_style", "•"))
        
        styled_content = self._apply_heading_format(styled_content, target_style.get("heading_format", "ALL_CAPS"))
        
        styled_content = self._apply_emphasis_style(styled_content, target_style.get("emphasis_style", "**bold**"))
        
        return styled_content
    
    def _apply_bullet_style(self, text: str, target_bullet: str) -> str:
        bullet_patterns = [r'^\s*[•○\-\*→▪]\s', r'^\s*\d+\.\s']
        
        lines = text.split('\n')
        styled_lines = []
        
        for line in lines:
            styled_line = line
            for pattern in bullet_patterns:
                if re.match(pattern, line):
                    styled_line = re.sub(pattern, f'{target_bullet} ', line)
                    break
            styled_lines.append(styled_line)
        
        return '\n'.join(styled_lines)
    
    def _apply_heading_format(self, text: str, target_format: str) -> str:
        lines = text.split('\n')
        styled_lines = []
        
        heading_pattern = r'^#{1,3}\s*(.+)$'
        
        for line in lines:
            match = re.match(heading_pattern, line)
            if match:
                heading_text = match.group(1).strip()
                heading_level = len(line) - len(line.lstrip('#'))
                
                if target_format == "ALL_CAPS":
                    formatted_heading = heading_text.upper()
                elif target_format == "Title_Case":
                    formatted_heading = heading_text.title()
                elif target_format == "lowercase":
                    formatted_heading = heading_text.lower()
                else:
                    formatted_heading = heading_text
                
                styled_line = '#' * heading_level + ' ' + formatted_heading
                styled_lines.append(styled_line)
            else:
                styled_lines.append(line)
        
        return '\n'.join(styled_lines)
    
    def _apply_emphasis_style(self, text: str, target_emphasis: str) -> str:
        if target_emphasis == "**bold**":
            text = re.sub(r'\*([^*]+)\*(?!\*)', r'**\1**', text)
        elif target_emphasis == "*italic*":
            text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
        elif target_emphasis.upper() == "UPPERCASE":
            text = re.sub(r'\*\*([^*]+)\*\*', lambda m: m.group(1).upper(), text)
            text = re.sub(r'\*([^*]+)\*', lambda m: m.group(1).upper(), text)
        
        return text
    
    def match_sample_style(self, content: str, sample_style_profile: Dict[str, Any]) -> str:
        target_style = {
            "bullet_style": sample_style_profile.get("bullet_style", "•"),
            "heading_format": sample_style_profile.get("heading_format", "ALL_CAPS"),
            "emphasis_style": sample_style_profile.get("emphasis_markers", ["**"])[0] if sample_style_profile.get("emphasis_markers") else "**bold**"
        }
        
        return self.apply_style_to_content(content, target_style)
    
    def generate_style_report(self, original_text: str, styled_text: str) -> Dict[str, Any]:
        original_patterns = self.style_matcher.extract_formatting_patterns(original_text)
        styled_patterns = self.style_matcher.extract_formatting_patterns(styled_text)
        
        original_metrics = self.style_matcher.calculate_style_consistency(original_text)
        styled_metrics = self.style_matcher.calculate_style_consistency(styled_text)
        
        return {
            "original_patterns": original_patterns,
            "styled_patterns": styled_patterns,
            "original_consistency": asdict(original_metrics),
            "styled_consistency": asdict(styled_metrics),
            "improvement": styled_metrics.overall_score - original_metrics.overall_score
        }