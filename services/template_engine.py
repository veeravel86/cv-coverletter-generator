"""
Template Engine Service - Jinja2-based templating for CV generation
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template
from models.cv_data import CVData, ContactInfo, RoleExperience


class TemplateEngine:
    """Jinja2-based template engine for CV generation"""
    
    def __init__(self, template_dir: str = "templates"):
        """Initialize template engine with template directory"""
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False,  # We're generating markdown/text, not HTML
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['format_bullets'] = self._format_bullets
        self.env.filters['clean_markdown'] = self._clean_markdown
    
    def _format_bullets(self, bullets: list) -> str:
        """Format bullet points for display"""
        if not bullets:
            return ""
        return "\n".join([f"• {bullet}" for bullet in bullets])
    
    def _clean_markdown(self, text: str) -> str:
        """Clean markdown formatting for plain text output"""
        if not text:
            return ""
        # Remove bold formatting
        text = text.replace("**", "")
        # Remove italic formatting  
        text = text.replace("*", "")
        return text.strip()
    
    def render_cv_preview(self, cv_data: CVData) -> str:
        """Render CV preview using markdown template"""
        try:
            template = self.env.get_template('cv_preview.md')
            
            # Prepare template context
            context = {
                'contact': {
                    'name': cv_data.contact.name,
                    'email': cv_data.contact.email,
                    'phone': cv_data.contact.phone,
                    'location': cv_data.contact.location,
                    'linkedin': cv_data.contact.linkedin,
                    'website': cv_data.contact.website
                },
                'professional_summary': cv_data.professional_summary,
                'skills': cv_data.skills,
                'current_role': {
                    'job_title': cv_data.current_role.job_title,
                    'company': cv_data.current_role.company,
                    'location': cv_data.current_role.location,
                    'start_date': cv_data.current_role.start_date,
                    'end_date': cv_data.current_role.end_date,
                    'work_duration': f"{cv_data.current_role.start_date} - {cv_data.current_role.end_date}",
                    'bullets': cv_data.current_role.bullets
                },
                'previous_roles': [],
                'additional_info': cv_data.additional_info,
                'generated_at': cv_data.generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add previous roles if available
            if cv_data.previous_roles:
                for role in cv_data.previous_roles:
                    context['previous_roles'].append({
                        'job_title': role.job_title,
                        'company': role.company,
                        'location': role.location,
                        'start_date': role.start_date,
                        'end_date': role.end_date,
                        'work_duration': f"{role.start_date} - {role.end_date}",
                        'bullets': role.bullets
                    })
            
            return template.render(**context)
            
        except Exception as e:
            raise Exception(f"Failed to render CV preview template: {str(e)}")
    
    def render_cv_for_pdf(self, cv_data: CVData) -> str:
        """Render CV for PDF generation (clean text, no markdown)"""
        try:
            template = self.env.get_template('cv_pdf.txt')
            
            # Prepare template context (same as preview but clean output)
            context = {
                'contact': {
                    'name': cv_data.contact.name,
                    'email': cv_data.contact.email,
                    'phone': cv_data.contact.phone,
                    'location': cv_data.contact.location,
                    'linkedin': cv_data.contact.linkedin,
                    'website': cv_data.contact.website
                },
                'professional_summary': cv_data.professional_summary,
                'skills': cv_data.skills,
                'current_role': {
                    'position_name': cv_data.current_role.job_title,
                    'company_name': cv_data.current_role.company,
                    'location': cv_data.current_role.location,
                    'start_date': cv_data.current_role.start_date,
                    'end_date': cv_data.current_role.end_date,
                    'work_duration': f"{cv_data.current_role.start_date} - {cv_data.current_role.end_date}",
                    'key_bullets': [bullet.to_formatted_string() for bullet in cv_data.current_role.bullets]
                },
                'previous_roles': [],
                'additional_info': cv_data.additional_info,
                'generated_at': cv_data.generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add previous roles if available
            if cv_data.previous_roles:
                for role in cv_data.previous_roles:
                    context['previous_roles'].append({
                        'position_name': role.job_title,
                        'company_name': role.company,
                        'location': role.location,
                        'start_date': role.start_date,
                        'end_date': role.end_date,
                        'work_duration': f"{role.start_date} - {role.end_date}",
                        'key_bullets': [bullet.to_formatted_string() for bullet in role.bullets]
                    })
            
            return template.render(**context)
            
        except Exception as e:
            raise Exception(f"Failed to render CV PDF template: {str(e)}")
    
    def render_cv_from_session_data(self, session_data: Dict[str, Any], contact_info: Dict[str, str]) -> str:
        """Render CV from session state data structure"""
        try:
            template = self.env.get_template('cv_preview.md')
            
            # Extract structured data from session
            llm_responses = session_data.get('llm_json_responses', {})
            individual_generations = session_data.get('individual_generations', {})
            
            # Build context from session data
            context = {
                'contact': contact_info,
                'professional_summary': individual_generations.get('executive_summary', ''),
                'skills': self._extract_skills_from_session(individual_generations.get('top_skills', '')),
                'current_role': self._extract_current_role_from_session(llm_responses),
                'previous_roles': self._extract_previous_roles_from_session(llm_responses),
                'additional_info': None,
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return template.render(**context)
            
        except Exception as e:
            raise Exception(f"Failed to render CV from session data: {str(e)}")
    
    def _extract_skills_from_session(self, skills_text: str) -> list:
        """Extract skills list from formatted text"""
        if not skills_text:
            return []
        
        # Try to parse from formatted text like "**Skill1** | **Skill2** | **Skill3**"
        if '|' in skills_text:
            skills = [skill.strip().replace('**', '') for skill in skills_text.split('|')]
            return [skill for skill in skills if skill]
        
        # Fallback: split by lines or commas
        if '\n' in skills_text:
            skills = [skill.strip().replace('**', '').replace('•', '').strip() 
                     for skill in skills_text.split('\n')]
        else:
            skills = [skill.strip().replace('**', '') for skill in skills_text.split(',')]
        
        return [skill for skill in skills if skill]
    
    def _extract_current_role_from_session(self, llm_responses: Dict) -> Dict:
        """Extract current role data from session LLM responses"""
        experience_data = llm_responses.get('experience_bullets', {})
        
        if 'role_data' in experience_data:
            role_data = experience_data['role_data']
            return {
                'position_name': role_data.get('position_name', 'Current Position'),
                'company_name': role_data.get('company_name', 'Current Company'),
                'location': role_data.get('location', 'Location'),
                'start_date': role_data.get('start_date', ''),
                'end_date': role_data.get('end_date', 'Present'),
                'work_duration': role_data.get('work_duration', ''),
                'key_bullets': experience_data.get('optimized_bullets', [])
            }
        
        # Fallback structure
        return {
            'position_name': 'Current Position',
            'company_name': 'Current Company',
            'location': 'Location',
            'start_date': '',
            'end_date': 'Present',
            'work_duration': '',
            'key_bullets': []
        }
    
    def _extract_previous_roles_from_session(self, llm_responses: Dict) -> list:
        """Extract previous roles data from session LLM responses"""
        previous_data = llm_responses.get('previous_experience', {})
        
        if 'previous_roles_data' in previous_data:
            roles = []
            for role_data in previous_data['previous_roles_data']:
                roles.append({
                    'position_name': role_data.get('position_name', 'Previous Position'),
                    'company_name': role_data.get('company_name', 'Previous Company'),
                    'location': role_data.get('location', 'Location'),
                    'start_date': role_data.get('start_date', ''),
                    'end_date': role_data.get('end_date', ''),
                    'work_duration': role_data.get('work_duration', ''),
                    'key_bullets': role_data.get('key_bullets', [])
                })
            return roles
        
        return []
    
    def create_pdf_context(self, cv_data: CVData) -> Dict[str, Any]:
        """Create context dictionary optimized for PDF generation"""
        context = {
            'contact': {
                'name': cv_data.contact.name,
                'email': cv_data.contact.email,
                'phone': cv_data.contact.phone,
                'location': cv_data.contact.location,
                'linkedin': cv_data.contact.linkedin,
                'website': cv_data.contact.website
            },
            'professional_summary': cv_data.professional_summary,
            'skills': cv_data.skills,
            'current_role': {
                'position_name': cv_data.current_role.job_title,
                'company_name': cv_data.current_role.company,
                'location': cv_data.current_role.location,
                'start_date': cv_data.current_role.start_date,
                'end_date': cv_data.current_role.end_date,
                'bullets': [bullet.to_formatted_string() for bullet in cv_data.current_role.bullets]
            },
            'previous_roles': [],
            'additional_info': cv_data.additional_info
        }
        
        # Add previous roles
        for role in cv_data.previous_roles:
            context['previous_roles'].append({
                'position_name': role.job_title,
                'company_name': role.company,
                'location': role.location,
                'start_date': role.start_date,
                'end_date': role.end_date,
                'bullets': [bullet.to_formatted_string() for bullet in role.bullets]
            })
        
        return context
    
    def render_custom_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render any custom template with provided context"""
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            raise Exception(f"Failed to render template '{template_name}': {str(e)}")


# Global template engine instance
template_engine = TemplateEngine()