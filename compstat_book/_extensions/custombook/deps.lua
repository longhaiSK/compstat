-- Bundles the extension's stylesheet and scripts as an HTML dependency so
-- Quarto copies them into the output's lib folder and links them correctly.
-- Paths below are resolved relative to this filter's own directory.
function Pandoc(doc)
  if quarto.doc.is_format("html") then
    quarto.doc.add_html_dependency({
      name = "custombook",
      version = "1.0.0",
      stylesheets = { "bookstyles.css" },
      scripts = { "num_eq.js", "merge-toc.js" }
    })
  end
  return doc
end
