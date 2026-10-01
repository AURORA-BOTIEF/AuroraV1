
def calculate_target_words(lesson_data: dict, module_info: dict) -> int:
    """Calculate target word count for a lesson."""
    # This is the logic from strands_content_gen.py
    lesson_duration = lesson_data.get('duration_minutes', module_info.get('duration_minutes', 45))
    
    print(f"DEBUG: lesson_duration resolved to: {lesson_duration} (Type: {type(lesson_duration)})")

    lesson_bloom = lesson_data.get('bloom_level', module_info.get('bloom_level', 'Understand'))
    
    # Handle compound bloom levels
    if '/' in lesson_bloom:
        bloom_parts = [b.strip() for b in lesson_bloom.split('/')]
        bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
        lesson_bloom = max(bloom_parts, key=lambda x: bloom_order.index(x) if x in bloom_order else 0)
    
    # Bloom multipliers
    bloom_multipliers = {
        'Remember': 1.0,
        'Understand': 1.1,
        'Apply': 1.2,
        'Analyze': 1.3,
        'Evaluate': 1.4,
        'Create': 1.5
    }
    
    bloom_mult = bloom_multipliers.get(lesson_bloom, 1.1)
    
    # Base calculation: 45 words per minute for deep, academic content (approx 200-250 words per 5 min topic)
    try:
        base_words = lesson_duration * 45
        print(f"DEBUG: base_words calculated: {base_words}")
        base_words = int(base_words * bloom_mult)
        return base_words
    except Exception as e:
        print(f"CRASH DETECTED: {e}")
        return -1

# Test case matching the user's YAML
module_info = {'duration_minutes': 180, 'bloom_level': 'Understand'}
lesson_data_null = {'title': '1.1 ¿Qué son las bases de datos?', 'duration_minutes': None, 'bloom_level': 'Comprender'}

print("Testing with duration_minutes: null")
result = calculate_target_words(lesson_data_null, module_info)
