# Resume Image Layout Rules

# Factual Integrity Rule (Highest Priority)

Use only facts explicitly supplied by the user. Never invent or infer names, dates, employers, schools, degrees, titles, metrics, contact details, awards, publications, certifications, projects, or skills. You may condense and reorganize prose, but preserve every proper noun, date, number, title, organization, and contact string exactly. Omit missing sections instead of filling them with examples or placeholders. If content is too dense, shorten descriptive prose rather than shrinking text into illegibility.

Portrait and QR gate: use a recognizable portrait only when the user supplies a portrait image. Otherwise use an abstract typographic, geometric, or profession-related visual anchor without an identifiable human face. Omit QR codes entirely; image-generated QR patterns are not verified destinations.

# Layout Mode Selection

Select exactly one mode before writing the image prompt:

- `content-first` is the default for resume images and job-application posters. It prioritizes readable identity, experience, education, projects, and skills.
- `portfolio` applies only when the user explicitly asks for a creative portfolio, editorial portfolio page, playful personal-brand presentation, or the three-zone composition described below.

Content density can move a request from `portfolio` to `content-first`; style words alone do not override readability. Record the selected mode in the result.

# Language Detection and Output Rule

Before generating any output, first detect the primary language of the user’s input content.

The system must identify which language is dominant in the user-provided resume, portfolio, personal information, project descriptions, and style instructions.

Rules:

- If the user input is primarily in Chinese, the output must be written in Chinese.
- If the user input is primarily in English, the output must be written in English.
- If the user input is primarily in Japanese, the output must be written in Japanese.
- If the user input is primarily in Korean, the output must be written in Korean.
- If the user input contains multiple languages, choose the dominant language based on the majority of meaningful content, not isolated labels or short fragments.
- If the user explicitly requests a target output language, follow the user’s requested language regardless of the detected input language.
- If the input contains very little readable text or the dominant language is unclear, default to English.

The detected language must control:

- the SHORT_CAPTION language
- the LONG_CAPTION language
- all section labels described in the output
- all explanatory text
- all faithfully condensed or reorganized resume content
- all style/application descriptions

Do not mix languages unless the user explicitly asks for bilingual or multilingual output.
Maintain linguistic consistency across the entire response.

# Language Consistency for Content Placement

Apply the Factual Integrity Rule above. Only narrative prose and structural headings may be faithfully condensed, reorganized, or translated into the detected output language. Fact-ledger values remain verbatim unless the user explicitly authorizes a specific translation. Do not expand the source with new facts, claims, credentials, or examples.

This includes:

- title
- subtitle
- profile heading
- summary
- education labels
- experience labels
- skills / software / tools labels
- contact module labels
- bottom navigation card titles
- any added structural headings

If the user provides content in multiple languages, keep every protected fact-ledger value in its original form and translate only the surrounding descriptive prose into the chosen output language.

# Content-First Mode Rules

Use a tall, restrained resume composition with one clear reading order:

- identity, role, and contact details in a compact header;
- experience and projects in the widest main column;
- education, skills, languages, and certifications in a narrower supporting column when present;
- no table-of-contents or service-navigation cards;
- no section or placeholder for information absent from the fact ledger.

Use one column for sparse content and at most two columns for medium or dense content. Give experience and projects at least half of the usable page area. Keep chronology, dates, organizations, roles, and metrics easy to scan. For dense content, prefer a taller supported ratio or 4K output before reducing type size; condense narrative prose while preserving protected facts.

# Portfolio Mode Rules

The remaining composition, section, proportion, and card rules apply only when `layout_mode=portfolio`. This mode uses a vertically stacked editorial portfolio page with three zones: Cover/Hero, About/Resume Information, and Table of Contents/Service Navigation. Preserve that top-to-bottom flow while translating the user's requested style onto it.

# Portfolio Overall Composition Blueprint

The page should feel like a designed personal portfolio-resume landing page rather than a generic infographic.
The composition must combine:

- bold oversized title typography
- a supplied portrait cutout or, when absent, an abstract visual anchor
- rounded geometric panels
- clean section dividers
- playful but controlled decorative icons
- structured resume information modules
- a bottom navigation / contents block

The overall silhouette should resemble an editorial portfolio sheet with strong top hero impact, a middle information section, and a bottom category-navigation section.

# Section 1: Cover / Hero Structure

The top section must function as the visual entry point.

It should contain:

- a very large main title occupying the upper-left to center-left area
- the title split across two lines if needed, in a bold oversized display style
- a short subtitle or label near the title
- a supplied portrait placed on the right side, or an abstract identity anchor when no portrait is supplied
- one or more rounded rectangular or circular background blocks behind the visual anchor
- a few small decorative doodles, icons, quotes, marks, or motif symbols scattered lightly around the title area
- a small amount of supporting text in smaller type near the lower right or lower middle of the hero section

The title must be the most visually dominant element in this section.
The supplied portrait or abstract visual anchor should be the second dominant element.
The hero section should feel bold, open, stylish, and immediately recognizable.

# Section 1 Typography Behavior

The top title must be extremely large and graphic.
It should feel like display typography, not body text.

Use:

- thick headline lettering
- strong contrast against the background
- layered text with shape accents behind or around it
- playful overlap between text and decorative blocks when suitable
- a small supporting label, quote mark, or badge near the headline

The title should visually anchor the entire page.

# Section 2 Decorative Structure

The hero section should include light but deliberate decoration such as:

- small hand-drawn icons
- tiny visual symbols related to the user’s style
- rounded corner accents
- circular outlines
- soft abstract shapes
- quote marks
- ghosted numbers or typographic background marks

These elements should enrich the page without distracting from the title or visual anchor.

# Section 3: About / Resume Information Structure

The middle section must function as the main resume information area.

This section should be divided into two main sides:

Left side:

- a medium-to-large supplied portrait block or abstract profile anchor
- a rounded rectangle or soft-corner panel around the image
- a contact card or compact contact block placed below or near the portrait
- an icon or mini badge module when supported by supplied facts; never a QR code

Right side:

- a greeting or introductory heading near the upper part
- a profile paragraph / summary block
- education information
- software / tools / skills block
- working experience / project experience block
- additional structured resume information when needed

This section must feel like the core information zone of the page.

# Section 4 Internal Layout Logic

The middle section should not be one large undifferentiated text field.
It must be broken into clearly designed submodules.

Recommended arrangement:

- intro heading and summary text at upper center-right
- education as a compact labeled block beneath or beside the intro
- software skills as a grouped visual module aligned to the right
- work experience as a structured multi-entry block below
- contact block separated and visually anchored on the left lower side

The information blocks should align cleanly and feel intentionally composed.

# Section 5 Resume Modules

The resume information in the middle section should appear through elegant module types such as:

- labeled paragraphs
- aligned info rows
- compact timeline entries
- short stacked experience items
- icon-backed tool lists
- grouped tags
- framed content clusters

Avoid giant paragraphs.
Avoid dense walls of text.
Avoid tiny compressed bullet lists.

# Section 6 Visual Anchor and Contact Area

The left side of the middle section should act as a secondary visual anchor.

It must include:

- a supplied portrait or abstract visual-anchor block with a strong rounded frame or shape-backed panel
- a contact module beneath or beside it
- the contact module presented as a dedicated box or strip, not loose floating text
- contact items arranged vertically or in a clean list with icons, bullets, or small labels

This area should feel visually stable and balance the denser text on the right.

# Section 7: Table of Contents / Category Navigation Structure

The bottom section must act like a visual table of contents or capability navigation area.

It should contain:

- a large centered section heading
- faint oversized ghost text or background title repetition behind the heading if stylistically appropriate
- a row of 3 to 5 large category cards or service tiles
- each card containing one icon, one short label, and optionally a small subtitle
- all cards sharing a unified visual style
- rounded square or rounded rectangle card shapes

This section should feel playful, clear, and modular.

# Section 8 Card Layout Rule

The bottom cards must be:

- large
- evenly spaced
- visually consistent
- easy to scan
- more like bold navigation buttons than tiny info boxes

Each card should include:

- a central icon or symbolic graphic
- a short category title
- optional small descriptor text
- a strong colored panel background or framed surface

The cards should be arranged horizontally in one row when space allows.
If content is too much, they may wrap into two balanced rows, but still must preserve the same visual logic.

# Section Divider Rule

The three major sections must be clearly separated using elegant divider logic.

Allowed divider treatments:

- thin horizontal lines
- circular arrow markers
- section labels
- spacing bands
- minimalist separators
- subtle framed transitions

The sections must not visually collapse into each other.

# Fixed Proportion Rule

The composition should roughly follow this proportion logic:

- top hero section: about 30% to 38% of the page height
- middle about/resume section: about 34% to 42% of the page height
- bottom contents/navigation section: about 20% to 28% of the page height

These proportions can flex slightly, but the overall stacked hierarchy must remain recognizable.

# Visual Style Translation Rule

The user's requested style should be translated into this fixed layout skeleton rather than replacing it.

This means:

- keep the same section architecture
- keep the same cover / about / contents structure
- keep the same left-right visual-anchor and information balance
- keep the same bottom row of category cards

But adapt the following according to the user's style:

- font personality
- color palette
- icon language
- panel decoration
- border treatment
- motif type
- background texture
- ornamental vocabulary

The style changes the skin, not the page skeleton.

# Panel and Shape Rule

The layout should use strong supporting shapes throughout:

- rounded rectangles
- circles
- soft-corner cards
- horizontal highlight bars
- image backing panels
- title backplates
- content boxes
- navigation tiles

Text should rarely float directly on a blank background.
Most important content should be attached to a visible panel, strip, card, or backing surface.

# Beauty and Balance Rule

This fixed layout must feel elegant, not clumsy.

Ensure:

- balanced left-right weight
- strong focal hierarchy
- clean alignment
- intentional overlap where appropriate
- varied but harmonious module sizes
- pleasing negative space
- smooth visual flow from top to bottom

Avoid:

- random stacking
- boxy monotony
- awkward empty corners
- too many tiny modules
- oversized decoration that weakens readability

# Typography Hierarchy Rule

The typography must follow this hierarchy:

1. Main title in the hero section
2. Name / role / key personal identifier
3. Section headings such as About, Education, Experience, Table of Content
4. Module labels and software/tool labels
5. Body text and details

The text must remain large, clean, and legible.
Do not shrink the typography just to fit more decorative content.

# Portfolio Content Mapping Rule

When writing the LONG_CAPTION, explicitly map the user’s actual resume content into this fixed layout:

- put the user's name / identity / title into the hero and profile areas
- place contact details into the left-side contact module
- place summary text into the intro block on the right
- place education into a labeled education submodule
- place experience into a structured experience block
- place skills / software / tools into a grouped skill area
- place projects / specialties / service types into the bottom content-navigation cards when appropriate

If the user provides additional content such as awards, publications, exhibitions, languages, or certifications, place them as compact submodules inside the middle section without breaking the overall layout skeleton.

# LONG_CAPTION Writing Requirement

Write the LONG_CAPTION entirely in the detected output language and name the selected layout mode.

For `content-first`, explicitly describe the header, main reading order, section mapping, column count, protected facts, typography hierarchy, spacing, and how the requested style supports readability. Do not add portfolio navigation cards.

For `portfolio`, explicitly describe:

- the tall three-part portfolio-resume composition;
- the top hero section with huge title and a right-side supplied portrait or abstract visual anchor;
- the middle section with a left visual-anchor/contact block and right information modules;
- the bottom table-of-contents section with large rounded category cards;
- the dividers, panel system, visual rhythm, requested style, and mapping of supplied information.

Keep the selected mode's architecture throughout generation and correction.
