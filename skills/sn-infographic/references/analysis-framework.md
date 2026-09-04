# Infographic Content Analysis Framework

Deep analysis framework applying instructional design principles to infographic creation.

## Purpose

Before creating an infographic, thoroughly analyze the source material to:

- Understand the content at a deep level
- Identify clear learning objectives for the viewer
- Structure information for maximum clarity and retention
- Match content to optimal layout×style combinations
- Preserve all supplied facts without inventing new claims

## Instructional Design Mindset

Approach content analysis as a **world-class instructional designer**:

| Principle | Application |
|-----------|-------------|
| **Deep Understanding** | Read the entire document before analyzing any part |
| **Learner-Centered** | Focus on what the viewer needs to understand |
| **Visual Storytelling** | Use visuals to communicate, not just decorate |
| **Cognitive Load** | Simplify complex ideas without losing accuracy |
| **Data Integrity** | Keep numbers, dates, proper nouns, quotations, and claims traceable to the source; condense only explanatory prose |

## Analysis Dimensions

### 1. Content Type Classification

| Type | Characteristics | Best Layout | Best Style |
|------|-----------------|-------------|------------|
| **Timeline/History** | Sequential events, dates, progression | linear-progression | aged-academia, craft-handmade |
| **Process/Tutorial** | Step-by-step instructions, how-to | linear-progression, winding-roadmap | ikea-manual, technical-schematic |
| **Comparison** | A vs B, pros/cons, before-after | binary-comparison, comparison-matrix | corporate-memphis, swiss-style |
| **Hierarchy** | Levels, priorities, pyramids | hierarchical-layers, tree-branching | corporate-memphis, technical-schematic |
| **Relationships** | Connections, overlaps, influences | venn-diagram, hub-spoke | corporate-memphis, data-visualization |
| **Data/Metrics** | Statistics, KPIs, measurements | dashboard, periodic-table | data-visualization, technical-schematic |
| **Cycle/Loop** | Recurring processes, feedback loops | circular-flow, s-curve | technical-schematic, corporate-memphis |
| **System/Structure** | Components, architecture, anatomy | structural-breakdown, isometric-tech-stack | technical-schematic, ikea-manual |
| **Journey/Narrative** | Stories, user flows, milestones | winding-roadmap, story-mountain | storybook-watercolor, comic-strip |
| **Overview/Summary** | Multiple topics, feature highlights | bento-grid, periodic-table | chalkboard, corporate-memphis |
| **Problem/Solution** | Root cause, fix, before-after resolution | bridge, iceberg | corporate-memphis, swiss-style |
| **Categories/Collection** | Grouped items, taxonomy, catalog entries | periodic-table, tile-layout | corporate-memphis, flat-design |
| **Spatial/Geographic** | Maps, regions, location-based data | isometric-map, isometric-tech-stack | technical-schematic, data-visualization |
| **Cross-functional/Workflow** | Multi-team processes, handoffs, lanes | swimlane, linear-progression | corporate-memphis, technical-schematic |
| **Feature List/Catalog** | Product features, spec sheets, repeated units | modular-repetition, bento-grid | tech-brand, material-design |
| **Single Concept Spotlight** | One idea, deep dive, hero message | single-focal-point, big-typography | minimalism, luxury-minimal |
| **Dialogue/Q&A** | FAQ, interview, conversation format | speech-bubbles, character-guide | paper-collage, cartoon-flat |
| **Discovery/Exploration** | Hidden layers, reveal, non-linear browsing | hidden-details, nonlinear-path | impressionism, pen-sketch |
| **Network/Multi-center** | Distributed nodes, peer relationships | multi-focal, hub-spoke | data-visualization, technical-schematic |
| **Report/Long-form** | Structured document, sections, executive summary | chapter-layout, f-pattern | swiss-style, corporate-memphis |
| **Marketing/CTA** | Persuasion, call-to-action, brand message | z-pattern, tile-layout | tech-brand, corporate-memphis |

### 2. Learning Objective Identification

Every infographic should have 1-3 clear learning objectives.

**Good Learning Objectives**:

- Specific and measurable
- Focus on what the viewer will understand, not just see
- Written from the viewer's perspective

**Format**: "After viewing this infographic, the viewer will understand..."

| Content Aspect | Objective Type |
|----------------|----------------|
| Core concept | "...what [topic] is and why it matters" |
| Process | "...how to [accomplish something]" |
| Comparison | "...the key differences between [A] and [B]" |
| Relationships | "...how [elements] connect to each other" |
| Data | "...the significance of [key statistics]" |

### 3. Audience Analysis

| Factor | Questions | Impact |
|--------|-----------|--------|
| **Knowledge Level** | What do they already know? | Determines complexity depth |
| **Context** | Why are they viewing this? | Determines emphasis points |
| **Expectations** | What do they hope to learn? | Determines success criteria |
| **Visual Preferences** | Professional, playful, technical? | Influences style choice |

### 4. Complexity Assessment

| Level | Indicators | Layout Recommendation |
|-------|------------|----------------------|
| **Simple** (3-5 points) | Few main concepts, clear relationships | sparse layouts, single focus |
| **Moderate** (6-8 points) | Multiple concepts, some relationships | balanced layouts, clear sections |
| **Complex** (9+ points) | Many concepts, intricate relationships | structured layouts, multiple sections; use one dominant reading flow when exact CJK text is dense |

### 4.1 Exact Text Density Assessment

Build a required-text inventory before selecting the final layout. A required text unit is each exact field that must be rendered in a distinct semantic role, even when related fields may later share one visual row. Give every unit a stable descriptive ID such as `spring.lichun.name`, `spring.lichun.date`, or `spring.lichun.tip`.

Record:

- `required_text_unit_count`: number of exact required fields;
- `cjk_character_count`: number of Unicode characters named `CJK UNIFIED IDEOGRAPH-*` or `CJK COMPATIBILITY IDEOGRAPH-*` across those fields;
- `text_density_risk`: the risk returned by `scripts/infographic_policy.py`.

Do not estimate these values manually. `scripts/infographic_policy.py` is the single source of truth for counting and threshold boundaries. Its result is a rendering-risk heuristic, not a guarantee. High-risk CJK content requires the single-reading-flow rules in `prompt-writing-rules.md` and character-level review after every round.

### 5. Visual Opportunity Mapping

Identify what can be shown rather than told:

| Content Element | Visual Treatment |
|-----------------|------------------|
| Numbers/Statistics | Large, highlighted numerals |
| Comparisons | Side-by-side, split screen |
| Processes | Arrows, numbered steps, flow |
| Hierarchies | Pyramids, layers, size differences |
| Relationships | Lines, connections, overlapping shapes |
| Categories | Color coding, grouping, sections |
| Timelines | Horizontal/vertical progression |
| Quotes | Callout boxes, quotation marks |

### 6. Data Verbatim Extraction

**Critical**: Preserve the meaning of every supplied fact. Copy numbers, dates, proper nouns, quotations, and contact-like strings exactly; explanatory prose may be condensed without changing its claims.

| Data Type | Handling Rule |
|-----------|---------------|
| **Statistics** | Copy exactly: "73%" not "about 70%" |
| **Quotes** | Copy word-for-word with attribution |
| **Names** | Preserve exact spelling |
| **Dates** | Keep original format |
| **Technical Terms** | Do not simplify or substitute |
| **Lists** | Preserve order when it carries meaning; wording may be shortened without changing the claims |

**Never**:

- Round numbers
- Paraphrase quotes
- Change the meaning of a supplied claim
- Add implied information
- Remove context that affects meaning

## Output Format

Analysis results (`analysis.json`) must be in the following format:

```json
{
  "title": "[Main topic title]",
  "topic": "[educational/technical/business/creative/etc.]",
  "data_type": "[timeline/hierarchy/comparison/process/etc.]",
  "complexity": "[simple/moderate/complex]",
  "point_count": "[number of main points]",
  "source_language": "[detected language]",
  "user_language": "[user's language]",
  "main_topic": "[1-2 sentence summary of what this content is about]",
  "learning_objectives": [
    "[Primary objective]",
    "[Secondary objective]",
    "[Tertiary objective if applicable]"
  ],
  "target_audience": {
    "knowledge_level": "[Beginner/Intermediate/Expert]",
    "context": "[Why they're viewing this]",
    "expectations": "[What they hope to learn]"
  },
  "content_type_analysis": {
    "data_structure": "[How information relates to itself]",
    "key_relationships": "[What connects to what]",
    "visual_opportunities": "[What can be shown rather than told]"
  },
  "key_data_points_verbatim": [
    "[Exact data point 1]",
    "[Exact data point 2]",
    "[Exact quote with attribution]"
  ],
  "required_text_inventory": [
    {"id": "section.item.field", "text": "[Exact required text]", "role": "[title/date/label/body/etc.]"}
  ],
  "required_text_unit_count": 0,
  "cjk_character_count": 0,
  "text_density_risk": "normal",
  "layout_style_signals": [
    {
      "signal": "content_type",
      "input": "[type]",
      "suggests": "[layout]"
    },
    {
      "signal": "tone",
      "input": "[tone]",
      "suggests": "[style]"
    },
    {
      "signal": "audience",
      "input": "[audience]",
      "suggests": "[style]"
    },
    {
      "signal": "complexity",
      "input": "[level]",
      "suggests": "[layout density]"
    }
  ],
  "design_instructions": "[Any style, color, layout, or visual preferences extracted from user's steering prompt]",
  "recommended_combinations": [
    {
      "role": "recommended",
      "label": "[User-language direction name]",
      "layout": "[Layout]",
      "style": "[Style]",
      "recommended": true,
      "rationale": "[Brief rationale]",
      "tradeoff": "[Concrete tradeoff]"
    },
    {
      "role": "clarity-first",
      "label": "[User-language direction name]",
      "layout": "[Layout]",
      "style": "[Style]",
      "recommended": false,
      "rationale": "[Brief rationale]",
      "tradeoff": "[Concrete tradeoff]"
    },
    {
      "role": "expressive",
      "label": "[User-language direction name]",
      "layout": "[Layout]",
      "style": "[Style]",
      "recommended": false,
      "rationale": "[Brief rationale]",
      "tradeoff": "[Concrete tradeoff]"
    }
  ],
  "selection": {
    "mode": "confirm",
    "status": "pending",
    "source": null,
    "layout": null,
    "style": null
  }
}
```

## Analysis Checklist

Before proceeding to structured content generation:

- [ ] Have I read the entire source document?
- [ ] Can I summarize the main topic in 1-2 sentences?
- [ ] Have I identified 1-3 clear learning objectives?
- [ ] Do I understand the target audience?
- [ ] Have I classified the content type correctly?
- [ ] Have I extracted all data points verbatim?
- [ ] Have I assigned stable IDs to all required text and measured CJK density?
- [ ] Have I identified visual opportunities?
- [ ] Have I extracted design instructions from user input?
- [ ] Have I recommended 3 viable, meaningfully distinct layout×style combinations with a rationale and tradeoff for each?
- [ ] If selection is still pending, have I stopped before prompt assembly and image generation?
