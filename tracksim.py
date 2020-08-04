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
    

    parser.add_argument(
        '--no-filter',
        help='Do not filter out input filenames',
        action='store_true',
    )

    args = parser.parse_args()

    options = vars(args)

    # filter out start/lap files
    if not options['no_filter']:
        options['files'] = [
            f for f in options['files']
            if not re.search('laps|starts', f)
        ]

    if options['head'] > 0:
        logger.warn('Only taking top %d files' % options['head'])
        options['files'] = options['files'][:options['head']]        
    
    return options

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

    bbox_increase_long = c.BBOX_INCREASE_LAT * cosine_lat
    
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
        diffs['position_long'] = diffs['position_long'] * lon_lat_ratio
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

    calculate_norms(metadata)
    similarity_data = calculate_similarities(data, grouper)
    logger.info('Calculated similarities')

    if options['add_directional_similarity']:
        rasterize_directional(data, grouper)
        calculate_directional_norms(metadata)
            
        directional_similarity_data = calculate_directional_similarities(
            data,
            grouper,
        )
        logger.info('Calculated directional similarities')

    else:
        directional_similarity_data = None

    write_results_to_disk(
        similarity_data,
        directional_similarity_data,
        options
    )


    logger.info('Done!')
        

# python3 calculate_similarities.py ../fit_conversion/subject_data/spriesdaddy/fit_csv/

def write_results_to_disk(
        simdata,
        dsimdata,
        options,
):
    # get unique pairs
    keys, values = zip(*simdata.items())

    source_data = {
            'fn1': [k[0] for k in keys],
            'fn2': [k[1] for k in keys],
            'similarity': values
    }
    if dsimdata is not None:
        source_data.update(
            {'directional_similarity': [dsimdata[k] for k in keys]}
        )
    df = pd.DataFrame(
        source_data
    )

    logger.info('Writing data to %s' % options['output_filename'])

    df.to_csv(options['output_filename'], index=False)
    

if __name__=='__main__':
    options = get_options()

    main(options)
