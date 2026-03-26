import requests

digital_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n<<\n/Length 400\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(IRS Form 1099-INT) Tj\n0 -14 Td\n(This is a test of the digital pdf pipeline where we insert generic string values to pass the routing threshold.) Tj\n0 -14 Td\n(We need more than 50 characters so the pdf layout analyser believes it is a real file.) Tj\n0 -14 Td\n(Box 1: 15.00) Tj\n0 -14 Td\n(Payer TIN: 12-3456789) Tj\n0 -14 Td\n(Some more characters just to be absolutely certain text length exceeds fifty characters.) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n0000000204 00000 n \n0000000287 00000 n \ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n680\n%%EOF\n"

with open("test_digital.pdf", "wb") as f:
    f.write(digital_pdf)

try:
    with open("test_digital.pdf", "rb") as f:
        res = requests.post("http://127.0.0.1:5000/extract", files={"file": f}, data={"form_type": "1099-INT"})
    print(res.status_code)
    print(res.text)
except Exception as e:
    print(e)
