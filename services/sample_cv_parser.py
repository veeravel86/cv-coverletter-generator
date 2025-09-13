import os
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

import streamlit as st
from openai import OpenAI

from models.cv_data import CVData, ContactInfo, RoleExperience, ExperienceBullet

logger = logging.getLogger(__name__)

@dataclass
class SampleCVParseConfig:
    temperature: float = 0.1
    max_tokens: int = 2000
    model: str = "gpt-4o-mini"  # Can be gpt-4o-mini, gpt-4o, or gpt-5

class SampleCVParser:
    def __init__(self, config: SampleCVParseConfig = None):
        self.config = config or SampleCVParseConfig()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def _get_model_compatible_params(self, model: str, max_tokens: int) -> Dict[str, Any]:
        """Get model-compatible parameters for OpenAI API calls"""
        # GPT-5 and newer models use max_completion_tokens
        if model in ["gpt-5"]:
            return {"max_completion_tokens": max_tokens}
        else:
            return {"max_tokens": max_tokens}
    
    def parse_sample_cv_to_json(self, sample_cv_text: str) -> Dict[str, Any]:
        """Parse sample CV text and return structured JSON data matching CVData format"""
        
        if not sample_cv_text or not sample_cv_text.strip():
            logger.warning("Empty sample CV text provided")
            return self._get_empty_cv_structure()
        
        try:
            # Create LLM prompt to extract structured data
            system_prompt = self._create_parsing_system_prompt()
            user_prompt = self._create_parsing_user_prompt(sample_cv_text)
            
            # Get model-compatible parameters
            token_params = self._get_model_compatible_params(self.config.model, self.config.max_tokens)
            
            response = self.openai_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                **token_params
            )
            
            raw_response = response.choices[0].message.content.strip()
            parsed_data = self._process_llm_response(raw_response)
            
            return {
                "cv_data": parsed_data,
                "raw_response": raw_response,
                "parsing_successful": True,
                "message": "Successfully parsed sample CV"
            }
            
        except Exception as e:
            logger.error(f"Error parsing sample CV: {e}")
            return {
                "cv_data": self._get_empty_cv_structure(),
                "raw_response": "",
                "parsing_successful": False,
                "message": f"Error parsing sample CV: {str(e)}"
            }
    
    def _create_parsing_system_prompt(self) -> str:
        return """You are an expert CV parser. Your task is to extract structured information from CV text and return it as valid JSON.

You must extract and structure ALL the information from the CV into the exact JSON format specified. Pay special attention to:
- Contact information (name, email, phone, location, linkedin, website)
- Professional summary/objective
- Complete work experience with achievements
- Skills and competencies
- Any additional sections (education, certifications, etc.)

CRITICAL FORMATTING REQUIREMENTS:
- Return ONLY valid JSON, no markdown code blocks, no explanations
- Use double quotes for all strings
- Properly escape special characters
- Each experience entry should have detailed achievement bullets
- Extract dates, locations, and company information accurately
- Professional summary should be concise but comprehensive

The output must match the CVData structure exactly."""
    
    def _create_parsing_user_prompt(self, sample_cv_text: str) -> str:
        return f"""Parse the following CV text and extract ALL information into the exact JSON structure below.

CV TEXT TO PARSE:
{sample_cv_text}

REQUIRED JSON OUTPUT FORMAT:
{{
  "contact": {{
    "name": "Full Name from CV",
    "email": "email@domain.com",
    "phone": "phone number",
    "location": "City, Country",
    "linkedin": "linkedin.com/in/profile or null",
    "website": "website URL or null"
  }},
  "professional_summary": "Professional summary/objective text from CV (comprehensive but concise)",
  "skills": [
    "Skill 1",
    "Skill 2",
    "Skill 3"
  ],
  "experience": [
    {{
      "company": "Company Name",
      "position": "Job Title",
      "location": "City, Country",
      "start_date": "MMM YYYY",
      "end_date": "MMM YYYY or Present",
      "duration": "X years Y months",
      "achievements": [
        "Achievement 1 with specific details and metrics if available",
        "Achievement 2 with impact and results",
        "Achievement 3 with technical details"
      ]
    }}
  ]
}}

PARSING INSTRUCTIONS:
1. Extract EXACT information from the CV text - do not invent or assume
2. For missing information, use "Not specified" or null as appropriate
3. Preserve all achievement bullets and work descriptions exactly as written
4. Calculate work duration from dates where possible
5. Extract ALL experience entries, not just the most recent
6. Include ALL skills mentioned in the CV
7. Professional summary should capture the essence of the candidate

Return ONLY the JSON object with all extracted information."""
    
    def _process_llm_response(self, raw_response: str) -> Dict[str, Any]:
        """Process and validate the LLM response"""
        
        # Clean the response - remove common prefixes/suffixes and markdown formatting
        clean_response = raw_response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()
        
        try:
            # Parse JSON
            parsed_data = json.loads(clean_response)
            
            # Validate and clean the structure
            validated_data = self._validate_cv_structure(parsed_data)
            
            return validated_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            return self._get_empty_cv_structure()
    
    def _validate_cv_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and ensure proper CV data structure"""
        
        validated = {
            "contact": {
                "name": data.get("contact", {}).get("name", "Not specified"),
                "email": data.get("contact", {}).get("email", "Not specified"),
                "phone": data.get("contact", {}).get("phone", "Not specified"),
                "location": data.get("contact", {}).get("location", "Not specified"),
                "linkedin": data.get("contact", {}).get("linkedin"),
                "website": data.get("contact", {}).get("website")
            },
            "professional_summary": data.get("professional_summary", "Professional summary not available"),
            "skills": data.get("skills", []),
            "experience": []
        }
        
        # Validate experience entries
        for exp in data.get("experience", []):
            if isinstance(exp, dict):
                validated_exp = {
                    "company": exp.get("company", "Not specified"),
                    "position": exp.get("position", "Not specified"),
                    "location": exp.get("location", "Not specified"),
                    "start_date": exp.get("start_date", "Not specified"),
                    "end_date": exp.get("end_date", "Not specified"),
                    "duration": exp.get("duration", "Not specified"),
                    "achievements": exp.get("achievements", [])
                }
                validated["experience"].append(validated_exp)
        
        return validated
    
    def _get_empty_cv_structure(self) -> Dict[str, Any]:
        """Return empty CV structure as fallback"""
        return {
            "contact": {
                "name": "Not specified",
                "email": "Not specified",
                "phone": "Not specified",
                "location": "Not specified",
                "linkedin": None,
                "website": None
            },
            "professional_summary": "Professional summary not available",
            "skills": [],
            "experience": []
        }
    
    def convert_to_cvdata_format(self, parsed_cv: Dict[str, Any]) -> Optional[Dict]:
        """Convert parsed CV data to a format compatible with the existing JSON viewer"""
        
        try:
            # For the JSON viewer, we return the simple dictionary format
            # The user wanted the same JSON structure for both sample and generated CV
            return parsed_cv
            
        except Exception as e:
            logger.error(f"Error in convert_to_cvdata_format: {e}")
            return parsed_cv
    
    def get_sample_cv_json(self, sample_cv_text: str) -> Dict[str, Any]:
        """Main method to parse sample CV and return JSON structure"""
        
        # Parse the CV text
        parse_result = self.parse_sample_cv_to_json(sample_cv_text)
        
        if not parse_result["parsing_successful"]:
            logger.warning("Sample CV parsing failed, returning empty structure")
        
        return {
            "cv_data": parse_result["cv_data"],
            "cvdata_object": self.convert_to_cvdata_format(parse_result["cv_data"]),
            "parsing_successful": parse_result["parsing_successful"],
            "raw_llm_response": parse_result["raw_response"],
            "message": parse_result["message"]
        }

@st.cache_resource
def get_sample_cv_parser():
    """Cached sample CV parser instance"""
    return SampleCVParser()

def parse_and_cache_sample_cv(sample_cv_text: str) -> Dict[str, Any]:
    """Parse sample CV and cache the result in session state"""
    
    if not sample_cv_text:
        return {"success": False, "message": "No sample CV text provided"}
    
    try:
        # Get parser instance
        parser = get_sample_cv_parser()
        
        # Parse the CV
        result = parser.get_sample_cv_json(sample_cv_text)
        
        # Cache in session state
        st.session_state.sample_cv_json = result["cv_data"]
        st.session_state.sample_cv_object = result["cvdata_object"]
        st.session_state.sample_cv_parsed = True
        
        logger.info("Sample CV successfully parsed and cached")
        return {
            "success": True,
            "message": result["message"],
            "cv_data": result["cv_data"],
            "parsing_successful": result["parsing_successful"]
        }
        
    except Exception as e:
        logger.error(f"Error parsing and caching sample CV: {e}")
        return {
            "success": False,
            "message": f"Error parsing sample CV: {str(e)}"
        }