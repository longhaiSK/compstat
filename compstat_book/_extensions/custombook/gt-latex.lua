-- gt writes its LaTeX tables with fixed font sizes (12pt body, 20pt title,
-- 14pt subtitle), larger than the book's 11pt text. Map them to the
-- document's own sizes so that tables match the surrounding text, and set
-- each table in the gtfit environment (header.tex), which shrinks a table
-- that is wider than the line. Uncaptioned tables are set in place ([H])
-- instead of floating away from the code that prints them.
local gt_sizes = {
  { '\\fontsize{12.0pt}{14.0pt}\\selectfont', '\\normalsize' },
  { '\\fontsize{20}{25}\\selectfont', '\\large' },
  { '\\fontsize{14}{17}\\selectfont', '\\normalsize' },
  { '\\fontsize{12}{15}\\selectfont', '\\normalsize' },
}

local function fix_gt(el)
  if (el.format == 'latex' or el.format == 'tex') and el.text:find('\\fontsize', 1, true) then
    local text = el.text
    for _, s in ipairs(gt_sizes) do
      text = text:gsub(s[1]:gsub('%p', '%%%0'), (s[2]:gsub('%%', '%%%%')))
    end
    text = text:gsub('\\begin{tabular%*}(%b{})(%b{})', function(width, spec)
      local inner = spec:sub(2, -2):gsub('^@{\\extracolsep{\\fill}}', '', 1)
      return '\\begin{gtfit}' .. width .. '{' .. inner .. '}'
    end)
    text = text:gsub('\\end{tabular%*}', '\\end{gtfit}')
    -- keep an uncaptioned table next to the code and text around it
    text = text:gsub('\\begin{table}\n', '\\begin{table}[H]\n')
    el.text = text
    return el
  end
end

-- Runs at pre-quarto, while the gt output is still a raw ("tex") block:
-- Quarto later takes table floats apart and keeps the body out of filters' reach.
return {
  { RawBlock = fix_gt, RawInline = fix_gt }
}
