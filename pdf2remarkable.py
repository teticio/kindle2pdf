"""
Upload PDFs to reMarkable from the CLI.
"""

import argparse
import json
import os
import subprocess
import sys
from base64 import b64encode
from uuid import uuid4

import requests


def get_pdf_title(pdf: bytes, file_path: str) -> str:
    """
    Extract the title from the PDF or use the file name if no title is found.

    Args:
        pdf (bytes): PDF file content
        file_path (str): Path to the PDF file

    Returns:
        str: Title of the PDF
    """
    start_index = pdf.find(b"/Title")
    if start_index != -1:
        start_index = pdf.find(b"(", start_index) + 1
        end_index = pdf.find(b")", start_index)
        return pdf[start_index:end_index].decode("utf-8", errors="ignore")
    return os.path.splitext(os.path.basename(file_path))[0]


def get_auth_token(dotfile_path: str) -> str:
    """
    Retrieve or generate the authentication token.

    Args:
        dotfile_path (str): Path to the dotfile storing the auth token

    Returns:
        str: Authentication token
    """
    if not os.path.exists(dotfile_path):
        url = "https://my.remarkable.com/device/browser/connect"
        try:
            if sys.platform == "win32":
                os.startfile(url)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(
                    ["xdg-open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except OSError:
            pass

        otc = input(f"Please visit {url} and paste your OTC here: ")
        response = requests.post(
            "https://webapp.cloud.remarkable.com/token/json/2/device/new",
            data=json.dumps(
                {"code": otc, "deviceID": str(uuid4()), "deviceDesc": "browser-chrome"}
            ),
            timeout=300,
        )
        response.raise_for_status()
        with open(dotfile_path, "w", encoding="utf-8") as f:
            f.write(response.text)

    with open(dotfile_path, "r", encoding="utf-8") as f:
        return f.read()


def upload_pdf_to_remarkable(pdf: bytes, title: str, auth: str) -> None:
    """
    Upload the PDF to reMarkable cloud.

    Args:
        pdf (bytes): PDF file content
        title (str): Title of the PDF
        auth (str): Authentication token
    """
    headers = {
        "authorization": f"Bearer {auth}",
    }

    response = requests.post(
        "https://webapp.cloud.remarkable.com/token/json/2/user/new",
        headers=headers,
        timeout=300,
    )
    response.raise_for_status()
    token = response.text
    metadata = {"file_name": title}

    headers = {
        "authorization": f"Bearer {token}",
        "content-type": "application/pdf",
        "rm-meta": b64encode(json.dumps(metadata).encode("utf-8")),
    }

    response = requests.post(
        "https://internal.cloud.remarkable.com/doc/v2/files",
        headers=headers,
        data=pdf,
        timeout=300,
    )
    response.raise_for_status()


def main() -> int:
    """
    Main function to upload PDFs to reMarkable.

    Returns:
        int: Exit status
    """
    parser = argparse.ArgumentParser(
        description="Upload PDFs to reMarkable from the CLI."
    )
    parser.add_argument("input", help="PDF file path")
    args = parser.parse_args()

    with open(args.input, "rb") as file:
        pdf = file.read()

    title = get_pdf_title(pdf, args.input)
    dotfile_path = os.path.join(os.path.expanduser("~"), ".pdf2remarkable")
    auth = get_auth_token(dotfile_path)
    upload_pdf_to_remarkable(pdf, title, auth)

    return 0


if __name__ == "__main__":
    sys.exit(main())
