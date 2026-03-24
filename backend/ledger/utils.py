import uuid

def generate_document_id():
    return "DOC-" + str(uuid.uuid4())[:8]
