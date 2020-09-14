## analysis.r
# Max Candocia - maxcandocia@gmail.com
# 2020-09-12
#
# analyze data (which will then be put into an Rhtml file)
# this script is not executed for the article, but will be used for testing/building of graphics

library(tidyverse)
library(lubridate)
library(cetcolor)

DATA_DIRECTORY='/ntfsl/data/fit_processed_data'
RASTER_DIRECTORY=file.path(DATA_DIRECTORY,'rasters')

similarity_df = read_csv(
  file.path(
    DATA_DIRECTORY,
    'similarities.csv'
  )
)

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

ggplot(
  similarity_df %>% 
    complete(id1,id2,fill=list(similarity=0, directional_similarity=0)) %>%
    inner_join(
      run_summary_simple_df %>%
        transmute(id1=event_id, date1=date)
    ) %>%
    inner_join(
      run_summary_simple_df %>%
        transmute(id2=event_id, date2=date)
    )
  ) + 
  geom_tile(aes(x=id1, y=id2, fill=similarity)) + 
  scale_fill_gradientn(colors=cet_pal(7, 'inferno')) +
  ggtitle('Similarity of my runs') + 
  xlab('Run #') + ylab('Run #')

monthly_seq = seq.POSIXt(from=as.POSIXct('2017-09-01'),to=as.POSIXct('2020-10-01'), by='month')
quarterly_seq = seq.POSIXt(from=as.POSIXct('2017-09-01'),to=as.POSIXct('2020-10-01'), by='quarter')

ggplot(
  similarity_df %>% 
    complete(id1,id2,fill=list(similarity=0, directional_similarity=0)) %>%
    inner_join(
      run_summary_simple_df %>%
        transmute(id1=event_id, date1=as.POSIXct(date))
    ) %>%
    inner_join(
      run_summary_simple_df %>%
        transmute(id2=event_id, date2=as.POSIXct(date))
    )
) + 
  geom_tile(aes(x=date1, y=date2, fill=similarity)) + 
  scale_fill_gradientn(colors=cet_pal(7, 'inferno')) +
  ggtitle('Similarity of my runs') + 
  xlab('Run Date') + ylab('Run Date') + 
  scale_x_datetime(
    breaks=quarterly_seq
  ) + 
  scale_y_datetime(
    breaks=quarterly_seq
  ) + 
  theme(axis.text.x = element_text(angle=90))


# let's look at Fat Can run, event #127
# other IDs: 175,  304
# raster only
FATCAT_ID=304
FATCAT_IDS=c(127,175,304)
ggplot(
  rasters_df %>% 
    inner_join(
      members_ids_df %>%
        inner_join(
          mapfile_df
        ) %>%
        filter(id %in% FATCAT_IDS)
    )
) + 
  geom_tile(
    aes(
      x=long_bin,y=lat_bin,fill=factor(id)
    ),
    alpha=0.5
  )


# bases for article image