"""
Services package for CV and Cover Letter Generator
"""

from .template_engine import template_engine
from .parallel_processor import parallel_processor

__all__ = ['template_engine', 'parallel_processor']