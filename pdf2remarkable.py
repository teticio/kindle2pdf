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


def main() -> int:
    """
    Main function to upload PDFs to reMarkable.

    Args:
        input (str): PDF file path

    Returns:
        int: Exit status
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="PDF file path")
    args = parser.parse_args()

    with open(args.input, "rb") as file:
        pdf = file.read()
        start_index = pdf.find(b"/Title")
        if start_index != -1:
            start_index = pdf.find(b"(", start_index) + 1
            end_index = pdf.find(b")", start_index)
            title = pdf[start_index:end_index].decode("utf-8", errors="ignore")
        else:
            title = os.path.splitext(os.path.basename(args.input))[0]

    dotfile_path = os.path.join(os.path.expanduser("~"), ".pdf2remarkable")
    if not os.path.exists(dotfile_path):
        with open(dotfile_path, "w", encoding="utf-8") as f:
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
                data=f'{{"code":"{otc}","deviceID":"{str(uuid4())}","deviceDesc":"browser-chrome"}}',
                timeout=300,
            )
            response.raise_for_status()
            f.write(response.text)

    with open(dotfile_path, "r", encoding="utf-8") as f:
        auth = f.read()

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


if __name__ == "__main__":
    sys.exit(main())
