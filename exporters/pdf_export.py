import os
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

import streamlit as st
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import black, darkblue, HexColor

from services.style_extract import StyleProfile

logger = logging.getLogger(__name__)

class PDFExporter:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)
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
    
    def create_professional_cv_pdf(self, cv_content: str, contact_info: Dict[str, str], 
                                  color_scheme: str = "teal") -> str:
        """Create a professionally formatted CV PDF with the specified design"""
        
        try:
            # Validate input parameters
            if not cv_content or not cv_content.strip():
                raise ValueError("CV content is empty or None")
            
            if not contact_info or not contact_info.get('name'):
                raise ValueError("Contact information missing or invalid")
            
            if len(cv_content.strip()) < 50:
                raise ValueError(f"CV content too short ({len(cv_content)} characters)")
            
            # Setup color scheme
            colors = self._get_color_scheme(color_scheme)
            
            # Create output path
            outputs_dir = Path("outputs")
            outputs_dir.mkdir(exist_ok=True)
            output_path = outputs_dir / f"Professional_CV_{contact_info['name'].replace(' ', '_')}.pdf"
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=0.7*inch,
                leftMargin=0.7*inch,
                topMargin=0.8*inch,
                bottomMargin=0.8*inch
            )
            
            story = []
            
            # Setup professional styles
            prof_styles = self._create_professional_styles(colors)
            
            # 1. Header Section - Single line contact info
            contact_header = self._format_contact_header(contact_info)
            story.append(Paragraph(contact_header, prof_styles['ContactHeader']))
            story.append(Spacer(1, 0.3*inch))
            
            # Parse CV sections
            sections = self._parse_professional_cv_sections(cv_content)
            
            # 2. Professional Summary (≤30 words)
            if 'summary' in sections:
                story.append(Paragraph("PROFESSIONAL SUMMARY", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph(sections['summary'], prof_styles['BodyText']))
                story.append(Spacer(1, 0.2*inch))
            
            # 3. Skills Section - Visual boxes, 4 per row
            if 'skills' in sections:
                story.append(Paragraph("CORE SKILLS", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                self._add_skills_boxes(story, sections['skills'], prof_styles, colors)
                story.append(Spacer(1, 0.2*inch))
            
            # 4. Experience Section - Two-Tier System
            if 'experience' in sections:
                story.append(Paragraph("PROFESSIONAL EXPERIENCE", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                self._add_professional_experience(story, sections['experience'], prof_styles, colors)
                story.append(Spacer(1, 0.2*inch))
            
            # 5. Previous Experience (if available)
            if 'previous_experience' in sections:
                self._add_previous_experience(story, sections['previous_experience'], prof_styles)
                story.append(Spacer(1, 0.2*inch))
            
            # 6. Additional Information Table
            if 'additional_info' in sections:
                story.append(Paragraph("ADDITIONAL INFORMATION", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                self._add_additional_info_table(story, sections['additional_info'], prof_styles)
            
            # Validate that we have content to put in the PDF
            if not story:
                raise ValueError("No content sections were generated for the PDF")
            
            if len(story) < 3:  # Should have at least contact, summary, and one other section
                raise ValueError(f"Insufficient PDF content sections ({len(story)})")
            
            # Build PDF
            doc.build(story)
            
            # Validate the generated PDF file
            if not os.path.exists(output_path):
                raise Exception("PDF file was not created successfully")
            
            file_size = os.path.getsize(output_path)
            if file_size < 2000:  # Professional PDF should be at least 2KB
                raise Exception(f"Generated PDF is too small ({file_size} bytes), likely empty or corrupted")
            
            logger.info(f"Professional CV exported to PDF: {output_path} ({file_size} bytes)")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error creating professional CV PDF: {e}")
            raise e
    
    def _get_color_scheme(self, scheme: str) -> Dict[str, Any]:
        """Get color scheme configuration"""
        schemes = {
            "teal": {
                "primary": HexColor("#008B8B"),    # Dark Teal
                "secondary": HexColor("#20B2AA"),  # Light Sea Green
                "accent": HexColor("#4682B4"),     # Steel Blue
                "text": black
            },
            "blue": {
                "primary": HexColor("#003366"),
                "secondary": HexColor("#336699"),
                "accent": HexColor("#6699CC"),
                "text": black
            }
        }
        return schemes.get(scheme, schemes["teal"])
    
    def _create_professional_styles(self, colors: Dict[str, Any]) -> Dict[str, ParagraphStyle]:
        """Create professional paragraph styles"""
        
        styles = {}
        
        # Contact header style
        styles['ContactHeader'] = ParagraphStyle(
            name='ContactHeader',
            fontSize=11,
            textColor=colors["text"],
            alignment=TA_CENTER,
            spaceAfter=0
        )
        
        # Section heading style
        styles['SectionHeading'] = ParagraphStyle(
            name='SectionHeading',
            fontSize=12,
            textColor=colors["primary"],
            fontName='Helvetica-Bold',
            spaceBefore=6,
            spaceAfter=6,
            borderWidth=1,
            borderColor=colors["primary"],
            borderPadding=3
        )
        
        # Body text style
        styles['BodyText'] = ParagraphStyle(
            name='BodyText',
            fontSize=10,
            textColor=colors["text"],
            alignment=TA_JUSTIFY,
            spaceAfter=4
        )
        
        # Skills box style
        styles['SkillBox'] = ParagraphStyle(
            name='SkillBox',
            fontSize=9,
            textColor=colors["text"],
            backColor=colors["secondary"],
            alignment=TA_CENTER,
            borderWidth=1,
            borderColor=colors["primary"],
            borderPadding=4
        )
        
        # Job title style
        styles['JobTitle'] = ParagraphStyle(
            name='JobTitle',
            fontSize=11,
            textColor=colors["primary"],
            fontName='Helvetica-Bold',
            spaceBefore=6,
            spaceAfter=3
        )
        
        # Experience bullet style
        styles['ExperienceBullet'] = ParagraphStyle(
            name='ExperienceBullet',
            fontSize=10,
            textColor=colors["text"],
            leftIndent=0.2*inch,
            bulletIndent=0.1*inch,
            spaceAfter=3
        )
        
        return styles
    
    def _format_contact_header(self, contact_info: Dict[str, str]) -> str:
        """Format contact information as single line with pipe separators"""
        parts = []
        
        if contact_info.get('name'):
            parts.append(f"<b>{contact_info['name']}</b>")
        
        if contact_info.get('email'):
            parts.append(f"📧 {contact_info['email']}")
        
        if contact_info.get('phone'):
            parts.append(f"📞 {contact_info['phone']}")
        
        if contact_info.get('location'):
            parts.append(f"📍 {contact_info['location']}")
        
        if contact_info.get('linkedin'):
            linkedin_clean = contact_info['linkedin'].replace('https://', '').replace('http://', '')
            parts.append(f"💼 {linkedin_clean}")
        
        if contact_info.get('website'):
            website_clean = contact_info['website'].replace('https://', '').replace('http://', '')
            parts.append(f"🌐 {website_clean}")
        
        return " | ".join(parts)
    
    def _parse_professional_cv_sections(self, cv_content: str) -> Dict[str, str]:
        """Parse the professionally formatted CV content with enhanced validation"""
        sections = {}
        current_section = None
        current_content = []
        
        if not cv_content or not cv_content.strip():
            logger.warning("Empty CV content provided for parsing")
            return sections
        
        lines = cv_content.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith('**') and line_stripped.endswith('**'):
                # Section header
                if current_section and current_content:
                    content = '\n'.join(current_content).strip()
                    if content:  # Only add non-empty sections
                        sections[current_section] = content
                
                section_name = line_stripped.replace('**', '').lower().replace(' ', '_')
                if 'professional_summary' in section_name:
                    current_section = 'summary'
                elif 'core_skills' in section_name or 'skills' in section_name:
                    current_section = 'skills'
                elif 'professional_experience' in section_name:
                    current_section = 'experience'
                elif 'previous_roles' in section_name:
                    current_section = 'previous_experience'
                elif 'additional_information' in section_name:
                    current_section = 'additional_info'
                else:
                    current_section = section_name
                
                current_content = []
                
            elif line_stripped == '---':
                # Section separator
                continue
            else:
                if current_section and line_stripped:
                    current_content.append(line_stripped)
        
        # Add the last section
        if current_section and current_content:
            content = '\n'.join(current_content).strip()
            if content:  # Only add non-empty sections
                sections[current_section] = content
        
        # Log sections found for debugging
        logger.info(f"Parsed CV sections: {list(sections.keys())}")
        
        # Validate that we have minimum required sections
        required_sections = ['summary', 'skills', 'experience']
        found_sections = [s for s in required_sections if s in sections and sections[s].strip()]
        
        if len(found_sections) < 2:
            logger.warning(f"Insufficient sections found: {found_sections}. Required: {required_sections}")
        
        return sections
    
    def _add_skills_boxes(self, story: List, skills_text: str, styles: Dict, colors: Dict):
        """Add skills in colored boxes, 4 per row"""
        import re
        
        # Extract skills
        skills = []
        lines = skills_text.split('\n')
        for line in lines:
            if '|' in line:
                # Split by pipe and clean each skill
                row_skills = [skill.strip().replace('**', '') for skill in line.split('|')]
                skills.extend([skill for skill in row_skills if skill])
        
        # Create skill boxes in rows of 4
        for i in range(0, len(skills), 4):
            row_skills = skills[i:i+4]
            skill_row = " | ".join([f'<span backcolor="{colors["secondary"]}" color="white"><b> {skill} </b></span>' for skill in row_skills])
            story.append(Paragraph(skill_row, styles['BodyText']))
            story.append(Spacer(1, 0.05*inch))
    
    def _add_professional_experience(self, story: List, experience_text: str, styles: Dict, colors: Dict):
        """Add current role with detailed 8 bullets"""
        lines = experience_text.split('\n')
        
        # Add job title
        for line in lines:
            if '|' in line and 'Present' in line:
                story.append(Paragraph(f'<b>{line}</b>', styles['JobTitle']))
                story.append(Spacer(1, 0.1*inch))
                break
        
        # Add experience bullets
        bullet_count = 0
        for line in lines:
            if line.strip().startswith('•') and bullet_count < 8:
                bullet_text = line.strip()[1:].strip()
                if ':' in bullet_text:
                    # Format with bold heading
                    parts = bullet_text.split(':', 1)
                    formatted_bullet = f'• <b>{parts[0].strip()}</b>: {parts[1].strip()}'
                else:
                    formatted_bullet = f'• {bullet_text}'
                
                story.append(Paragraph(formatted_bullet, styles['ExperienceBullet']))
                bullet_count += 1
    
    def _add_previous_experience(self, story: List, prev_exp_text: str, styles: Dict):
        """Add previous experience section (concise)"""
        story.append(Paragraph("<b>Previous Roles</b>", styles['JobTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        # Format previous experience concisely
        lines = prev_exp_text.split('\n')
        for line in lines:
            if line.strip():
                story.append(Paragraph(line.strip(), styles['BodyText']))
    
    def _add_additional_info_table(self, story: List, additional_info_text: str, styles: Dict):
        """Add additional information as a clean table"""
        from reportlab.platypus import Table, TableStyle
        
        # Parse table content
        lines = additional_info_text.split('\n')
        table_data = []
        
        for line in lines:
            if '|' in line and not line.startswith('|--'):
                # Parse table row
                parts = [part.strip() for part in line.split('|') if part.strip()]
                if len(parts) >= 2:
                    table_data.append(parts[:2])  # Take first 2 columns
        
        if table_data:
            # Create table
            table = Table(table_data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor("#E0E0E0")),
                ('TEXTCOLOR', (0, 0), (-1, 0), black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor("#F8F8F8")),
                ('GRID', (0, 0), (-1, -1), 1, black)
            ]))
            
            story.append(table)

    def create_structured_cv_pdf(self, contact_info: Dict[str, str], individual_sections: Dict[str, str], 
                                color_scheme: str = "teal") -> str:
        """Create a structured CV PDF using individual generated sections"""
        
        try:
            # Debug logging
            logger.info(f"Creating structured PDF with sections: {list(individual_sections.keys())}")
            for section_name, content in individual_sections.items():
                content_preview = content[:100] + "..." if len(content) > 100 else content
                logger.info(f"Section '{section_name}': {len(content)} chars - '{content_preview}'")
            
            # Validate input
            if not contact_info or not contact_info.get('name'):
                raise ValueError("Contact information missing or invalid")
            
            # Setup color scheme
            colors = self._get_color_scheme(color_scheme)
            
            # Create output path
            outputs_dir = Path("outputs")
            outputs_dir.mkdir(exist_ok=True)
            output_path = outputs_dir / f"Structured_CV_{contact_info['name'].replace(' ', '_')}.pdf"
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=0.7*inch,
                leftMargin=0.7*inch,
                topMargin=0.8*inch,
                bottomMargin=0.8*inch
            )
            
            story = []
            
            # Setup professional styles for structured layout
            prof_styles = self._create_structured_styles(colors)
            
            # 1. Header Section - Single line contact info with pipe separators
            contact_line = f"{contact_info.get('name', 'N/A')} | {contact_info.get('email', '')} | {contact_info.get('phone', '')} | {contact_info.get('location', '')}"
            story.append(Paragraph(contact_line, prof_styles['ContactHeader']))
            story.append(Spacer(1, 0.3*inch))
            
            # 2. Professional Summary (≤30 words from generated content)
            if individual_sections.get('executive_summary'):
                story.append(Paragraph("<b>PROFESSIONAL SUMMARY</b>", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                summary = self._clean_text_content(individual_sections['executive_summary'])
                story.append(Paragraph(summary, prof_styles['SummaryText']))
                story.append(Spacer(1, 0.2*inch))
            
            # 3. Skills Section - Visual boxes, 4 per row
            if individual_sections.get('top_skills'):
                story.append(Paragraph("<b>CORE SKILLS</b>", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                self._add_structured_skills_boxes(story, individual_sections['top_skills'], prof_styles, colors)
                story.append(Spacer(1, 0.2*inch))
            
            # 4. Current Role Experience - Top 8 SAR Bullets (Detailed)
            if individual_sections.get('experience_bullets'):
                story.append(Paragraph("<b>PROFESSIONAL EXPERIENCE</b>", prof_styles['SectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                
                # Parse and add current role header from experience content
                self._add_current_role_experience(story, individual_sections['experience_bullets'], prof_styles)
                story.append(Spacer(1, 0.2*inch))
            
            # 5. Previous Roles - Summarized (3-4 bullets max per role)
            previous_exp_content = individual_sections.get('previous_experience', '').strip()
            if previous_exp_content:
                logger.info(f"Adding previous roles section - content length: {len(previous_exp_content)}")
                story.append(Paragraph("<b>PREVIOUS ROLES</b>", prof_styles['SubSectionHeading']))
                story.append(Spacer(1, 0.1*inch))
                self._add_summarized_previous_roles(story, previous_exp_content, prof_styles)
                story.append(Spacer(1, 0.2*inch))
            else:
                logger.warning("Previous experience section is empty or missing - skipping")
            
            # 6. Additional Information Table (if any additional info exists)
            # This would be added if we had certifications, awards, etc.
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Structured CV PDF created successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error creating structured CV PDF: {e}")
            raise e
    
    def _create_structured_styles(self, colors: Dict) -> Dict:
        """Create professional styles for structured CV layout"""
        styles = {}
        
        # Contact header - single line
        styles['ContactHeader'] = ParagraphStyle(
            'ContactHeader',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors['primary'],
            alignment=TA_CENTER,
            spaceAfter=0
        )
        
        # Section headings
        styles['SectionHeading'] = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors['primary'],
            spaceBefore=0,
            spaceAfter=0,
            leftIndent=0
        )
        
        # Sub-section headings
        styles['SubSectionHeading'] = ParagraphStyle(
            'SubSectionHeading',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=colors['primary'],
            spaceBefore=0,
            spaceAfter=0,
            leftIndent=0
        )
        
        # Summary text
        styles['SummaryText'] = ParagraphStyle(
            'SummaryText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=black,
            alignment=TA_JUSTIFY,
            leftIndent=0
        )
        
        # Job header - for job titles (LinkedIn-style: bold and larger)
        styles['JobHeader'] = ParagraphStyle(
            'JobHeader',
            parent=self.styles['Normal'],
            fontSize=13,
            fontName='Helvetica-Bold',
            textColor=black,
            spaceBefore=0,
            spaceAfter=2,
            leading=16
        )
        
        # Company/location text
        styles['CompanyText'] = ParagraphStyle(
            'CompanyText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors['secondary'],
            spaceBefore=0,
            spaceAfter=4
        )
        
        # Date text
        styles['DateText'] = ParagraphStyle(
            'DateText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=HexColor('#666666'),
            spaceBefore=0,
            spaceAfter=2
        )
        
        # Bullet points
        styles['BulletText'] = ParagraphStyle(
            'BulletText',
            parent=self.styles['Normal'],
            fontSize=9.5,
            textColor=black,
            leftIndent=15,
            bulletIndent=5,
            spaceBefore=3,
            spaceAfter=3,
            leading=12
        )
        
        # Job titles for previous roles (LinkedIn-style: bold and larger, same as JobHeader)
        styles['JobTitle'] = ParagraphStyle(
            'JobTitle',
            parent=self.styles['Normal'],
            fontSize=13,
            fontName='Helvetica-Bold',
            textColor=black,
            spaceBefore=12,
            spaceAfter=2,
            leftIndent=0,
            leading=16
        )
        
        return styles
    
    def create_direct_cv_pdf(self, contact_info: Dict, whole_cv_content: str, color_scheme: str = "teal") -> str:
        """Create PDF directly from whole CV content without section headers"""
        try:
            # Parse the whole CV content into sections
            sections = self._parse_whole_cv_content(whole_cv_content)
            
            # Create filename
            name = contact_info.get('name', 'CV').replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Direct_CV_{name}_{timestamp}.pdf"
            output_path = self.output_dir / filename
            
            # Create document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )
            
            # Get colors and styles
            colors = self._get_color_scheme(color_scheme)
            styles = self._create_structured_styles(colors)
            
            # Create story
            story = []
            
            # Contact header
            contact_header = self._create_contact_header(contact_info, styles['ContactHeader'])
            story.append(contact_header)
            story.append(Spacer(1, 0.2*inch))
            
            # Process sections directly from parsed content
            for section_name, content in sections.items():
                if not content.strip():
                    continue
                    
                if section_name == 'summary':
                    story.append(Paragraph("<b>PROFESSIONAL SUMMARY</b>", styles['SectionHeading']))
                    story.append(Spacer(1, 0.1*inch))
                    story.append(Paragraph(content, styles['SummaryText']))
                    story.append(Spacer(1, 0.2*inch))
                    
                elif section_name == 'skills':
                    story.append(Paragraph("<b>CORE SKILLS</b>", styles['SectionHeading']))
                    story.append(Spacer(1, 0.1*inch))
                    self._add_structured_skills_boxes(story, content, styles, colors)
                    story.append(Spacer(1, 0.2*inch))
                    
                elif section_name == 'experience':
                    story.append(Paragraph("<b>PROFESSIONAL EXPERIENCE</b>", styles['SectionHeading']))
                    story.append(Spacer(1, 0.1*inch))
                    self._add_direct_experience_content(story, content, styles)
                    story.append(Spacer(1, 0.2*inch))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Direct CV PDF created successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error creating direct CV PDF: {e}")
            raise e
    
    def _parse_whole_cv_content(self, content: str) -> Dict[str, str]:
        """Parse whole CV content into sections"""
        sections = {}
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and separators
            if not line or line == '---':
                continue
            
            # Detect section headers
            line_upper = line.upper()
            if 'PROFESSIONAL SUMMARY' in line_upper or 'SUMMARY' in line_upper:
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'summary'
                current_content = []
            elif ('CORE SKILLS' in line_upper or 'SKILLS' in line_upper) and not line_upper.startswith('•'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'skills'
                current_content = []
                # Skip the header line, don't add it to content
                continue
            elif 'PROFESSIONAL EXPERIENCE' in line_upper or 'EXPERIENCE' in line_upper:
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'experience'
                current_content = []
            else:
                # Add content to current section
                if current_section:
                    current_content.append(line)
        
        # Add the last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _add_direct_experience_content(self, story: List, content: str, styles: Dict):
        """Add experience content directly without additional headers"""
        lines = content.split('\n')
        current_role_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a job title line (contains company and dates)
            if '|' in line and any(year in line for year in ['2019', '2020', '2021', '2022', '2023', '2024', '2025']):
                # Process previous role if exists
                if current_role_lines:
                    self._process_role_block(story, current_role_lines, styles)
                    current_role_lines = []
                
                # Start new role
                current_role_lines = [line]
            else:
                # Add to current role
                current_role_lines.append(line)
        
        # Process the last role
        if current_role_lines:
            self._process_role_block(story, current_role_lines, styles)
    
    def _process_role_block(self, story: List, role_lines: List[str], styles: Dict):
        """Process a single role block with LinkedIn-style formatting"""
        if not role_lines:
            return
            
        # First line should be job title with company and dates
        header_line = role_lines[0]
        
        # Parse job title, company, and dates
        if '|' in header_line:
            parts = [part.strip() for part in header_line.split('|')]
            if len(parts) >= 3:
                job_title = parts[0]
                company_location = parts[1] 
                dates = parts[2]
                
                # LinkedIn-style header: job title and dates on same line
                job_header_data = [[
                    Paragraph(job_title, styles['JobHeader']),
                    Paragraph(dates, styles['DateText'])
                ]]
                
                job_header_table = Table(job_header_data, colWidths=[4.5*inch, 2*inch])
                job_header_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]))
                
                story.append(job_header_table)
                
                # Company and location
                if company_location:
                    story.append(Paragraph(company_location, styles['CompanyText']))
                
                story.append(Spacer(1, 0.05*inch))
        
        # Add bullet points (skip the first line which is the header)
        for line in role_lines[1:]:
            if line.strip() and line.startswith(('•', '-', '*')):
                # Format bullet with first two words bold
                formatted_bullet = self._format_bullet_with_bold_start(line, styles)
                story.append(formatted_bullet)
                story.append(Spacer(1, 0.03*inch))
    
    def _clean_text_content(self, content: str) -> str:
        """Clean and format text content for PDF"""
        if not content:
            return ""
        
        # Remove markdown formatting
        content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', content)
        content = re.sub(r'\*(.*?)\*', r'<i>\1</i>', content)
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n', '\n', content)
        content = content.strip()
        
        return content
    
    def _add_structured_skills_boxes(self, story: List, skills_text: str, styles: Dict, colors: Dict):
        """Add each skill in its own individual colored box with gaps between them"""
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib.colors import HexColor
        
        # Extract skills from the generated content
        skills = self._extract_skills_list(skills_text)
        
        # Get the actual color values
        bg_color = colors.get('secondary', HexColor('#20B2AA'))
        text_color = HexColor('#FFFFFF')
        
        # Create truly individual boxes - one skill per table, properly spaced
        box_width = 1.3 * inch
        max_skills_per_row = 3  # Reduce to 3 for better spacing
        
        # Group skills into rows
        for i in range(0, len(skills), max_skills_per_row):
            row_skills = skills[i:i+max_skills_per_row]
            # Filter out empty skills
            row_skills = [skill.strip() for skill in row_skills if skill.strip()]
            
            if row_skills:
                # Build table with individual cells, each cell is a separate skill box
                table_data = [[]]
                col_widths = []
                
                for j, skill in enumerate(row_skills):
                    # Add skill to table data
                    table_data[0].append(skill)
                    col_widths.append(box_width)
                    
                    # Add spacer column between skills (except after last skill)
                    if j < len(row_skills) - 1:
                        table_data[0].append("")  # Empty spacer cell
                        col_widths.append(0.3 * inch)  # Spacer width
                
                # Create the table
                skills_table = Table(table_data, colWidths=col_widths)
                
                # Apply styling - each skill gets individual box styling
                table_style = []
                for col_idx in range(len(table_data[0])):
                    cell_content = table_data[0][col_idx]
                    
                    if cell_content and cell_content.strip():  # This is a skill cell (not spacer)
                        table_style.extend([
                            ('BACKGROUND', (col_idx, 0), (col_idx, 0), bg_color),
                            ('TEXTCOLOR', (col_idx, 0), (col_idx, 0), text_color),
                            ('ALIGN', (col_idx, 0), (col_idx, 0), 'CENTER'),
                            ('VALIGN', (col_idx, 0), (col_idx, 0), 'MIDDLE'),
                            ('FONTNAME', (col_idx, 0), (col_idx, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (col_idx, 0), (col_idx, 0), 9),
                            ('TOPPADDING', (col_idx, 0), (col_idx, 0), 6),
                            ('BOTTOMPADDING', (col_idx, 0), (col_idx, 0), 6),
                            ('LEFTPADDING', (col_idx, 0), (col_idx, 0), 8),
                            ('RIGHTPADDING', (col_idx, 0), (col_idx, 0), 8),
                            ('BOX', (col_idx, 0), (col_idx, 0), 1, bg_color),
                            ('GRID', (col_idx, 0), (col_idx, 0), 1, bg_color)
                        ])
                    # Spacer cells get no styling (remain invisible)
                
                skills_table.setStyle(TableStyle(table_style))
                story.append(skills_table)
                story.append(Spacer(1, 0.15*inch))
    
    def _extract_skills_list(self, skills_text: str) -> List[str]:
        """Extract individual skills from generated skills content"""
        skills = []
        if not skills_text:
            return skills
        
        lines = skills_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip header lines
            line_upper = line.upper()
            if ('CORE SKILLS' in line_upper or 
                'SKILLS' in line_upper or 
                line.startswith('#') or
                line.lower().startswith('skills') or 
                line.lower().startswith('core skills')):
                continue
                
            # Remove bullets and formatting
            line = re.sub(r'^[\-\•\*\+\d\.]\s*', '', line)
            line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)  # Remove markdown bold
            line = line.strip()
            
            if not line:
                continue
            
            # Split by common separators
            if '|' in line:
                row_skills = [skill.strip() for skill in line.split('|') if skill.strip()]
                skills.extend(row_skills)
            elif ',' in line and len(line.split(',')) > 1:
                row_skills = [skill.strip() for skill in line.split(',') if skill.strip()]
                skills.extend(row_skills)
            else:
                # Single skill - validate it's reasonable length
                if len(line.split()) <= 4:  # Skills should be short phrases
                    skills.append(line)
        
        return skills[:10]  # Limit to top 10 skills
    
    def _add_current_role_experience(self, story: List, experience_text: str, styles: Dict):
        """Add current role with LinkedIn-style formatting"""
        if not experience_text:
            return
            
        lines = [line.strip() for line in experience_text.split('\n') if line.strip()]
        job_title_found = False
        
        # Look for job title line (contains |)
        for line in lines:
            if '|' in line and not line.startswith(('•', '-', '*', '**')):
                # Parse job title, company, location, dates
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    job_title = parts[0]
                    company_location = parts[1]
                    
                    # Extract dates if present (usually in format MM/YYYY - Present or MM/YYYY - MM/YYYY)
                    date_pattern = r'(\d{2}/\d{4}\s*-\s*(?:\d{2}/\d{4}|Present|Current))'
                    date_match = re.search(date_pattern, company_location)
                    
                    if date_match:
                        dates = date_match.group(1)
                        company_location = company_location.replace(dates, '').strip()
                    else:
                        dates = "Present"
                    
                    # LinkedIn-style: Bold job title on left, dates on right
                    # Using a table for proper alignment
                    from reportlab.platypus import Table, TableStyle
                    
                    job_header_data = [[
                        Paragraph(job_title, styles['JobHeader']),
                        Paragraph(dates, styles['DateText'])
                    ]]
                    
                    job_header_table = Table(job_header_data, colWidths=[4.5*inch, 2*inch])
                    job_header_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                        ('TOPPADDING', (0, 0), (-1, -1), 0),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                    ]))
                    
                    story.append(job_header_table)
                    
                    # Add company and location line below
                    if company_location:
                        story.append(Paragraph(company_location, styles['CompanyText']))
                    
                    story.append(Spacer(1, 0.05*inch))
                    job_title_found = True
                    break
        
        # If no job title found, use default
        if not job_title_found:
            from reportlab.platypus import Table, TableStyle
            default_header = [[
                Paragraph("<b>Current Position</b>", styles['JobHeader']),
                Paragraph("Present", styles['DateText'])
            ]]
            default_table = Table(default_header, colWidths=[4.5*inch, 2*inch])
            default_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(default_table)
            story.append(Spacer(1, 0.05*inch))
        
        # Add the 8 SAR bullets
        self._add_sar_experience_bullets(story, experience_text, styles)

    def _add_sar_experience_bullets(self, story: List, experience_text: str, styles: Dict):
        """Add 8 SAR bullets with bold headings for current role"""
        bullets = self._extract_sar_bullets(experience_text)
        
        for bullet in bullets[:8]:  # Exactly 8 bullets
            # Clean bullet text of asterisk characters
            clean_bullet = self._clean_bullet_text(bullet)
            
            # Format SAR bullet with bold first two words before colon
            if ':' in clean_bullet:
                heading, description = clean_bullet.split(':', 1)
                heading = heading.strip()
                description = description.strip()
                
                # Extract first two words from heading and make them bold
                heading_words = heading.split()
                if len(heading_words) >= 2:
                    # Make first two words bold, rest normal
                    first_two_bold = f"<b>{heading_words[0]} {heading_words[1]}</b>"
                    remaining_words = " ".join(heading_words[2:]) if len(heading_words) > 2 else ""
                    if remaining_words:
                        formatted_heading = f"{first_two_bold} {remaining_words}"
                    else:
                        formatted_heading = first_two_bold
                    formatted_bullet = f"• {formatted_heading}: {description}"
                else:
                    # Less than 2 words, just make all bold
                    formatted_bullet = f"• <b>{heading}:</b> {description}"
            else:
                formatted_bullet = f"• {clean_bullet}"
            
            story.append(Paragraph(formatted_bullet, styles['BulletText']))
    
    def _extract_sar_bullets(self, experience_text: str) -> List[str]:
        """Extract SAR formatted bullets from experience text"""
        bullets = []
        if not experience_text:
            return bullets
        
        lines = experience_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and (':' in line or len(line) > 20):  # SAR bullets or substantial content
                # Clean existing bullet formatting
                line = re.sub(r'^[\-\•\*\+]\s*', '', line)
                bullets.append(line)
        
        return bullets
    
    def _clean_bullet_text(self, bullet_text: str) -> str:
        """Clean bullet text by removing asterisk characters and other formatting"""
        if not bullet_text:
            return ""
        
        # Remove single and double asterisks (markdown formatting)
        cleaned = re.sub(r'\*\*', '', bullet_text)  # Remove double asterisks
        cleaned = re.sub(r'\*', '', cleaned)        # Remove single asterisks
        
        # Remove other common markdown formatting
        cleaned = re.sub(r'__', '', cleaned)        # Remove double underscores
        cleaned = re.sub(r'_', '', cleaned)         # Remove single underscores
        
        # Clean up extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def _add_summarized_previous_roles(self, story: List, previous_text: str, styles: Dict):
        """Add previous roles with 3-4 bullets max per role"""
        logger.info(f"_add_summarized_previous_roles called with {len(previous_text) if previous_text else 0} characters")
        
        if not previous_text:
            logger.warning("No previous roles content provided")
            return
            
        # Clean and parse the text into lines
        cleaned_text = self._clean_text_content(previous_text)
        lines = [line.strip() for line in cleaned_text.split('\n') if line.strip()]
        
        # Check if we have job title lines with pipe symbols
        has_job_titles = any('|' in line and not line.startswith(('•', '-', '*', '**')) for line in lines)
        logger.info(f"Previous roles has job titles with |: {has_job_titles}")
        
        if has_job_titles:
            # Process with individual job titles
            self._process_previous_roles_with_titles(story, lines, styles)
        else:
            # No job titles found, treat as summary bullets under a generic header
            logger.info("No job titles found, adding generic previous roles header")
            story.append(Paragraph("<b>Previous Experience Highlights</b>", styles['JobTitle']))
            story.append(Spacer(1, 0.05*inch))
            
            # Add all bullets under this generic header
            bullet_count = 0
            max_bullets = 8  # Limit total bullets for previous roles
            
            for line in lines:
                if bullet_count >= max_bullets:
                    break
                    
                # Check if this is a bullet point
                if line.startswith(('•', '-', '*', '**')):
                    clean_bullet = self._clean_bullet_text(line)
                    if clean_bullet:
                        bullet_text = clean_bullet.lstrip('•-*').strip()
                        if bullet_text:
                            story.append(Paragraph(f"• {bullet_text}", styles['BulletText']))
                            bullet_count += 1
                
                # If line doesn't have bullet marker but looks like content, treat as bullet
                elif len(line) > 20:  # Substantial content
                    clean_bullet = self._clean_bullet_text(line)
                    if clean_bullet:
                        story.append(Paragraph(f"• {clean_bullet}", styles['BulletText']))
                        bullet_count += 1
        
        # Add some spacing after previous roles
        story.append(Spacer(1, 0.1*inch))
    
    def _process_previous_roles_with_titles(self, story: List, lines: List[str], styles: Dict):
        """Process previous roles with LinkedIn-style formatting"""
        from reportlab.platypus import Table, TableStyle
        
        current_role = None
        current_company = None
        bullet_count = 0
        max_bullets_per_role = 4
        
        for line in lines:
            # Check if this is a role/company line (contains |)
            if '|' in line and not line.startswith(('•', '-', '*', '**')):
                # Parse job title, company, location, dates
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    current_role = parts[0]
                    company_info = parts[1]
                    bullet_count = 0  # Reset bullet count for new role
                    
                    # Extract dates from company info
                    date_pattern = r'(\d{2}/\d{4}\s*-\s*(?:\d{2}/\d{4}|Present|Current))'
                    date_match = re.search(date_pattern, company_info)
                    
                    if date_match:
                        dates = date_match.group(1)
                        company_location = company_info.replace(dates, '').strip()
                    else:
                        # Fallback if no dates found
                        dates = ""
                        company_location = company_info
                    
                    # LinkedIn-style: Bold job title on left, dates on right
                    job_header_data = [[
                        Paragraph(current_role, styles['JobTitle']),
                        Paragraph(dates, styles['DateText'])
                    ]]
                    
                    job_header_table = Table(job_header_data, colWidths=[4.5*inch, 2*inch])
                    job_header_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                        ('TOPPADDING', (0, 0), (-1, -1), 0),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                    ]))
                    
                    # Add spacing between roles for better readability
                    if bullet_count > 0:  # Not the first role
                        story.append(Spacer(1, 0.15*inch))
                    
                    story.append(job_header_table)
                    
                    # Add company and location line below
                    if company_location:
                        story.append(Paragraph(company_location, styles['CompanyText']))
                    
                    story.append(Spacer(1, 0.05*inch))
                    
            # Check if this is a bullet point
            elif line.startswith(('•', '-', '*', '**')) and bullet_count < max_bullets_per_role:
                # Clean the bullet text
                clean_bullet = self._clean_bullet_text(line)
                if clean_bullet:
                    # Remove bullet marker and create formatted bullet
                    bullet_text = clean_bullet.lstrip('•-*').strip()
                    if bullet_text:
                        story.append(Paragraph(f"• {bullet_text}", styles['BulletText']))
                        bullet_count += 1
            
            # If line doesn't have bullet marker but looks like content, treat as bullet
            elif current_role and bullet_count < max_bullets_per_role and len(line) > 10:
                clean_bullet = self._clean_bullet_text(line)
                if clean_bullet:
                    story.append(Paragraph(f"• {clean_bullet}", styles['BulletText']))
                    bullet_count += 1

    def create_cv_from_structured_data(self, cv_data, color_scheme: str = "teal") -> str:
        """Create CV PDF from CVData structured object"""
        
        try:
            # Import CVData here to avoid circular imports
            from models.cv_data import CVData
            
            if not isinstance(cv_data, CVData):
                raise ValueError("cv_data must be a CVData instance")
            
            # Setup color scheme
            colors = self._get_color_scheme(color_scheme)
            
            # Create output path
            outputs_dir = Path("outputs")
            outputs_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"CV_{cv_data.contact.name.replace(' ', '_')}_{timestamp}.pdf"
            pdf_path = outputs_dir / filename
            
            # Create styles
            styles = self._create_professional_styles(colors)
            
            # Create document
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=50,
                leftMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            story = []
            
            # Add contact header
            contact_text = cv_data.contact.name
            if cv_data.contact.email:
                contact_text += f" | 📧 {cv_data.contact.email}"
            if cv_data.contact.phone:
                contact_text += f" | 📞 {cv_data.contact.phone}"
            if cv_data.contact.location:
                contact_text += f" | 📍 {cv_data.contact.location}"
            if cv_data.contact.linkedin:
                contact_text += f" | 💼 {cv_data.contact.linkedin}"
            if cv_data.contact.website:
                contact_text += f" | 🌐 {cv_data.contact.website}"
            
            story.append(Paragraph(contact_text, styles['ContactHeader']))
            story.append(Spacer(1, 15))
            
            # Add professional summary
            if cv_data.professional_summary:
                story.append(Paragraph("PROFESSIONAL SUMMARY", styles['SectionHeader']))
                story.append(Spacer(1, 8))
                story.append(Paragraph(cv_data.professional_summary, styles['BodyText']))
                story.append(Spacer(1, 15))
            
            # Add skills
            if cv_data.skills:
                story.append(Paragraph("CORE SKILLS", styles['SectionHeader']))
                story.append(Spacer(1, 8))
                
                # Format skills in rows of 4
                skills_rows = []
                for i in range(0, len(cv_data.skills), 4):
                    row_skills = cv_data.skills[i:i+4]
                    formatted_row = " | ".join([f"<b>{skill}</b>" for skill in row_skills])
                    skills_rows.append(formatted_row)
                
                for row in skills_rows:
                    story.append(Paragraph(row, styles['SkillsText']))
                story.append(Spacer(1, 15))
            
            # Add current role
            if cv_data.current_role:
                story.append(Paragraph("PROFESSIONAL EXPERIENCE", styles['SectionHeader']))
                story.append(Spacer(1, 8))
                
                # Role header
                role_header = f"<b>{cv_data.current_role.job_title}</b> | {cv_data.current_role.company}, {cv_data.current_role.location} | {cv_data.current_role.start_date} - {cv_data.current_role.end_date}"
                story.append(Paragraph(role_header, styles['CompanyHeader']))
                story.append(Spacer(1, 8))
                
                # Add bullets
                for bullet in cv_data.current_role.bullets:
                    bullet_text = f"• <b>{bullet.heading}</b>: {bullet.content}"
                    story.append(Paragraph(bullet_text, styles['BulletText']))
                
                story.append(Spacer(1, 15))
            
            # Add previous roles
            for role in cv_data.previous_roles:
                role_header = f"<b>{role.job_title}</b> | {role.company}, {role.location} | {role.start_date} - {role.end_date}"
                story.append(Paragraph(role_header, styles['CompanyHeader']))
                story.append(Spacer(1, 8))
                
                for bullet in role.bullets:
                    bullet_text = f"• <b>{bullet.heading}</b>: {bullet.content}"
                    story.append(Paragraph(bullet_text, styles['BulletText']))
                
                story.append(Spacer(1, 10))
            
            # Add additional info
            if cv_data.additional_info:
                story.append(Spacer(1, 10))
                story.append(Paragraph(cv_data.additional_info, styles['BodyText']))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"CVData-based PDF created successfully: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Error creating PDF from CVData: {e}")
            raise

@st.cache_resource
def get_pdf_exporter():
    return PDFExporter()