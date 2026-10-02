"""Extraction schemas sent to Sarvam Document Intelligence (/doc-ai/v1/job/extract).

Sarvam rules: root must be type "object" with non-empty "properties";
every field needs a "type" and a non-empty "description". Max nesting depth 4.
"""

PAN_SCHEMA = {
    "type": "object",
    "properties": {
        "pan_number": {
            "type": "string",
            "description": "The 10-character Permanent Account Number printed on the card, e.g. AABCS1429E",
        },
        "holder_name": {
            "type": "string",
            "description": "Name of the PAN holder exactly as printed (person or entity/company name)",
        },
        "father_name": {
            "type": "string",
            "description": "Father's name, printed only on PAN cards of individuals. Empty if not present",
        },
        "date": {
            "type": "string",
            "description": "Date of birth (individual) or date of incorporation/formation (entity), as printed, in DD/MM/YYYY",
        },
        "date_label": {
            "type": "string",
            "description": "The label printed next to the date, e.g. 'Date of Birth' or 'Date of Incorporation/Formation'",
        },
    },
}

# Add more schemas here later: GST_SCHEMA, COI_SCHEMA, BOARD_RESOLUTION_SCHEMA, CHEQUE_SCHEMA ...
SCHEMAS = {"pan": PAN_SCHEMA}
