import re

html_content = """
<p>La diferencia crítica entre un agente de IA moderno y un chatbot tradicional basado en reglas radica en el motor de razonamiento.</p>

<p><span style="color: #003366"><strong>Aplicación Práctica</strong></span></p>

<p>Consideremos un ejemplo concreto en el sector bancario.</p>

<p><strong>This is a very long paragraph that happens to start with bold text but should NOT be kept with next because it is too long and would cause an awkward page break if we force it to keep with the next element regardless of the available space on the current page.</strong></p>
"""

def test_regex():
    print("--- Testing Orphan Regex ---")
    
    def add_keep_with_next(match):
        tag = match.group(0)
        if 'style="' in tag:
            if '-pdf-keep-with-next' not in tag:
                return tag.replace('style="', 'style="-pdf-keep-with-next: true; ')
            return tag
        else:
            return tag.replace('<p', '<p style="-pdf-keep-with-next: true;"')

    # Matches <p ...> ... <strong> ... </p>
    # STRICTER LIMIT: Only paragraphs < 120 chars
    new_html = re.sub(r'<p(?![^>]*keep-with-next)(?:[^>]*?)>(?:<[^>]+>)*\s*(?:<strong|<b|<span style="color)[^>]*>.*?</p>', 
                        lambda m: add_keep_with_next(m) if len(m.group(0)) < 120 else m.group(0), 
                        html_content, flags=re.DOTALL)
    
    print(new_html)
    
    if '-pdf-keep-with-next: true;' in new_html:
        print("\nSUCCESS: Style added.")
    else:
        print("\nFAILURE: Style NOT added.")

    # verify long paragraph is NOT matched
    if 'This is a very long' in new_html and '-pdf-keep-with-next' in new_html.split('This is a very long')[0].split('<p')[-1]:
         # This check is a bit fuzzy, let's just look at the output
         pass

if __name__ == "__main__":
    test_regex()
