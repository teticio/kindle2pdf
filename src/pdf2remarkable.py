"""
Upload PDFs to reMarkable Cloud from the CLI.
"""

import argparse
import io
import json
import logging
import os
import subprocess
import sys
from base64 import b64encode
from uuid import uuid4

import PyPDF2
import requests

from .utils import sanitize_filename

logger = logging.getLogger("pdf2remarkable")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)


class PDF2Remarkable:
    """
    Class to upload PDFs to reMarkable Cloud.
    """

    def __init__(self):
        dotfile_path = os.path.join(os.path.expanduser("~"), ".pdf2remarkable")
        self.auth = self.get_auth_token(dotfile_path)

    def get_auth_token(self, dotfile_path: str) -> str:
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
                    {
                        "code": otc,
                        "deviceID": str(uuid4()),
                        "deviceDesc": "browser-chrome",
                    }
                ),
                timeout=300,
            )
            response.raise_for_status()
            with open(dotfile_path, "w", encoding="utf-8") as f:
                f.write(response.text)

        with open(dotfile_path, "r", encoding="utf-8") as f:
            return f.read()

    def upload_pdf_to_remarkable(self, pdf: bytes, title: str) -> None:
        """
        Upload PDF bytes to reMarkable Cloud.

        Args:
            pdf (bytes): PDF file content
            title (str): Title of the PDF
        """
        headers = {
            "authorization": f"Bearer {self.auth}",
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

    def pdf2remarkable(self, file_path: str) -> None:
        """
        Upload PDF file to reMarkable Cloud.

        Args:
            file_path (str): Path to the PDF file
        """
        with open(file_path, "rb") as file:
            pdf = file.read()

        reader = PyPDF2.PdfReader(io.BytesIO(pdf))
        title = reader.metadata.title
        if not title:
            title = sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])
        self.upload_pdf_to_remarkable(pdf, title)
        logger.info(f'"{title}" uploaded to reMarkable.')


def main() -> int:
    """
    Main function to upload PDFs to reMarkable Cloud.

    Returns:
        int: Exit status
    """
    parser = argparse.ArgumentParser(
        description="Upload PDFs to reMarkable from the CLI."
    )
    parser.add_argument("input", help="PDF file path")
    args = parser.parse_args()

    try:
        pdf2remarkable = PDF2Remarkable()
        pdf2remarkable.pdf2remarkable(args.input)
    except Exception as e:
        logger.error(e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
