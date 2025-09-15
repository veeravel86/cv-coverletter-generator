#!/usr/bin/env python3
"""
Test script to verify GPT-5 model compatibility across all services.
This ensures all services correctly use max_completion_tokens for GPT-5.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.llm import OpenAILLMService
from services.skills_generator import SkillsGenerationConfig, SkillsGenerator
from services.experience_generator import ExperienceGenerationConfig, ExperienceGenerator  
from services.summary_generator import SummaryGenerationConfig, SummaryGenerator
from services.sample_cv_parser import SampleCVParseConfig, SampleCVParser
from services.ingest import PDFIngestor

def test_model_compatibility():
    """Test that all services handle GPT-5 model parameters correctly"""
    
    test_results = []
    
    # Test cases: [service_name, model, expected_param]
    test_cases = [
        ("gpt-4o-mini", "max_tokens"),
        ("gpt-4o", "max_tokens"), 
        ("gpt-5", "max_completion_tokens")
    ]
    
    print("🧪 Testing Model Compatibility Across All Services")
    print("=" * 60)
    
    # Test 1: OpenAILLMService static method
    print("\n1. Testing OpenAILLMService...")
    for model, expected_param in test_cases:
        params = OpenAILLMService._get_model_compatible_params_static(model, 1000)
        has_correct_param = expected_param in params
        print(f"   ✅ {model}: {expected_param} ({'✓' if has_correct_param else '✗'})")
        test_results.append(("OpenAILLMService", model, has_correct_param))
    
    # Test 2: SkillsGenerator
    print("\n2. Testing SkillsGenerator...")
    skills_config = SkillsGenerationConfig()
    skills_gen = SkillsGenerator(skills_config)
    for model, expected_param in test_cases:
        params = skills_gen._get_model_compatible_params(model, 1000)
        has_correct_param = expected_param in params
        print(f"   ✅ {model}: {expected_param} ({'✓' if has_correct_param else '✗'})")
        test_results.append(("SkillsGenerator", model, has_correct_param))
    
    # Test 3: ExperienceGenerator
    print("\n3. Testing ExperienceGenerator...")
    exp_config = ExperienceGenerationConfig()
    exp_gen = ExperienceGenerator(exp_config)
    for model, expected_param in test_cases:
        params = exp_gen._get_model_compatible_params(model, 1000)
        has_correct_param = expected_param in params
        print(f"   ✅ {model}: {expected_param} ({'✓' if has_correct_param else '✗'})")
        test_results.append(("ExperienceGenerator", model, has_correct_param))
    
    # Test 4: SummaryGenerator
    print("\n4. Testing SummaryGenerator...")
    summary_config = SummaryGenerationConfig()
    summary_gen = SummaryGenerator(summary_config)
    for model, expected_param in test_cases:
        params = summary_gen._get_model_compatible_params(model, 1000)
        has_correct_param = expected_param in params
        print(f"   ✅ {model}: {expected_param} ({'✓' if has_correct_param else '✗'})")
        test_results.append(("SummaryGenerator", model, has_correct_param))
    
    # Test 5: SampleCVParser
    print("\n5. Testing SampleCVParser...")
    parser_config = SampleCVParseConfig()
    parser = SampleCVParser(parser_config)
    for model, expected_param in test_cases:
        params = parser._get_model_compatible_params(model, 1000)
        has_correct_param = expected_param in params
        print(f"   ✅ {model}: {expected_param} ({'✓' if has_correct_param else '✗'})")
        test_results.append(("SampleCVParser", model, has_correct_param))
    
    # Test 6: PDFIngestor
    print("\n6. Testing PDFIngestor...")
    ingest_service = PDFIngestor()
    for model, expected_param in test_cases:
        params = ingest_service._get_model_compatible_params(model, 1000)
        has_correct_param = expected_param in params
        print(f"   ✅ {model}: {expected_param} ({'✓' if has_correct_param else '✗'})")
        test_results.append(("PDFIngestor", model, has_correct_param))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    failed_tests = [r for r in test_results if not r[2]]
    passed_tests = [r for r in test_results if r[2]]
    
    print(f"✅ Passed: {len(passed_tests)}")
    print(f"❌ Failed: {len(failed_tests)}")
    
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for service, model, _ in failed_tests:
            print(f"   - {service} with {model}")
        return False
    else:
        print("\n🎉 ALL TESTS PASSED! All services correctly handle GPT-5 compatibility.")
        return True

if __name__ == "__main__":
    success = test_model_compatibility()
    sys.exit(0 if success else 1)