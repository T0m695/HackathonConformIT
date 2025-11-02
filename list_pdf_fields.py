from pypdf import PdfReader, PdfWriter

pdf_path = "formulaire.pdf"

reader = PdfReader(pdf_path)
writer = PdfWriter()
writer.append(reader)

fields = writer.get_form_text_fields()

print(f"📋 {len(fields)} champs trouvés dans le PDF:\n")
for field_name, field_value in fields.items():
    print(f"  '{field_name}': '{field_value}'")
