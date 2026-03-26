import re
from typing import Dict

def parse_response(raw_text: str) -> Dict[str, str]:
    """
    Parses the response from the model and extracts the thinking, content, and summary sections.

    Args:
        raw_text (str): The raw text from the model.

    Returns:
        Dict[str, str]: A dictionary containing the extracted sections.
    """
    result = {}
    
    # Define regex patterns for each section, use non-greedy matching to ensure we capture the correct content
    patterns = {
        "thinking": r"<thinking>(.*?)(?:</thinking>|$)",
        "content": r"<content>(.*?)(?:</content>|$)",
        "summary": r"<summary>(.*?)(?:</summary>|$)"
    }
    
    # Extract each section using regex
    for key, pattern in patterns.items():
        match = re.search(pattern, raw_text, re.DOTALL)
        if match:
            result[key] = match.group(1).strip()
        else:
            result[key] = ""  # If section is not found, return an empty string
    if not result["content"]:
        result["content"] = raw_text.strip()  # If no content tag, use the whole response as content
    return result

if __name__ == "__main__":
    # Example usage, assume model returns a response in the following format:
    raw_text = """<thinking> I am thinking... </thinking>
<content> Here is the content you requested.
has many lines 
more lines
<summary> This is a summary of the content. </summary>"""
    result = parse_response(raw_text)
    for key, value in result.items():
        print(f"{key}: {value}")