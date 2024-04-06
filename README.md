# Kindle2PDF

## Introduction

A Python script to render your Kindle books as PDFs without needing a device. This is ideal if you want to read them on a ReMarkable tablet or similar.

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
