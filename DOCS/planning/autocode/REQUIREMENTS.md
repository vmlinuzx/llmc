# REQUIREMENTS: Master Index

**SDD Source:** `DOCS/planning/SDD_Documentation_Architecture_2.0.md` → Phase 2.3
**Target Document:** `DOCS/index.md`
**Audience:** All users (New, Power Users, Operators, Contributors)

---

## Objective

Create the master entry point for the entire documentation suite, providing clear navigation paths for different user personas (learners, doers, operators, understanders) based on the Diátaxis framework.

---

## Acceptance Criteria

### AC-1: Header and Welcome
**Location:** Top of file
- Title: "LLMC Documentation"
- Tagline: "The Large Language Model Compressor" (or current project tagline)
- Brief, welcoming introduction.

### AC-2: "Start Here" Callout
**Location:** Prominent section (near top)
- Explicit link to `getting-started/index.md` for new users.
- Can be part of a "Quick Links" or standalone alert.

### AC-3: Main Sections (Diátaxis)
**Location:** Body
- **Getting Started** (Tutorials): Links to `getting-started/`
- **User Guide** (How-to): Links to `user-guide/`
- **Operations** (Ops): Links to `operations/`
- **Architecture** (Explanations): Links to `architecture/`
- **Reference** (Reference): Links to `reference/`
- **Development** (Contributors): Links to `development/`

*For each section:*
- Icon/Emoji (e.g., 🎓, 📖, 🔧, 🏗️, 📚, 👩‍💻)
- Brief description of what to find there.
- 3-5 key sub-links (e.g., Installation, Configuration, Daemon).

### AC-4: Planning Section
**Location:** Below main sections
- Link to `planning/`
- Description: "Roadmap, SDDs, and Project Management"

### AC-5: Version & External Links
**Location:** Footer
- Current version info (if available/static)
- Links to GitHub Repo, Issue Tracker, etc.

---

## Style Requirements

- **Voice:** Welcoming, professional, clear.
- **Structure:** Clean navigation, use of lists and tables for readability.
- **Terminology:** Use "LLMC" for the tool. Use Diátaxis terms (Tutorials, Guides, Reference, Explanation) where helpful to explain the section's purpose.

---

## Out of Scope

- ❌ Detailed content for sub-pages (just links).
- ❌ Generating the sub-pages themselves (unless they don't exist, but focus is index).

---

## Verification

B-Team must verify:
1. All 6 main sections + Planning are present.
2. Links point to the correct directories/files.
3. Formatting is clean (Markdown).
4. "Start Here" is obvious.

---

**END OF REQUIREMENTS**