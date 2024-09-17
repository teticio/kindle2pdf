import re


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove special characters.
    """
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", filename)
    filename = filename.strip().strip(". ")
    return filename
