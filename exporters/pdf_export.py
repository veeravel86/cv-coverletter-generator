import os
import logging
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

import streamlit as st
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import black, darkblue

from services.style_extract import StyleProfile

logger = logging.getLogger(__name__)

class PDFExporter:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        # Custom styles for CV formatting
        self.styles.add(ParagraphStyle(
            name='CVTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=12,
            textColor=darkblue,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CVHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=6,
            textColor=darkblue,
            leftIndent=0
        ))
        
        self.styles.add(ParagraphStyle(
            name='CVContact',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CVBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY
        ))
        
        self.styles.add(ParagraphStyle(
            name='CVBullet',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=4,
            leftIndent=0.25*inch,
            bulletIndent=0.1*inch
        ))
        
        self.styles.add(ParagraphStyle(
            name='JobTitle',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceBefore=6,
            spaceAfter=3,
            textColor=darkblue
        ))
    
    def _parse_markdown_cv(self, cv_content: str) -> Dict[str, Any]:
        sections = {}
        current_section = None
        current_content = []
        
        lines = cv_content.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith('#'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                
                if line_stripped.startswith('# '):
                    sections['name'] = line_stripped[2:].strip()
                    current_section = None
                    current_content = []
                elif line_stripped.startswith('## '):
                    current_section = line_stripped[3:].strip().lower().replace(' ', '_')
                    current_content = []
            else:
                if current_section and line_stripped:
                    current_content.append(line_stripped)
        
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _add_contact_section(self, story: List, contact_text: str, style_profile: StyleProfile):
        if not contact_text:
            return
        
        # Clean up contact text and format it
        contact_lines = [line.strip() for line in contact_text.split('\n') if line.strip()]
        
        if style_profile.contact_format == "horizontal":
            # Join all contact info on one line
            contact_info = " | ".join(contact_lines)
            story.append(Paragraph(contact_info, self.styles['CVContact']))
        else:
            # Vertical contact format
            for line in contact_lines:
                if line.startswith('**') and line.endswith('**'):
                    clean_line = line.replace('**', '')
                else:
                    clean_line = line
                story.append(Paragraph(clean_line, self.styles['CVContact']))
        
        story.append(Spacer(1, 0.2*inch))
    
    def _add_section_heading(self, story: List, heading: str):
        story.append(Paragraph(heading.upper(), self.styles['CVHeading']))
    
    def _add_career_summary(self, story: List, summary_text: str):
        if not summary_text:
            return
        
        story.append(Paragraph(summary_text, self.styles['CVBody']))
        story.append(Spacer(1, 0.15*inch))
    
    def _add_skills_section(self, story: List, skills_text: str, style_profile: StyleProfile):
        if not skills_text:
            return
        
        lines = skills_text.split('\n')
        skills = []
        
        for line in lines:
            line = line.strip()
            if line.startswith(('•', '-', '*', '○', '▪')):
                skill = line[1:].strip()
                if skill:
                    skills.append(skill)
        
        # Format skills in rows of 3
        skills_per_row = 3
        for i in range(0, len(skills), skills_per_row):
            row_skills = skills[i:i + skills_per_row]
            skills_line = f" {style_profile.bullet_style} ".join(row_skills)
            story.append(Paragraph(f"{style_profile.bullet_style} {skills_line}", self.styles['CVBullet']))
        
        story.append(Spacer(1, 0.1*inch))
    
    def _add_experience_section(self, story: List, experience_text: str, style_profile: StyleProfile):
        if not experience_text:
            return
        
        lines = experience_text.split('\n')
        current_job_elements = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '|' in line and not line.startswith(('•', '-', '*', '**')):
                # Add previous job if exists
                if current_job_elements:
                    job_group = KeepTogether(current_job_elements)
                    story.append(job_group)
                    story.append(Spacer(1, 0.1*inch))
                    current_job_elements = []
                
                # Parse job title line
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    job_title = f"<b>{parts[0]}</b> | {parts[1]}"
                    if len(parts) >= 3:
                        job_title += f" | <i>{parts[2]}</i>"
                    
                    current_job_elements.append(Paragraph(job_title, self.styles['JobTitle']))
            
            elif line.startswith(('•', '-', '*', '○', '▪')):
                bullet_text = line[1:].strip()
                if bullet_text:
                    bullet_para = Paragraph(f"{style_profile.bullet_style} {bullet_text}", self.styles['CVBullet'])
                    current_job_elements.append(bullet_para)
        
        # Add the last job
        if current_job_elements:
            job_group = KeepTogether(current_job_elements)
            story.append(job_group)
    
    def _add_education_section(self, story: List, education_text: str):
        if not education_text:
            return
        
        lines = education_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and '|' in line:
                parts = [p.strip() for p in line.split('|')]
                
                if len(parts) >= 1:
                    edu_text = f"<b>{parts[0]}</b>"
                
                if len(parts) >= 2:
                    edu_text += f" | {parts[1]}"
                
                if len(parts) >= 3:
                    edu_text += f" | <i>{parts[2]}</i>"
                
                story.append(Paragraph(edu_text, self.styles['CVBody']))
                story.append(Spacer(1, 0.05*inch))
    
    def _add_certifications_section(self, story: List, certs_text: str, style_profile: StyleProfile):
        if not certs_text:
            return
        
        lines = certs_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith(('•', '-', '*', '○', '▪')):
                cert_text = line[1:].strip()
                if cert_text:
                    story.append(Paragraph(f"{style_profile.bullet_style} {cert_text}", self.styles['CVBullet']))
            elif line:
                story.append(Paragraph(f"{style_profile.bullet_style} {line}", self.styles['CVBullet']))
    
    def export_to_pdf(self, cv_content: str, style_profile: StyleProfile, 
                      output_path: str, name: str = None) -> str:
        try:
            # Create PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=1*inch,
                bottomMargin=1*inch
            )
            
            story = []
            
            # Parse CV content
            sections = self._parse_markdown_cv(cv_content)
            
            # Add title
            if name or sections.get('name'):
                story.append(Paragraph(name or sections.get('name', 'CV'), self.styles['CVTitle']))
                story.append(Spacer(1, 0.2*inch))
            
            # Define section order
            section_order = [
                ('contact_information', 'CONTACT INFORMATION'),
                ('career_summary', 'CAREER SUMMARY'),
                ('skills', 'SKILLS'),
                ('experience', 'EXPERIENCE'),
                ('education', 'EDUCATION'),
                ('certifications', 'CERTIFICATIONS')
            ]
            
            # Add sections
            for section_key, section_title in section_order:
                if section_key in sections:
                    self._add_section_heading(story, section_title)
                    
                    if section_key == 'contact_information':
                        self._add_contact_section(story, sections[section_key], style_profile)
                    elif section_key == 'career_summary':
                        self._add_career_summary(story, sections[section_key])
                    elif section_key == 'skills':
                        self._add_skills_section(story, sections[section_key], style_profile)
                    elif section_key == 'experience':
                        self._add_experience_section(story, sections[section_key], style_profile)
                    elif section_key == 'education':
                        self._add_education_section(story, sections[section_key])
                    elif section_key == 'certifications':
                        self._add_certifications_section(story, sections[section_key], style_profile)
            
            # Build PDF
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            doc.build(story)
            
            logger.info(f"CV exported to PDF: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting to PDF: {e}")
            raise e
    
    def export_cover_letter_to_pdf(self, cover_letter_content: str, 
                                   output_path: str, applicant_name: str = None) -> str:
        try:
            # Create PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=1*inch,
                leftMargin=1*inch,
                topMargin=1*inch,
                bottomMargin=1*inch
            )
            
            story = []
            
            # Add applicant name if provided
            if applicant_name:
                story.append(Paragraph(applicant_name, self.styles['CVTitle']))
                story.append(Spacer(1, 0.3*inch))
            
            # Add cover letter content
            paragraphs = cover_letter_content.split('\n\n')
            
            for para_text in paragraphs:
                para_text = para_text.strip()
                if para_text:
                    story.append(Paragraph(para_text, self.styles['CVBody']))
                    story.append(Spacer(1, 0.2*inch))
            
            # Build PDF
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            doc.build(story)
            
            logger.info(f"Cover letter exported to PDF: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting cover letter to PDF: {e}")
            raise e

@st.cache_resource
def get_pdf_exporter():
    return PDFExporter()