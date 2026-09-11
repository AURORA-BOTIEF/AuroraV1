import logging
from html_first_generator import HTMLSlideBuilder, generate_html_output, LayoutDefinitions

logging.basicConfig(level=logging.INFO)

print("Starting test...")

# Create mock slides with the new features
slides = [
    {
        "title": "Welcome to Slide Enhancements",
        "subtitle": "Testing new features",
        "layout": "text-only",
        "content_blocks": [
            {
                "type": "bullets",
                "items": ["We have added summarization", "We have added images", "We have added tables", "We have added code"]
            }
        ]
    },
    {
        "title": "Code Syntax Highlighting Test",
        "subtitle": "Should look like VS Code",
        "layout": "code-full",
        "content_blocks": [
            {
                "type": "code",
                "language": "python",
                "code": "def hello_world():\n    print('Hello world!')\n    return True\n\n# Test comment\nclass Test:\n    pass"
            }
        ]
    },
    {
        "title": "Table Rendering Test",
        "subtitle": "Data representation",
        "layout": "table",
        "content_blocks": [
            {
                "type": "table",
                "heading": "Example Data",
                "headers": ["Name", "Role", "City"],
                "rows": [
                    ["Alice", "Admin", "New York"],
                    ["Bob", "User", "London"],
                    ["Charlie", "Editor", "Paris"]
                ],
                "notes": "End of table."
            }
        ]
    },
    {
        "title": "Image Inclusion Test",
        "layout": "image-left",
        "content_blocks": [
            {
                "type": "image",
                "image_reference": "test_image",
                "caption": "A beautiful test image"
            },
            {
                "type": "bullets",
                "heading": "Image Points",
                "items": ["Point 1 about image", "Point 2 about image"]
            }
        ]
    }
]

# Map the mock image to a placeholder
image_mapping = {
    "test_image": "https://via.placeholder.com/500x380.png?text=Test+Image"
}

print("Calling generate_html_output...")

# Generate HTML
html = generate_html_output(
    slides=slides,
    style='professional',
    image_url_mapping=image_mapping,
    course_title="Quality Enhancements Test"
)

# Save to file
OUTPUT_FILE = "test_output.html"
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ HTML generated successfully and saved to {OUTPUT_FILE}")
