import os
import hashlib
from PyPDF2 import PdfReader
import docx
from django.core.exceptions import ValidationError

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        text = ''
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + '\n'
        return text

    elif ext == '.docx':
        doc = docx.Document(file_path)
        text = ''
        for para in doc.paragraphs:
            text += para.text + '\n'
        return text

    else:
        # Unsupported format
        return ''

def generate_ngrams(text, n=4):
    # Convert to lowercase
    text = text.lower()

    # Split into words
    words = text.split()

    # Create n-grams
    ngrams = []
    for i in range(len(words) - n + 1):
        ngram = tuple(words[i:i+n])
        ngrams.append(ngram)

    return ngrams

def calculate_jaccard_similarity(text1, text2, n=4):
    # Generate n-grams
    ngrams1 = set(generate_ngrams(text1, n))
    ngrams2 = set(generate_ngrams(text2, n))

    if not ngrams1 or not ngrams2:
        return 0

    intersection = ngrams1.intersection(ngrams2)
    union = ngrams1.union(ngrams2)

    similarity = len(intersection) / len(union)

    # Convert to percentage
    return round(similarity * 100, 2)


def hash_uploaded_file(uploaded_file):
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)

    uploaded_file.seek(0)
    return hasher.hexdigest()


def hash_stored_file(file_field):
    if not file_field:
        return None

    hasher = hashlib.sha256()
    try:
        with file_field.open('rb') as existing_file:
            for chunk in iter(lambda: existing_file.read(8192), b''):
                hasher.update(chunk)
    except OSError:
        return None

    return hasher.hexdigest()


def validate_unique_past_report(uploaded_file, existing_reports):
    uploaded_hash = hash_uploaded_file(uploaded_file)

    for report in existing_reports:
        existing_hash = hash_stored_file(report.file)
        if existing_hash and existing_hash == uploaded_hash:
            raise ValidationError("This file has already been uploaded.")
