# Kindle2PDF and PDF2Remarkable

## Introduction

A Python script to render your Kindle books as PDFs without needing a device. This is ideal if you want to read them on a reMarkable tablet or similar.

A script is also provided to upload the PDFs to the reMarkable Cloud, which is particularly useful on Linux as the official desktop application is not available.

## Installation

```bash
pip install kindle2pdf
```

## Usage

First you need to login to `https://read.amazon.com/` on Chrome. The Python script will automatically retreive any cookies it needs. Then, assuming you own the book with the ASIN `B0182LFAIA`, you can run the following command:

```bash
kindle2pdf B0182LFAIA
```

To find out the ASIN of any book, you can either inspect the URL of the book in the Kindle Cloud Reader, or search for it in Amazon. You'll need to make sure that it corresponds to the edition that you own.

If you want to upload a PDF to the reMarkable Cloud you can add the switch `--remarkable` to `kindle2pdf` or simply

```bash
pdf2remarkable "The Cybergypsies.pdf"
```

The first time you run this, you will be asked to pair your device. Just follow the instructions and paste your OTC.

## Troubleshooting

* If you get a "Permission denied" error when running `kindle2pdf` on Windows, try closing any Chrome browsers.

* If you have authentication problems with `pdf2remarkable` or want to re-pair your device, delete the `.pdf2remarkable` file in your home directory and run the script again.

* If you run into what looks to be a bug, you can run `kindle2pdf` with `--save-mock` and create an issue with a link to your `responses.jsonl` for debugging purposes. Any sensitive IDs or persistent tokens will have been removed.
