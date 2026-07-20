# Architecture

## User Interface

Odysseus provides the project workspace, file uploads, preview interface, and AI conversation.

## AI Orchestration

Claude interprets uploaded files, identifies drawing content, requests missing scale information, and coordinates processing tools.

## Document Processing Engine

The processing engine extracts raster and vector information from PDFs and images.

It detects:

* Lines
* Polylines
* Arcs
* Circles
* Text
* Dimensions
* Walls
* Doors
* Windows
* Rooms
* Common drawing symbols

## Geometry Engine

The geometry engine converts detected features into precise CAD coordinates and cleans up imperfect results.

## AutoCAD Connection

A custom AutoCAD plugin receives validated geometry and creates editable drawing objects.

## Export

The system will initially support DXF export, followed by direct AutoCAD integration and DWG workflows.
