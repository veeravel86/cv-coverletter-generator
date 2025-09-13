"""
HTML to PDF Conversion Service - Convert beautiful HTML CV previews to PDF
"""

import weasyprint
import markdown
import tempfile
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class HTMLToPDFConverter:
    """Service for converting HTML/Markdown CV previews to PDF"""
    
    def __init__(self):
        """Initialize the HTML to PDF converter"""
        self.css_styles = self._get_cv_styles()
    
    def convert_markdown_to_pdf(self, markdown_content: str, output_path: Optional[str] = None) -> bytes:
        """
        Convert markdown CV content to PDF
        
        Args:
            markdown_content: The markdown content from CV preview
            output_path: Optional path to save PDF file
            
        Returns:
            PDF content as bytes
        """
        try:
            # Convert markdown to HTML
            html_content = markdown.markdown(
                markdown_content, 
                extensions=['tables', 'fenced_code', 'nl2br']
            )
            
            # Wrap in full HTML document with styling
            full_html = self._create_styled_html(html_content)
            
            # Convert to PDF using WeasyPrint
            pdf_bytes = self._html_to_pdf(full_html, output_path)
            
            logger.info(f"✅ Successfully converted CV markdown to PDF ({len(pdf_bytes)} bytes)")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"❌ Failed to convert markdown to PDF: {str(e)}")
            raise
    
    def convert_html_to_pdf(self, html_content: str, output_path: Optional[str] = None) -> bytes:
        """
        Convert HTML CV content to PDF
        
        Args:
            html_content: The HTML content
            output_path: Optional path to save PDF file
            
        Returns:
            PDF content as bytes
        """
        try:
            # Add styling if not already present
            if '<head>' not in html_content.lower():
                styled_html = self._create_styled_html(html_content)
            else:
                styled_html = html_content
            
            # Convert to PDF
            pdf_bytes = self._html_to_pdf(styled_html, output_path)
            
            logger.info(f"✅ Successfully converted HTML to PDF ({len(pdf_bytes)} bytes)")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"❌ Failed to convert HTML to PDF: {str(e)}")
            raise
    
    def _html_to_pdf(self, html_content: str, output_path: Optional[str] = None) -> bytes:
        """Convert HTML content to PDF using WeasyPrint"""
        try:
            # Create HTML document
            html_doc = weasyprint.HTML(string=html_content)
            
            if output_path:
                # Write to file and also return bytes
                html_doc.write_pdf(output_path)
                with open(output_path, 'rb') as f:
                    return f.read()
            else:
                # Return bytes directly
                return html_doc.write_pdf()
                
        except Exception as e:
            logger.error(f"❌ WeasyPrint conversion failed: {str(e)}")
            raise
    
    def _create_styled_html(self, body_content: str) -> str:
        """Wrap content in full HTML document with professional styling"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CV</title>
    <style>
        {self.css_styles}
    </style>
</head>
<body>
    <div class="cv-container">
        {body_content}
    </div>
</body>
</html>
"""
    
    def _get_cv_styles(self) -> str:
        """Get professional CV styling that matches the preview"""
        return """
        /* Professional CV Styling */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', 'Helvetica', sans-serif;
            line-height: 1.6;
            color: #333;
            background: white;
            font-size: 11pt;
        }
        
        .cv-container {
            max-width: 8.5in;
            margin: 0 auto;
            padding: 0.75in;
            background: white;
        }
        
        /* Header Styling */
        h1 {
            font-size: 24pt;
            font-weight: bold;
            color: #2c3e50;
            text-align: center;
            margin-bottom: 8pt;
            border-bottom: 2px solid #3498db;
            padding-bottom: 6pt;
        }
        
        /* Contact Info */
        .contact-info {
            text-align: center;
            margin-bottom: 16pt;
            color: #555;
            font-size: 10pt;
        }
        
        .contact-info span {
            margin: 0 8pt;
        }
        
        /* Section Headers */
        h2 {
            font-size: 14pt;
            font-weight: bold;
            color: #2c3e50;
            margin-top: 20pt;
            margin-bottom: 8pt;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 4pt;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        h3 {
            font-size: 12pt;
            font-weight: bold;
            color: #34495e;
            margin-top: 12pt;
            margin-bottom: 4pt;
        }
        
        /* Professional Summary */
        .executive-summary {
            font-style: italic;
            background: #f8f9fa;
            padding: 12pt;
            border-left: 4px solid #3498db;
            margin-bottom: 16pt;
            border-radius: 4px;
        }
        
        /* Core Skills */
        .core-skills {
            display: flex;
            flex-wrap: wrap;
            gap: 8pt;
            margin-bottom: 16pt;
        }
        
        .skill-tag {
            background: #3498db;
            color: white;
            padding: 4pt 8pt;
            border-radius: 12pt;
            font-size: 9pt;
            font-weight: bold;
            display: inline-block;
        }
        
        /* Experience Section */
        .experience-item {
            margin-bottom: 16pt;
            page-break-inside: avoid;
        }
        
        .role-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4pt;
        }
        
        .role-title {
            font-weight: bold;
            font-size: 12pt;
            color: #2c3e50;
        }
        
        .role-dates {
            font-size: 10pt;
            color: #7f8c8d;
            font-style: italic;
        }
        
        .company-name {
            font-size: 11pt;
            color: #34495e;
            margin-bottom: 6pt;
        }
        
        /* Bullet Points */
        ul {
            list-style: none;
            padding-left: 0;
            margin: 8pt 0;
        }
        
        li {
            margin-bottom: 4pt;
            padding-left: 16pt;
            position: relative;
        }
        
        li:before {
            content: "•";
            color: #3498db;
            font-weight: bold;
            position: absolute;
            left: 0;
        }
        
        /* Bold headers in bullets */
        li strong {
            color: #2c3e50;
        }
        
        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 8pt 0;
        }
        
        th, td {
            padding: 6pt;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background: #f8f9fa;
            font-weight: bold;
            color: #2c3e50;
        }
        
        /* Page breaks */
        .page-break {
            page-break-before: always;
        }
        
        /* Print optimizations */
        @media print {
            .cv-container {
                margin: 0;
                padding: 0.5in;
                box-shadow: none;
            }
            
            body {
                font-size: 10pt;
            }
        }
        
        /* Additional Info Section */
        .additional-info {
            background: #f8f9fa;
            padding: 12pt;
            border-radius: 4px;
            margin-top: 16pt;
        }
        
        .additional-info h3 {
            color: #2c3e50;
            margin-bottom: 8pt;
        }
        
        /* Responsive design */
        @media (max-width: 8.5in) {
            .cv-container {
                padding: 0.5in;
            }
            
            .role-header {
                flex-direction: column;
                align-items: flex-start;
            }
        }
        """


# Global converter instance
html_to_pdf_converter = HTMLToPDFConverter()