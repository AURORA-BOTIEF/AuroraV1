
import logging
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_module_title_logic():
    # Mock book_data with a structure where Lesson 1 is skipped
    book_data = {
        "outline_modules": [
            {
                "title": "Module 1 Integration",
                "lessons": [
                    {"title": "Lab: First Activity"},  # Should be skipped
                    {"title": "Lesson 1: Introduction"}, # Should trigger module title if logic is correct
                ]
            }
        ]
    }

    # Simulate processing loop
    current_module_number = 1
    # Test case 1: Processing the "Lab" lesson (skipped)
    lesson_lab = {"title": "Lab: First Activity", "module_number": 1, "type": "lab"}
    
    # Test case 2: Processing the "Introduction" lesson
    lesson_intro = {"title": "Lesson 1: Introduction", "module_number": 1}
    
    print("\n--- Testing Lesson: Lab ---")
    process_lesson(lesson_lab, book_data)
    
    print("\n--- Testing Lesson: Intro ---")
    process_lesson(lesson_intro, book_data)

def process_lesson(lesson, book_data):
    lesson_title = lesson.get('title')
    current_module_number = lesson.get('module_number', 1)
    
    # Logic extracted from html_first_generator.py
    actual_lesson_number_in_module = 0
    if 'outline_modules' in book_data:
        outline_modules = book_data.get('outline_modules', [])
        if current_module_number <= len(outline_modules):
            module_info = outline_modules[current_module_number - 1]
            module_lessons = module_info.get('lessons', [])
            # Find which lesson this is in the module
            for idx, mod_lesson in enumerate(module_lessons, 1):
                # EXACT MATCH CHECK - Potential Point of Failure
                if mod_lesson.get('title', '') == lesson_title:
                    actual_lesson_number_in_module = idx
                    break
    
    print(f"Lesson Title: '{lesson_title}'")
    print(f"Actual Lesson Number: {actual_lesson_number_in_module}")
    
    # Logic: Insert module title slide ONLY for the first lesson of each module
    if actual_lesson_number_in_module == 1:
        print("MATCH: Adding Module Title Slide")
    else:
        print("NO MATCH: Not adding module title")

if __name__ == "__main__":
    test_module_title_logic()
