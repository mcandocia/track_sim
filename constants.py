# how many seconds to use to calculate angle for angle-based calculations
# (acts as a smoothing coefficient)
ANGLE_LAG_SECONDS=5

# interval between counting parts 
RASTER_COOLDOWN_INTERVAL=30

# probably only need these for debugging/QA purposes
RASTER_LAT_OFFSET=0
RASTER_LONG_OFFSET=0

RASTER_SIZE_M=20

RASTER_SIZE_LAT=RASTER_SIZE_M/111000


# product of decay by distance;
# minimum factor = RASTER_DECAY_FACTOR ^ RASTER_MANHATTAN_DISTANCE_MAX
RASTER_DECAY_FACTOR=0.8
RASTER_MANHATTAN_DISTANCE_MAX=2


# determine increase in bbox size from above constants
BBOX_INCREASE_LAT=(RASTER_MANHATTAN_DISTANCE_MAX + 1) * RASTER_SIZE_LAT

