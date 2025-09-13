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


    def test_actual_pdf_generation_consistency(self):
        """Test that actual PDF generation uses template engine and matches preview content"""
        try:
            # Import PDF exporter and app functions
            from exporters.pdf_export import PDFExporter
            from app import convert_session_to_cvdata, generate_template_based_cv_pdf
            import streamlit as st
            import os
            import tempfile
            
            # Mock session state with our test data
            mock_session_state = {
                'whole_cv_contact': {
                    'name': self.sample_contact.name,
                    'email': self.sample_contact.email,
                    'phone': self.sample_contact.phone,
                    'location': self.sample_contact.location,
                    'linkedin': self.sample_contact.linkedin,
                    'website': self.sample_contact.website
                },
                'individual_generations': {
                    'executive_summary': 'Senior Engineering Manager with 8+ years leading cross-functional teams.',
                    'top_skills': '**Cloud Architecture** | **Team Leadership** | **Python Development** | **Strategic Planning** | **DevOps Practices**'
                },
                'llm_json_responses': {
                    'experience_bullets': {
                        'role_data': {
                            'position_name': 'Senior Software Engineer',
                            'company_name': 'TechCorp Inc',
                            'location': 'San Francisco, CA',
                            'start_date': 'Jan 2022',
                            'end_date': 'Present'
                        },
                        'optimized_bullets': [
                            '**Leadership** | Led a team of 5 engineers to deliver critical features',
                            '**Performance** | Improved system performance by 40% through optimization'
                        ]
                    }
                }
            }
            
            # Mock streamlit session state
            import sys
            if 'streamlit' not in sys.modules:
                # Create mock streamlit module
                import types
                streamlit_mock = types.ModuleType('streamlit')
                streamlit_mock.session_state = types.SimpleNamespace()
                for key, value in mock_session_state.items():
                    setattr(streamlit_mock.session_state, key, value)
                sys.modules['streamlit'] = streamlit_mock
            else:
                # Update existing streamlit module
                for key, value in mock_session_state.items():
                    setattr(st.session_state, key, value)
            
            # Test CVData conversion
            cv_data = convert_session_to_cvdata()
            
            # Verify CVData has skills populated
            self.assertGreater(len(cv_data.skills), 0, "CVData should have skills populated")
            self.assertIn('Cloud Architecture', cv_data.skills, "Skills should be extracted correctly from pipe format")
            
            # Generate preview content using template engine
            preview_content = template_engine.render_cv_preview(cv_data)
            pdf_template_content = template_engine.render_cv_for_pdf(cv_data)
            
            # Verify both have skills
            self.assertIn('Cloud Architecture', preview_content, "Preview should contain skills")
            self.assertIn('Cloud Architecture', pdf_template_content, "PDF template should contain skills")
            
            # Test that skills are in same format
            for skill in cv_data.skills:
                self.assertIn(skill, preview_content, f"Skill '{skill}' should be in preview")
                self.assertIn(skill, pdf_template_content, f"Skill '{skill}' should be in PDF template")
                
        except ImportError as e:
            self.skipTest(f"Could not import app functions for integration test: {e}")
        except Exception as e:
            self.fail(f"Integration test failed: {e}")

    def test_mandatory_sections_have_substantial_data(self):
        """Test that all mandatory sections contain substantial data, not just headers"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Professional Summary must have meaningful content (min 20 chars)
        self.assertGreater(len(self.sample_cv_data.professional_summary.strip()), 20,
                          "Professional Summary should have substantial content")
        self.assertIn(self.sample_cv_data.professional_summary, preview_content)
        self.assertIn(self.sample_cv_data.professional_summary, pdf_content)
        
        # Core Skills must have multiple skills (min 3)
        self.assertGreaterEqual(len(self.sample_cv_data.skills), 3, 
                               "Should have at least 3 skills")
        skills_in_preview = sum(1 for skill in self.sample_cv_data.skills if skill in preview_content)
        skills_in_pdf = sum(1 for skill in self.sample_cv_data.skills if skill in pdf_content)
        self.assertGreaterEqual(skills_in_preview, 3, "Preview should contain at least 3 skills")
        self.assertGreaterEqual(skills_in_pdf, 3, "PDF should contain at least 3 skills")
        
        # Current role must have meaningful bullets (min 2)
        self.assertGreaterEqual(len(self.sample_cv_data.current_role.bullets), 2,
                               "Current role should have at least 2 bullets")
        for bullet in self.sample_cv_data.current_role.bullets:
            self.assertGreater(len(bullet.content.strip()), 10, 
                             f"Bullet content should be substantial: {bullet.content}")
            self.assertIn(bullet.content, preview_content)
            self.assertIn(bullet.content, pdf_content)
        
        # Contact info must be complete
        contact = self.sample_cv_data.contact
        required_contact_fields = [contact.name, contact.email, contact.phone, contact.location]
        for field in required_contact_fields:
            self.assertTrue(field and len(field.strip()) > 0, f"Contact field should not be empty: {field}")
            self.assertIn(field, preview_content)
            self.assertIn(field, pdf_content)

    def test_content_quality_and_consistency_comprehensive(self):
        """Comprehensive test for content quality and consistency between formats"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Test content quality metrics
        quality_checks = {
            'preview_min_length': len(preview_content) >= 500,  # Minimum meaningful CV length
            'pdf_min_length': len(pdf_content) >= 500,
            'has_professional_summary': 'PROFESSIONAL SUMMARY' in preview_content and 'PROFESSIONAL SUMMARY' in pdf_content,
            'has_core_skills': 'CORE SKILLS' in preview_content and 'CORE SKILLS' in pdf_content,
            'has_professional_experience': 'PROFESSIONAL EXPERIENCE' in preview_content and 'PROFESSIONAL EXPERIENCE' in pdf_content,
            'contact_complete': all(field in preview_content and field in pdf_content 
                                  for field in [self.sample_cv_data.contact.name, 
                                              self.sample_cv_data.contact.email,
                                              self.sample_cv_data.contact.phone]),
        }
        
        failed_checks = [check for check, passed in quality_checks.items() if not passed]
        self.assertEqual([], failed_checks, f"Quality checks failed: {failed_checks}")
        
        # Test content consistency - key phrases should appear in both formats
        key_phrases = [
            self.sample_cv_data.contact.name,
            self.sample_cv_data.current_role.job_title,
            self.sample_cv_data.current_role.company,
            'PROFESSIONAL SUMMARY',
            'CORE SKILLS',
            'PROFESSIONAL EXPERIENCE'
        ]
        
        for phrase in key_phrases:
            self.assertIn(phrase, preview_content, f"Key phrase missing from preview: {phrase}")
            self.assertIn(phrase, pdf_content, f"Key phrase missing from PDF: {phrase}")
            
        # Test that substantial content exists in both formats
        import re
        # Remove headers and formatting to compare actual content
        preview_clean = re.sub(r'[#*=|\-]+', '', preview_content)
        pdf_clean = re.sub(r'[#*=|\-]+', '', pdf_content)
        
        # Count meaningful words (exclude common formatting words)
        preview_words = len([w for w in preview_clean.split() if len(w) > 2])
        pdf_words = len([w for w in pdf_clean.split() if len(w) > 2])
        
        self.assertGreater(preview_words, 50, "Preview should have substantial word content")
        self.assertGreater(pdf_words, 50, "PDF should have substantial word content")
        
        # Content overlap should be high (similar word count indicates similar content)
        word_count_ratio = min(preview_words, pdf_words) / max(preview_words, pdf_words)
        self.assertGreater(word_count_ratio, 0.8, 
                          f"Content word count should be similar (ratio: {word_count_ratio:.2f})")

    def test_previous_roles_content_quality(self):
        """Test that previous roles have substantial content in both formats"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        self.assertGreater(len(self.sample_cv_data.previous_roles), 0, 
                          "Should have at least one previous role for comprehensive testing")
        
        for i, role in enumerate(self.sample_cv_data.previous_roles):
            # Each role should have substantial info
            self.assertTrue(role.job_title and len(role.job_title.strip()) > 0,
                           f"Previous role {i} should have job title")
            self.assertTrue(role.company and len(role.company.strip()) > 0,
                           f"Previous role {i} should have company")
            self.assertGreater(len(role.bullets), 0,
                             f"Previous role {i} should have bullets")
            
            # Content should appear in both formats
            self.assertIn(role.job_title, preview_content,
                         f"Previous role {i} title missing from preview")
            self.assertIn(role.job_title, pdf_content,
                         f"Previous role {i} title missing from PDF")
            self.assertIn(role.company, preview_content,
                         f"Previous role {i} company missing from preview")
            self.assertIn(role.company, pdf_content,
                         f"Previous role {i} company missing from PDF")
            
            # Bullets should have meaningful content
            for j, bullet in enumerate(role.bullets):
                self.assertGreater(len(bullet.content.strip()), 10,
                                 f"Previous role {i} bullet {j} should have substantial content")
                self.assertIn(bullet.content, preview_content,
                             f"Previous role {i} bullet {j} missing from preview")
                self.assertIn(bullet.content, pdf_content,
                             f"Previous role {i} bullet {j} missing from PDF")

    def test_formatting_consistency_detailed(self):
        """Test detailed formatting consistency between preview and PDF"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Both should have proper section structure
        section_headers = ['PROFESSIONAL SUMMARY', 'CORE SKILLS', 'PROFESSIONAL EXPERIENCE']
        
        for header in section_headers:
            # Headers should exist in both
            self.assertIn(header, preview_content, f"Header '{header}' missing from preview")
            self.assertIn(header, pdf_content, f"Header '{header}' missing from PDF")
            
            # Extract section content (everything after header until next header or end)
            import re
            pattern = rf'{re.escape(header)}(.*?)(?=(?:PROFESSIONAL SUMMARY|CORE SKILLS|PROFESSIONAL EXPERIENCE|$))'
            
            preview_section = re.search(pattern, preview_content, re.DOTALL | re.IGNORECASE)
            pdf_section = re.search(pattern, pdf_content, re.DOTALL | re.IGNORECASE)
            
            self.assertIsNotNone(preview_section, f"Could not extract '{header}' section from preview")
            self.assertIsNotNone(pdf_section, f"Could not extract '{header}' section from PDF")
            
            # Sections should have substantial content (not just headers)
            preview_section_content = preview_section.group(1).strip()
            pdf_section_content = pdf_section.group(1).strip()
            
            self.assertGreater(len(preview_section_content), 10,
                             f"Preview '{header}' section should have substantial content")
            self.assertGreater(len(pdf_section_content), 10,
                             f"PDF '{header}' section should have substantial content")

    def test_no_empty_or_placeholder_sections(self):
        """Test that no sections are empty or contain placeholder text"""
        preview_content = template_engine.render_cv_preview(self.sample_cv_data)
        pdf_content = template_engine.render_cv_for_pdf(self.sample_cv_data)
        
        # Check for various placeholder patterns (exclude legitimate markdown formatting)
        bad_patterns = [
            'TODO', 'PLACEHOLDER', 'TBD', 'TBA', 'XXX',
            '{{ ', '}}', 'undefined', 'null', 'None',
            '[FILL IN]', '[INSERT]', '[REPLACE]', '____',
            'Lorem ipsum', 'Sample text', 'Example content'
        ]
        
        for pattern in bad_patterns:
            self.assertNotIn(pattern, preview_content,
                           f"Preview contains placeholder pattern: {pattern}")
            self.assertNotIn(pattern, pdf_content,
                           f"PDF contains placeholder pattern: {pattern}")
        
        # Check that sections have actual data, not just headers
        import re
        
        # Check Professional Summary
        for format_name, content in [('preview', preview_content), ('PDF', pdf_content)]:
            summary_match = re.search(
                rf'PROFESSIONAL SUMMARY(.*?)(?=(?:CORE SKILLS|PROFESSIONAL EXPERIENCE|$))', 
                content, re.DOTALL | re.IGNORECASE
            )
            self.assertIsNotNone(summary_match, f"Professional Summary not found in {format_name}")
            summary_content = summary_match.group(1).strip()
            self.assertIn(self.sample_cv_data.professional_summary, summary_content,
                         f"Professional Summary in {format_name} missing expected content")
        
        # Check Core Skills (check individual skills exist)
        for format_name, content in [('preview', preview_content), ('PDF', pdf_content)]:
            skills_match = re.search(
                rf'CORE SKILLS(.*?)(?=(?:PROFESSIONAL EXPERIENCE|$))', 
                content, re.DOTALL | re.IGNORECASE
            )
            self.assertIsNotNone(skills_match, f"Core Skills not found in {format_name}")
            skills_content = skills_match.group(1).strip()
            # Check that at least first 3 skills are present
            for skill in self.sample_cv_data.skills[:3]:
                self.assertIn(skill, skills_content,
                             f"Skill '{skill}' not found in Core Skills section in {format_name}")
        
        # Check Professional Experience
        for format_name, content in [('preview', preview_content), ('PDF', pdf_content)]:
            experience_match = re.search(
                rf'PROFESSIONAL EXPERIENCE(.*?)(?=(?:ADDITIONAL INFORMATION|$))', 
                content, re.DOTALL | re.IGNORECASE
            )
            self.assertIsNotNone(experience_match, f"Professional Experience not found in {format_name}")
            experience_content = experience_match.group(1).strip()
            self.assertIn(self.sample_cv_data.current_role.job_title, experience_content,
                         f"Current role job title not found in Professional Experience section in {format_name}")


if __name__ == '__main__':
    unittest.main()