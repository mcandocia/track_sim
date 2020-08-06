# Track Similarity

## Overview

This script will calculate the similarity of GPS-based tracks, using direction-agnostic similarity (for detecting congruent routes) as well as direction-based similarity (for detecting directionally-congruent routes and their reverses).

At this point, none of the similarity metrics differentiate between otherwise identical routes that start and end at different points, such as a circle starting at the east end going clockwise vs. a circle starting at the west end going clockwise.

Caveat: There may be a slight difference for the directional, though, based on how the angle is extrapolated at the end of a file's track data.

### Requirements

The only requirements for running this script are the following

* Numpy
* Pandas
* Python 3
* Properly formatted CSV files

Note that for large sets of data, you might need a decent bit of RAM, but that would be for thousands of 30+ minute tracks, or possibly differently-configured constants (explained below).

## How to run

### Input

The input should be CSV files with two columns (others can be present, but will be ignored):

* `position_long`
* `position_lat`

These should be float columns that can be positive or negative and have units of degrees.

I recommend having the file encoded in ASCII/UTF-8.

### Caveats

* Self-similarity is calculated and should always be 1

* Tracks outside of contiguous groups do not have their similarities calculated, as they would be 0 anyway. This may change in the future.

### Execution

Simply run

    python3 tracksim.py /some/directory/*.csv --output-filename=/an/output/file.csv

You can also add

    --add-directional-similarity

to include directional similarity, as well as

    --head [number]

to test the script out on a smaller number of files.

Other arguments:

* `--truncate-file-path` - Only use filename, not folder/full path, in the output file.

* `--map-filename` - A filename of a CSV with columns "filename" and "id" to map to output data.

* `--remove-filenames` - Remove filenames from output file. I only recommend this if you have `--map-filename` specified.

* `--no-filter` - Do not filter out `*laps*` or `*starts*`-patterned files. 

* `--weight-smooth` - Uses square of average of nonzero weights rather than multiplying them to increase similarity and effects of overlap.

* `--weight-center-only` - EXPERIMENTAL. Requires a weight of 1 in at least 1 track when computing similarities, but has issues when comparing events that have a lot of tightly interwoven paths (e.g., running on a pill-shaped track). I can't quite get the effect to work well, especially for non-directional. Workaround: set `--weight-smooth` and use a max manhattan distance of 4 with large weights, except for the last one, possibly. Make sure that the bin size is 20-40 meters. This is analagous to measuring the overlap of two slightly off-center markers on a sheet of paper.

## Algorithm (General)

The script has a few main steps:

1. Create bounding boxes for each track (min/max latitude/longitudes)

2. Group tracks together based on overlapping bounding boxes

3. Build a raster for each track, using bins based on latitude and longitude. The longitude bins are based on the median longitude of each group, so a group that spans a very wide range of latitudes may behave inconsistently, which would require further refining the grouping algorithm. The raster cells also expand into neighboring cells based on a decaying weight in the constants.

4. Calculate the *norms* of each track (sum of squared weights across raster cells)

5. Calculate the similarities using the above data.

6. Write results to CSV


## Adjusting Constants

Some constants in `constants.py` can be adjusted for different behavior.

* `ANGLE_LAG_SECONDS` controls how much lag should be used to calculate the angle of a path. This is important, as it allows for smoothing of data when the GPS may be a bit shaky. It also smooths sharp corners and extrapolates the last `N` angles if directional statistics are used, where `N` is its value.

* `RASTER_COOLDOWN_INTERVAL` indicates how many seconds must pass before a raster cell can have its weight re-incremented. i.e., if someone passes through a cell 10 minutes apart, it will have its weight incremented twice as long as this constant is less than 600. This constant generally prevents slower speeds from creating inconsistent results, but walking might end up increasing cell count if the cells are too large/raster manhattan max distance (explained later) is larger

* `RASTER_LAT_OFFSET`/`RASTER_LONG_OFFSET` - You can set these values to offsets to use when calculating raster bins. I would only use these to test consistency of calculations.

* `RASTER_SIZE_M` - This is the size of the raster grid in meters. Smaller values will yield more precise results, which might work even better given a larger manhattan distance, but will also be somewhat slower.

* `RASTER_DECAY_FACTOR` - This is the decay factor when calculating weights for cells further from the main raster. Each unit of (Manhattan) distance multiplies the weight by this factor. For some raster functions, this behaves in a separate way.

* `RASTER_MANHATTAN_DISTANCE_MAX` - The maximum Manhattan distance to use to calculate weighted values of the raster. This can greatly increase computation time, as it quadratically increases the size of data stored, as well as increasing the size of bounding boxes.

* `RASTER_METHOD` - Method of handling raster weights. This is a string that is a key in `RASTER_FUNCTIONS`

* `CUSTOM_RASTER_PROFILE` - custom-defined weights by index of Manhattan distance. Length must be one greater than max Manhattan distance if `RASTER_METHOD='custom'`

* `RASTER_FUNCTIONS` - Functions used to determine weights. First argument is the decay rate, the second argument is the distance.

Other values in `constants.py` are meant to be calculated by the file and not be touched by the user.

Some of these constants may end up being command-line options later.