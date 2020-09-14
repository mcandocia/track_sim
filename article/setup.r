
library(tidyverse)
library(lubridate)
library(cetcolor)
library(ggmap)
library(kableExtra)
library(xml2)

DATA_DIRECTORY='/ntfsl/data/fit_processed_data'
RASTER_DIRECTORY=file.path(DATA_DIRECTORY,'rasters')

add_html_id <- function(x, id){
  x = x %>%
    kable_as_xml() 
  
  x %>%
    xml_set_attr('id', id) 
  
  x %>%
    xml_as_kable()
}

expand_similarities <- function(x){
  bind_rows(
    similarity_df,
    similarity_df %>%
      mutate(
        id1_temp = id2,
        id2=id1,
        id1=id1_temp
      ) %>%
      select(-id1_temp)
  ) %>%
    filter(!duplicated(paste(id1,id2)))
}

similarity_df = read_csv(
  file.path(
    DATA_DIRECTORY,
    'similarities.csv'
  )
) %>%
  expand_similarities()

run_summary_df = read_csv(
  file.path(
    DATA_DIRECTORY,
    's1_summaries.csv'
  )
)

mapfile_df = read_csv(
  file.path(
    DATA_DIRECTORY,
    's1_mapfile.csv'
  )
)

run_id_df = read_csv(file.path(DATA_DIRECTORY, 's1_mapfile.csv'))

rasters_edf = read_csv(file.path(RASTER_DIRECTORY,'raster_members_expanded.csv'))
drasters_edf = read_csv(file.path(RASTER_DIRECTORY, 'raster_directional_members_expanded.csv'))

rasters_df = read_csv(file.path(RASTER_DIRECTORY,'raster_members.csv'))
drasters_df = read_csv(file.path(RASTER_DIRECTORY, 'raster_directional_members.csv'))

members_ids_df = read_csv(file.path(RASTER_DIRECTORY, 'raster_members_ids.csv')) %>%
  mutate(filename=gsub('.*/','',filename))

raster_groups_df = read_csv(file.path(RASTER_DIRECTORY, 'raster_groups.csv'))

# TODO: add offset into calculation
raster_transform <- function(data){
  data %>%
    left_join(
      raster_groups_df %>%
        select(group_id, long_raster_size, median_lat, median_long) %>%
        mutate(lat_raster_size = long_raster_size * cos(pi/180*median_lat)),
      by='group_id'
    ) %>%
    mutate(
      long_center=long_bin * long_raster_size,
      lat_center = lat_bin * lat_raster_size
    )
}

get_loc <- function(data){
  c(
    lat=median(data$lat_center),
    lon=median(data$long_center)
  )
}

get_bbox <- function(data, lat_margin=0.002, long_margin=0.002){
  lat_range = range(data$lat_center)+ c(-1,1) * lat_margin
  long_range=range(data$long_center) + c(-1,1) * long_margin
  
  return(c(
    bottom=min(lat_range),
    top=max(lat_range),
    left=min(long_range),
    right=max(long_range)
  ))
}

run_summary_simple_df = run_summary_df %>% 
  select(
    timestamp_start_run, 
    event_id,
    lat_median,
    long_median,
    timezone,
    total_distance,
    speed_average,
    n_laps,
    n_rests
  ) %>% 
  transmute(
    event_id, 
    timestamp=as.POSIXct(timestamp_start_run, origin='1970-01-01'),
    lat_median,
    long_median,
    timezone,
    total_distance,
    speed_average,
    n_laps,
    n_rests,
    date=as.Date(timestamp)
  )


monthly_seq = seq.POSIXt(from=as.POSIXct('2017-09-01'),to=as.POSIXct('2020-10-01'), by='month')
quarterly_seq = seq.POSIXt(from=as.POSIXct('2017-07-01'),to=as.POSIXct('2020-10-01'), by='quarter')
