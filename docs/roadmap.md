# Roadmap

## Phase 1 — Project Foundation

* Repository structure
* Development environment
* File upload workflow
* Sample drawing library

## Phase 2 — Basic 2D Extraction

* Import PDF and image files
* Detect page size and scale
* Extract vector PDF linework
* Detect raster lines
* Export basic DXF files

## Phase 3 — Geometry Cleanup

* Merge broken lines
* Remove duplicate geometry
* Snap nearby endpoints
* Detect parallel and perpendicular lines
* Detect arcs and circles
* Correct distorted photo perspective

## Phase 4 — Drawing Recognition

* Recognize walls
* Recognize doors and windows
* Recognize rooms
* Read text and dimensions
* Detect common architectural symbols

## Phase 5 — Review Interface

* Overlay detected geometry on the source file
* Select and edit detected objects
* Accept or reject generated geometry
* Show confidence levels
* Calibrate drawing scale manually

## Phase 6 — AutoCAD Integration

* Build AutoCAD .NET plugin
* Send geometry to the active drawing
* Read selected AutoCAD objects
* Update generated geometry
* Undo an AI-generated operation

## Phase 7 — Advanced 2D Workflows

* Layer assignment
* Block recognition
* Dimension reconstruction
* Title block recognition
* Multi-sheet project handling

## Phase 8 — 3D Reconstruction

* Detect levels and elevations
* Extrude walls
* Create doors and windows
* Generate basic 3D building geometry
* Export to AutoCAD or Revit-compatible formats
