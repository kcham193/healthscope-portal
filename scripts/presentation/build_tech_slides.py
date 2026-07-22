"""
Build HealthScope_Technical_Deck.pptx — technical briefing deck for data
engineers / architects. Reuses the design tokens and helper patterns from
build_healthscope_presentation.py in hf-data-portal (navy + teal + amber
accents on white; typography-led; thin dividers) but produces a longer,
denser deck with real numbers, code snippets, and architecture diagrams.

Deps:
    pip install python-pptx

Usage (from the deploy clone root):
    python scripts/presentation/build_tech_slides.py

Output:
    HealthScope_Technical_Deck.pptx  (in the current working directory)

Slides:
     1. Title
     2. The problem  — MoH registries answer 'where', not 'who reaches it'
     3. What we built — four intelligence layers over MoH data
     4. Repo topology — two repos, one submodule, one deploy target
     5. ETL pipeline v2 — extract / transform / load
     6. Canonical schema — one 30-column CSV per country
     7. Portal stack — Quarto + client-side JS, zero backend
     8. Registry Explorer — coverage at a glance
     9. Voronoi vs radial catchments — the honest-catchment story
    10. Travel-time bands — modelled accessibility
    11. Tanzania flagship — the R pipeline
    12. Tanzania flagship — the headline numbers
    13. Deployment — GitHub Pages, no build server
    14. Chatbot layer — scope + guardrails
    15. Limits & roadmap
    16. Team + acknowledgments
"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

# ─── design tokens ─────────────────────────────────────────────────────────
NAVY       = RGBColor(0x1A, 0x3C, 0x5E)
TEAL       = RGBColor(0x3E, 0x7C, 0xB1)
INK        = RGBColor(0x1F, 0x2A, 0x37)
GREY       = RGBColor(0x6B, 0x72, 0x80)
LIGHT_GREY = RGBColor(0xCB, 0xD0, 0xD6)
PALE       = RGBColor(0xF3, 0xF5, 0xF8)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
AMBER      = RGBColor(0xC9, 0xA2, 0x27)  # HealthScope brand gold
GREEN_1    = RGBColor(0x1A, 0x98, 0x50)  # travel-time band <30 min
GREEN_2    = RGBColor(0xA6, 0xD9, 0x6A)  # 30-60
ORANGE     = RGBColor(0xFD, 0xAE, 0x61)  # 60-90
RED        = RGBColor(0xD7, 0x30, 0x27)  # >90
PURPLE     = RGBColor(0x54, 0x27, 0x8F)  # Voronoi catchment top-quintile

TITLE_FONT = "Calibri"
BODY_FONT  = "Calibri"
CODE_FONT  = "Consolas"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# ─── presentation setup ────────────────────────────────────────────────────
prs = Presentation()
prs.slide_width  = SLIDE_W
prs.slide_height = SLIDE_H

BLANK_LAYOUT = prs.slide_layouts[6]


def new_slide():
    s = prs.slides.add_slide(BLANK_LAYOUT)
    force_white_background(s)
    return s


def force_white_background(slide):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = WHITE


# ─── low-level helpers ─────────────────────────────────────────────────────
def add_text(slide, x, y, w, h, text, *, font=BODY_FONT, size=14, bold=False,
             italic=False, color=INK, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, line_spacing=1.25):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = line
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
    return tb


def add_bullets(slide, x, y, w, h, items, *, size=15, color=INK,
                line_spacing=1.35, bullet_color=AMBER):
    """Bullet-like list. items = list of str, each line rendered with a • prefix
    in AMBER followed by INK body text."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = line_spacing
        if i > 0:
            p.space_before = Pt(4)
        r_dot = p.add_run()
        r_dot.text = "• "
        r_dot.font.name = BODY_FONT
        r_dot.font.size = Pt(size)
        r_dot.font.bold = True
        r_dot.font.color.rgb = bullet_color

        r_body = p.add_run()
        r_body.text = item
        r_body.font.name = BODY_FONT
        r_body.font.size = Pt(size)
        r_body.font.color.rgb = color
    return tb


def add_line(slide, x1, y1, x2, y2, *, color=NAVY, weight=1.0):
    ln = slide.shapes.add_connector(1, x1, y1, x2, y2)
    ln.line.color.rgb = color
    ln.line.width = Pt(weight)
    return ln


def add_rect(slide, x, y, w, h, *, fill=None, line_color=LIGHT_GREY,
             line_weight=0.75, no_line=False):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shp.shadow.inherit = False
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if no_line:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_weight)
    return shp


def add_rounded_rect(slide, x, y, w, h, *, fill=None, line_color=NAVY,
                     line_weight=1.0, no_line=False):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.shadow.inherit = False
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if no_line:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_weight)
    return shp


def add_code_block(slide, x, y, w, h, code, *, size=11):
    """Monospaced code box on a pale grey card."""
    add_rect(slide, x, y, w, h, fill=PALE, no_line=True)
    tb = slide.shapes.add_textbox(x + Inches(0.15), y + Inches(0.12),
                                  w - Inches(0.3), h - Inches(0.24))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    lines = code.split("\n")
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = 1.15
        r = p.add_run()
        r.text = ln if ln else " "
        r.font.name = CODE_FONT
        r.font.size = Pt(size)
        r.font.color.rgb = INK
    return tb


def add_header(slide, title, *, eyebrow=None, subtitle=None):
    if eyebrow:
        add_text(slide, Inches(0.7), Inches(0.55), Inches(11), Inches(0.3),
                 eyebrow.upper(), size=10, bold=True, color=TEAL,
                 line_spacing=1.0)
    add_text(slide, Inches(0.7), Inches(0.85), Inches(12), Inches(0.95),
             title, font=TITLE_FONT, size=32, bold=True, color=NAVY,
             line_spacing=1.05)
    if subtitle:
        add_text(slide, Inches(0.7), Inches(1.62), Inches(12), Inches(0.5),
                 subtitle, size=14, color=GREY, italic=True, line_spacing=1.2)
        rule_y = Inches(2.05)
    else:
        rule_y = Inches(1.72)
    add_line(slide, Inches(0.7), rule_y, Inches(1.9), rule_y,
             color=NAVY, weight=1.5)


def add_footer(slide, page_number, total):
    add_line(slide, Inches(0.7), Inches(7.15), Inches(12.6), Inches(7.15),
             color=LIGHT_GREY, weight=0.5)
    add_text(slide, Inches(0.7), Inches(7.22), Inches(9), Inches(0.25),
             "HealthScope  ·  Technical build overview  ·  Malaria Atlas Project — Dar es Salaam Node",
             size=9, color=GREY)
    add_text(slide, Inches(11.5), Inches(7.22), Inches(1.1), Inches(0.25),
             f"{page_number:02d} / {total:02d}",
             size=9, color=GREY, align=PP_ALIGN.RIGHT)


def add_metric_tile(slide, x, y, w, h, value, label, *, color=AMBER):
    add_rect(slide, x, y, w, h, fill=WHITE, line_color=LIGHT_GREY,
             line_weight=0.75)
    add_text(slide, x + Inches(0.1), y + Inches(0.15), w - Inches(0.2),
             Inches(0.7), value, font=TITLE_FONT, size=28, bold=True,
             color=color, align=PP_ALIGN.CENTER, line_spacing=1.0)
    add_text(slide, x + Inches(0.1), y + Inches(0.85), w - Inches(0.2),
             Inches(0.35), label, size=10, color=GREY,
             align=PP_ALIGN.CENTER, line_spacing=1.2)


# ─── slides ────────────────────────────────────────────────────────────────

def slide_title(total):
    s = new_slide()
    # Big navy block on the left third
    add_rect(s, Emu(0), Emu(0), Inches(4.5), SLIDE_H, fill=NAVY, no_line=True)
    add_rect(s, Inches(0.5), Inches(2.8), Inches(0.08), Inches(0.9),
             fill=AMBER, no_line=True)
    add_text(s, Inches(0.75), Inches(2.7), Inches(3.5), Inches(0.5),
             "HEALTHSCOPE", font=TITLE_FONT, size=13, bold=True, color=AMBER,
             line_spacing=1.0)
    add_text(s, Inches(0.75), Inches(3.15), Inches(3.5), Inches(1.3),
             "Health Facility\nIntelligence Portal", font=TITLE_FONT,
             size=32, bold=True, color=WHITE, line_spacing=1.05)
    add_text(s, Inches(0.75), Inches(5.15), Inches(3.5), Inches(1.0),
             "Malaria Atlas Project\nDar es Salaam Node",
             size=11, color=RGBColor(0xC5, 0xD1, 0xDE), line_spacing=1.4)

    # Right side: technical framing
    add_text(s, Inches(5.3), Inches(2.5), Inches(7.5), Inches(0.4),
             "TECHNICAL BUILD OVERVIEW", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    add_text(s, Inches(5.3), Inches(2.9), Inches(7.5), Inches(2.2),
             "How we built HealthScope:\ndata pipeline, portal, and analyses.",
             font=TITLE_FONT, size=30, bold=True, color=NAVY,
             line_spacing=1.1)
    add_line(s, Inches(5.3), Inches(4.85), Inches(6.5), Inches(4.85),
             color=NAVY, weight=1.5)
    add_text(s, Inches(5.3), Inches(4.95), Inches(7.5), Inches(1.2),
             "From MoH facility registries to a public, reproducible, "
             "open-source portal.",
             size=15, color=GREY, italic=True, line_spacing=1.45)


def slide_problem(total, page):
    s = new_slide()
    add_header(s, "MoH facility registries answer 'where', not 'who reaches it'",
               eyebrow="The gap", subtitle="What we can and can't do with a bare MoH facility list")
    add_bullets(s, Inches(0.7), Inches(2.4), Inches(6.5), Inches(3.5), [
        "MoH registries publish facility name + coordinates + basic metadata.",
        "They rarely publish population served, road access, or per-service availability.",
        "Static PDF maps or spreadsheets don't inform planning around access.",
        "'Nearest facility' is a straight-line concept in most tools — even when the "
        "user's real question is 'can I get there in an hour?'",
    ])

    # Right column: sample MoH-shape data
    add_text(s, Inches(7.7), Inches(2.4), Inches(5.0), Inches(0.3),
             "What raw MoH data looks like",
             size=11, bold=True, color=TEAL, line_spacing=1.0)
    # A simple table-style rectangle
    add_rect(s, Inches(7.7), Inches(2.75), Inches(5.0), Inches(3.5),
             fill=PALE, no_line=True)
    add_text(s, Inches(7.85), Inches(2.85), Inches(4.7), Inches(3.3),
             "facility_code   100675-8\n"
             "facility_name   CANOSSA DISPENSARY\n"
             "admin1          Arusha\n"
             "admin2          Arusha\n"
             "facility_type   Dispensary\n"
             "ownership       Private (FBO)\n"
             "latitude        -3.45802\n"
             "longitude       36.71262\n"
             "\n"
             "# What's missing:\n"
             "#   catchment_population       ?\n"
             "#   pop_within_5km             ?\n"
             "#   pop_within_60min_travel    ?\n"
             "#   is_reachable_by_road       ?",
             font=CODE_FONT, size=10, color=INK, line_spacing=1.35)
    add_footer(s, page, total)


def slide_what_we_built(total, page):
    s = new_slide()
    add_header(s, "Four intelligence layers on top of MoH data",
               eyebrow="What we built",
               subtitle="Each layer transforms the raw registry into something planners can act on")

    # Four coloured boxes across the middle
    box_y = Inches(2.6)
    box_w = Inches(2.9)
    box_h = Inches(3.2)
    gap = Inches(0.15)
    total_w = 4 * box_w + 3 * gap
    start_x = (SLIDE_W - total_w) / 2

    boxes = [
        ("1", "Facility Registry Lake",
         "Standardised facility data\nfrom MoH sources across\n8 SSA countries. Multi-\ncountry harmonised schema.",
         AMBER),
        ("2", "Population & Access",
         "Voronoi catchments +\nmodelled travel-time bands.\nWho each facility serves,\nwho can reach it.",
         GREEN_1),
        ("3", "Service Intelligence",
         "Per-domain service\ncoverage across the registry\nand per-facility service\nprofiles.",
         ORANGE),
        ("4", "Find Facility",
         "Public-facing search\ntool: pick a service, get\nnearest facilities with real\nroad-network distance.",
         TEAL),
    ]
    for i, (num, title, body, color) in enumerate(boxes):
        x = start_x + i * (box_w + gap)
        add_rect(s, x, box_y, box_w, box_h, fill=WHITE, line_color=LIGHT_GREY,
                 line_weight=0.75)
        # coloured stripe on top
        add_rect(s, x, box_y, box_w, Inches(0.08), fill=color, no_line=True)
        add_text(s, x + Inches(0.2), box_y + Inches(0.25), Inches(0.5),
                 Inches(0.4), num, font=TITLE_FONT, size=26, bold=True,
                 color=color, line_spacing=1.0)
        add_text(s, x + Inches(0.2), box_y + Inches(0.85), box_w - Inches(0.4),
                 Inches(0.6), title, font=TITLE_FONT, size=15, bold=True,
                 color=NAVY, line_spacing=1.15)
        add_text(s, x + Inches(0.2), box_y + Inches(1.5), box_w - Inches(0.4),
                 Inches(1.6), body, size=11, color=INK, line_spacing=1.4)

    # Bottom stat strip
    add_line(s, Inches(0.7), Inches(6.15), Inches(12.6), Inches(6.15),
             color=LIGHT_GREY, weight=0.5)
    add_text(s, Inches(0.7), Inches(6.3), Inches(12), Inches(0.5),
             "≈ 131,700 facilities  ·  8 countries  ·  100 m raster resolution  ·  0 backend servers",
             size=13, bold=True, color=NAVY, align=PP_ALIGN.CENTER,
             line_spacing=1.0)
    add_footer(s, page, total)


def slide_repo_topology(total, page):
    s = new_slide()
    add_header(s, "Two repos, one submodule, one deploy target",
               eyebrow="Repository layout",
               subtitle="Working copy vs. public deploy — kept separate so source can move faster than production")

    # Draw three columns as boxes with arrows
    box_y = Inches(2.6)
    box_h = Inches(2.2)
    box_w = Inches(3.5)
    xs = [Inches(0.7), Inches(4.9), Inches(9.1)]

    labels = [
        ("hf-data-portal",
         "Source / working repo\n\n• Author-only clone\n• Rendered iteratively\n• Not deployed",
         AMBER),
        ("healthscope-portal",
         "Deploy clone\n\n• Also contains rendered docs/\n• GitHub Pages serves from docs/\n• Pushed only when work is release-ready",
         TEAL),
        ("map-data-engineering.github.io\n/healthscope-portal",
         "Public site\n\n• Live URL\n• CDN-cached HTML + CSV/GeoJSON\n• End users hit this directly",
         NAVY),
    ]
    for i, (name, body, color) in enumerate(labels):
        x = xs[i]
        add_rect(s, x, box_y, box_w, box_h, fill=WHITE, line_color=color,
                 line_weight=1.5)
        add_rect(s, x, box_y, Inches(0.08), box_h, fill=color, no_line=True)
        add_text(s, x + Inches(0.25), box_y + Inches(0.15), box_w - Inches(0.35),
                 Inches(0.5), name, font=TITLE_FONT, size=13, bold=True,
                 color=color, line_spacing=1.1)
        add_text(s, x + Inches(0.25), box_y + Inches(0.75),
                 box_w - Inches(0.35), box_h - Inches(0.9), body,
                 size=11, color=INK, line_spacing=1.4)

    # Arrows between them
    for i in [0, 1]:
        add_line(s, xs[i] + box_w, box_y + box_h / 2,
                 xs[i + 1] - Emu(20000), box_y + box_h / 2,
                 color=NAVY, weight=1.25)

    # ETL submodule strip below
    add_rect(s, Inches(0.7), Inches(5.4), Inches(11.9), Inches(1.2),
             fill=PALE, no_line=True)
    add_text(s, Inches(0.9), Inches(5.55), Inches(11.5), Inches(0.35),
             "SHARED SUBSTRATE",
             size=10, bold=True, color=TEAL, line_spacing=1.0)
    add_text(s, Inches(0.9), Inches(5.85), Inches(11.5), Inches(0.6),
             "etl/  →  git submodule at map-data-engineering/health_facility_etl. "
             "Standardises MoH source data into per-country CSVs consumed by both "
             "the working and deploy clones.",
             size=12, color=INK, line_spacing=1.45)
    add_footer(s, page, total)


def slide_etl(total, page):
    s = new_slide()
    add_header(s, "MoH source → standardised CSV in three steps",
               eyebrow="ETL pipeline (v2)",
               subtitle="Idempotent, versionable, per-country. Reruns take minutes.")

    # Three-step flow across the top half
    step_y = Inches(2.5)
    step_h = Inches(1.6)
    step_w = Inches(3.7)
    gap = Inches(0.35)
    total_w = 3 * step_w + 2 * gap
    start_x = (SLIDE_W - total_w) / 2

    steps = [
        ("EXTRACT",
         "Fetch the latest per-country registry\n"
         "(CSV export, DHIS2 API, or MFR portal).",
         AMBER),
        ("TRANSFORM",
         "Standardise columns, validate coords\n"
         "against country bbox, mint stable UIDs,\n"
         "map raw services onto the 7-domain\n"
         "canonical hierarchy.",
         TEAL),
        ("LOAD",
         "Publish versioned per-country CSVs\n"
         "under etl/data/processed/\n"
         "country_standardized/ — read directly\n"
         "by the portal at build time.",
         NAVY),
    ]
    for i, (name, body, color) in enumerate(steps):
        x = start_x + i * (step_w + gap)
        add_rect(s, x, step_y, step_w, step_h, fill=WHITE, line_color=color,
                 line_weight=1.25)
        add_text(s, x + Inches(0.2), step_y + Inches(0.15), step_w - Inches(0.4),
                 Inches(0.4), name, font=TITLE_FONT, size=13, bold=True,
                 color=color, line_spacing=1.0)
        add_text(s, x + Inches(0.2), step_y + Inches(0.55), step_w - Inches(0.4),
                 step_h - Inches(0.7), body, size=11, color=INK,
                 line_spacing=1.4)
        if i < 2:
            add_line(s, x + step_w, step_y + step_h / 2,
                     x + step_w + gap, step_y + step_h / 2,
                     color=GREY, weight=1.0)

    # Details / callouts below
    add_text(s, Inches(0.7), Inches(4.4), Inches(12), Inches(0.4),
             "IMPLEMENTATION NOTES",
             size=10, bold=True, color=TEAL, line_spacing=1.0)
    add_bullets(s, Inches(0.7), Inches(4.75), Inches(12), Inches(2.2), [
        "Per-country crosswalks live as YAML under etl/config/ — service categories, "
        "column renames, and bounding-box validation.",
        "Facility UIDs are country-scoped and stable across reruns (TZA-000001, KEN-000001…). "
        "Downstream joins are safe.",
        "Coordinate validation drops rows outside the country bbox before publishing "
        "— stops one bad geocode from crashing every consumer.",
        "Outputs are plain CSV. The portal reads them client-side with Papa Parse; "
        "no server layer required.",
    ], size=13)
    add_footer(s, page, total)


def slide_schema(total, page):
    s = new_slide()
    add_header(s, "One 30-column CSV per country",
               eyebrow="Canonical schema",
               subtitle="Everything the portal needs, in a flat file the whole team can open in Excel")

    add_code_block(s, Inches(0.7), Inches(2.4), Inches(12), Inches(4.3),
                   "facility_code       TZA-000001                   # stable UID (country-scoped)\n"
                   "facility_name       CANOSSA DISPENSARY\n"
                   "zone                Northern Zone\n"
                   "admin1              Arusha                       # region\n"
                   "admin2              Arusha                       # district\n"
                   "council             Arusha CC\n"
                   "ward                Engutoto\n"
                   "village             Block J\n"
                   "facility_type       Dispensary                   # from canonical typology\n"
                   "ownership_detail    Faith Based Organization (FBO)\n"
                   "ownership           Private                       # collapsed 4-way categorical\n"
                   "status              Operating\n"
                   "latitude            -3.45802\n"
                   "longitude           36.71262\n"
                   "coordinate_valid    TRUE\n"
                   "data_source         MoH Tanzania HFR 2026\n"
                   "extraction_date     2026-...\n"
                   "\n"
                   "# Service flags (per canonical 7-domain hierarchy):\n"
                   "inpatient, outpatient, maternity, emergency, laboratory,\n"
                   "malaria_services, ...",
                   size=11)
    add_footer(s, page, total)


def slide_frontend(total, page):
    s = new_slide()
    add_header(s, "Quarto + client-side JS, zero backend",
               eyebrow="Portal architecture",
               subtitle="Every page is static HTML — data lands in the browser and rendering happens there")

    # Left column: the static stack
    add_text(s, Inches(0.7), Inches(2.4), Inches(5.6), Inches(0.4),
             "BUILD TIME (Quarto)", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    add_bullets(s, Inches(0.7), Inches(2.75), Inches(5.6), Inches(2.5), [
        "Quarto compiles *.qmd → *.html into docs/.",
        "Resource files (etl CSVs, hex geojsons, ors-key.js) are\n"
        "  copied via _quarto.yml resources: entries.",
        "Custom SCSS drives the theme; navbar + footer defined\n"
        "  once in _quarto.yml.",
        "Freeze cache skips rerender when only navigation changes.",
    ], size=12)

    add_text(s, Inches(0.7), Inches(5.15), Inches(5.6), Inches(0.4),
             "RUNTIME (client-side)", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    add_bullets(s, Inches(0.7), Inches(5.5), Inches(5.6), Inches(1.6), [
        "Leaflet — interactive maps",
        "Papa Parse — CSVs fetched + parsed in the browser",
        "Chart.js — histograms + summary charts",
        "OpenRouteService API — road distance / travel time",
    ], size=12)

    # Right column: architecture diagram (schematic)
    diag_x = Inches(7.0)
    diag_y = Inches(2.4)
    diag_w = Inches(5.6)

    def bar(y, label, sub, color):
        add_rect(s, diag_x, y, diag_w, Inches(0.55), fill=color, no_line=True)
        add_text(s, diag_x + Inches(0.2), y + Inches(0.08), diag_w - Inches(0.4),
                 Inches(0.4), label, font=TITLE_FONT, size=12, bold=True,
                 color=WHITE, line_spacing=1.0)
        add_text(s, diag_x + Inches(0.2), y + Inches(0.32),
                 diag_w - Inches(0.4), Inches(0.25), sub, size=9,
                 color=RGBColor(0xEE, 0xEE, 0xEE), italic=True,
                 line_spacing=1.0)

    bars = [
        ("Visitor's browser",     "Chrome / Safari / Edge / Firefox",  NAVY),
        ("HTML + CSS + JS",       "docs/*.html on GitHub Pages CDN",   TEAL),
        ("Data (CSV + GeoJSON)",  "docs/etl/... + docs/data/population/...", AMBER),
        ("External APIs",         "OpenRouteService (routing), Botpress (chat)", GREY),
    ]
    step = Inches(0.85)
    for i, (label, sub, color) in enumerate(bars):
        bar(diag_y + step * i, label, sub, color)
        if i < len(bars) - 1:
            add_line(s, diag_x + diag_w / 2, diag_y + step * i + Inches(0.55),
                     diag_x + diag_w / 2, diag_y + step * (i + 1),
                     color=LIGHT_GREY, weight=1.0)
    add_footer(s, page, total)


def slide_registry(total, page):
    s = new_slide()
    add_header(s, "Registry Explorer — coverage at a glance",
               eyebrow="Feature 1",
               subtitle="A single map + filter panel that loads 8 countries in parallel and stays snappy")

    add_bullets(s, Inches(0.7), Inches(2.4), Inches(6.5), Inches(3.5), [
        "Fetches all 8 per-country CSVs concurrently (Promise.all + Papa Parse).",
        "Country boundaries drawn from Natural Earth GeoJSON; hover to preview count.",
        "Filters (country, type, ownership, name search) resolve client-side over "
        "the in-memory dataset — no server round-trips.",
        "Filtered subset can be re-downloaded as CSV in one click.",
        "Country selector dropdown alphabetised across the whole portal for "
        "consistent muscle memory.",
    ], size=13)

    # Right: numbers
    add_text(s, Inches(7.9), Inches(2.4), Inches(5.0), Inches(0.4),
             "PER-COUNTRY FACILITY COUNT",
             size=11, bold=True, color=TEAL, line_spacing=1.0)
    counts = [
        ("Nigeria",  "51,023"),
        ("Ethiopia", "40,035"),
        ("Kenya",    "17,353"),
        ("Tanzania", "13,075"),
        ("Uganda",   "8,512"),
        ("Zambia",   "3,731"),
        ("Malawi",   "1,929"),
        ("Botswana", "1,076"),
    ]
    row_y = Inches(2.85)
    row_h = Inches(0.4)
    for i, (name, count) in enumerate(counts):
        y = row_y + row_h * i
        add_text(s, Inches(7.9), y, Inches(2.5), row_h, name,
                 size=12, color=INK, line_spacing=1.1)
        add_text(s, Inches(10.5), y, Inches(2.3), row_h, count,
                 size=12, bold=True, color=AMBER, align=PP_ALIGN.RIGHT,
                 line_spacing=1.1)
    add_footer(s, page, total)


def slide_voronoi(total, page):
    s = new_slide()
    add_header(s, "Voronoi catchments beat radial buffers",
               eyebrow="Method — Feature 2",
               subtitle="Radial buffers overlap and double-count people. Voronoi tiles the country without gaps or overlap.")

    col_w = Inches(5.7)
    col_h = Inches(4.0)
    y = Inches(2.4)

    # Left: radial (limitations)
    add_rect(s, Inches(0.7), y, col_w, col_h, fill=WHITE,
             line_color=LIGHT_GREY, line_weight=1.0)
    add_rect(s, Inches(0.7), y, Inches(0.08), col_h, fill=RED, no_line=True)
    add_text(s, Inches(0.95), y + Inches(0.15), col_w - Inches(0.3),
             Inches(0.4), "RADIAL 5 / 10 km BUFFER",
             size=11, bold=True, color=RED, line_spacing=1.0)
    add_text(s, Inches(0.95), y + Inches(0.55), col_w - Inches(0.3),
             Inches(0.5), "Fixed circle around each facility",
             font=TITLE_FONT, size=16, bold=True, color=NAVY,
             line_spacing=1.1)
    add_bullets(s, Inches(0.95), y + Inches(1.15), col_w - Inches(0.3),
                Inches(2.5), [
        "Circles from neighbouring facilities overlap.",
        "Every overlapping cell of population is counted twice or more.",
        "Median 5 km catchment for Tanzania inflates to ~12,700 people.",
        "Total pop across all catchments >> national population.",
    ], size=11)

    # Right: Voronoi (advantages)
    x2 = Inches(7.0)
    add_rect(s, x2, y, col_w, col_h, fill=WHITE,
             line_color=LIGHT_GREY, line_weight=1.0)
    add_rect(s, x2, y, Inches(0.08), col_h, fill=GREEN_1, no_line=True)
    add_text(s, x2 + Inches(0.25), y + Inches(0.15), col_w - Inches(0.3),
             Inches(0.4), "VORONOI (NEAREST-FACILITY)",
             size=11, bold=True, color=GREEN_1, line_spacing=1.0)
    add_text(s, x2 + Inches(0.25), y + Inches(0.55), col_w - Inches(0.3),
             Inches(0.5), "Each facility owns its Voronoi cell",
             font=TITLE_FONT, size=16, bold=True, color=NAVY,
             line_spacing=1.1)
    add_bullets(s, x2 + Inches(0.25), y + Inches(1.15), col_w - Inches(0.3),
                Inches(2.5), [
        "Every point in the country belongs to exactly one facility.",
        "No overlap, no gaps. Total pop across catchments ≈ national pop.",
        "Median 5 km-equivalent catchment for Tanzania: ~4,780 people.",
        "Clipped to country boundary (simplified 500 m for GEOS safety).",
    ], size=11)

    # Bottom bar: implementation note
    add_rect(s, Inches(0.7), Inches(6.55), Inches(11.9), Inches(0.55),
             fill=PALE, no_line=True)
    add_text(s, Inches(0.9), Inches(6.62), Inches(11.5), Inches(0.4),
             "R implementation: sf::st_voronoi(st_union(sites_utm)) → clip to country → "
             "exactextractr::exact_extract(worldpop_100m, polygons, \"sum\").",
             font=CODE_FONT, size=10, color=INK, line_spacing=1.1)
    add_footer(s, page, total)


def slide_travel_time(total, page):
    s = new_slide()
    add_header(s, "Modelled travel-time bands, not straight-line distance",
               eyebrow="Method — Feature 2",
               subtitle="Every 100 m pixel gets a minutes-to-nearest-facility estimate; then bucketed into 4 bands")

    # Left column: pipeline
    add_text(s, Inches(0.7), Inches(2.4), Inches(6.0), Inches(0.4),
             "PIPELINE (R)", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    add_code_block(s, Inches(0.7), Inches(2.8), Inches(6.0), Inches(3.6),
                   "# scripts/population/tanzania/11_travel_time_bands.R\n"
                   "\n"
                   "tt  <- rast('travel_time_100m.tif')\n"
                   "pop <- rast('worldpop_2026_100m.tif')\n"
                   "\n"
                   "# Aggregate to 300 m for memory safety on 8 GB laptops\n"
                   "pop <- aggregate(pop, fact = 3, fun = 'sum')\n"
                   "tt  <- aggregate(tt,  fact = 3, fun = 'mean')\n"
                   "tt  <- project(tt, pop, method = 'bilinear')\n"
                   "\n"
                   "# 4 travel-time bands\n"
                   "bands <- classify(tt, rbind(\n"
                   "  c(-Inf, 30, 1),  c(30,  60, 2),\n"
                   "  c(60,  90, 3),   c(90, Inf, 4)\n"
                   "))\n"
                   "\n"
                   "# Sum pop per band and per district\n"
                   "zonal(pop, bands, fun = 'sum')\n"
                   "zonal(pop, dist_r, fun = 'sum')",
                   size=10)

    # Right column: bands + colour swatches
    band_x = Inches(7.2)
    band_w = Inches(5.4)
    add_text(s, band_x, Inches(2.4), band_w, Inches(0.4),
             "OUTPUT — 4 BANDS", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    bands = [
        (GREEN_1, "0 – 30 min",  "Immediate reach — usually urban / peri-urban."),
        (GREEN_2, "30 – 60 min", "Practical reach on foot or by shared transport."),
        (ORANGE,  "60 – 90 min", "Marginal — realistic only with vehicle access."),
        (RED,     ">90 min",     "Effectively unreached in a single-day journey."),
    ]
    row_y = Inches(2.85)
    for i, (color, label, sub) in enumerate(bands):
        y = row_y + Inches(0.85) * i
        add_rect(s, band_x, y, Inches(0.6), Inches(0.6), fill=color,
                 no_line=True)
        add_text(s, band_x + Inches(0.8), y + Inches(0.02), band_w - Inches(0.9),
                 Inches(0.35), label, font=TITLE_FONT, size=14, bold=True,
                 color=NAVY, line_spacing=1.0)
        add_text(s, band_x + Inches(0.8), y + Inches(0.36), band_w - Inches(0.9),
                 Inches(0.4), sub, size=11, color=INK, line_spacing=1.2)
    add_footer(s, page, total)


def slide_tz_pipeline(total, page):
    s = new_slide()
    add_header(s, "Tanzania flagship — 4 R scripts, ~30 min end-to-end",
               eyebrow="Case study — the pipeline",
               subtitle="Reproducible: raw inputs are gitignored; each script writes a portal-ready output")

    add_code_block(s, Inches(0.7), Inches(2.4), Inches(12), Inches(3.9),
                   "scripts/population/tanzania/\n"
                   "├─ 10_wdpa_mask.R          Filters WDPA to strict IUCN categories (Ia, Ib, II, III)\n"
                   "│                           for optional map overlay context.\n"
                   "│\n"
                   "├─ 11_travel_time_bands.R  Aligns 100 m modelled travel-time surface to 100 m\n"
                   "│                           constrained WorldPop 2026, classifies into 4 bands,\n"
                   "│                           produces national + per-district population rollups.\n"
                   "│\n"
                   "├─ 12_voronoi_catchments.R Voronoi polygons per facility, clipped to country border,\n"
                   "│                           WorldPop summed inside each polygon.\n"
                   "│\n"
                   "└─ 13_simplify_bands.R     Post-processes 50 MB polygonised bands GeoJSON down to\n"
                   "                            ~10 MB (1 km simplification tolerance).",
                   size=10)
    add_bullets(s, Inches(0.7), Inches(6.35), Inches(12), Inches(0.7), [
        "Windows R memory notes baked in: OpenBLAS thread cap, GDAL cache bump, terraOptions(todisk=TRUE), aggressive gc()."
    ], size=11)
    add_footer(s, page, total)


def slide_tz_numbers(total, page):
    s = new_slide()
    add_header(s, "Tanzania: 4.74 M people beyond 90 min of the nearest facility",
               eyebrow="Case study — the numbers",
               subtitle="These are the numbers a health minister actually acts on")

    # Top row: 4 headline metrics
    tile_y = Inches(2.4)
    tile_h = Inches(1.35)
    tile_w = Inches(2.85)
    gap = Inches(0.2)
    start_x = (SLIDE_W - 4 * tile_w - 3 * gap) / 2
    tiles = [
        ("82.4 %", "0 – 30 min\n(57.6 M people)",   GREEN_1),
        ("7.6 %",  "30 – 60 min\n(5.31 M)",          GREEN_2),
        ("3.2 %",  "60 – 90 min\n(2.25 M)",          ORANGE),
        ("6.8 %",  ">90 min\n(4.74 M)",              RED),
    ]
    for i, (v, l, c) in enumerate(tiles):
        x = start_x + i * (tile_w + gap)
        add_rect(s, x, tile_y, tile_w, tile_h, fill=WHITE,
                 line_color=LIGHT_GREY, line_weight=0.75)
        add_rect(s, x, tile_y, tile_w, Inches(0.06), fill=c, no_line=True)
        add_text(s, x, tile_y + Inches(0.2), tile_w, Inches(0.6),
                 v, font=TITLE_FONT, size=28, bold=True, color=c,
                 align=PP_ALIGN.CENTER, line_spacing=1.0)
        add_text(s, x, tile_y + Inches(0.85), tile_w, Inches(0.5),
                 l, size=11, color=INK, align=PP_ALIGN.CENTER,
                 line_spacing=1.25)

    # Worst-served districts table
    tbl_y = Inches(4.15)
    add_text(s, Inches(0.7), tbl_y, Inches(12), Inches(0.4),
             "WORST-SERVED DISTRICTS BY POPULATION > 60 MIN",
             size=11, bold=True, color=TEAL, line_spacing=1.0)
    tbl_top = tbl_y + Inches(0.45)
    row_h = Inches(0.36)
    cols_x = [Inches(0.7), Inches(3.3), Inches(6.0), Inches(8.7), Inches(11.0)]
    add_rect(s, Inches(0.7), tbl_top, Inches(11.9), row_h, fill=NAVY,
             no_line=True)
    headers = ["District", "Total pop", "Pop >60 min", "% >60 min", "Rank"]
    for i, h in enumerate(headers):
        add_text(s, cols_x[i], tbl_top + Inches(0.05), Inches(2.5), row_h,
                 h.upper(), size=10, bold=True, color=WHITE,
                 line_spacing=1.0)
    rows = [
        ("Kaliua",  "863,781",  "474,216", "54.9 %", "1"),
        ("Ikungi",  "488,587",  "189,254", "38.7 %", "2"),
        ("Chunya",  "467,850",  "175,547", "37.5 %", "3"),
        ("Nkasi",   "510,660",  "165,782", "32.5 %", "4"),
        ("Uyui",    "639,989",  "164,534", "25.7 %", "5"),
    ]
    for i, row in enumerate(rows):
        y = tbl_top + row_h * (i + 1)
        if i % 2 == 0:
            add_rect(s, Inches(0.7), y, Inches(11.9), row_h, fill=PALE,
                     no_line=True)
        for j, cell in enumerate(row):
            color = AMBER if j == 2 else INK
            bold  = (j == 2)
            add_text(s, cols_x[j], y + Inches(0.05), Inches(2.5), row_h,
                     cell, size=11, color=color, bold=bold, line_spacing=1.0)
    add_footer(s, page, total)


def slide_deployment(total, page):
    s = new_slide()
    add_header(s, "GitHub Pages, no build server",
               eyebrow="Deployment",
               subtitle="One command to render locally, one to publish — no CI/CD complexity")

    add_text(s, Inches(0.7), Inches(2.4), Inches(6.0), Inches(0.4),
             "DEPLOY WORKFLOW", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    add_code_block(s, Inches(0.7), Inches(2.8), Inches(6.0), Inches(3.4),
                   "# 1. Edit source in healthscope-portal/\n"
                   "vim population-access.qmd\n"
                   "\n"
                   "# 2. Render (Windows-safe wrapper — see below)\n"
                   ".\\render.ps1              # whole site\n"
                   ".\\render.ps1 index.qmd    # single page\n"
                   "\n"
                   "# 3. Push docs/ + source to GitHub\n"
                   "git add -A\n"
                   "git commit -m \"feature X\"\n"
                   "git push origin main\n"
                   "\n"
                   "# 4. GitHub Pages redeploys from docs/\n"
                   "#    within 1-3 min. No server hop.",
                   size=10)

    add_text(s, Inches(7.0), Inches(2.4), Inches(5.6), Inches(0.4),
             "GOTCHAS WORTH KNOWING",
             size=11, bold=True, color=TEAL, line_spacing=1.0)
    add_bullets(s, Inches(7.0), Inches(2.8), Inches(5.6), Inches(3.4), [
        "Windows: quarto.cmd breaks on paths with spaces. render.ps1 uses the 8.3 short path.",
        "docs/ is committed alongside source (no CI). Simpler; requires one extra step per push.",
        "GitHub Pages CDN caches aggressively — hard-refresh after every publish.",
        "SCSS parse warning is cosmetic; rendering succeeds despite exit code 1.",
    ], size=12)
    add_footer(s, page, total)


def slide_chatbot(total, page):
    s = new_slide()
    add_header(s, "Mapy — a scoped chat assistant, not a data oracle",
               eyebrow="Assistance layer",
               subtitle="Botpress webchat v5 embed with a system prompt that refuses out-of-scope questions")

    add_bullets(s, Inches(0.7), Inches(2.4), Inches(6.5), Inches(3.5), [
        "Scope: portal navigation + Malaria Atlas Project context. That's it.",
        "Explicitly declines: specific data lookups (\"how many facilities in Kaliua?\"), "
        "methodology explanations, medical advice.",
        "Knowledge base seeded from the portal's sitemap.xml (auto-crawled by Botpress) "
        "and the public MAP institutional pages.",
        "Single _chatbot-embed.html include registered via _quarto.yml → include-after-body.",
        "Bot config lives at bpcontent.cloud; dashboard changes propagate to the portal without a redeploy.",
    ], size=13)

    # Right column: the system prompt snippet
    add_text(s, Inches(7.5), Inches(2.4), Inches(5.2), Inches(0.4),
             "SYSTEM PROMPT (EXCERPT)",
             size=11, bold=True, color=TEAL, line_spacing=1.0)
    add_code_block(s, Inches(7.5), Inches(2.8), Inches(5.2), Inches(3.8),
                   "You are HealthScope Assistant —\n"
                   "a navigation helper for the\n"
                   "HealthScope portal, produced by\n"
                   "the Malaria Atlas Project.\n"
                   "\n"
                   "Your job is limited to two things:\n"
                   " 1. Portal navigation.\n"
                   " 2. MAP project context.\n"
                   "\n"
                   "Decline politely and redirect for:\n"
                   " - Specific data questions.\n"
                   " - Methodological details.\n"
                   " - Medical advice.\n"
                   "\n"
                   "Never invent facility counts or\n"
                   "district statistics.",
                   size=10)
    add_footer(s, page, total)


def slide_roadmap(total, page):
    s = new_slide()
    add_header(s, "Tanzania flagship shipped; seven more to scale",
               eyebrow="Where we are",
               subtitle="What's on disk, what's blocking, what unlocks it")

    # Two columns: shipped vs coming
    y = Inches(2.4)
    col_h = Inches(4.5)
    col_w = Inches(5.9)

    # Shipped
    add_rect(s, Inches(0.7), y, col_w, col_h, fill=WHITE,
             line_color=GREEN_1, line_weight=1.25)
    add_rect(s, Inches(0.7), y, Inches(0.08), col_h, fill=GREEN_1,
             no_line=True)
    add_text(s, Inches(0.95), y + Inches(0.15), col_w - Inches(0.3),
             Inches(0.4), "SHIPPED",
             size=11, bold=True, color=GREEN_1, line_spacing=1.0)
    add_text(s, Inches(0.95), y + Inches(0.55), col_w - Inches(0.3),
             Inches(0.5), "Live on map-data-engineering.github.io",
             font=TITLE_FONT, size=15, bold=True, color=NAVY,
             line_spacing=1.1)
    add_bullets(s, Inches(0.95), y + Inches(1.2), col_w - Inches(0.3),
                Inches(3.2), [
        "Registry Explorer across all 8 countries.",
        "Service Intelligence + Find Facility (client-side ORS routing).",
        "Population & Access — Tanzania flagship: Voronoi + travel-time + district ranking.",
        "Data Sources page with per-country MoH portal links.",
        "Botpress chatbot embedded on every page.",
    ], size=12)

    # Coming
    x2 = Inches(6.8)
    add_rect(s, x2, y, col_w, col_h, fill=WHITE, line_color=AMBER,
             line_weight=1.25)
    add_rect(s, x2, y, Inches(0.08), col_h, fill=AMBER, no_line=True)
    add_text(s, x2 + Inches(0.25), y + Inches(0.15), col_w - Inches(0.3),
             Inches(0.4), "NEXT",
             size=11, bold=True, color=AMBER, line_spacing=1.0)
    add_text(s, x2 + Inches(0.25), y + Inches(0.55), col_w - Inches(0.3),
             Inches(0.5), "Blocking dependencies + follow-ups",
             font=TITLE_FONT, size=15, bold=True, color=NAVY,
             line_spacing=1.1)
    add_bullets(s, x2 + Inches(0.25), y + Inches(1.2), col_w - Inches(0.3),
                Inches(3.2), [
        "Travel-time surface per remaining country (7 countries, ~4 weeks of pipeline work each).",
        "Constrained WorldPop 100 m per remaining country.",
        "Cloudflare Worker proxy for the ORS key (currently in gitignored client JS).",
        "Automated rerun of the R pipeline via GitHub Actions on data updates.",
        "Underserved-zones layer (sub-obj 4) — needs steps 1 and 2 for all countries first.",
    ], size=12)
    add_footer(s, page, total)


def slide_team(total, page):
    s = new_slide()
    add_header(s, "Team, sources, and how to get in touch",
               eyebrow="Acknowledgments")

    # Team
    add_text(s, Inches(0.7), Inches(2.4), Inches(5.5), Inches(0.4),
             "TEAM", size=11, bold=True, color=TEAL, line_spacing=1.0)
    add_text(s, Inches(0.7), Inches(2.8), Inches(5.5), Inches(1.3),
             "Malaria Atlas Project — Dar es Salaam Node\n"
             "Data engineering, GIS, epidemiology, and portal build.",
             size=13, color=INK, line_spacing=1.55)

    # Data sources
    add_text(s, Inches(0.7), Inches(4.3), Inches(5.5), Inches(0.4),
             "PRIMARY DATA SOURCES",
             size=11, bold=True, color=TEAL, line_spacing=1.0)
    add_bullets(s, Inches(0.7), Inches(4.7), Inches(5.5), Inches(2.3), [
        "MoH facility registries (per country — see the Data Sources page).",
        "WorldPop 2020 (1 km, unconstrained) + 2026 (100 m, constrained).",
        "OpenStreetMap + GeoFabrik extracts for road networks.",
        "WDPA (UNEP-WCMC & IUCN, May 2026) for protected-area masks.",
    ], size=12)

    # Right column: links
    add_text(s, Inches(7.0), Inches(2.4), Inches(5.6), Inches(0.4),
             "GET INVOLVED", size=11, bold=True, color=TEAL,
             line_spacing=1.0)
    add_text(s, Inches(7.0), Inches(2.85), Inches(5.6), Inches(3.5),
             "Live portal\n"
             "map-data-engineering.github.io/healthscope-portal\n"
             "\n"
             "Source (portal)\n"
             "github.com/map-data-engineering/healthscope-portal\n"
             "\n"
             "Source (ETL)\n"
             "github.com/map-data-engineering/health_facility_etl\n"
             "\n"
             "Malaria Atlas Project\n"
             "map.ox.ac.uk",
             size=12, color=INK, line_spacing=1.55)
    add_footer(s, page, total)


# ─── assemble the deck ─────────────────────────────────────────────────────
BUILDERS = [
    slide_title,          # 1
    slide_problem,        # 2
    slide_what_we_built,  # 3
    slide_repo_topology,  # 4
    slide_etl,            # 5
    slide_schema,         # 6
    slide_frontend,       # 7
    slide_registry,       # 8
    slide_voronoi,        # 9
    slide_travel_time,    # 10
    slide_tz_pipeline,    # 11
    slide_tz_numbers,     # 12
    slide_deployment,     # 13
    slide_chatbot,        # 14
    slide_roadmap,        # 15
    slide_team,           # 16
]
TOTAL = len(BUILDERS)

# Title slide takes no page number; the rest do.
BUILDERS[0](TOTAL)
for i, builder in enumerate(BUILDERS[1:], start=2):
    builder(TOTAL, i)

OUT = Path("HealthScope_Technical_Deck.pptx")
prs.save(OUT)
print(f"Wrote {OUT.resolve()}  ({TOTAL} slides)")
