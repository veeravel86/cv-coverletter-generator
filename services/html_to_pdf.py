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
            line-height: 1.4;
            color: #333;
            background: white;
            font-size: 10pt;
        }
        
        .cv-container {
            max-width: 8.5in;
            margin: 0 auto;
            padding: 0.15in;
            background: white;
        }
        
        /* Header Styling */
        h1 {
            font-size: 20pt;
            font-weight: bold;
            color: #0077b5;
            text-align: center;
            margin-bottom: 4pt;
            border-bottom: 2px solid #0077b5;
            padding-bottom: 4pt;
        }
        
        /* Contact Info */
        .contact-info {
            text-align: center;
            margin-bottom: 8pt;
            color: #555;
            font-size: 7pt;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .contact-info span {
            margin: 0 4pt;
        }
        
        /* Section Headers */
        h2 {
            font-size: 12pt;
            font-weight: bold;
            color: #0077b5;
            margin-top: 10pt;
            margin-bottom: 4pt;
            border-bottom: 1px solid #0077b5;
            padding-bottom: 2pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        h3 {
            font-size: 11pt;
            font-weight: bold;
            color: #0077b5;
            margin-top: 6pt;
            margin-bottom: 2pt;
        }
        
        /* Professional Summary */
        .executive-summary {
            font-style: italic;
            background: #f8f9fa;
            padding: 6pt;
            border-left: 3px solid #0077b5;
            margin-bottom: 8pt;
            border-radius: 2px;
            color: #000000;
        }
        
        /* Core Skills */
        .core-skills {
            display: flex;
            flex-wrap: wrap;
            gap: 2pt;
            margin-bottom: 8pt;
            line-height: 1.1;
        }
        
        .skill-tag {
            background: #e1f5fe;
            color: #0077b5;
            padding: 2pt 6pt;
            border-radius: 8pt;
            font-size: 7.5pt;
            font-weight: bold;
            display: inline-block;
            border: 1px solid #0077b5;
            box-shadow: 0 1pt 2pt rgba(0,0,0,0.1);
        }
        
        /* Experience Section */
        .experience-item {
            margin-bottom: 8pt;
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
            color: #0077b5;
        }
        
        .role-dates {
            font-size: 9pt;
            color: #7f8c8d;
            font-style: italic;
        }
        
        .company-name {
            font-size: 11pt;
            color: #0077b5;
            margin-bottom: 6pt;
        }
        
        /* Bullet Points */
        ul {
            list-style: none;
            padding-left: 0;
            margin: 4pt 0;
        }
        
        li {
            margin-bottom: 2pt;
            padding-left: 12pt;
            position: relative;
            color: #000000;
        }
        
        li:before {
            content: "•";
            color: #0077b5;
            font-weight: bold;
            position: absolute;
            left: 0;
        }
        
        /* Bold headers in bullets - shaded like skill tags */
        li strong {
            background: #e1f5fe;
            color: #0077b5;
            padding: 1pt 4pt;
            border-radius: 4pt;
            font-size: 8pt;
            font-weight: bold;
            display: inline-block;
            border: 1px solid #0077b5;
            box-shadow: 0 1pt 2pt rgba(0,0,0,0.1);
            margin-right: 4pt;
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
                padding: 0.2in;
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