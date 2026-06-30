"""brando — the public API. Re-exports every public rule/macro one place.

A brand loads from here:

    load("@brando//:defs.bzl",
         "brand_doc", "brand_resources", "brand_latex_class",
         "brand_skin", "brand_mdbook_theme",
         "brand_svgs", "brand_icons", "brand_iconcomposer",
         "brand_wordmark", "brand_office_pptx", "brand_office_docx")

The mark-authoring Python library is consumed as py_library deps, not loaded:
    @brando//marklib:marklib        # shapely CSG + layered-SVG/composite emission
    @brando//marklib:raster         # hermetic Pillow rasterization helpers
    @brando//marklib:iconcomposer   # Icon Composer .icon bundle emission
"""

# Tectonic docs: brand_doc rule + brand_resources rule + templated LaTeX class.
load(
    "//doc:defs.bzl",
    _BrandResourcesInfo = "BrandResourcesInfo",
    _brand_doc = "brand_doc",
    _brand_latex_class = "brand_latex_class",
    _brand_resources = "brand_resources",
)

# meridian-theme skin pipeline: textpb -> binpb (validated) + json.
load("//skins:defs.bzl", _brand_skin = "brand_skin")

# Templated mdBook theme overlay.
load("//mdbook:defs.bzl", _brand_mdbook_theme = "brand_mdbook_theme")

# Mark/icon/wordmark/office packaging macros.
load(
    "//wordmark:defs.bzl",
    _brand_icons = "brand_icons",
    _brand_iconcomposer = "brand_iconcomposer",
    _brand_office_docx = "brand_office_docx",
    _brand_office_pptx = "brand_office_pptx",
    _brand_svgs = "brand_svgs",
    _brand_wordmark = "brand_wordmark",
)

BrandResourcesInfo = _BrandResourcesInfo
brand_doc = _brand_doc
brand_resources = _brand_resources
brand_latex_class = _brand_latex_class
brand_skin = _brand_skin
brand_mdbook_theme = _brand_mdbook_theme
brand_svgs = _brand_svgs
brand_icons = _brand_icons
brand_iconcomposer = _brand_iconcomposer
brand_wordmark = _brand_wordmark
brand_office_pptx = _brand_office_pptx
brand_office_docx = _brand_office_docx
