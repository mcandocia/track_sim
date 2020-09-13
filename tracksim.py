## calculate_similarities.py
# Max Candocia - maxcandocia@gmail.com
# 2020-07-29
#
# calculate similarites from all tracks in file


'''
TEST SCRIPT

python3 tracksim.py ../fit_conversion/subject_data/maxcan_v2/fit_csv/running*.csv
'''

import os
import numpy as np
import sys
import argparse
import pandas as pd
import re
from copy import copy

from utility import Clogger

import constants as c

from calculate_similarity import rasterize
from calculate_similarity import rasterize_directional
from calculate_similarity import calculate_similarities
from calculate_similarity import calculate_directional_similarities
from calculate_similarity import calculate_norms
from calculate_similarity import calculate_directional_norms
from calculate_similarity import set_weights_func

from group_clusters import GroupProcessor

logger = Clogger('calculate_similarities.log')

logger.debug('initialized logger')

PI=np.pi

def get_options():
    parser = argparse.ArgumentParser(
        description='Get similarities between gps-type tracks'
    )

    parser.add_argument(
        'files',
        nargs='+',
        help='Input files'
    )

    parser.add_argument(
        '--output-filename',
        help='Output filename',
        default='track_similarities.csv'
    )

    parser.add_argument(
        '--add-directional-similarity',
        action='store_true',
        help='Add direction-based similarity metrics',
    )

    parser.add_argument(
        '--head',
        type=int,
        default=0,
        help='Take top N records of data instead of all data'
    )

    # averaging weights cannot produce sums > 1 mathematically
    parser.add_argument(
        '--weight-smooth',
        action='store_true',
        help='Take average of both weights (if both nonzero) when '
        'comparing raster cells, rather than each weight as is. This '
        'should result in higher similarities.'
    )

    parser.add_argument(
        '--weight-center-only',
        action='store_true',
        help='Do not use any weights outside of center to calculate '
        'norm or similarity (first center for similarity).'
    )
        

    '''
    parser.add_argument(
        '--add-inter-group-pairs',
        action='store_true',
        help='Add inter-group pairs (all 0s) to the resulting output file'
    )
    '''
    

    parser.add_argument(
        '--no-filter',
        help='Do not filter out input filenames',
        action='store_true',
    )

    parser.add_argument(
        '--truncate-file-path',
        action='store_true',
        help='Truncate the path portion of filenames. This happens '
        'before joining to map file if map file is used.'
    )

    parser.add_argument(
        '--map-filename',
        default=None,
        required=False,
        help='A filename of a CSV with columns "filename" and "id"to map back to output data',
    )

    parser.add_argument(
        '--remove-filenames',
        action='store_true',
        help='Remove filenames from output file. Only '
        'recommended if used with "--map-filename"'
    )

    parser.add_argument(
        '--rasterized-output-prefix',
        default=None,
        required=False,
        help='Filename prefix for rasters built (including directional)'
    )

    # raster parameters
    parser.add_argument(
        '--raster-method',
        choices=['','custom','exponential','power','linear','cosine','near_intersect','normal'],
        default='',
        required=False,
        help='Method for raster weighting. Default is value from constants.py',
        dest='RASTER_METHOD'
    )

    parser.add_argument(
        '--angle-lag-seconds',
        default=None,
        type=int,
        required=False,
        help='Lag used for calculating angles of path',
        dest='ANGLE_LAG_SECONDS'
    )

    parser.add_argument(
        '--raster-cooldown-interval',
        default=None,
        type=int,
        required=False,
        help='Amount of "cooldown" time before a new raster path '
        'is registered over a previously-traversed one',
        dest='RASTER_COOLDOWN_INTERVAL'
    )

    parser.add_argument(
        '--raster-size-m',
        default=None,
        type=float,
        help='Raster grid size in meters',
        dest='RASTER_SIZE_M'
    )

    parser.add_argument(
        '--raster-decay-factor',
        default=None,
        type=float,
        help='Decay factor for certain raster functions',
        dest='RASTER_DECAY_FACTOR'
    )

    parser.add_argument(
        '--raster-manhattan-distance-max',
        default=None,
        type=int,
        help='Maximum distance for raster calculations in '
        'terms of grid units',
        dest='RASTER_MANHATTAN_DISTANCE_MAX'
    )

    parser.add_argument(
        '--custom-raster-profile',
        type=float,
        nargs='*',
        default=[],
        required=False,
        help='Weights used for custom raster method. '
        'First should be 1 if provided.',
        dest='CUSTOM_RASTER_PROFILE',
    )
        

    args = parser.parse_args()

    options = vars(args)

    update_constants(options)
            

    # this should be true always
    options['add_inter_group_pairs'] = True

    # filter out start/lap files
    if not options['no_filter']:
        options['files'] = [
            f for f in options['files']
            if not re.search('laps|starts', f)
        ]

    if options['head'] > 0:
        logger.warn('Only taking top %d files' % options['head'])
        options['files'] = options['files'][:options['head']]

    if options['weight_smooth']:
        set_weights_func(lambda x, y: ((x+y)/2) ** 2)
    
    return options

def update_constants(options):
    # lazy way of updating constants
    # I don't advise this method in general
    # it might be better to just have a class in the future
    # that can update its own values...
    for opt in dir(c):
        if options.get(c):
            logger.debug(
                'Overriding default value of %s (%s) with %s' % (
                    opt,
                    ascii(getattr(c, opt)),
                    ascii(options.get(opt)),
                )
            )
            setattr(c, opt, options.get(opt))
            if opt == 'RASTER_SIZE_M':
                RASTER_SIZE_LAT = options['RASTER_SIZE_M']/111000
            if opt in ['RASTER_SIZE_M','RASTER_MANHATTAN_DISTANCE_MAX']:
                c.BBOX_INCREASE_LAT=(c.RASTER_MANHATTAN_DISTANCE_MAX + 1) * c.RASTER_SIZE_LAT
            if opt == 'RASTER_METHOD':
                c.RASTER_FUNCTION = c.RASTER_FUNCTIONS[c.RASTER_METHOD]    

def filter_bad_data(
        files,
        data
):
    fns = copy(files)
    n_bad = 0
    for fn in fns:
        if data[fn].shape[0] == 0:
            n_bad+=1
            logger.warn('Removing %s due to 0 rows' % fn)
            files.pop(files.index(fn))
            data.pop(fn)

    if n_bad > 0:
        logger.warn('Removed %d files for having 0 rows' % n_bad)
    else:
        logger.debug('No rows removed from filter')
            

def get_metadata(record, fn):
    #logger.debug('summarizing %s' % fn)
    
    median_lat = np.median(record['position_lat'])
    cosine_lat = np.cos(PI/180 * median_lat)

    bbox_increase_long = c.BBOX_INCREASE_LAT / cosine_lat
    
    bbox = {
        'lat': [
            np.min(record['position_lat']) - c.BBOX_INCREASE_LAT,
            np.max(record['position_lat']) + c.BBOX_INCREASE_LAT,
        ],
        'long': [
            np.min(record['position_long']) - bbox_increase_long,
            np.max(record['position_long']) + bbox_increase_long,
        ],
    }

    return {
        'bbox': bbox,
        'distance': np.max(record['distance']),
        'ts_start': record['timestamp'][0],
        'filename': fn,
        'median_lat': median_lat,
        'cosine_lat': cosine_lat,
    }

def add_directions(data, options):
    for fn in data.keys():
        record = data[fn]
        clat, clon = (
            np.median(record['position_lat']),
            np.median(record['position_long'])
        )
        lon_lat_ratio = np.cos(PI/180 * clat)
        diffs = record[['position_lat','position_long']].diff(
            c.ANGLE_LAG_SECONDS
        )

        # shifts differences to original values, then fills last rows with last direction
        diffs = diffs.dropna().reset_index().append(
            diffs.iloc[[-1] * c.ANGLE_LAG_SECONDS].reset_index()
        ).reset_index()
        diffs['position_long'] = diffs['position_long'] / lon_lat_ratio
        record['angle'] = np.arctan2(
            diffs['position_lat'],
            diffs['position_long']
        )
    logger.info('Done adding directions')
        

def main(options):
    # load all files into memory brrrrr
    logger.info('loading data')

        
    data = {
        fn: pd.read_csv(fn)[['position_long','position_lat','timestamp','distance','timezone']]
        for fn in options['files']
    }


    filter_bad_data(
        options['files'],
        data,        
    )

    logger.info('Creating metadata')

    metadata = {
        fn: get_metadata(data[fn], fn)
        for fn in options['files']
    }

    logger.info('Grouping tracks')
    grouper = GroupProcessor(
        metadata=metadata
    )
    
    logger.debug('%d groups created' % len(grouper.groups))

    grouper.print_group_sizes()
    
    logger.info('Adding directions')
    add_directions(data, options)

    # applies rasterization to grouper->groups->members objects
    rasterize(data, grouper)

    calculate_norms(metadata, options)
    similarity_data = calculate_similarities(
        data,
        grouper,
        options,
    )
    logger.info('Calculated similarities')
    write_grouper_to_disk(grouper, options)    

    if options['add_directional_similarity']:
        rasterize_directional(data, grouper)
        calculate_directional_norms(metadata, options)
            
        directional_similarity_data = calculate_directional_similarities(
            data,
            grouper,
            options,
        )
        
        logger.info('Calculated directional similarities')
        write_grouper_to_disk(grouper, options, directional=True)

    else:
        directional_similarity_data = None

    write_results_to_disk(
        similarity_data,
        directional_similarity_data,
        options,
        grouper
    )


    logger.info('Done!')

def write_grouper_to_disk(grouper, options, directional=False):
    if options['rasterized_output_prefix']:
        logger.info(
            'Writing data from grouper to disk. Concatenating first, which may take a '
            'while. Directional: %s' % directional
        )
        df_dict = grouper.groups_to_df_dict(directional=directional, options=options)
        prefix = options['rasterized_output_prefix']
        if directional:
            prefix = '%s_directional' % prefix
            
        filenames = {
            k: '%s_%s.csv' % (prefix, k)
            for k in ['groups','members','members_ids','members_expanded',]
        }
        for k, fn in filenames.items():
            logger.info('Writing %s to disk' % fn)
            df_dict[k].to_csv(
                fn,
                index=False
            )    
        

# python3 calculate_similarities.py ../fit_conversion/subject_data/spriesdaddy/fit_csv/

def write_results_to_disk(
        simdata,
        dsimdata,
        options,
        grouper
):
    # get unique pairs
    keys, values = zip(*simdata.items())

    source_data = {
            'fn1': [k[0] for k in keys],
            'fn2': [k[1] for k in keys],
            'similarity': values
    }
    cols = []
    if not options['remove_filenames']:
        cols.extend(['fn1','fn2',])
    cols.extend(['similarity'])
    if dsimdata is not None:
        cols+=['directional_similarity']
        source_data.update(
            {'directional_similarity': [dsimdata[k] for k in keys]}
        )
    df = pd.DataFrame(
        source_data
    )

    if options['add_inter_group_pairs']:
        logger.info('Adding inter-group pairs')
        filename_pairs = list(grouper.inter_group_filename_pairs())
        inter_pair_df = pd.DataFrame({
            'fn1': [x[0] for x in filename_pairs],
            'fn2': [x[1] for x in filename_pairs],
        })
        inter_pair_df['similarity'] = 0
        if dsimdata is not None:
            inter_pair_df['directional_similarity'] = 0
        df = df.append(
            inter_pair_df,
            ignore_index=True
        )

    if options['truncate_file_path']:
        sub_regex = re.compile(r'.*/')
        df['fn1'] = df['fn1'].str.replace(sub_regex,'')
        df['fn2'] = df['fn2'].str.replace(sub_regex,'')

    if options['map_filename']:
        cols.extend(['id1','id2'])
        logger.info('Attempting map of column filenames with external CSV')
        try:
            map_df = pd.read_csv(options['map_filename'])
        except Exception as e:
            logger.error('Could not find file %s' % ascii(options['map_filename']))
            map_df = None

        if map_df is None:
            map_df = pd.DataFrame({})
        elif 'filename' not in map_df.columns or 'id' not in map_df.columns:
            logger.error('Cannot find "id" or "filename" columns in map file. Skipping')
        else:
            try:
                logger.info('merging df with map file')
                map_df = map_df[['filename','id']]
                df = df.merge(
                    map_df.rename({'id':'id1'}, axis=1),
                    how='left',
                    left_on='fn1',
                    right_on='filename'
                )
                df = df.merge(
                    map_df.rename({'id':'id2'}, axis=1),
                    how='left',
                    left_on='fn2',
                    right_on='filename'
                )
                logger.info('merged df and map')
                    
                    
            except Exception as e:
                logger.error(str(e))
                logger.error('Could not map IDs back to file')
                

    logger.info('Writing data to %s' % options['output_filename'])

    df[cols].to_csv(options['output_filename'], index=False)
    

if __name__=='__main__':
    options = get_options()

    main(options)
