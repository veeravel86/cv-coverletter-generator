"""
Parallel Processing Service - Concurrent LLM calls and document processing
"""

import asyncio
import concurrent.futures
from typing import Dict, List, Any, Callable, Optional
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ParallelProcessor:
    """Service for running parallel/concurrent operations to speed up document processing"""
    
    def __init__(self, max_workers: int = 5):
        """Initialize with maximum concurrent workers"""
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    
    def run_parallel_llm_calls(self, llm_service, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run multiple LLM calls in parallel
        
        Args:
            llm_service: The LLM service instance
            tasks: List of task dictionaries with keys: 'name', 'prompt', 'max_tokens'
        
        Returns:
            Dictionary with task names as keys and responses as values
        """
        def make_llm_call(task):
            """Make a single LLM call"""
            try:
                start_time = time.time()
                response = llm_service.generate_content(
                    task['prompt'], 
                    max_tokens=task.get('max_tokens', 500)
                )
                elapsed = time.time() - start_time
                logger.info(f"✅ LLM call '{task['name']}' completed in {elapsed:.2f}s")
                return task['name'], response, True
            except Exception as e:
                logger.error(f"❌ LLM call '{task['name']}' failed: {str(e)}")
                return task['name'], str(e), False
        
        # Submit all tasks to thread pool
        futures = {self.executor.submit(make_llm_call, task): task['name'] for task in tasks}
        
        results = {}
        errors = {}
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            task_name, response, success = future.result()
            if success:
                results[task_name] = response
            else:
                errors[task_name] = response
        
        # Log summary
        total_tasks = len(tasks)
        successful = len(results)
        failed = len(errors)
        
        logger.info(f"🎯 Parallel LLM processing complete: {successful}/{total_tasks} successful, {failed} failed")
        
        if errors:
            logger.warning(f"⚠️ Failed tasks: {list(errors.keys())}")
        
        return {
            'results': results,
            'errors': errors,
            'summary': {
                'total': total_tasks,
                'successful': successful,
                'failed': failed
            }
        }
    
    def run_parallel_cv_sections(self, llm_service, context_builder) -> Dict[str, Any]:
        """
        Generate all independent CV sections in parallel
        
        Returns:
            Dictionary with section names and their generated content
        """
        # Get superset context once for all sections
        superset_context = context_builder.retriever.get_superset_context()
        
        # Define all independent CV generation tasks
        tasks = [
            {
                'name': 'executive_summary',
                'prompt': self._create_executive_summary_prompt(superset_context),
                'max_tokens': 200
            },
            {
                'name': 'top_skills',
                'prompt': self._create_top_skills_prompt(superset_context),
                'max_tokens': 500
            },
            {
                'name': 'additional_info',
                'prompt': self._create_additional_info_prompt(superset_context),
                'max_tokens': 500
            }
        ]
        
        logger.info(f"🚀 Starting parallel CV section generation ({len(tasks)} sections)")
        start_time = time.time()
        
        # Run all tasks in parallel
        results = self.run_parallel_llm_calls(llm_service, tasks)
        
        elapsed = time.time() - start_time
        logger.info(f"⚡ Parallel CV sections completed in {elapsed:.2f}s")
        
        return results
    
    def run_parallel_experience_bullets(self, llm_service, context_builder, role_data: Dict) -> List[str]:
        """
        Generate experience bullets for multiple roles in parallel
        
        Args:
            llm_service: LLM service instance
            context_builder: Context builder for retrieving context
            role_data: Dictionary with role information
        
        Returns:
            List of optimized bullet points
        """
        if not role_data.get('key_bullets'):
            return []
        
        bullets = role_data['key_bullets']
        role_name = role_data.get('position_name', 'Position')
        company = role_data.get('company_name', 'Company')
        
        # Create optimization task for the role
        bullet_prompt = f"""You are an expert CV writer. Transform the following work experience bullets into professional SAR (Situation-Action-Result) format.

ROLE CONTEXT:
Position: {role_name}
Company: {company}

ORIGINAL BULLETS:
{chr(10).join(bullets)}

OPTIMIZATION RULES:
1. Use SAR format: Situation | Action | Result
2. Start with 2-word bold heading: **Action Verb + Focus**
3. Include quantified results when possible
4. Keep each bullet under 25 words
5. Use impactful action verbs
6. Maintain professional tone

FORMATTING:
- Format: **Heading** | SAR content
- Example: **System Design** | Architected microservices platform that reduced deployment time by 60% and improved system reliability for 50k+ users

OUTPUT FORMAT (JSON):
{{
  "optimized_bullets": [
    "**First Action** | Professional SAR format bullet 1",
    "**Second Action** | Professional SAR format bullet 2",
    "**Third Action** | Professional SAR format bullet 3"
  ]
}}"""
        
        task = {
            'name': f'{role_name}_bullets',
            'prompt': bullet_prompt,
            'max_tokens': 1500
        }
        
        results = self.run_parallel_llm_calls(llm_service, [task])
        
        if results['results']:
            try:
                import json
                bullet_response = list(results['results'].values())[0]
                
                # Clean the response - remove markdown code blocks if present
                cleaned_response = bullet_response.strip()
                if '```json' in cleaned_response:
                    # Extract JSON from markdown code block
                    start_idx = cleaned_response.find('```json') + 7
                    end_idx = cleaned_response.find('```', start_idx)
                    if end_idx > start_idx:
                        cleaned_response = cleaned_response[start_idx:end_idx].strip()
                elif '```' in cleaned_response:
                    # Remove any markdown code blocks
                    cleaned_response = cleaned_response.replace('```', '').strip()
                
                bullet_data = json.loads(cleaned_response)
                return bullet_data.get('optimized_bullets', bullets)
            except:
                logger.warning(f"⚠️ JSON parsing failed for {role_name} bullets, using original")
                return bullets
        
        return bullets
    
    def run_parallel_document_processing(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process multiple documents in parallel (PDF extraction, embeddings, etc.)
        
        Args:
            documents: List of document dictionaries with processing instructions
            
        Returns:
            Dictionary with document processing results
        """
        def process_document(doc_config):
            """Process a single document"""
            try:
                doc_id = doc_config['id']
                doc_path = doc_config['path']
                processor_func = doc_config['processor']
                
                start_time = time.time()
                result = processor_func(doc_path)
                elapsed = time.time() - start_time
                
                logger.info(f"✅ Document '{doc_id}' processed in {elapsed:.2f}s")
                return doc_id, result, True
                
            except Exception as e:
                logger.error(f"❌ Document '{doc_config['id']}' processing failed: {str(e)}")
                return doc_config['id'], str(e), False
        
        if not documents:
            return {'results': {}, 'errors': {}, 'summary': {'total': 0, 'successful': 0, 'failed': 0}}
        
        # Submit all document processing tasks
        futures = {self.executor.submit(process_document, doc): doc['id'] for doc in documents}
        
        results = {}
        errors = {}
        
        # Collect results
        for future in concurrent.futures.as_completed(futures):
            doc_id, result, success = future.result()
            if success:
                results[doc_id] = result
            else:
                errors[doc_id] = result
        
        logger.info(f"📄 Parallel document processing complete: {len(results)}/{len(documents)} successful")
        
        return {
            'results': results,
            'errors': errors,
            'summary': {
                'total': len(documents),
                'successful': len(results),
                'failed': len(errors)
            }
        }
    
    def _create_executive_summary_prompt(self, context: str) -> str:
        """Create prompt for executive summary generation"""
        return f"""Generate a compelling 2-sentence executive summary (max 40 words) for this professional profile.

CONTEXT:
{context}

REQUIREMENTS:
- Maximum 40 words total
- 2 sentences maximum  
- Focus on leadership, technical expertise, and business impact
- Use active voice and strong action verbs
- Highlight unique value proposition

EXAMPLES:
- "Senior Engineering Manager with 8+ years leading cross-functional teams to deliver scalable solutions. Proven track record of driving digital transformation initiatives that increased operational efficiency by 40% across global organizations."

- "Results-driven Technology Leader specializing in AI/ML implementation and team development. Successfully scaled engineering teams from 5 to 50+ while maintaining 95%+ code quality and reducing deployment cycles by 60%."

Generate a professional executive summary following this format."""
    
    def _create_top_skills_prompt(self, context: str) -> str:
        """Create prompt for top skills generation"""
        return f"""Extract and format the TOP 10 most relevant professional skills from this profile.

CONTEXT:
{context}

REQUIREMENTS:
1. Extract EXACTLY 10 skills
2. Focus on technical skills, leadership abilities, and core competencies
3. Use professional terminology
4. Format as: **Skill Name**
5. Prioritize by relevance and impact
6. Include mix of technical and soft skills

FORMAT EXAMPLE:
**Cloud Architecture** | **Team Leadership** | **Python Development** | **Strategic Planning** | **DevOps Practices** | **Stakeholder Management** | **Data Analytics** | **Process Optimization** | **Cross-functional Collaboration** | **Performance Management**

Output the skills in the exact format shown above, separated by " | "."""
    
    def _create_additional_info_prompt(self, context: str) -> str:
        """Create prompt for additional info generation"""
        return f"""Generate an additional information section highlighting certifications, awards, publications, or notable achievements.

CONTEXT:
{context}

REQUIREMENTS:
- Include certifications, awards, publications, patents, or speaking engagements
- Format as bullet points with **Bold Headers**
- Maximum 5 items
- Focus on professional achievements that add credibility
- Only include items explicitly mentioned in the context

FORMAT EXAMPLE:
**CERTIFICATIONS & ACHIEVEMENTS**

• **AWS Solutions Architect** | Professional certification for cloud architecture design
• **Published Research** | Co-authored paper on "AI in Financial Services" (IEEE Conference 2023)  
• **Industry Recognition** | Named "Top 40 Under 40" technology leaders by Tech Weekly Magazine
• **Patent Holder** | US Patent for "Automated Data Processing System" (#11,234,567)

Generate similar content based on the provided context. If no additional achievements are found, return "No additional certifications or achievements specified in the provided context."
"""
    
    def cleanup(self):
        """Clean up the thread pool executor"""
        try:
            self.executor.shutdown(wait=True)
            logger.info("🧹 Parallel processor cleanup completed")
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {str(e)}")


# Global parallel processor instance
parallel_processor = ParallelProcessor(max_workers=5)