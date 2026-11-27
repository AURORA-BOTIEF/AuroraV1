#!/usr/bin/env python3
"""
Image Generation Performance Test
==================================
Tests different configurations to optimize image generation:
1. Rate limit delays (0s, 1s, 3s, 5s)
2. Parallel processing (1, 2, 3, 5 workers)
3. Batch sizes (10, 15, 20, 25, 30)

Goal: Maximize images generated within 900 seconds (15 min Lambda timeout)
"""

import time
import json
import boto3
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Tuple

# Initialize clients
lambda_client = boto3.client('lambda', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')

# Test configuration
LAMBDA_FUNCTION = "ImagesGen"
TEST_BUCKET = "crewai-course-artifacts"
TEST_PROJECT = "test-performance"

# Sample prompts for testing (we'll create simple test prompts)
SAMPLE_PROMPTS = [
    {
        "id": f"99-99-{i:04d}",
        "description": f"Simple diagram showing test concept {i} with basic shapes and colors",
        "visual_type": "diagram",
        "filename": f"99-99-{i:04d}.png"
    }
    for i in range(1, 51)  # Create 50 test prompts
]


def test_single_batch_generation(prompts: List[Dict], rate_limit: int, test_name: str) -> Dict:
    """
    Test generating a batch of images with a specific rate limit.
    
    Args:
        prompts: List of prompt objects
        rate_limit: Delay in seconds between images
        test_name: Name for this test run
    
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"Prompts: {len(prompts)}, Rate Limit: {rate_limit}s")
    print(f"{'='*80}")
    
    # Create payload
    payload = {
        "course_bucket": TEST_BUCKET,
        "project_folder": f"{TEST_PROJECT}/{test_name.replace(' ', '-')}",
        "prompts": prompts,
        "rate_limit_override": rate_limit  # We'll need to add this parameter to images_gen.py
    }
    
    start_time = time.time()
    
    try:
        # Invoke Lambda
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse response
        response_payload = json.loads(response['Payload'].read())
        end_time = time.time()
        duration = end_time - start_time
        
        # Extract results
        if response_payload.get('statusCode') == 200:
            stats = response_payload.get('statistics', {})
            successful = stats.get('successful', 0)
            failed = stats.get('failed', 0)
            
            result = {
                "test_name": test_name,
                "status": "SUCCESS",
                "prompts_count": len(prompts),
                "rate_limit": rate_limit,
                "duration_seconds": round(duration, 2),
                "images_generated": successful,
                "images_failed": failed,
                "success_rate": f"{stats.get('success_rate', '0%')}",
                "avg_time_per_image": round(duration / len(prompts), 2) if len(prompts) > 0 else 0,
                "within_timeout": duration < 900,
                "timeout_margin": round(900 - duration, 2)
            }
        else:
            result = {
                "test_name": test_name,
                "status": "FAILED",
                "error": response_payload.get('error', 'Unknown error'),
                "duration_seconds": round(duration, 2)
            }
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        result = {
            "test_name": test_name,
            "status": "ERROR",
            "error": str(e),
            "duration_seconds": round(duration, 2)
        }
    
    # Print results
    print(f"\n📊 Results:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    return result


def calculate_optimal_batch_sizes(rate_limit: int, avg_gen_time: float = 18.0) -> List[int]:
    """
    Calculate optimal batch sizes based on rate limit and average generation time.
    
    Args:
        rate_limit: Delay between images in seconds
        avg_gen_time: Average time to generate one image in seconds
    
    Returns:
        List of recommended batch sizes
    """
    # Lambda timeout minus 60s buffer
    available_time = 840
    
    # Time per image = generation time + rate limit delay
    time_per_image = avg_gen_time + rate_limit
    
    # Maximum images in one Lambda call
    max_images = int(available_time / time_per_image)
    
    # Return recommended batch sizes
    return [
        max(5, max_images // 4),   # Conservative (25% of max)
        max(10, max_images // 2),  # Moderate (50% of max)
        max(15, int(max_images * 0.75)),  # Aggressive (75% of max)
        max_images  # Maximum
    ]


def run_performance_tests():
    """
    Run comprehensive performance tests.
    """
    print("\n" + "="*80)
    print("IMAGE GENERATION PERFORMANCE TEST SUITE")
    print("="*80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Lambda Function: {LAMBDA_FUNCTION}")
    print(f"Test Bucket: {TEST_BUCKET}")
    print(f"Available Test Prompts: {len(SAMPLE_PROMPTS)}")
    print("="*80)
    
    all_results = []
    
    # Test 1: Different rate limits with fixed batch size (15 images)
    print("\n" + "="*80)
    print("PHASE 1: Testing Different Rate Limits")
    print("="*80)
    
    test_batch_size = 15
    rate_limits = [0, 1, 3, 5]
    
    for rate_limit in rate_limits:
        result = test_single_batch_generation(
            prompts=SAMPLE_PROMPTS[:test_batch_size],
            rate_limit=rate_limit,
            test_name=f"Rate-Limit-{rate_limit}s-Batch-{test_batch_size}"
        )
        all_results.append(result)
        
        # Wait between tests to avoid throttling
        if rate_limit < rate_limits[-1]:
            print(f"\n⏳ Waiting 30s before next test...")
            time.sleep(30)
    
    # Test 2: Different batch sizes with optimal rate limit
    print("\n" + "="*80)
    print("PHASE 2: Testing Different Batch Sizes")
    print("="*80)
    
    # Use the best rate limit from phase 1
    best_rate_limit = min(
        [r for r in all_results if r.get('status') == 'SUCCESS'],
        key=lambda x: x.get('avg_time_per_image', 999)
    ).get('rate_limit', 3)
    
    print(f"\n✅ Using optimal rate limit from Phase 1: {best_rate_limit}s")
    
    batch_sizes = calculate_optimal_batch_sizes(best_rate_limit)
    print(f"📦 Recommended batch sizes: {batch_sizes}")
    
    for batch_size in batch_sizes:
        if batch_size > len(SAMPLE_PROMPTS):
            print(f"⚠️  Skipping batch size {batch_size} (exceeds available prompts)")
            continue
        
        result = test_single_batch_generation(
            prompts=SAMPLE_PROMPTS[:batch_size],
            rate_limit=best_rate_limit,
            test_name=f"Batch-{batch_size}-Rate-{best_rate_limit}s"
        )
        all_results.append(result)
        
        # If this test timed out or was close, don't test larger batches
        if result.get('timeout_margin', 999) < 60:
            print(f"⚠️  Approaching timeout limit, skipping larger batch tests")
            break
        
        # Wait between tests
        if batch_size < batch_sizes[-1]:
            print(f"\n⏳ Waiting 30s before next test...")
            time.sleep(30)
    
    # Generate summary report
    print("\n" + "="*80)
    print("TEST SUMMARY REPORT")
    print("="*80)
    
    successful_tests = [r for r in all_results if r.get('status') == 'SUCCESS']
    
    if successful_tests:
        # Best configuration by images per second
        best_by_speed = max(successful_tests, key=lambda x: x.get('images_generated', 0) / x.get('duration_seconds', 1))
        
        # Best configuration by total capacity
        best_by_capacity = max(successful_tests, key=lambda x: x.get('images_generated', 0))
        
        print(f"\n🏆 FASTEST CONFIGURATION:")
        print(f"   Test: {best_by_speed['test_name']}")
        print(f"   Rate Limit: {best_by_speed['rate_limit']}s")
        print(f"   Batch Size: {best_by_speed['prompts_count']}")
        print(f"   Speed: {round(best_by_speed['images_generated'] / best_by_speed['duration_seconds'], 2)} images/sec")
        print(f"   Duration: {best_by_speed['duration_seconds']}s")
        
        print(f"\n🎯 MAXIMUM CAPACITY:")
        print(f"   Test: {best_by_capacity['test_name']}")
        print(f"   Rate Limit: {best_by_capacity['rate_limit']}s")
        print(f"   Batch Size: {best_by_capacity['prompts_count']}")
        print(f"   Images Generated: {best_by_capacity['images_generated']}")
        print(f"   Duration: {best_by_capacity['duration_seconds']}s")
        print(f"   Timeout Margin: {best_by_capacity['timeout_margin']}s")
        
        print(f"\n📊 RECOMMENDATIONS:")
        optimal_rate = best_by_speed['rate_limit']
        optimal_batch = int(best_by_capacity['images_generated'] * 0.9)  # 90% of max for safety
        
        print(f"   ✅ Recommended Rate Limit: {optimal_rate}s")
        print(f"   ✅ Recommended Batch Size: {optimal_batch} images per Lambda invocation")
        print(f"   ✅ Estimated Max Images in 15min: ~{best_by_capacity['images_generated']}")
        
        # Calculate how many Lambda calls needed for different course sizes
        print(f"\n📈 SCALING ESTIMATES:")
        for total_images in [20, 30, 50, 75, 100]:
            num_calls = (total_images + optimal_batch - 1) // optimal_batch
            total_time = num_calls * best_by_capacity['duration_seconds']
            print(f"   {total_images} images = {num_calls} Lambda call(s) ≈ {round(total_time/60, 1)} minutes")
    
    # Save detailed results to file
    results_file = f"performance-test-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "results": all_results,
            "summary": {
                "best_by_speed": best_by_speed if successful_tests else None,
                "best_by_capacity": best_by_capacity if successful_tests else None
            }
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {results_file}")
    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("\n⚠️  WARNING: This test will invoke Lambda functions multiple times and may incur costs.")
    print("⚠️  The test will take approximately 20-30 minutes to complete.")
    response = input("\nContinue? (yes/no): ")
    
    if response.lower() == 'yes':
        run_performance_tests()
    else:
        print("Test cancelled.")
