# Grid Generator

![grid-thumb](https://github.com/user-attachments/assets/74ff5b33-9906-4cb9-b3fd-c498c394ac63)

**Author:** The French Monkey (TFMSTYLE)  
**Version:** 1.0.0  

---

## Overview

The Grid Generator is a procedural tool that builds a wide variety of 2D grid-based patterns directly in Blender.  
It supports multiple geometric layouts such as **Rectangular**, **Circular**, **Hexagonal**, and **Voronoi**, each with customizable density, scaling, and decorative layers.  
You can generate grids with multiple overlaid components such as **main lines**, **subgrids**, **dots**, **crosses**, **squares**, and **ticks**, all procedurally controlled from the sidebar panel.  

This tool is ideal for creating architectural diagrams, graphic layouts, terrain guides, or any structured pattern-based geometry.

---

## Parameters

### Live Update
Automatically regenerates the grid whenever a parameter changes.  
Useful for real-time adjustments; disable for better performance in large scenes.

---

### Shape
Defines the geometric layout of the grid.  
Available options:
- **Rectangular:** Classic row-and-column pattern.  
- **Circular:** Concentric rings with radial segments.  
- **Hexagonal:** Honeycomb-style hex tiling.  
- **Voronoi:** Organic, cell-like pattern based on Voronoi partitioning.

---

### Scale
Uniformly scales the entire grid.  
Affects all layers and placements proportionally.

---

## Rectangular Parameters

### Columns
Number of vertical divisions.

---

### Rows
Number of horizontal divisions.

---

### Step X
Spacing between columns along the X-axis.

---

### Step Y
Spacing between rows along the Y-axis.

---

## Circular Parameters

### Rings
Number of concentric circles forming the grid.

---

### Segments per Ring
Number of divisions per circular ring.

---

### Outer Radius
Radius of the outermost ring.

---

### Inner Radius
Radius of the innermost ring.  
Defines a hollow center region if greater than zero.

---

## Hexagonal Parameters

### Rings
Number of hexagonal rings radiating from the center.

---

### Hex Radius
Overall radius of the hexagonal grid.  
Affects both spacing and scale of cells.

---

## Voronoi Parameters

### Site Columns
Number of points generated horizontally to seed the Voronoi diagram.

---

### Site Rows
Number of points generated vertically.

---

### Relax Iterations
Number of Lloyd relaxation steps applied to smooth cell distribution.  
Higher values create more uniform patterns.

---

## Main Lines

### Main Lines
Enables or disables the primary structural grid lines.

---

### Main Thickness
Thickness of the main grid lines.

---

## Subgrid Lines

### Subgrid Lines
Adds finer lines between the main grid divisions.

---

### Subgrid Factor
Defines how many sub-steps are inserted between primary lines.

---

### Subgrid Thickness
Controls the line thickness for subgrid elements.

---

## Dots / Rings

### Dots / Rings
Adds circular elements placed according to the chosen placement mode.

---

### Outer Radius
Outer radius of each dot or ring.

---

### Inner Radius
Inner radius for hollow rings.  
Set to zero for solid discs.

---

### Segments
Number of segments used to build each circular shape.  
Higher values yield smoother edges.

---

### Dot Placement
Determines where dots or rings are positioned:
- **Intersections:** At grid crossing points.  
- **Centers:** At cell centers.  
- **Edge Midpoints:** At the middle of each edge.  
- **Random:** Randomly distributed within the grid bounds.

---

### Dot Density
Controls how densely dots are distributed across the grid.

---

### Dot Count (Random)
Number of random points used when Dot Placement is set to “Random.”

---

### Dot Spacing
Minimum allowed spacing between generated dots.  
Prevents overlap in dense distributions.

---

### Size Random %
Applies a random variation to the size of each dot or ring.

---

### Dot Seed
Random seed used for size and placement variation.

---

## Crosses

### Crosses
Adds plus-shaped cross markers throughout the grid.

---

### Cross Size
Overall size of each cross.

---

### Cross Thickness
Line thickness for each cross arm.

---

### Cross Placement
Determines where crosses are positioned (same modes as dots).

---

### Cross Density
Adjusts how many crosses are generated relative to the grid size.

---

### Cross Count (Random)
Number of randomly placed crosses when using Random placement mode.

---

### Cross Spacing
Minimum distance between each cross.

---

### Size Random %
Applies random scaling to each cross instance.

---

### Cross Seed
Random seed controlling size and placement variation.

---

## Squares

### Squares
Enables square elements distributed across the grid.

---

### Square Size
Overall size of the outer square.

---

### Inner Size
Defines the size of the inner square (for hollow squares).  
Set to zero for solid squares.

---

### Square Placement
Determines where squares are positioned (same modes as dots).

---

### Square Density
Controls how many squares are distributed within the grid.

---

### Square Count (Random)
Number of squares when placement is random.

---

### Square Spacing
Spacing between squares to avoid overlap.

---

### Size Random %
Adds random scaling to the square sizes.

---

### Square Seed
Random seed for size and position variation.

---

## Ticks

### Ticks
Adds short line markers along edges or grid intersections.

---

### Tick Length
Total length of each tick mark.

---

### Tick Thickness
Thickness of each tick line.

---

### Tick Angle (°)
Rotation of tick marks relative to the grid.

---

### Tick Spacing (Edge Path)
Spacing between tick marks when marching along edges.

---

### Tick Placement
Defines where ticks are generated:
- **Intersections**
- **Centers**
- **Edge Midpoints**
- **Random**
- **Edge Path** – even spacing along grid edges.

---

### Tick Density
Controls how many tick marks are distributed across the grid.

---

### Tick Count (Random)
Number of tick marks used in random placement mode.

---

### Tick Spacing (Points)
Minimum distance between point-based tick placements.

---

### Size Random %
Adds random variation to tick lengths.

---

### Tick Seed
Random seed controlling tick size and placement randomness.

---

## Operators

### Generate Grid
Creates or updates the grid mesh with the current parameters.

---

### Reset
Restores all parameters to default values.  
Preserves layer visibility toggles and live update state.

---

### Delete Grid
Deletes the selected grid object and all its generated layers.

---

## Usage Notes

- Select the **Shape** to define the grid base topology.  
- Enable **Main Lines** and **Subgrid Lines** for foundational structure.  
- Use **Dots**, **Crosses**, **Squares**, or **Ticks** for decorative or diagrammatic elements.  
- **Live Update** is convenient for iteration but may be heavy in dense grids.  
- Generated grids are composed of standard mesh objects parented to an Empty for easy organization.  
- Each generated layer can be edited, duplicated, or converted to geometry nodes for advanced use.
