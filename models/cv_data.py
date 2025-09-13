"""
CV Data Model - Structured data representation for CV content
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import json


@dataclass
class ContactInfo:
    """Contact information structure"""
    name: str
    email: str
    phone: str
    location: str
    linkedin: Optional[str] = None
    website: Optional[str] = None
    
    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ExperienceBullet:
    """Single experience bullet point"""
    heading: str  # First two words (e.g., "AI Integration")
    content: str  # Rest of the bullet content
    
    def to_formatted_string(self) -> str:
        """Return formatted bullet with bold heading"""
        return f"**{self.heading}** | {self.content}"


@dataclass
class RoleExperience:
    """Single role/position experience"""
    job_title: str
    company: str
    location: str
    start_date: str
    end_date: str
    bullets: List[ExperienceBullet] = field(default_factory=list)
    
    def to_dict(self):
        return {
            'job_title': self.job_title,
            'company': self.company,
            'location': self.location,
            'dates': f"{self.start_date} - {self.end_date}",
            'bullets': [bullet.to_formatted_string() for bullet in self.bullets]
        }


@dataclass
class CVData:
    """Complete CV data structure"""
    
    # Contact Information
    contact: ContactInfo
    
    # Professional Summary (max 40 words)
    professional_summary: str
    
    # Core Skills (list of skills, max 10)
    skills: List[str]
    
    # Current Role Experience
    current_role: RoleExperience
    
    # Previous Roles
    previous_roles: List[RoleExperience] = field(default_factory=list)
    
    # Additional Information (optional)
    additional_info: Optional[str] = None
    
    # Metadata
    style_profile: Optional[Dict] = None
    generated_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'contact': self.contact.to_dict(),
            'professional_summary': self.professional_summary,
            'skills': self.skills,
            'current_role': self.current_role.to_dict(),
            'previous_roles': [role.to_dict() for role in self.previous_roles],
            'additional_info': self.additional_info,
            'style_profile': self.style_profile,
            'generated_at': self.generated_at
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CVData':
        """Create CVData instance from dictionary"""
        contact = ContactInfo(**data['contact'])
        
        current_role_data = data['current_role']
        current_bullets = [
            ExperienceBullet(
                heading=bullet.split(' | ')[0].replace('**', ''),
                content=bullet.split(' | ')[1] if ' | ' in bullet else bullet
            )
            for bullet in current_role_data.get('bullets', [])
        ]
        
        current_role = RoleExperience(
            job_title=current_role_data['job_title'],
            company=current_role_data['company'],
            location=current_role_data['location'],
            start_date=current_role_data['dates'].split(' - ')[0],
            end_date=current_role_data['dates'].split(' - ')[1],
            bullets=current_bullets
        )
        
        previous_roles = []
        for role_data in data.get('previous_roles', []):
            role_bullets = [
                ExperienceBullet(
                    heading=bullet.split(' | ')[0].replace('**', ''),
                    content=bullet.split(' | ')[1] if ' | ' in bullet else bullet
                )
                for bullet in role_data.get('bullets', [])
            ]
            
            previous_roles.append(RoleExperience(
                job_title=role_data['job_title'],
                company=role_data['company'],
                location=role_data['location'],
                start_date=role_data['dates'].split(' - ')[0],
                end_date=role_data['dates'].split(' - ')[1],
                bullets=role_bullets
            ))
        
        return cls(
            contact=contact,
            professional_summary=data['professional_summary'],
            skills=data['skills'],
            current_role=current_role,
            previous_roles=previous_roles,
            additional_info=data.get('additional_info'),
            style_profile=data.get('style_profile'),
            generated_at=data.get('generated_at')
        )
    
    def format_for_preview(self) -> str:
        """Format CV data for text preview"""
        sections = []
        
        # Contact header
        contact_line = f"{self.contact.name} | 📧 {self.contact.email} | 📞 {self.contact.phone} | 📍 {self.contact.location}"
        if self.contact.linkedin:
            contact_line += f" | 🔗 {self.contact.linkedin}"
        sections.append(contact_line)
        
        # Professional Summary
        sections.append(f"**PROFESSIONAL SUMMARY**\n\n{self.professional_summary}")
        
        # Core Skills
        skills_formatted = " | ".join([f"**{skill}**" for skill in self.skills])
        sections.append(f"**CORE SKILLS**\n\n{skills_formatted}")
        
        # Professional Experience
        exp_lines = [f"**PROFESSIONAL EXPERIENCE**\n"]
        
        # Current role
        exp_lines.append(f"{self.current_role.job_title} | {self.current_role.company}, {self.current_role.location} | {self.current_role.start_date} - {self.current_role.end_date}\n")
        for bullet in self.current_role.bullets:
            exp_lines.append(f"• {bullet.to_formatted_string()}")
        
        # Previous roles
        for role in self.previous_roles:
            exp_lines.append(f"\n{role.job_title} | {role.company}, {role.location} | {role.start_date} - {role.end_date}\n")
            for bullet in role.bullets:
                exp_lines.append(f"• {bullet.to_formatted_string()}")
        
        sections.append("\n".join(exp_lines))
        
        # Additional info
        if self.additional_info:
            sections.append(self.additional_info)
        
        return "\n\n---\n\n".join(sections)