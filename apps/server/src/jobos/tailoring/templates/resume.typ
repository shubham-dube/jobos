// ATS-friendly one-column resume. All content arrives as JSON via sys.inputs (rendered as plain text).
#let d = json(bytes(sys.inputs.data))
#set document(title: d.name + " - Resume", author: d.name)
#set page(paper: d.page, margin: (x: 1.45cm, y: 1.15cm))
#set text(font: d.fonts, size: d.size * 1pt, lang: "en", hyphenate: false)
#set par(justify: false, leading: 0.48em, spacing: 0.5em)
#set list(indent: 0.35em, body-indent: 0.45em, spacing: 0.32em, marker: [•])

#let section(title) = block(width: 100%, above: 0.85em, below: 0.4em, stroke: (bottom: 0.6pt),
  inset: (bottom: 2.5pt))[#text(size: 10.5pt, weight: "bold", upper(title))]

#let entry(e) = {
  block(above: 0.55em, below: 0.25em, breakable: false)[
    #text(weight: "bold", e.title)#if e.org != "" [, #e.org]#h(1fr)#e.right
    #if e.sub != "" [ \ #text(style: "italic", e.sub)#h(1fr)#e.location ]
  ]
  if e.bullets.len() > 0 { list(..e.bullets.map(b => [#b])) }
}

#align(center)[
  #text(size: 17pt, weight: "bold", d.name) \
  #v(-0.2em)
  #d.contact.join("  |  ")
  #if d.links.len() > 0 [ \ #d.links.map(l => link(l.url, l.label)).join("  |  ") ]
]

#for s in d.order {
  if s == "summary" and d.summary != none {
    section("Summary")
    d.summary
  } else if s == "education" and d.education.len() > 0 {
    section("Education")
    for e in d.education { entry(e) }
  } else if s == "experience" and d.experience.len() > 0 {
    section("Experience")
    for e in d.experience { entry(e) }
  } else if s == "projects" and d.projects.len() > 0 {
    section("Projects")
    for e in d.projects { entry(e) }
  } else if s == "skills" and d.skills.len() > 0 {
    section("Skills")
    for g in d.skills {
      block(above: 0.35em, below: 0.2em)[#if g.label != "" [#text(weight: "bold", g.label): ]#g.items.join(", ")]
    }
  } else if s == "awards" and d.awards.len() > 0 {
    section("Awards")
    list(..d.awards.map(a => [#a]))
  }
}
