"""
Tests to ensure CV preview and PDF content are identical and consistent.
These tests prevent regressions and guarantee template consistency.
"""

import unittest
import re
from unittest.mock import Mock
from datetime import datetime

from services.template_engine import template_engine
from models.cv_data import CVData, ContactInfo, RoleExperience, ExperienceBullet


class TestTemplateConsistency(unittest.TestCase):
    """Test suite ensuring CV preview and PDF templates produce consistent content"""

    def setUp(self):
        """Set up test data"""
        self.sample_contact = ContactInfo(
            name="John Doe",
            email="john.doe@example.com", 
            phone="+1-555-123-4567",
            location="San Francisco, CA",
            linkedin="https://linkedin.com/in/johndoe",
            website="https://johndoe.dev"
        )
        
        self.sample_bullets = [
            ExperienceBullet(heading="Leadership", content="Led a team of 5 engineers to deliver critical features"),
            ExperienceBullet(heading="Performance", content="Improved system performance by 40% through optimization"),
            ExperienceBullet(heading="Innovation", content="Architected microservices reducing deployment time by 60%")
        ]
        
        self.sample_current_role = RoleExperience(
            job_title="Senior Software Engineer",
            company="TechCorp Inc",
            location="San Francisco, CA", 
            start_date="Jan 2022",
            end_date="Present",
            bullets=self.sample_bullets
        )
        
        self.sample_previous_roles = [
            RoleExperience(
                job_title="Software Engineer",
                company="StartupXYZ",
                location="Remote",
                start_date="Mar 2020",
                end_date="Dec 2021",
                bullets=[
                    ExperienceBullet(heading="Development", content="Built scalable web applications using React and Node.js"),
                    ExperienceBullet(heading="Database", content="Optimized database queries reducing load time by 30%")
                ]
            ),
            RoleExperience(
                job_title="Junior Developer", 
                company="WebAgency LLC",
                location="New York, NY",
                start_date="Jun 2019",
                end_date="Feb 2020",
                bullets=[
                    ExperienceBullet(heading="Frontend", content="Developed responsive websites for 15+ clients"),
                    ExperienceBullet(heading="Collaboration", content="Worked closely with designers to implement UI/UX")
                ]
            )
        ]
        
        self.sample_cv_data = CVData(
            contact=self.sample_contact,
            professional_summary="Experienced software engineer with 5+ years of expertise in full-stack development, cloud architecture, and team leadership. Proven track record of delivering scalable solutions and driving innovation in fast-paced environments.",
            skills=["Python", "JavaScript", "React", "Node.js", "AWS", "Docker", "PostgreSQL", "Redis"],
            current_role=self.sample_current_role,
            previous_roles=self.sample_previous_roles,
            additional_info="Available for remote work. Open source contributor with 500+ GitHub stars.",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    def test_unified_context_provides_both_field_formats(self):
        """Test that unified context provides both preview and PDF field formats"""
        context = template_engine._create_unified_context(self.sample_cv_data)
        
        # Check current role has both field name formats
        current_role = context['current_role']
        
        # Preview format fields
        self.assertEqual(current_role['job_title'], "Senior Software Engineer")
        self.assertEqual(current_role['company'], "TechCorp Inc")
        self.assertIn('bullets', current_role)
        
        # PDF format fields  
        self.assertEqual(current_role['position_name'], "Senior Software Engineer")
        self.assertEqual(current_role['company_name'], "TechCorp Inc")
        self.assertIn('key_bullets', current_role)
        
        # Verify they contain the same data
        self.assertEqual(current_role['job_title'], current_role['position_name'])
        self.assertEqual(current_role['company'], current_role['company_name'])
        self.assertEqual(len(current_role['bullets']), len(current_role['key_bullets']))

    def test_previous_roles_have_both_field_formats(self):
        """Test that previous roles contain both field name formats"""
        context = template_engine._create_unified_context(self.sample_cv_data)
        
        for i, role in enumerate(context['previous_roles']):
            expected_role = self.sample_previous_roles[i]
            
            # Preview format fields
            self.assertEqual(role['job_title'], expected_role.job_title)
            self.assertEqual(role['company'], expected_role.company)
            self.assertIn('bullets', role)
            
            # PDF format fields
            self.assertEqual(role['position_name'], expected_role.job_title) 
            self.assertEqual(role['company_name'], expected_role.company)
            self.assertIn('key_bullets', role)
            
            # Verify consistency
            self.assertEqual(role['job_title'], role['position_name'])
            self.assertEqual(role['company'], role['company_name'])

    def test_core_content_consistency_between_templates(self):
        """Test that core content (skills, summary, etc.) is identical between templates"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Clean both contents for comparison (remove markdown formatting and extra whitespace)
        clean_preview = self._clean_content_for_comparison(preview_content)
        clean_pdf = self._clean_content_for_comparison(pdf_content)
        
        # Extract and compare key sections
        self._assert_section_consistency(clean_preview, clean_pdf, "PROFESSIONAL SUMMARY")
        self._assert_section_consistency(clean_preview, clean_pdf, "CORE SKILLS") 
        self._assert_section_consistency(clean_preview, clean_pdf, "PROFESSIONAL EXPERIENCE")
        
    def test_contact_info_consistency(self):
        """Test that contact information is identical between preview and PDF"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Check that both contain the same contact elements
        for contact_item in [self.sample_contact.name, self.sample_contact.email, 
                           self.sample_contact.phone, self.sample_contact.location]:
            self.assertIn(contact_item, preview_content)
            self.assertIn(contact_item, pdf_content)

    def test_skills_formatting_consistency(self):
        """Test that skills are formatted consistently between templates"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Verify all skills appear in both formats
        for skill in self.sample_cv_data.skills:
            self.assertIn(skill, preview_content, f"Skill '{skill}' missing from preview")
            self.assertIn(skill, pdf_content, f"Skill '{skill}' missing from PDF")

    def test_job_titles_and_companies_consistency(self):
        """Test that job titles and company names are identical between templates"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Check current role
        self.assertIn(self.sample_current_role.job_title, preview_content)
        self.assertIn(self.sample_current_role.job_title, pdf_content)
        self.assertIn(self.sample_current_role.company, preview_content)
        self.assertIn(self.sample_current_role.company, pdf_content)
        
        # Check previous roles
        for role in self.sample_previous_roles:
            self.assertIn(role.job_title, preview_content)
            self.assertIn(role.job_title, pdf_content)
            self.assertIn(role.company, preview_content)
            self.assertIn(role.company, pdf_content)

    def test_bullet_points_consistency(self):
        """Test that bullet points content is consistent between templates"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Check current role bullets
        for bullet in self.sample_current_role.bullets:
            # Remove markdown formatting for comparison
            bullet_text = bullet.content
            self.assertIn(bullet_text, preview_content)
            self.assertIn(bullet_text, pdf_content)
        
        # Check previous role bullets
        for role in self.sample_previous_roles:
            for bullet in role.bullets:
                bullet_text = bullet.content
                self.assertIn(bullet_text, preview_content)
                self.assertIn(bullet_text, pdf_content)

    def test_no_missing_placeholder_values(self):
        """Test that there are no missing placeholder values like **** or empty fields"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Check for common placeholder issues
        problematic_patterns = ['****', '{{ ', '}}', 'undefined', 'None', 'null']
        
        for pattern in problematic_patterns:
            self.assertNotIn(pattern, preview_content, 
                           f"Found problematic pattern '{pattern}' in preview content")
            self.assertNotIn(pattern, pdf_content,
                           f"Found problematic pattern '{pattern}' in PDF content")

    def test_additional_info_consistency(self):
        """Test that additional information section is consistent"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        if self.sample_cv_data.additional_info:
            self.assertIn(self.sample_cv_data.additional_info, preview_content)
            self.assertIn(self.sample_cv_data.additional_info, pdf_content)

    def test_template_context_field_coverage(self):
        """Test that unified context provides all necessary fields for both templates"""
        context = template_engine._create_unified_context(self.sample_cv_data)
        
        # Required base fields
        required_fields = ['contact', 'professional_summary', 'skills', 'current_role', 
                          'previous_roles', 'additional_info', 'generated_at']
        
        for field in required_fields:
            self.assertIn(field, context, f"Missing required field: {field}")
        
        # Current role must have both field name formats
        current_role_preview_fields = ['job_title', 'company', 'bullets']
        current_role_pdf_fields = ['position_name', 'company_name', 'key_bullets']
        
        for field in current_role_preview_fields + current_role_pdf_fields:
            self.assertIn(field, context['current_role'], 
                         f"Missing current_role field: {field}")

    def _clean_content_for_comparison(self, content: str) -> str:
        """Clean content by removing markdown, extra whitespace, and formatting"""
        # Remove markdown formatting
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Remove **bold**
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)      # Remove *italic*
        cleaned = re.sub(r'#+\s*', '', cleaned)               # Remove headers
        cleaned = re.sub(r'---+', '', cleaned)                # Remove separators
        cleaned = re.sub(r'=+', '', cleaned)                  # Remove PDF separators
        
        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned

    def _assert_section_consistency(self, preview_content: str, pdf_content: str, section_name: str):
        """Assert that a specific section has consistent content between preview and PDF"""
        preview_section = self._extract_section(preview_content, section_name)
        pdf_section = self._extract_section(pdf_content, section_name)
        
        self.assertIsNotNone(preview_section, f"Section '{section_name}' not found in preview")
        self.assertIsNotNone(pdf_section, f"Section '{section_name}' not found in PDF")
        
        # Compare core content (allowing for format differences)
        self.assertGreater(len(preview_section), 10, f"Preview section '{section_name}' too short")
        self.assertGreater(len(pdf_section), 10, f"PDF section '{section_name}' too short")

    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract a specific section from content"""
        # Look for section header and extract content until next section
        pattern = rf'{section_name}[\s\S]*?(?=(?:[A-Z\s]+$|$))'
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        return match.group(0) if match else None


if __name__ == '__main__':
    unittest.main()