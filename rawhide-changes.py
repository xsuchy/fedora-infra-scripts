#!/usr/bin/python
import glob
import os
import re
import base64
import sys
import email
from email import policy
from email.parser import BytesParser


def extract_plain_text(file_path):
    """
    Reads an EML file and returns the plain text body.
    """
    try:
        with open(file_path, 'rb') as f:
            # We use policy.default to get a modern EmailMessage object
            msg = BytesParser(policy=policy.default).parse(f)

        # get_body(preferencelist=('plain',)) finds the plain text part automatically
        body_part = msg.get_body(preferencelist=('plain',))

        if body_part:
            return body_part.get_content()
        else:
            return "No plain text content found in this email."

    except FileNotFoundError:
        return "Error: File not found."
    except Exception as e:
        return f"An error occurred: {e}"

def parse_email_content(content):
    """
    Finds the ADDED PACKAGES section and extracts Package and Summary.
    """
    # Look for the section specifically
    section_match = re.search(r"===== ADDED PACKAGES =====(.*?)(?:=====|$)", content, re.DOTALL)
    if not section_match:
        return

    section_text = section_match.group(1)
    
    # Regex to find Package and Summary blocks
    # Looks for 'Package: ...' followed by 'Summary: ...'
    pattern = re.compile(r"Package:\s*(?P<pkg>.*?)\nSummary:\s*(?P<sum>.*?)\n", re.MULTILINE)
   
    RESULT = {} 
    for match in pattern.finditer(section_text):
        package = match.group('pkg').strip()
        RESULT[package] = f" {package} - {match.group('sum').strip()}"
    return RESULT

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py YYYYMM")
        sys.exit(1)

    yyyymm = sys.argv[1]

    if len(yyyymm) != 6 or not yyyymm.isdigit():
        print("Error: Parameter must be in YYYYMM format (e.g., 202602)")
        sys.exit(1)
   
    # 2. Format the search pattern
    # Transforms '202310' into '*2023-10*'
    year = yyyymm[:4]
    month = yyyymm[4:]
    pattern = f"*{year}-{month}*"
   
    # 3. Find and process files
    files = glob.glob("/home/msuchy/Downloads/composes/"+pattern)
   
    if not files:
        print("No matching files found.")
        return
   
    RESULT = {}
    for file_path in files:
        if os.path.isfile(file_path):
            #print(f"Processing: {file_path}")
            try:
                content = extract_plain_text(file_path)
                RESULT.update(parse_email_content(content))
            except Exception as e:
                print(f"Could not read file {file_path}: {e}")
    for i in sorted(RESULT.keys()):
        print(RESULT[i])

if __name__ == '__main__':
    main()
