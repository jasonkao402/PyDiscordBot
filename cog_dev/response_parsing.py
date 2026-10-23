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
        # "thinking": r"<thinking>(.*?)(?:</thinking>|$)",
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
        content_start = raw_text.find("<content>")
        content_end = raw_text.find("</content>")
        if content_start != -1 and content_end != -1 and content_end > content_start:
            result["content"] = raw_text[content_start + len("<content>"):content_end].strip()
            
        elif content_start != -1:
            result["content"] = raw_text[content_start + len("<content>"):].strip()
            
        elif content_end != -1:
            result["content"] = raw_text[:content_end].strip()
            result["summary"] = raw_text[content_end + len("</content>"):].strip()
        
        else:
            result["content"] = raw_text.strip()
    return result

if __name__ == "__main__":
    # Example usage, assume model returns a response in the following format:
#     raw_text = """<thinking> I am thinking... </thinking>
# <content> Here is the content you requested.
# has many lines 
# more lines
# <summary> This is a summary of the content. </summary>"""
    raw_text = """哈基米喔南北綠豆1\n<content>哈基米喔南北綠豆2哈基米喔南北綠豆3\n哈基米喔南北綠豆4\n哈基米喔南北綠豆5\n哈基米喔南北綠豆6\n"""
    result = parse_response(raw_text)
    for key, value in result.items():
        print(f"{key}: {value}")