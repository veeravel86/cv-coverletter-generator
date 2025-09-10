import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json

import streamlit as st
from jinja2 import Environment, FileSystemLoader, Template

from services.style_extract import StyleProfile

logger = logging.getLogger(__name__)

class MarkdownExporter:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
    def parse_cv_content(self, cv_content: str) -> Dict[str, Any]:
        sections = {}
        current_section = None
        current_content = []
        
        lines = cv_content.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            line_upper = line_stripped.upper()
            
            if self._is_section_header(line_upper):
                if current_section:
                    sections[current_section] = self._parse_section_content(
                        current_section, '\n'.join(current_content)
                    )
                current_section = self._normalize_section_name(line_upper)
                current_content = []
            else:
                if current_section and line_stripped:
                    current_content.append(line_stripped)
        
        if current_section and current_content:
            sections[current_section] = self._parse_section_content(
                current_section, '\n'.join(current_content)
            )
        
        return self._structure_parsed_data(sections)
    
    def _is_section_header(self, line: str) -> bool:
        section_indicators = [
            'CAREER SUMMARY', 'PROFESSIONAL SUMMARY', 'SUMMARY',
            'SKILLS', 'TECHNICAL SKILLS', 'CORE COMPETENCIES',
            'EXPERIENCE', 'WORK EXPERIENCE', 'PROFESSIONAL EXPERIENCE',
            'EDUCATION', 'ACADEMIC BACKGROUND',
            'CERTIFICATIONS', 'CERTIFICATES'
        ]
        
        return any(indicator in line for indicator in section_indicators)
    
    def _normalize_section_name(self, section_header: str) -> str:
        mappings = {
            'CAREER SUMMARY': 'career_summary',
            'PROFESSIONAL SUMMARY': 'career_summary',
            'SUMMARY': 'career_summary',
            'SKILLS': 'skills',
            'TECHNICAL SKILLS': 'skills',
            'CORE COMPETENCIES': 'skills',
            'EXPERIENCE': 'experience',
            'WORK EXPERIENCE': 'experience',
            'PROFESSIONAL EXPERIENCE': 'experience',
            'EDUCATION': 'education',
            'ACADEMIC BACKGROUND': 'education',
            'CERTIFICATIONS': 'certifications',
            'CERTIFICATES': 'certifications'
        }
        
        for key, value in mappings.items():
            if key in section_header:
                return value
        
        return section_header.lower().replace(' ', '_')
    
    def _parse_section_content(self, section_type: str, content: str) -> Any:
        if section_type == 'career_summary':
            return content.strip()
        
        elif section_type == 'skills':
            return self._parse_skills(content)
        
        elif section_type == 'experience':
            return self._parse_experience(content)
        
        elif section_type == 'education':
            return self._parse_education(content)
        
        elif section_type == 'certifications':
            return self._parse_certifications(content)
        
        else:
            return content.strip()
    
    def _parse_skills(self, content: str) -> list:
        skills = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith(('•', '-', '*', '○', '▪')):
                skill = line[1:].strip()
                if skill:
                    skills.append(skill)
            elif line and not line.startswith(('•', '-', '*')):
                if ',' in line:
                    line_skills = [s.strip() for s in line.split(',') if s.strip()]
                    skills.extend(line_skills)
                elif '|' in line:
                    line_skills = [s.strip() for s in line.split('|') if s.strip()]
                    skills.extend(line_skills)
                else:
                    skills.append(line)
        
        return skills[:10]
    
    def _parse_experience(self, content: str) -> list:
        jobs = []
        lines = content.split('\n')
        current_job = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if '|' in line and not line.startswith(('•', '-', '*')):
                if current_job:
                    jobs.append(current_job)
                
                parts = [p.strip() for p in line.split('|')]
                current_job = {
                    'title': parts[0] if len(parts) > 0 else '',
                    'company': parts[1] if len(parts) > 1 else '',
                    'dates': parts[2] if len(parts) > 2 else '',
                    'bullets': []
                }
            
            elif line.startswith(('•', '-', '*', '○', '▪')) and current_job:
                bullet = line[1:].strip()
                if bullet:
                    current_job['bullets'].append(bullet)
        
        if current_job:
            jobs.append(current_job)
        
        return jobs
    
    def _parse_education(self, content: str) -> list:
        education = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and '|' in line:
                parts = [p.strip() for p in line.split('|')]
                edu_entry = {
                    'degree': parts[0] if len(parts) > 0 else '',
                    'institution': parts[1] if len(parts) > 1 else '',
                    'year': parts[2] if len(parts) > 2 else '',
                    'details': ''
                }
                education.append(edu_entry)
        
        return education
    
    def _parse_certifications(self, content: str) -> list:
        certs = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith(('•', '-', '*', '○', '▪')):
                cert = line[1:].strip()
                if cert:
                    certs.append(cert)
            elif line:
                certs.append(line)
        
        return certs
    
    def _structure_parsed_data(self, sections: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'name': 'Generated CV',
            'contact_info': {
                'email': 'email@example.com',
                'phone': '(123) 456-7890',
                'location': 'City, State',
                'linkedin': 'linkedin.com/in/profile'
            },
            'career_summary': sections.get('career_summary', ''),
            'skills': sections.get('skills', []),
            'experience': sections.get('experience', []),
            'education': sections.get('education', []),
            'certifications': sections.get('certifications', [])
        }
    
    def format_with_style(self, cv_data: Dict[str, Any], style_profile: StyleProfile, 
                         template_name: str = "cv_default.jinja.md") -> str:
        try:
            template = self.jinja_env.get_template(template_name)
            
            formatted_data = cv_data.copy()
            formatted_data['style'] = {
                'bullet_style': style_profile.bullet_style,
                'heading_format': style_profile.heading_format,
                'contact_format': style_profile.contact_format,
                'date_format': style_profile.date_format
            }
            
            formatted_cv = template.render(**formatted_data)
            
            return self._apply_style_formatting(formatted_cv, style_profile)
            
        except Exception as e:
            logger.error(f"Error formatting CV with template: {e}")
            return self._create_fallback_format(cv_data, style_profile)
    
    def _apply_style_formatting(self, content: str, style_profile: StyleProfile) -> str:
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            if line.strip().startswith('##') and style_profile.heading_format == "ALL_CAPS":
                header_text = line.replace('##', '').strip()
                formatted_lines.append(f"## {header_text.upper()}")
            elif line.strip().startswith('##') and style_profile.heading_format == "Title_Case":
                header_text = line.replace('##', '').strip()
                formatted_lines.append(f"## {header_text.title()}")
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _create_fallback_format(self, cv_data: Dict[str, Any], style_profile: StyleProfile) -> str:
        bullet = style_profile.bullet_style
        
        sections = []
        
        if cv_data.get('name'):
            sections.append(f"# {cv_data['name']}")
        
        if cv_data.get('contact_info'):
            sections.append("## CONTACT INFORMATION")
            contact = cv_data['contact_info']
            if style_profile.contact_format == "horizontal":
                contact_line = f"{contact.get('email', '')} {bullet} {contact.get('phone', '')} {bullet} {contact.get('location', '')}"
                if contact.get('linkedin'):
                    contact_line += f" {bullet} {contact['linkedin']}"
                sections.append(contact_line)
            else:
                sections.extend([
                    f"**Email:** {contact.get('email', '')}",
                    f"**Phone:** {contact.get('phone', '')}",
                    f"**Location:** {contact.get('location', '')}"
                ])
                if contact.get('linkedin'):
                    sections.append(f"**LinkedIn:** {contact['linkedin']}")
        
        if cv_data.get('career_summary'):
            sections.append("## CAREER SUMMARY")
            sections.append(cv_data['career_summary'])
        
        if cv_data.get('skills'):
            sections.append("## SKILLS")
            for skill in cv_data['skills']:
                sections.append(f"{bullet} {skill}")
        
        if cv_data.get('experience'):
            sections.append("## EXPERIENCE")
            for job in cv_data['experience']:
                job_header = f"**{job.get('title', '')}** | {job.get('company', '')} | {job.get('dates', '')}"
                sections.append(job_header)
                sections.append("")
                for bullet_point in job.get('bullets', []):
                    sections.append(f"{bullet} {bullet_point}")
                sections.append("")
        
        if cv_data.get('education'):
            sections.append("## EDUCATION")
            for edu in cv_data['education']:
                edu_line = f"**{edu.get('degree', '')}** | {edu.get('institution', '')} | {edu.get('year', '')}"
                sections.append(edu_line)
                if edu.get('details'):
                    sections.append(edu['details'])
                sections.append("")
        
        if cv_data.get('certifications'):
            sections.append("## CERTIFICATIONS")
            for cert in cv_data['certifications']:
                sections.append(f"{bullet} {cert}")
        
        return '\n'.join(sections)
    
    def export_cv(self, cv_content: str, style_profile: StyleProfile, 
                  output_path: str, template_name: str = "cv_default.jinja.md") -> str:
        try:
            cv_data = self.parse_cv_content(cv_content)
            formatted_cv = self.format_with_style(cv_data, style_profile, template_name)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_cv)
            
            logger.info(f"CV exported to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting CV to markdown: {e}")
            raise e

@st.cache_resource
def get_markdown_exporter():
    return MarkdownExporter()