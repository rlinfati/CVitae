-- {{< cv TYPE FILE >}}: render a YAML list of CV entries in the language of the document.
-- Any field may be a plain value or a map {en: ..., es: ...}.

local LABELS = {
  en = {
    team = "Team",
    publications = "Publications", theses = "Theses supervised", grants = "Grants as PI",
    idx = "a publication can appear in more than one index",
    undergrad = "Undergraduate", phd = "PhD", msc = "MSc",
    competitive = "External funding", university = "UBB funding",
    groups = "Research groups",
    and_ = "and", ["in"] = "In",
    idx_title = "indexes", journals = "journal articles", confs = "conference articles and book chapters", preprints = "preprints",
    thesis = "Thesis", advisor = "Advisor", scholarship = "Scholarship", award = "Award",
    role_names = { PI = "Principal Investigator", ["Co-I"] = "Co-Investigator", YR = "Young Researcher", TS = "Technical Staff" },
    as_of = "as of", citations = "Citations", h_index = "h-index", i10_index = "i10-index",
    months = { "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December" },
  },
  es = {
    team = "Equipo",
    publications = "Publicaciones", theses = "Tesis dirigidas", grants = "Proyectos como PI",
    idx = "una publicación puede estar en más de un índice",
    undergrad = "Pregrado", phd = "Doctorado", msc = "Magíster",
    competitive = "Financiamiento externo", university = "Financiamiento UBB",
    groups = "Grupos de investigación",
    and_ = "y", ["in"] = "En",
    idx_title = "índices", journals = "artículos en revistas", confs = "artículos en conferencias y capítulos de libro", preprints = "preprints",
    thesis = "Tesis", advisor = "Director de tesis", scholarship = "Beca", award = "Premio",
    role_names = { PI = "Investigador/a principal", ["Co-I"] = "Co-investigador/a", YR = "Investigador/a joven", TS = "Personal técnico" },
    as_of = "al", citations = "Citas", h_index = "Índice h", i10_index = "Índice i10",
    months = { "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre" },
  },
}

local function now_label()
  return os.date("%Y") .. "+"
end

local function str(v)
  return pandoc.utils.stringify(v)
end

local function doc_lang(meta)
  local l = meta.lang and str(meta.lang):sub(1, 2) or "en"
  return LABELS[l] and l or "en"
end

local function loc(v, lang)
  if v == nil then return nil end
  if pandoc.utils.type(v) == "table" then
    local x = v[lang] or v.en
    return x and str(x) or nil
  end
  return str(v)
end

local function inl(s)
  local out, first = pandoc.Inlines({}), true
  for w in s:gmatch("[^ \t\r\n]+") do
    if not first then out:insert(pandoc.Space()) end
    out:insert(pandoc.Str(w))
    first = false
  end
  return out
end

local function rich(v, lang)
  -- like loc() but keeps markup (links, emphasis) of the YAML value
  if v == nil then return pandoc.Inlines({}) end
  if pandoc.utils.type(v) == "table" then v = v[lang] or v.en end
  if pandoc.utils.type(v) == "Inlines" then return v end
  return inl(str(v))
end

local function fmt_reviews(list)
  local arr = {}
  for i, r in ipairs(list) do
    arr[i] = { y = tonumber(str(r.year)), n = r.n and tonumber(str(r.n)) or 1, c = (r.candidate == true), i = i }
  end
  table.sort(arr, function(a, b)
    if a.y ~= b.y then return a.y > b.y end
    if a.c ~= b.c then return not a.c end
    return a.i < b.i
  end)
  local parts = {}
  for _, r in ipairs(arr) do
    local s = tostring(r.y)
    if r.n > 1 then s = s .. " x" .. r.n end
    if r.c then s = s .. " (C)" end
    parts[#parts + 1] = s
  end
  return table.concat(parts, ", ")
end

local function fmt_editions(list)
  local arr = {}
  for i, e in ipairs(list) do
    arr[i] = { y = tonumber(str(e.year)), ed = e.edition and str(e.edition) or nil, i = i }
  end
  table.sort(arr, function(a, b)
    if a.y ~= b.y then return a.y > b.y end
    return a.i < b.i
  end)
  local parts = {}
  for _, e in ipairs(arr) do
    parts[#parts + 1] = tostring(e.y) .. (e.ed and (" (" .. e.ed .. ")") or "")
  end
  return table.concat(parts, ", ")
end

local function series_label(it)
  if it.acronym then return str(it.acronym) .. " - " .. str(it.name) end
  if it.label then return str(it.label) end
  return str(it.name)
end

local function read_items(file)
  local root = (quarto.project and quarto.project.directory) or "."
  local f = assert(io.open(root .. "/" .. file, "r"), "cv: cannot open " .. file)
  local txt = f:read("a")
  f:close()
  return pandoc.read("---\n" .. txt .. "\n---\n", "markdown").meta.items
end

local function open_span(start)
  local y = os.date("%Y")
  if tostring(start) == y then return y .. "+" end
  return tostring(start) .. "-" .. now_label()
end

local function opt(v)
  -- kwargs entries may be missing or empty: return a non-empty string or nil
  if v == nil then return nil end
  local s = str(v)
  if s == "" then return nil end
  return s
end

local function cutoff(last)
  last = opt(last)
  if not last then return nil end
  return tonumber(os.date("%Y")) - tonumber(last) + 1
end

local function keep(it, cut)
  if not cut then return true end
  local e
  if it["end"] then e = tonumber(str(it["end"]))
  elseif it.year then e = tonumber(str(it.year):match("^(%d%d%d%d)"))
  else e = tonumber(os.date("%Y")) end
  return (e or 0) >= cut
end

local function years(it, L)
  local s = str(it.start)
  if not it["end"] then return open_span(s) end
  local e = str(it["end"])
  if e == s then return s end
  return s .. "-" .. e
end

local function joined(parts)
  -- parts: list of Inlines, joined with " - "
  local out = pandoc.Inlines({})
  for i, p in ipairs(parts) do
    if i > 1 then
      out:insert(pandoc.Space()); out:insert(pandoc.Str("-")); out:insert(pandoc.Space())
    end
    out:extend(p)
  end
  return out
end

local function lead(it, L, rest)
  local out = pandoc.Inlines({ pandoc.Strong({ pandoc.Str(years(it, L) .. ".") }), pandoc.Space() })
  out:extend(rest)
  return out
end

local function term_key(t)
  local y = t:match("^(%d%d%d%d)")
  local s = t:match("^%d%d%d%d%-(%d)")
  return (tonumber(y) or 0) * 10 + (tonumber(s) or 0)
end

local function sorted_desc(list, key)
  local dec = {}
  for i, v in ipairs(list) do dec[i] = { v = v, k = key(v), i = i } end
  table.sort(dec, function(a, b)
    if a.k ~= b.k then return a.k > b.k end
    return a.i < b.i
  end)
  local out = {}
  for i, d in ipairs(dec) do out[i] = d.v end
  return out
end

local renderers = {}

function renderers.projects(items, lang, L, cut)
  local blocks = {}
  for _, it in ipairs(items) do
   if keep(it, cut) then
    local parts = { inl(loc(it.title, lang)), pandoc.Inlines({ pandoc.Emph({ pandoc.Str(str(it.role)) }) }), inl(loc(it.code, lang)) }
    if it.program then parts[#parts + 1] = inl(loc(it.program, lang)) end
    parts[#parts + 1] = inl(loc(it.country, lang))
    if it.team then
      local names = {}
      for _, n in ipairs(it.team) do names[#names + 1] = loc(n, lang) end
      parts[#parts + 1] = inl(L.team .. ": " .. table.concat(names, ", "))
    end
    blocks[#blocks + 1] = { pandoc.Plain(lead(it, L, joined(parts))) }
   end
  end
  return blocks
end

function renderers.education(items, lang, L, cut, brief)
  local blocks = {}
  for _, it in ipairs(items) do
    do
      local head = inl(loc(it.title, lang))
      if it.original then
        if lang == "es" then
          head:insert(pandoc.Space()); head:insert(pandoc.Str("("))
          head:insert(pandoc.Emph(inl(str(it.original)))); head:insert(pandoc.Str(")"))
        else
          head:insert(pandoc.Space()); head:insert(pandoc.Str("/")); head:insert(pandoc.Space())
          head:insert(pandoc.Emph(inl(str(it.original))))
        end
      end
      local line = joined({ head, inl(str(it.institution) .. ", " .. loc(it.place, lang)) })
      local sub = {}
      for _, k in ipairs({ "thesis", "advisor", "scholarship", "award" }) do
        if it[k] and not brief then sub[#sub + 1] = { pandoc.Plain(inl(L[k] .. ": " .. loc(it[k], lang))) } end
      end
      local item = { pandoc.Plain(lead(it, L, line)) }
      if #sub > 0 then item[2] = pandoc.BulletList(sub) end
      blocks[#blocks + 1] = item
    end
  end
  return blocks
end

function renderers.programs(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    local prog = inl(loc(it.program, lang))
    if it.url then prog = pandoc.Inlines({ pandoc.Link(prog, str(it.url)) }) end
    blocks[#blocks + 1] = { pandoc.Plain(joined({ inl(loc(it.role, lang)), prog })) }
  end
  return blocks
end

function renderers.entries(items, lang, L, cut)
  local blocks = {}
  for _, it in ipairs(items) do
    if keep(it, cut) then
      blocks[#blocks + 1] = { pandoc.Plain(lead(it, L, rich(it.title, lang))) }
    end
  end
  return blocks
end

function renderers.pairs(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    blocks[#blocks + 1] = { pandoc.Plain(inl(loc(it.language, lang) .. ": " .. loc(it.level, lang))) }
  end
  return blocks
end

function renderers.journals(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    blocks[#blocks + 1] = { pandoc.Plain(inl(str(it.name) .. ": " .. fmt_reviews(it.reviews))) }
  end
  return blocks
end

function renderers.groups(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    local sub = {}
    for _, g in ipairs(it.items) do
      sub[#sub + 1] = { pandoc.Plain(inl(loc(g.name, lang) .. ": " .. fmt_reviews(g.reviews))) }
    end
    blocks[#blocks + 1] = { pandoc.Plain(lead(it, L, inl(loc(it.title, lang)))), pandoc.BulletList(sub) }
  end
  return blocks
end

function renderers.committees(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    local sub = {}
    for _, d in ipairs(it.degrees) do
      sub[#sub + 1] = { pandoc.Plain(inl(loc(d.name, lang) .. ": " .. fmt_reviews(d.reviews))) }
    end
    blocks[#blocks + 1] = { pandoc.Plain(inl(str(it.institution))), pandoc.BulletList(sub) }
  end
  return blocks
end

function renderers.conferences(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    if it.sub then
      local sub = {}
      for _, s in ipairs(it.sub) do
        sub[#sub + 1] = { pandoc.Plain(inl(series_label(s) .. ": " .. fmt_editions(s.editions))) }
      end
      blocks[#blocks + 1] = { pandoc.Plain(inl(series_label(it))), pandoc.BulletList(sub) }
    else
      blocks[#blocks + 1] = { pandoc.Plain(inl(series_label(it) .. ": " .. fmt_editions(it.editions))) }
    end
  end
  return blocks
end

local MONTHS = { january = 1, february = 2, march = 3, april = 4, may = 5, june = 6, july = 7, august = 8,
  september = 9, october = 10, november = 11, december = 12, enero = 1, febrero = 2, marzo = 3, abril = 4,
  mayo = 5, junio = 6, julio = 7, agosto = 8, septiembre = 9, octubre = 10, noviembre = 11, diciembre = 12 }
local MONTH_NAMES = {
  en = { "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December" },
  es = { "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre" },
}

local function month_label(raw, lang)
  local n = MONTHS[raw:lower()]
  return n and MONTH_NAMES[lang][n] or raw
end

local function author_inlines(list, L)
  local out, n = pandoc.Inlines({}), #list
  for i, a in ipairs(list) do
    local name = str(a)
    local presenter = name:sub(1, 1) == "*"
    if presenter then name = name:sub(2) end
    if i > 1 then
      if i == n then
        out:insert(pandoc.Space()); out:insert(pandoc.Str(L.and_)); out:insert(pandoc.Space())
      else
        out:insert(pandoc.Str(",")); out:insert(pandoc.Space())
      end
    end
    if presenter then out:insert(pandoc.Strong(inl(name))) else out:extend(inl(name)) end
  end
  return out
end

local function endp(s)
  if s:match("[%.%?!]$") then return s end
  return s .. "."
end

local function doi_link(doi)
  return pandoc.Link({ pandoc.Str("doi:" .. doi) }, "https://doi.org/" .. doi)
end

local function bib_item(it, style, lang, L)
  local f = function(k)
    local v = it[k] and str(it[k]) or nil
    if v == "" then return nil end
    return v
  end
  local out = author_inlines(it.authors, L)
  out:insert(pandoc.Space())
  out:extend(inl("(" .. f("year") .. ")."))
  out:insert(pandoc.Space())
  if style == "thesis" then
    out:insert(pandoc.Emph(inl(endp(f("title")):sub(1, -2))))
    out:insert(pandoc.Str("."))
    local bits = {}
    if f("degree") then bits[#bits + 1] = f("degree") end
    if f("school") then bits[#bits + 1] = f("school") end
    if f("address") then bits[#bits + 1] = f("address") end
    if #bits > 0 then out:insert(pandoc.Space()); out:extend(inl(endp(table.concat(bits, ", ")))) end
    return out
  end
  out:extend(inl(endp(f("title"))))
  if style == "article" then
    out:insert(pandoc.Space())
    local venue = pandoc.Emph(inl(f("journal") or ""))
    out:insert(venue)
    local tail = ""
    if f("volume") then tail = tail .. ", " .. f("volume") end
    if f("number") then tail = tail .. "(" .. f("number") .. ")" end
    if f("pages") then tail = tail .. ", " .. f("pages") end
    out:extend(inl(tail .. "."))
  elseif style == "conference" then
    out:insert(pandoc.Space())
    out:extend(inl(L["in"] .. ":"))
    out:insert(pandoc.Space())
    out:insert(pandoc.Emph(inl(f("booktitle") or "")))
    local tail = ""
    if f("volume") then tail = tail .. ", " .. f("volume") end
    if f("pages") then tail = tail .. ", " .. f("pages") end
    out:extend(inl(tail .. "."))
  elseif style == "talk" then
    out:insert(pandoc.Space())
    out:insert(pandoc.Emph(inl(f("booktitle") or "")))
    local tail = ""
    if f("address") then tail = tail .. ", " .. f("address") end
    if f("month") then tail = tail .. ", " .. month_label(f("month"), lang) .. " " .. f("year") end
    out:extend(inl(tail .. "."))
    if f("organization") then out:insert(pandoc.Space()); out:extend(inl(endp(f("organization")))) end
  elseif style == "report" then
    if f("institution") then out:insert(pandoc.Space()); out:extend(inl(endp(f("institution")))) end
  end
  if f("doi") then out:insert(pandoc.Space()); out:insert(doi_link(f("doi"))) end
  return out
end

local function render_bib(items, lang, L, cut, style)
  local blocks = {}
  for _, it in ipairs(items) do
    if keep(it, cut) then
      blocks[#blocks + 1] = { pandoc.Plain(bib_item(it, style, lang, L)) }
    end
  end
  return pandoc.OrderedList(blocks)
end

function renderers.appointments(items, lang, L, cut)
  local blocks = {}
  for _, it in ipairs(items) do
    local head = joined({ inl(str(it.institution) .. ", " .. str(it.city) .. ", " .. str(it.country)), inl(loc(it.unit, lang)) })
    local sub = {}
    for _, r in ipairs(it.ranks) do
      if keep(r, cut) then
        sub[#sub + 1] = { pandoc.Plain(inl(loc(r.title, lang) .. ": " .. years(r, L))) }
      end
    end
    blocks[#blocks + 1] = { pandoc.Plain(lead(it, L, head)), pandoc.BulletList(sub) }
  end
  return blocks
end

function renderers.teaching(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    local head = joined({ inl(loc(it.program, lang)), inl(str(it.institution) .. ", " .. str(it.country)) })
    local sub = {}
    for _, c in ipairs(it.courses) do
      local terms = {}
      for _, t in ipairs(c.terms) do terms[#terms + 1] = str(t) end
      terms = sorted_desc(terms, term_key)
      local label = loc(c.name, lang)
      if c.codes then
        local codes = {}
        for _, k in ipairs(c.codes) do codes[#codes + 1] = str(k) end
        label = label .. " (" .. table.concat(codes, ", ") .. ")"
      end
      sub[#sub + 1] = { pandoc.Plain(inl(label .. ": " .. table.concat(terms, " "))) }
    end
    blocks[#blocks + 1] = { pandoc.Plain(lead(it, L, head)), pandoc.BulletList(sub) }
  end
  return blocks
end

function renderers.training(items, lang, L)
  local blocks = {}
  for _, it in ipairs(items) do
    local head = joined({ inl(loc(it.title, lang)), inl(str(it.institution) .. ", " .. str(it.country)) })
    local sub = sorted_desc(it.courses, function(c) return tonumber(str(c.year)) end)
    local lines = {}
    for _, c in ipairs(sub) do
      lines[#lines + 1] = { pandoc.Plain(joined({ inl(str(c.year)), inl(loc(c.name, lang)), inl(str(c.hours)) })) }
    end
    blocks[#blocks + 1] = { pandoc.Plain(lead(it, L, head)), pandoc.BulletList(lines) }
  end
  return blocks
end

local function count_pi(file)
  local n = 0
  for _, it in ipairs(read_items(file)) do
    if str(it.role) == "PI" then n = n + 1 end
  end
  return n
end

local function active(file)
  return read_items(file)
end

local function summary(L)
  local c = count_pi("data/0601-projects-external.yml")
  local u = count_pi("data/0602-projects-ubiobio.yml")
  local g = count_pi("data/0603-projects-groups.yml")
  local wos, wos_n, scopus, gs_n, scielo_n = active("data/0701-pub-wos.yml"), 0, 0, 0, 0
  local scopus_list = active("data/0702-pub-scopus.yml")
  local peer, conf, prep = active("data/0703-pub-peer.yml"), active("data/0704-pub-conf.yml"), active("data/0705-pub-preprint.yml")
  for _, list in ipairs({ wos, scopus_list, peer, conf }) do
    for _, it in ipairs(list) do
      -- index counts come from the identifiers (id-wos / id-scopus)
      if it["id-wos"] then wos_n = wos_n + 1 end
      if it["id-scopus"] then scopus = scopus + 1 end
      if it["id-google-scholar"] then gs_n = gs_n + 1 end
      -- SciELO: only article level counts (id-scielo = PID; "NOK" = checked and absent)
      local sid = opt(it["id-scielo"])
      if sid and sid ~= "NOK" then scielo_n = scielo_n + 1 end
    end
  end
  local journals = #wos + #scopus_list + #peer
  local phd, msc, bsc = #active("data/0801-theses-phd-ubb.yml"), #active("data/0802-theses-msc-ubb.yml") + #active("data/0803-theses-msc-other.yml"), #active("data/0804-theses-bsc-ubb.yml")
  local lines = {
    string.format("%s: %d (%s: %d; %s: %d; %s: %d) - %s (%s): WoS %d, Scopus %d, Google Scholar %d, SciELO %d",
      L.publications, journals + #conf, L.journals, journals, L.confs, #conf, L.preprints, #prep,
      L.idx_title, L.idx, wos_n, scopus, gs_n, scielo_n),
    string.format("%s: %d (%s: %d; %s: %d; %s: %d)", L.theses, phd + msc + bsc, L.phd, phd, L.msc, msc, L.undergrad, bsc),
    string.format("%s: %d (%s: %d; %s: %d; %s: %d)", L.grants, c + u + g,
      L.competitive, c, L.university, u, L.groups, g),
  }
  local items = {}
  for i, l in ipairs(lines) do items[i] = { pandoc.Plain(inl(l)) } end
  return pandoc.BulletList(items)
end

-- Google Scholar numbers written by scripts/scholar-download.py (data/0101-scholar.yml)
local function scholar(lang, L)
  local it = read_items("data/0101-scholar.yml")[1]
  local y, m, d = str(it.date):match("^(%d+)-(%d+)-(%d+)$")
  local date = lang == "es" and string.format("%d de %s de %s", d, L.months[tonumber(m)], y)
    or string.format("%s %d, %s", L.months[tonumber(m)], d, y)
  local line = string.format("[Google Scholar](https://scholar.google.cl/citations?user=%s), %s %s: %s: %s · %s: %s · %s: %s.",
    str(it.user), L.as_of, date, L.citations, str(it.citations), L.h_index, str(it["h-index"]), L.i10_index, str(it["i10-index"]))
  return pandoc.Para(pandoc.read(line, "markdown").blocks[1].content)
end

-- text blocks: paragraphs, "label: value" bullets, optional level-2 heading
local function render_text(items, lang, short)
  local blocks, bullets = pandoc.Blocks({}), {}
  local function flush()
    if #bullets > 0 then blocks:insert(pandoc.BulletList(bullets)); bullets = {} end
  end
  for _, it in ipairs(items) do
    if not (it.only and str(it.only) ~= lang) and (not short or it.short == true) then
      if it.heading then
        flush()
        blocks:insert(pandoc.Header(2, rich(it.heading, lang)))
      elseif it.label then
        local line = pandoc.Inlines({})
        local label = rich(it.label, lang)
        label:insert(pandoc.Str(":"))
        line:extend(label)
        line:insert(pandoc.Space())
        line:extend(rich(it.value, lang))
        bullets[#bullets + 1] = { pandoc.Plain(line) }
      else
        flush()
        blocks:insert(pandoc.Para(rich(it.text, lang)))
      end
    end
  end
  flush()
  return blocks
end

-- style=web: markup of the personal site (../rlinfati.github.io): <h3> per institution, one <p> per entry
local function html_escape(v)
  -- YAML text goes through Pandoc's smart quotes: the site uses plain ones
  return (v:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub("\u{201C}", '"'):gsub("\u{201D}", '"'):gsub("\u{2019}", "'"):gsub("\u{2018}", "'"))
end

local function web_education(items, lang, L)
  local groups = {}
  for _, it in ipairs(items) do
    if it.web == true then
      local inst = str(it.institution)
      local last = groups[#groups]
      if not last or last.institution ~= inst then
        last = { institution = inst, paragraphs = {} }
        groups[#groups + 1] = last
      end
      local lines = { "<strong>" .. html_escape(loc(it.title, lang)) .. "</strong> " .. years(it, L) }
      local original = it.original and str(it.original) or (it.title.es and lang == "en" and str(it.title.es)) or nil
      if original then lines[#lines + 1] = "<em>" .. html_escape(original) .. "</em>" end
      for _, k in ipairs({ "advisor", "scholarship", "award" }) do
        if it[k] then lines[#lines + 1] = L[k] .. ": " .. html_escape(loc(it[k], lang)) end
      end
      last.paragraphs[#last.paragraphs + 1] = "<p>\n  " .. table.concat(lines, "<br>\n  ") .. "\n</p>"
    end
  end
  local blocks = pandoc.Blocks({})
  for i, g in ipairs(groups) do
    -- the markdown writer leaves no blank line between raw blocks: add it to all but the last
    blocks:insert(pandoc.RawBlock("html", "<h3>" .. html_escape(g.institution) .. "</h3>\n" .. table.concat(g.paragraphs, "\n") .. (i < #groups and "\n" or "")))
  end
  return blocks
end

-- style=web, work page: positions of the first appointment, then a list ordered by the `web` number of
-- 0301 (department), 0302 (programs) and 0303 (council)
local function web_link(text, url)
  text = html_escape(text)
  if url then return '<a href="' .. str(url) .. '">' .. text .. "</a>" end
  return text
end

local function web_li(head, course_list, lang)
  local lines = { "<li>", "  " .. head }
  if course_list and #course_list > 0 then
    lines[#lines + 1] = "  <ul>"
    for _, c in ipairs(course_list) do
      lines[#lines + 1] = "    <li>" .. html_escape(str(c.en)) .. " / <em>" .. html_escape(str(c.es)) .. "</em></li>"
    end
    lines[#lines + 1] = "  </ul>"
  end
  lines[#lines + 1] = "</li>"
  return lines
end

-- name and url of the first link inside a title field ({en, es} or plain markdown)
local function title_link(v, lang)
  local x = v
  if pandoc.utils.type(v) == "table" then x = v[lang] or v.en end
  for _, e in ipairs(x or {}) do
    if e.t == "Link" then return str(e.content), e.target end
  end
  return nil
end

local function web_work(appointments, programs, leadership, lang, L)
  local appointment
  for _, it in ipairs(appointments) do if it.web then appointment = it; break end end
  local ranks = {}
  for _, r in ipairs(appointment.ranks) do
    ranks[#ranks + 1] = "  <li>" .. html_escape(loc(r.title, lang)) .. ": " .. years(r, L) .. "</li>"
  end
  local entries = {}
  for _, it in ipairs(leadership) do
    if it.web then
      local name_en, url = title_link(it.title, "en")
      local name_es = title_link(it.title, "es")
      local head = web_link(name_en, url) .. " / <em>" .. html_escape(name_es) .. "</em>: " .. years(it, L)
      entries[#entries + 1] = { n = tonumber(str(it.web)), lines = web_li(head, nil, lang) }
    end
  end
  do
    local head = html_escape(loc(appointment.ranks[1].title, lang)) .. " - " .. web_link(str(appointment.unit.en), appointment.url)
      .. " / <em>" .. html_escape(str(appointment.unit.es)) .. "</em>"
    entries[#entries + 1] = { n = tonumber(str(appointment.web)), lines = web_li(head, appointment["web-courses"], lang) }
  end
  for _, it in ipairs(programs) do
    if it.web then
      local head = html_escape(str(it.role.en)) .. " - " .. web_link(str(it.program.en), it.url)
        .. " / <em>" .. html_escape(str(it.program.es)) .. "</em>"
      entries[#entries + 1] = { n = tonumber(str(it.web)), lines = web_li(head, it["web-courses"], lang) }
    end
  end
  table.sort(entries, function(a, b) return a.n < b.n end)
  local out = { "<h3>" .. html_escape(str(appointment.institution)) .. "</h3>", "<ul>" }
  for _, r in ipairs(ranks) do out[#out + 1] = r end
  out[#out + 1] = "</ul>"
  out[#out + 1] = "<ul>"
  for _, e in ipairs(entries) do
    for _, l in ipairs(e.lines) do out[#out + 1] = "  " .. l end
  end
  out[#out + 1] = "</ul>"
  return pandoc.Blocks({ pandoc.RawBlock("html", table.concat(out, "\n") .. "\n") })
end

-- style=web, home page: intro paragraph and the labelled lists of data/0000-about.yml
local function web_about(items, lang)
  local intro, bullets, heading = nil, {}, nil
  for _, it in ipairs(items) do
    if it.heading then heading = loc(it.heading, lang)
    elseif it.label then
      local lines = { "<li>", "    <strong>" .. html_escape(loc(it.label, lang)) .. ":</strong>" }
      local value, pos = loc(it.value, lang), 1
      while true do  -- one line per ";" segment
        local from, to = value:find("; ", pos, true)
        if not from then lines[#lines + 1] = "    " .. html_escape(value:sub(pos)); break end
        lines[#lines + 1] = "    " .. html_escape(value:sub(pos, from))
        pos = to + 1
      end
      lines[#lines + 1] = "</li>"
      bullets[#bullets + 1] = lines
    elseif heading and not intro then intro = loc(it.text, lang) end
  end
  local out = { "<h2>" .. html_escape(heading) .. "</h2>", "",
    '<div class="profile">',
    '  <img src="profile.jpg" alt="Rodrigo Linfati" width="200" height="200">',
    '  <div class="profile-text">',
    "<p>", html_escape(intro), "</p>",
    "  </div>", "</div>", "", "<ul>" }
  for _, lines in ipairs(bullets) do for _, l in ipairs(lines) do out[#out + 1] = l end end
  out[#out + 1] = "</ul>"
  for i, l in ipairs(out) do if l ~= "" then out[i] = "  " .. l end end
  return pandoc.Blocks({ pandoc.RawBlock("html", table.concat(out, "\n") .. "\n") })
end

-- style=web, research page: the projects with a `web` number (in the order of that number)
local function web_research(lists, lang, L)
  local entries = {}
  for source, items in ipairs(lists) do
    for _, it in ipairs(items) do
      if it.web then entries[#entries + 1] = { n = tonumber(str(it.web)), it = it, group = source == 2 } end
    end
  end
  table.sort(entries, function(a, b) return a.n < b.n end)
  local out = { "<ul>" }
  for i, e in ipairs(entries) do
    local it = e.it
    local code = html_escape(loc(it.code, lang))
    if it["web-mark"] == true then code = "<mark>" .. code .. "</mark>" end
    local en, es = html_escape(str(it.title.en)), html_escape(str(it.title.es))
    if e.group then en = "<em>" .. en .. "</em>" end
    out[#out + 1] = "  <li>"
    out[#out + 1] = "      " .. years(it, L) .. " - " .. code .. " - <strong>" .. L.role_names[str(it.role)] .. "</strong> -"
    out[#out + 1] = "      " .. en .. " / <em>" .. es .. "</em>"
    out[#out + 1] = "  </li>"
    if i < #entries then out[#out + 1] = "" end
  end
  out[#out + 1] = "</ul>"
  return pandoc.Blocks({ pandoc.RawBlock("html", table.concat(out, "\n") .. "\n\n\n") })
end

-- keeps only the entries with role= and/or mandante=
local function select_items(items, kwargs)
  local role, mandante, web = opt(kwargs.role), opt(kwargs.mandante), opt(kwargs.web) == "true"
  if not (role or mandante or web) then return items end
  local kept = {}
  for _, it in ipairs(items) do
    if (not role or str(it.role) == role) and (not mandante or str(it.mandante) == mandante) and (not web or it.web) then
      kept[#kept + 1] = it
    end
  end
  return kept
end

return {
  cv = function(args, kwargs, meta)
    local kind = str(args[1])
    if kind == "now" then return pandoc.Str(now_label()) end
    if kind == "span" then return pandoc.Str(open_span(str(args[2]))) end
    local lang = doc_lang(meta)
    local L = LABELS[lang]
    if kind == "summary" then return summary(L) end
    if kind == "scholar" then return scholar(lang, L) end
    if kind == "text" then
      if opt(kwargs.style) == "web" then return web_about(read_items(str(args[2])), lang) end
      local blocks = render_text(select_items(read_items(str(args[2])), kwargs), lang, opt(kwargs.short) == "true")
      if opt(kwargs.web) == "true" then  -- the web pages are written as markdown with html blocks: emit html
        return pandoc.Blocks({ pandoc.RawBlock("html", pandoc.write(pandoc.Pandoc(blocks), "html")) })
      end
      return blocks
    end
    if kind == "projects" and opt(kwargs.style) == "web" then
      local lists = {}
      for i = 2, #args do lists[#lists + 1] = read_items(str(args[i])) end
      return web_research(lists, lang, L)
    end
    if kind == "bib" then
      local file = str(args[2])
      return render_bib(select_items(read_items(file), kwargs), lang, L, cutoff(kwargs.last), opt(kwargs.style) or "article")
    end
    if kind == "education" and opt(kwargs.style) == "web" then return web_education(read_items(str(args[2])), lang, L) end
    if kind == "work" and opt(kwargs.style) == "web" then
      return web_work(read_items(str(args[2])), read_items(str(args[3])), read_items(str(args[4])), lang, L)
    end
    local render = assert(renderers[kind], "cv: unknown type " .. kind)
    local items = select_items(read_items(str(args[2])), kwargs)
    return pandoc.BulletList(render(items, lang, L, cutoff(kwargs.last), opt(kwargs.web) == "true"))
  end,
}
