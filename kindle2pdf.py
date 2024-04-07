"""
Kindle to PDF converter.
"""

import argparse
import io
import json
import logging
import sys
import tarfile
import tempfile
from base64 import b64decode
from time import time
from typing import Optional

import requests
from browser_cookie3 import chrome
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg
from tqdm.auto import tqdm

logger = logging.getLogger("kindle2pdf")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)


class Kindle2PDF:
    """
    A class to convert Kindle book content to a PDF file.

    Attributes:
        asin (str): Amazon Standard Identification Number of the book.
        session (dict): A dictionary containing session information for book rendering.
    """

    def __init__(
        self,
        asin: str,
        font_size: int = 12,
        page_size: tuple[float, float] = A4,
        dpi: int = 160,
    ) -> None:
        """
        Initializes the Kindle2PDF object with the specified ASIN and starts a reading session.

        Args:
            asin (str): The ASIN of the book to convert.
            font_size (int): The font size to use for rendering the book.
            page_size (tuple[float, float]): The size of the PDF pages.
            dpi (int): The DPI to use for rendering images.
        """
        self.asin = asin
        self.font_size = font_size
        self.page_size = page_size
        self.dpi = dpi
        self.session = self.start_reading_session()

    def start_reading_session(self) -> dict:
        """
        Starts a new reading session by authenticating with Amazon and retrieving session tokens.

        Returns:
            dict: A dictionary containing session information (title, version, end_pos, auth,
            headers, and cookies).
        """
        cookies = chrome(domain_name="amazon.com")

        headers = {
            "x-amzn-sessionid": requests.utils.dict_from_cookiejar(cookies)[
                "session-id"
            ],
        }

        params = {
            "serialNumber": "A2CTZ977SKFQZY",
            "deviceType": "A2CTZ977SKFQZY",
        }

        response = requests.get(
            "https://read.amazon.com/service/web/register/getDeviceToken",
            params=params,
            cookies=cookies,
            headers=headers,
            timeout=60,
        )
        if response.status_code != 200:
            logger.error(
                "Ensure you have logged in recently to https://read.amazon.com in Chrome."
            )
            return {}

        device_session_token = response.json()["deviceSessionToken"]

        headers = {"x-adp-session-token": device_session_token}

        params = {
            "asin": self.asin,
            "clientVersion": "20000100",
        }

        response = requests.get(
            "https://read.amazon.com/service/mobile/reader/startReading",
            params=params,
            cookies=cookies,
            headers=headers,
            timeout=60,
        )
        response = response.json()

        if not response.get("isOwned", False):
            logger.error("Book %s is not owned by you.", self.asin)
            return {}
        auth = response["karamelToken"]
        metadata_url = response["metadataUrl"]

        response = requests.get(metadata_url, timeout=60)
        response = response.text[
            response.text.find("loadMetadata(")
            + len("loadMetadata(") : response.text.rfind(");")
        ]
        response = json.loads(response)

        return {
            "title": response["title"],
            "version": response["version"],
            "end_pos": response["endPosition"],
            "auth": auth,
            "headers": headers,
            "cookies": cookies,
        }

    def render_book_pages(self, start_pos: int, num_pages: int) -> tuple[dict, dict]:
        """
        Renders a specified number of book pages starting from a given position.

        Args:
            start_pos (int): The starting position ID for rendering pages.
            num_pages (int): The number of pages to render.

        Returns:
            tuple[dict, dict]: A tuple containing dictionaries of page JSON data and decrypted
            images.
        """
        if time() > self.session["auth"]["expiresAt"] / 1000 - 5:
            self.session = self.start_reading_session()

        params = {
            "version": "3.0",
            "asin": self.asin,
            "contentType": "FullBook",
            "revision": self.session["version"],
            "fontFamily": "Bookerly",
            "fontSize": str(self.font_size),
            "lineHeight": "1.4",
            "dpi": str(self.dpi),
            "height": str(int(self.page_size[1] * self.dpi / 72)),
            "width": str(int(self.page_size[0] * self.dpi / 72)),
            "marginBottom": "0",
            "marginLeft": "9",
            "marginRight": "9",
            "marginTop": "0",
            "maxNumberColumns": "1",
            "theme": "default",
            "locationMap": "true",
            "packageType": "TAR",
            "encryptionVersion": "NONE",
            "numPage": num_pages,
            "skipPageCount": 0,
            "startingPosition": start_pos,
            "bundleImages": "false",  # Bundling doesn't work for all books
            "token": self.session["auth"]["token"],
        }

        response = requests.get(
            "https://read.amazon.com/renderer/render",
            params=params,
            cookies=self.session["cookies"],
            headers=self.session["headers"],
            timeout=60,
        )

        tar_stream = io.BytesIO(response.content)
        jsons = {}
        images = {}
        with tarfile.open(fileobj=tar_stream, mode="r:*") as tar:
            for member in tar.getmembers():
                f = tar.extractfile(member)
                if f is not None:
                    content = f.read()
                    if member.name.endswith(".json"):
                        jsons[member.name] = json.loads(content.decode("utf-8"))
                    elif member.name.startswith("assets/"):  # if bundleImages
                        images[member.name[len("assets/") :]] = content

        images = images or self.download_images(manifest=jsons["manifest.json"])
        self.decrypt_images(images=images, auth=self.session["auth"])

        return jsons, images

    def download_images(self, manifest: dict) -> dict:
        """
        Downloads images from the manifest.

        Args:
            manifest (dict): A dictionary containing image URLs.

        Returns:
            dict: A dictionary containing the downloaded images.
        """
        images = {}
        base_url = manifest["cdn"]["baseUrl"]

        for image in manifest["cdnResources"]:
            response = requests.get(
                base_url + "/" + image["url"] + "?" + manifest["cdn"]["authParameter"],
                params={
                    "token": self.session["auth"]["token"],
                    "expiration": self.session["auth"]["expiresAt"],
                },
                timeout=60,
            )

            if response.status_code != 200:
                logger.warning("Failed to download image %s.", image["url"])
                continue

            images[image["url"]] = response.content

        return images

    @staticmethod
    def decrypt_images(images: dict, auth: dict) -> None:
        """
        Decrypts the images using the session token.

        Args:
            images (dict): A dictionary of encrypted images.
            auth (dict): A dictionary containing the session token and expiration information.
        """
        i = auth["expiresAt"] % 60
        p = auth["token"][i : i + 40]
        key_material = p.encode()

        for image in images:
            salt = b64decode(images[image][:24])
            iv = b64decode(images[image][24:48])
            encrypted_data = b64decode(images[image][48:])

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=16,
                salt=salt,
                iterations=1000,
                backend=default_backend(),
            )
            key = kdf.derive(key_material)

            tag_length = 16
            encrypted_data_without_tag = encrypted_data[:-tag_length]
            tag = encrypted_data[-tag_length:]

            decryptor = Cipher(
                algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()
            ).decryptor()

            aad = p.encode()[:9]
            decryptor.authenticate_additional_data(aad)

            images[image] = (
                decryptor.update(encrypted_data_without_tag) + decryptor.finalize()
            )

    def render_pdf(
        self,
        jsons: list[dict],
        images: dict,
        pdf_canvas: canvas.Canvas,
        progress: Optional[tqdm] = None,
    ) -> Optional[int]:
        """
        Renders the PDF pages using the decrypted images and text.

        Args:
            jsons list(dict): A list of dictionaries containing book data.
            images (dict): A dictionary of decrypted images.
            pdf_canvas (canvas.Canvas): The canvas object to draw the PDF on.
            progress (tqdm): A tqdm progress bar to update.

        Returns:
            int: The position ID of the last rendered page.
        """
        end_pos = None
        pages = []
        for _ in jsons:
            if _.startswith("page_data_0_"):
                pages = jsons[_]
                break

        for page in pages:
            for child in page["children"]:
                transform = [_ * 72 / self.dpi for _ in child["transform"]]

                if child["type"] == "run":
                    for _ in jsons["glyphs.json"]:
                        if _["fontKey"] == child["fontKey"]:
                            font = _
                            break

                    glyphs = ""
                    for i, glyph in enumerate(child.get("glyphs", [])):
                        glyphs += f"""<g transform="translate({
                            child["xPosition"][i]}, 0) scale({child['fontSize'] / font['unitsPerEm']})">
                            <path d="{font['glyphs'][str(glyph)].get('path', '')}" 
                                fill="{child['textColor']}" stroke="{child['textColor']}"/>
                        </g>
                        """

                    svg_content = f"""<?xml version="1.0" standalone="no"?>
                    <svg version="1.1" xmlns="http://www.w3.org/2000/svg">
                        <g transform="matrix({transform[0]}, {transform[1]}, {transform[2]}, {transform[3]}, {transform[4]}, {transform[5]})">
                            {glyphs}
                        </g>
                    </svg>
                    """

                    drawing = svg2rlg(io.StringIO(svg_content))
                    renderPDF.draw(drawing, pdf_canvas, 0, self.page_size[1])

                elif child["type"] == "image":
                    with tempfile.NamedTemporaryFile(delete=True, suffix=".jpg") as tmp:
                        tmp.write(images[child["imageReference"]])
                        tmp.flush()
                        x = transform[4]
                        y = self.page_size[1] - (
                            transform[5] + child["rect"]["bottom"] * transform[3]
                        )
                        width = child["rect"]["right"] * transform[0]
                        height = child["rect"]["bottom"] * transform[3]
                        pdf_canvas.drawImage(
                            image=tmp.name, x=x, y=y, width=width, height=height
                        )

            pdf_canvas.showPage()
            end_pos = page["endPositionId"]
            if progress:
                progress.n = end_pos
                progress.refresh()

        return end_pos

    def render_book(self, output_path: Optional[str]) -> None:
        """
        Renders the entire book and saves it to the specified output path.

        Args:
            output_path (str): The path to save the PDF file to (automatically generated if None).
        """
        start_pos = 0
        num_pages = 10
        if output_path is None:
            output_path = f"{self.session['title']}.pdf"
        pdf_canvas = canvas.Canvas(output_path, pagesize=A4)

        with tqdm(total=self.session["end_pos"]) as progress:
            while start_pos <= self.session["end_pos"]:
                jsons, images = self.render_book_pages(
                    start_pos=start_pos, num_pages=num_pages
                )
                if not jsons:
                    return

                end_pos = self.render_pdf(
                    jsons=jsons,
                    images=images,
                    pdf_canvas=pdf_canvas,
                    progress=progress,
                )
                progress.n = end_pos
                progress.refresh()
                start_pos = end_pos + 1

        pdf_canvas.save()


def main() -> int:
    """
    Main function to convert a Kindle book to a PDF file.

    Args:
        asin (str): The ASIN of the book to convert.
        output (str): The path to save the PDF file to.
        font_size (int): The font size to use for rendering the book.

    Returns:
        int: The exit status of the conversion process.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("asin", help="ASIN of the book to convert")
    parser.add_argument("--output", help="Optional output PDF file path")
    parser.add_argument(
        "--font-size", help="Font size to use for rendering", default=12
    )
    args = parser.parse_args()
    kindle2pdf = Kindle2PDF(asin=args.asin, font_size=args.font_size)
    if not kindle2pdf.session:
        return 1
    kindle2pdf.render_book(output_path=args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
