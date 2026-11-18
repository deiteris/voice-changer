---
name: Voice Changer
description: An artwork-led workspace for real-time voice conversion.
colors:
  accent: "#63469e"
  accent-dark: "#c3a8f2"
  on-accent: "#ffffff"
  on-accent-dark: "#241935"
  ink: "#24232b"
  ink-dark: "#f3effa"
  muted: "#615e6b"
  muted-dark: "#bcb4c8"
  page: "#faf9fc"
  page-dark: "#19171f"
  paper: "#ffffff"
  paper-dark: "#22202a"
  line: "#e6e2eb"
  line-dark: "#40394a"
  tint: "#f0ebfa"
  tint-dark: "#30283f"
  live: "#276849"
  live-dark: "#8fdbb3"
  warning: "#865516"
  warning-dark: "#f0c380"
  error: "#a72e43"
  error-dark: "#ff9eae"
typography:
  display:
    fontFamily: "Poppins, Segoe UI, sans-serif"
    fontSize: "clamp(2.35rem, 5.1vw, 4.65rem)"
    fontWeight: 600
    lineHeight: 1.04
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Poppins, Segoe UI, sans-serif"
    fontSize: "clamp(1.2rem, 2vw, 1.56rem)"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Poppins, Segoe UI, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 600
    letterSpacing: "-0.03em"
  body:
    fontFamily: "Poppins, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    lineHeight: 1.55
  label:
    fontFamily: "Poppins, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  panel: "16px"
  card: "12px"
  field: "7px"
  pill: "999px"
spacing:
  panel: "clamp(16px, 2vw, 25px)"
  workspace: "24px"
  settings: "16px"
  model: "10px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 13px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
  button-utility:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 13px"
    height: "38px"
  button-selected:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.accent}"
  model-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
  model-card-selected:
    backgroundColor: "{colors.tint}"
  session-panel:
    backgroundColor: "{colors.tint}"
    rounded: "{rounded.panel}"
    padding: "{spacing.panel}"
  settings-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "3px 7px"
    height: "30px"
  workspace-dialog:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.panel}"
    width: "min(100%, 48rem)"
---

# Design System: Voice Changer

## Overview

**Creative North Star: "Voice workspace"**

The workspace uses model artwork as the first cue for choosing a voice. White panels frame the library and settings, while lilac groups the active conversion tools. In dark mode, charcoal and plum preserve the same hierarchy.

Poppins gives the display title and compact control labels a consistent voice. Fine borders group settings and a diffuse shadow separates dialogs from the workspace.

**Key Characteristics**

- Model artwork from installed voices
- A large centered title and compact utility header
- Pill actions, rounded panels, and explicit selection states

## Colors

### Primary

- Lilac surface tint groups live controls and marks pressed buttons and selected model cards.
- The stronger lilac accent marks links, keyboard focus, selection outlines, and the card check.

### Secondary

- Green marks active conversion and timings within budget. Amber marks timings near budget. Rose marks timings over budget.

### Neutral

- The pale workspace canvas sits behind white library, settings, and dialog surfaces. The dark scheme switches those surfaces to charcoal and the live region to plum.
- Charcoal ink leads the hierarchy, muted ink carries metadata, and fine dividers mark panel and row boundaries.

**The State Color Rule.** Use accent for selection and focus. Reserve green, amber, and rose for live state and timing feedback.

## Typography

Poppins is the workspace family, with Segoe UI and sans-serif fallbacks.

- Display uses a responsive, centered, balanced title at weight 600.
- Section headlines and the selected model name use weight 600 and tight tracking.
- Body copy follows a compact rhythm with relaxed leading. The centered intro description uses a maximum measure of 52ch.
- Controls and status labels use compact semibold type. Timing values use tabular figures.

## Layout

The main column caps at 1240px, with fluid side gutters and a 24px gap. At 850px the library and session sit in a 5:7 grid and the settings split into two equal columns. Below that threshold they stack. At 540px and below, the model grid uses three columns, the live controls move above the portrait, and model-dialog row actions wrap below the text.

## Elevation & Depth

Borders and surface tint establish depth in the workspace. The fixed dialog scrim dims the workspace and the outer frame has a diffuse shadow.

**The Tonal Panels Rule.** Keep library, session, and settings panels flat. Use the ambient shadow on the outer dialog frame.

## Shapes

Workspace panels and dialog frames use 16px corners. Model cards and the portrait surface use 12px corners. Text fields use 7px corners, actions are pill-shaped, and status and selection markers are round.

## Components

- **Actions.** The primary start button uses inverted ink and paper, with an accent hover. Utility pills use a paper fill and fine border. Pressed sort and transport options add the lilac fill. Keyboard focus uses a 2px accent outline offset by 3px.
- **Utility header.** A compact waveform mark and wordmark sit opposite version and action controls. At the narrow breakpoint the version is hidden and reset becomes icon-only with its accessible name.
- **Model cards.** The selection control uses a near-square cover crop, a truncated name, and muted model metadata. Active cards add a lilac ground, accent border, and circular check. Border and fill transitions honor reduced motion.
- **Live session.** The selected artwork is contained within a larger portrait. The live-status label pairs a colored dot with text. Timing readings sit in a two-column grid above the chart.
- **Fields and dialogs.** Native fields use paper, quiet borders, and the shared focus outline. Dialogs use a scrollable frame with a sticky title and rows divided by fine borders.

## Do's and Don'ts

- Do use the installed model artwork for the library thumbnail and selected portrait.
- Do pair the selected treatment with a visible check on model cards and an accessible pressed state.
- Do keep timing figures tabular as their values change.
- Don't crop the selected portrait with the library thumbnail treatment.
