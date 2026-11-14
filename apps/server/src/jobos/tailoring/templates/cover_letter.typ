// Plain cover letter. All content arrives as JSON via sys.inputs (rendered as plain text).
#let d = json(bytes(sys.inputs.data))
#set document(title: d.name + " - Cover Letter", author: d.name)
#set page(paper: d.page, margin: (x: 2.2cm, y: 2cm))
#set text(font: d.fonts, size: 11pt, lang: "en", hyphenate: false)
#set par(justify: false, leading: 0.62em, spacing: 1.1em)

#text(size: 15pt, weight: "bold", d.name) \
#d.contact.join("  |  ")

#v(1em)
#d.date

#d.recipient

#d.greeting

#for p in d.paragraphs { par(p) }

#d.closing \
#d.name
