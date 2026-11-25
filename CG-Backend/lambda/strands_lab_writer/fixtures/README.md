# Golden lab few-shot fixture (THOR audit item 9)

## Purpose

A **single curated lab slice** is injected into the live compact lab-writer prompt as a
structure and quality reference. Token cost is kept small (one excerpt, not a full course).

## LPI-010 status

The audit names **LPI-010 (Linux Essentials)** as the target golden course (rated 9/10).
**This repository does not contain production LPI-010 lab exports.** The file
`golden_lab_lpi010_slice.md` is a **stand-in**: it follows the same Spanish section
headings and step layout as high-scoring technical labs in this codebase (e.g. Linux CLI
practice), aligned with THOR structural rules.

**Replace `golden_lab_lpi010_slice.md` with a redacted slice from the accepted LPI-010
course** when that content is checked in or available from the owner's artifact store.
Keep the slice short (metadata + one or two fully detailed steps).

## Do not

- Fine-tune models on this file.
- Expand into a full multi-lab few-shot set without a product decision (audit: keep cost low).