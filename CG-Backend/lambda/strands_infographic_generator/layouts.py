"""
Slide Layout Definitions for HTML-First Architecture
=====================================================

Each layout defines:
1. Layout type and purpose
2. Exact container dimensions (pixels)
3. HTML template structure
4. AI guidelines for content generation

The AI agent uses these layouts to generate HTML directly,
knowing exactly how much space is available in each container.

SLIDE DIMENSIONS: 1280px × 720px
- Header: 120px (title + subtitle)
- Footer: 100px (reserved for logo + margin)
- Content Area: 500px (720 - 120 - 100)
"""

# =============================================================================
# LAYOUT SPECIFICATIONS
# =============================================================================

LAYOUTS = {
    # =========================================================================
    # TEXT-ONLY LAYOUT
    # Full width for bullet points, no images
    # Container: 400px height (with subtitle) or 450px (without)
    # =========================================================================
    "text-only": {
        "name": "Text Only",
        "description": "Full-width bullet points without images",
        "containers": {
            "content": {
                "width": 1160,   # 1280 - 60px padding each side
                "height": 400,  # Conservative to prevent overflow
                "purpose": "Bullet points, callouts, or paragraphs"
            }
        },
        "max_bullets": 8,  # 400px / 50px per bullet = 8 bullets
        "guidelines": """
CONTAINER: 1160px × 400px for all text content
- Each bullet line: ~50px height (font + line-height + margin)
- Maximum 8 bullets to prevent overflow
- If more content needed, SPLIT to continuation slide
        """
    },
    
    # =========================================================================
    # TEXT + CODE LAYOUT
    # Split: text on top, code block on bottom
    # =========================================================================
    "text-code": {
        "name": "Text + Code",
        "description": "Bullet points above, code block below",
        "containers": {
            "text": {
                "width": 1160,
                "height": 150,  # Top portion for explanatory text
                "purpose": "2-3 bullets explaining the code"
            },
            "code": {
                "width": 1160,
                "height": 250,  # Bottom portion for code
                "purpose": "Code snippet with syntax highlighting"
            }
        },
        "max_bullets": 3,  # Only 3 bullets with code
        "max_code_lines": 10,  # ~10 lines of code
        "guidelines": """
TEXT CONTAINER: 1160px × 150px (top)
- Maximum 3 bullets (50px each = 150px)
- Brief explanation of what the code demonstrates

CODE CONTAINER: 1160px × 250px (bottom)
- ~10 lines of code maximum
- Code fills available space without scroll if possible
        """
    },
    
    # =========================================================================
    # TEXT + IMAGE (Side by Side)
    # ALWAYS include explanatory bullets with images
    # =========================================================================
    "text-image-left": {
        "name": "Text + Image (Image Left)",
        "description": "Image on left 50%, bullets on right 50%",
        "containers": {
            "image": {
                "width": 520,
                "height": 380,
                "purpose": "Image, diagram, or screenshot"
            },
            "text": {
                "width": 520,
                "height": 380,
                "purpose": "Bullet points explaining the image"
            }
        },
        "max_bullets": 7,  # 380px / 50px = 7 bullets
        "guidelines": """
IMAGE CONTAINER: 520px × 380px (left side)
- Image scales to fit within container

TEXT CONTAINER: 520px × 380px (right side)
- REQUIRED: 3-7 bullets explaining the image
- NEVER leave empty - always add context
        """
    },
    
    "text-image-right": {
        "name": "Text + Image (Image Right)",
        "description": "Bullets on left 50%, image on right 50%",
        "containers": {
            "text": {
                "width": 520,
                "height": 380,
                "purpose": "Bullet points"
            },
            "image": {
                "width": 520,
                "height": 380,
                "purpose": "Image, diagram, or screenshot"
            }
        },
        "max_bullets": 7,
        "guidelines": """
TEXT CONTAINER: 520px × 380px (left side)
- REQUIRED: 3-7 bullets about the topic

IMAGE CONTAINER: 520px × 380px (right side)
- Visual representation of the concept
        """
    },
    
    # =========================================================================
    # IMAGE FULL WIDTH - Use sparingly, only for self-explanatory diagrams
    # =========================================================================
    "image-full": {
        "name": "Full-Width Image",
        "description": "Large image taking most of the slide - USE ONLY for self-explanatory diagrams",
        "containers": {
            "image": {
                "width": 1160,
                "height": 350,
                "purpose": "Large image, diagram, or screenshot"
            },
            "caption": {
                "width": 1160,
                "height": 50,
                "purpose": "Required caption explaining the image"
            }
        },
        "max_bullets": 0,
        "guidelines": """
IMAGE CONTAINER: 1160px × 350px
- ONLY use for complex diagrams that need full width
- PREFER text-image-left/right with bullets instead

CAPTION: Required, 1-2 sentences explaining the image
        """
    },
    
    # =========================================================================
    # CODE FULL WIDTH - For important, longer code examples
    # =========================================================================
    "code-full": {
        "name": "Full-Width Code",
        "description": "Large code block taking most of the slide",
        "containers": {
            "caption": {
                "width": 1160,
                "height": 50,
                "purpose": "Brief description of the code"
            },
            "code": {
                "width": 1160,
                "height": 350,
                "purpose": "Extended code example"
            }
        },
        "max_bullets": 0,
        "max_code_lines": 15,  # ~15 lines of code
        "guidelines": """
CODE CONTAINER: 1160px × 350px
- For longer, important code examples
- ~15 lines of code without scroll
- Include language header

CAPTION: 1-2 lines explaining what the code does
        """
    },
    
    # =========================================================================
    # TWO COLUMN - For comparisons
    # =========================================================================
    "two-column": {
        "name": "Two Columns",
        "description": "Two equal columns for comparison or parallel content",
        "containers": {
            "left": {
                "width": 520,
                "height": 380,
                "purpose": "Left column content"
            },
            "right": {
                "width": 520,
                "height": 380,
                "purpose": "Right column content"
            }
        },
        "max_bullets": 6,  # Per column
        "guidelines": """
EACH COLUMN: 520px × 380px
- Maximum 6 bullets per column
- Use for Before/After, Pros/Cons comparisons
        """
    },
    
    # =========================================================================
    # TABLE LAYOUT
    # =========================================================================
    "table": {
        "name": "Table",
        "description": "Tabular data presentation",
        "containers": {
            "table": {
                "width": 1160,
                "height": 340,
                "purpose": "Data table"
            },
            "notes": {
                "width": 1160,
                "height": 60,
                "purpose": "Optional notes or key takeaways"
            }
        },
        "max_rows": 8,  # ~8 rows before overflow
        "guidelines": """
TABLE CONTAINER: 1160px × 340px
- Header row: ~45px
- Data rows: ~35px each
- Maximum 8 rows
        """
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_layout_spec(layout_name: str) -> dict:
    """Get the specification for a layout."""
    return LAYOUTS.get(layout_name, LAYOUTS["text-only"])


def get_layout_guidelines(layout_name: str) -> str:
    """Get the AI guidelines for a layout."""
    spec = get_layout_spec(layout_name)
    return spec.get("guidelines", "")


def get_all_layouts_summary() -> str:
    """Get a summary of all available layouts for AI prompt."""
    summary_lines = ["AVAILABLE LAYOUTS AND CONTAINER SIZES:\n"]
    
    for name, spec in LAYOUTS.items():
        summary_lines.append(f"📐 {name.upper()}: {spec['description']}")
        for container_name, container in spec.get('containers', {}).items():
            summary_lines.append(f"   • {container_name}: {container['width']}px × {container['height']}px - {container['purpose']}")
        summary_lines.append("")
    
    return "\n".join(summary_lines)


def estimate_bullet_count(height_px: int, bullet_height: int = 45) -> int:
    """Estimate how many bullets fit in a given height."""
    return max(1, int(height_px / bullet_height))


def estimate_code_lines(height_px: int, line_height: int = 22) -> int:
    """Estimate how many code lines fit in a given height (accounting for header)."""
    header_height = 40
    return max(1, int((height_px - header_height) / line_height))


# =============================================================================
# LAYOUT CSS (to be included in HTML output)
# =============================================================================

LAYOUT_CSS = """
/* Layout-specific styles */
.layout-text-only .content-container {
    width: 100%;
    height: 480px;
    overflow: hidden;
}

.layout-text-code {
    display: flex;
    flex-direction: column;
    height: 480px;
}

.layout-text-code .text-container {
    height: 200px;
    overflow: hidden;
}

.layout-text-code .code-container {
    height: 260px;
    overflow: hidden;
}

.layout-text-image-left,
.layout-text-image-right {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
    height: 480px;
}

.layout-text-image-left .image-container,
.layout-text-image-right .image-container,
.layout-text-image-left .text-container,
.layout-text-image-right .text-container {
    height: 480px;
    overflow: hidden;
}

.layout-image-full .image-container {
    height: 450px;
    display: flex;
    justify-content: center;
    align-items: center;
}

.layout-image-full .caption-container {
    height: 30px;
    text-align: center;
    font-style: italic;
    color: #666;
}

.layout-code-full .code-container {
    height: 420px;
    overflow: hidden;
}

.layout-code-full .caption-container {
    height: 60px;
    overflow: hidden;
}

.layout-two-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
    height: 480px;
}

.layout-two-column .left-column,
.layout-two-column .right-column {
    height: 480px;
    overflow: hidden;
}

.layout-image-code {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
    height: 480px;
}

.layout-image-code .image-container,
.layout-image-code .code-container {
    height: 480px;
    overflow: hidden;
}

.layout-table .table-container {
    height: 400px;
    overflow: auto;
}

.layout-table .notes-container {
    height: 80px;
    overflow: hidden;
}
"""
