from collections import defaultdict
import constants as c
import numpy as np
import pandas as pd
from utility import Clogger
from utility import diamond_generator

from group_clusters import GroupProcessor

PI = np.pi


logger = Clogger('calculate_similarity.log')

def has_intersection(
        fn1,
        fn2,
        metadata=None
):
    if isinstance(fn1, dict) and isinstance(fn2, dict):
        bbox1 = fn1['bbox']
        bbox2 = fn2['bbox']
    else:
        bbox1 = metadata[fn1]['bbox']
        bbox2 = metadata[fn2]['bbox']

    return not (
        (bbox1['lat'][1] < bbox2['lat'][0]) or
        (bbox1['lat'][0] > bbox2['lat'][1]) or
        (bbox1['long'][1] < bbox2['long'][0]) or
        (bbox1['long'][0] > bbox2['long'][0])
    )


def calculate_similarities(data, grouper):
    logger.info('Calculating similarities...')
    similarities = {}
    counter = 0
    zero_counter = 0
    for member1, member2 in grouper.pairwise_group_iter():
        key = (member1['filename'], member2['filename'])
        if not has_intersection(
                member1,
                member2
        ):
            similarities[key] = 0
            zero_counter += 1
        else:
            similarities[key] = calculate_similarity(
                member1,
                member2
            )
        counter+=1
        if counter % 1000 == 0:
            logger.debug(
                'Calculated %d directional similarities (%d default zero-valued)' % (
                    counter,
                    zero_counter
                )
            )            

    return similarities


## TODO: GROUP RECORDS BY LATITUDE/LONGITUDE CONTINUITY FOR
##       RASTERIZING
##
##       1. Determine normal bounding boxes
##       2. Group events in contiguous areas to determine
##          how many longitude grid sizes should be used
##          (one for each group)
##       3. Check to make sure that longitude size doesn't
##          change by more than a few percent within each
##          group (if it does, maybe that's a solution for
##          a later date, such as assigning multiple rasters
##          for a given record, and using matching grids
##          for similarity calculations when otherwise
##          ambiguous)
##       4. Assign median (of medians) as the median latitude
##       5. Return dict of groups, then proceed to
##          rasterizing based on these groups
##


def group_tracks(metadata):
    # fn: bbox
    # bbox= {'lat': (.,.), 'long': (.,.)}

    groups = {}
    filenames = list(metadata.keys())

    # identical to single-linkage clustering with only 2 possible distances

    group_processor = GroupProcessor()

    logger.info('Adding values to group processor')
    for v in metadata.values():
        group_processor.add_member(v)

    logger.info('Performing final merges')
    n_merges = group_processor.merge_groups()
    logger.debug('%d mergest performed in final merges' % n_merges)

    return group_processor
        


def rasterize(data, grouper):
    """
    assigns "raster_dict" dict of dictionaries 
    to each member of each group of grouper object
    """
    # 1. determine longitude raster size
    # (grouper.attributes['long_raster_size'])

    # 2. bin latitude and longitude into bins

    # 3. create raster dictionary
    # FIELDS:
    #         * lat_center (6 digits) (using bin # for now)
    #         * long_center (6 digits) (using bin # for now)
    #         * count
    #         * step last updated at (temporary)

    # 4. convert raster dictionary to dataframe

    logger.info('Rasterizing')

    calc_lat_bin = lambda x: x // c.RASTER_SIZE_LAT

    n_processed = 0
    
    for i, group in enumerate(grouper.groups):
        logger.debug('Rasterizing group %d/%d' % ((i+1),len(grouper.groups)))
        calc_long_bin = lambda x: x // group.attributes['long_raster_size']
        for j, member in enumerate(group.members):
            fn = member['filename']
            # normal rasterization
            member['rasterization'] = pd.DataFrame(
                {
                    'lat_bin': calc_lat_bin(data[fn]['position_lat']),
                    'long_bin': calc_long_bin(data[fn]['position_long']),
                    'weight': 1.0,
                    'pk': np.arange(data[fn].shape[0]), # for intra-data ID when using manhattan r.
                }
            )

            # this template will be used to determine angles
            # note that only the highest weight will be used 
            raster_dict = defaultdict(lambda: defaultdict(float))
            # manhattan rasterization
            for pk, lat_bin, long_bin in zip(
                    member['rasterization']['pk'],
                    member['rasterization']['lat_bin'],
                    member['rasterization']['long_bin']
            ):
                # main rasterization
                # if update not detected
                for md in range(c.RASTER_MANHATTAN_DISTANCE_MAX+1):
                    weight = c.RASTER_DECAY_FACTOR ** md
                    for lat_bin_offset, long_bin_offset in diamond_generator(md):
                        rkey = (lat_bin+lat_bin_offset, long_bin+long_bin_offset)
                        if (
                                # if no recent weights encountered
                                raster_dict[rkey].get('last_update', -c.RASTER_COOLDOWN_INTERVAL-1) <
                                pk-c.RASTER_COOLDOWN_INTERVAL
                        ):
                            raster_dict[rkey]['last_update'] = pk
                            raster_dict[rkey]['sum_weight'] += weight
                            raster_dict[rkey]['last_weight'] = weight
                        elif (
                                # in case higher weight is encountered within time frame
                                raster_dict[rkey]['last_weight'] < weight
                        ):
                            prev_weight = raster_dict[rkey]['last_weight']
                            raster_dict[rkey]['last_update'] = pk
                            raster_dict[rkey]['last_weight'] = weight
                            raster_dict[rkey]['weight'] += weight - prev_weight
                            

            # final processing to wrap up loose ends
            member['raster_dict'] = raster_dict
            member['rkeys'] = set(raster_dict.keys())
            n_processed += 1            
            if (n_processed % 25) == 0:
                logger.debug('Rasterized %d tracks' % n_processed)

    logger.debug('Processed %d total' % n_processed)

    
        
                        


def rasterize_directional(data, grouper):
    # 1. determine longitude raster size (easy)

    # 2. bin latitude and longitude into bins

    # 3. create raster dictionary
    # FIELDS:
    #         * lat_center (6 digits)
    #         * long_center (6 digits)
    #         * count
    #         * step last updated at (temporary)
    #         * accumulator for angles within current window

    # 4. convert raster dictionary to dataframe

    logger.info('Directional rasterizing')

    calc_lat_bin = lambda x: x // c.RASTER_SIZE_LAT

    n_processed = 0
    
    for i, group in enumerate(grouper.groups):
        logger.debug('Rasterizing group %d/%d' % ((i+1),len(grouper.groups)))
        calc_long_bin = lambda x: x // group.attributes['long_raster_size']
        for j, member in enumerate(group.members):
            fn = member['filename']
            # normal rasterization
            member['rasterization'] = pd.DataFrame(
                {
                    'lat_bin': calc_lat_bin(data[fn]['position_lat']),
                    'long_bin': calc_long_bin(data[fn]['position_long']),
                    'weight': 1.0,
                    'pk': np.arange(data[fn].shape[0]), # for intra-data ID when using manhattan r.
                    'angle': data[fn]['angle'],
                }
            )


            def default_template():
                return {
                    'last_update': -c.RASTER_COOLDOWN_INTERVAL-1,
                    'last_angles': [],
                    'last_weight': 0.0,
                    'angle_history':[],
                    'weight_history': [],
                    'wrapped_up': True,
                }
            raster_dict = defaultdict(default_template)            
            # manhattan rasterization
            for pk, lat_bin, long_bin, angle in zip(
                    member['rasterization']['pk'],
                    member['rasterization']['lat_bin'],
                    member['rasterization']['long_bin'],
                    member['rasterization']['angle'],
            ):
                # main rasterization
                # if update not detected
                for md in range(c.RASTER_MANHATTAN_DISTANCE_MAX+1):
                    weight = c.RASTER_DECAY_FACTOR ** md
                    for lat_bin_offset, long_bin_offset in diamond_generator(md):
                        rkey = (lat_bin+lat_bin_offset, long_bin+long_bin_offset)
                        # if the last track has been wrapped up (will only be default here
                        # if it hasn't been initialized yet                        
                        if (
                                raster_dict[rkey]['wrapped_up']
                        ):
                            raster_dict[rkey]['last_update'] = pk
                            raster_dict[rkey]['wrapped_up'] = False
                            raster_dict[rkey]['last_angles'].append(angle)
                            raster_dict[rkey]['last_weight'] = weight
                        elif (
                                # if higher weight is encountered
                                weight > raster_dict[rkey]['last_weight'] and
                                pk < raster_dict[rkey]['last_update'] + c.RASTER_COOLDOWN_INTERVAL
                        ):
                            # reset last streak and update
                            raster_dict[rkey]['last_update'] = pk
                            raster_dict[rkey]['last_angles'] = [angle]
                            raster_dict[rkey]['last_weight'] = weight
                            
                        elif weight < raster_dict[rkey]['last_weight']:
                            pass
                        elif (
                                weight == raster_dict[rkey]['last_weight']
                                and
                                (
                                    raster_dict[rkey]['last_update'] + c.RASTER_COOLDOWN_INTERVAL >
                                    pk
                                )
                        ):
                            # add another entry
                            raster_dict[rkey]['last_angles'].append(angle)
                        else:
                            # wrap up previous streak
                            avg_angle = np.arctan2(
                                np.mean(np.sin(raster_dict[rkey]['last_angles'])),
                                np.mean(np.cos(raster_dict[rkey]['last_angles'])),
                            )
                            raster_dict[rkey]['angle_history'].append(avg_angle)
                            raster_dict[rkey]['weight_history'].append(
                                raster_dict[rkey]['last_weight']
                            )
                            # start new
                            raster_dict[rkey]['last_angles'] = [angle]
                            raster_dict[rkey]['last_weight'] = weight
                            

            # wrap everything up
            #logger.warn(list(raster_dict.keys())[:10])
            for rkey in list(raster_dict.keys()):
                # should always be true
                if not raster_dict[rkey]['wrapped_up']:
                    avg_angle = np.arctan2(
                        np.mean(np.sin(raster_dict[rkey]['last_angles'])),
                        np.mean(np.cos(raster_dict[rkey]['last_angles'])),
                    )
                    
                    raster_dict[rkey]['weight_history'].append(raster_dict[rkey]['last_weight'])
                    raster_dict[rkey]['angle_history'].append(avg_angle)
                    # save small bit of RAM
                    raster_dict[rkey]['last_angles'] = []
                    raster_dict[rkey]['wrapped_up'] = True
                else:
                    logger.error('pre-wrapped rkey')
                    logger.error(rkey)
                    logger.error(raster_dict[rkey])
                    
            member['directional_raster_dict'] = raster_dict
            # this would be redundant
            #member['directioanl_rkeys'] = set(raster_dict.keys())
            n_processed += 1            
            if (n_processed % 25) == 0:
                logger.debug('Rasterized %d tracks' % n_processed)

    logger.debug('Processed %d total' % n_processed)

        
def calculate_norms(data):
    for fn, member in data.items():
        sum_weights_squared = 0
        for rkey, data in member['raster_dict'].items():
            sum_weights_squared += data['sum_weight'] ** 2
        member['raster_norm'] = sum_weights_squared

def calculate_directional_norms(data):
    for fn, member in data.items():
        sum_weights_squared = 0
        for rkey, data in member['directional_raster_dict'].items():
            for weight in data['weight_history']:
                sum_weights_squared += weight ** 2
        member['raster_directional_norm'] = sum_weights_squared        


def calculate_similarity(r1, r2):
    # find similar rkeys

    keys1 = r1['rkeys']
    keys2 = r2['rkeys']

    sum_weight_product = 0
    for key in keys1.intersection(keys2):
        sum_weight_product += (
            r1['raster_dict'][key]['sum_weight'] *
            r2['raster_dict'][key]['sum_weight']
        )

    similarity = sum_weight_product / np.sqrt(r1['raster_norm']*r2['raster_norm'])
    return similarity

    
def calculate_directional_similarity(r1, r2):

    # find similar rkeys

    keys1 = r1['rkeys']
    keys2 = r2['rkeys']

    sum_weight_product = 0
    for key in keys1.intersection(keys2):
        weights1 = r1['directional_raster_dict'][key]['weight_history']
        weights2 = r2['directional_raster_dict'][key]['weight_history']
        angles1 = r1['directional_raster_dict'][key]['angle_history']
        angles2 = r2['directional_raster_dict'][key]['angle_history']

        # truncated data will not have any further contributions
        for w1, w2, a1, a2 in zip(weights1, weights2, angles1, angles2):
            cosine_sim = np.cos(a1-a2)
            sum_weight_product += cosine_sim * w1 * w2
        
        #
        
        #sum_weight_product += (
        #    r1['raster_dict'][key]['sum_weight'] *
        #    r2['raster_dict'][key]['sum_weight']
        #)

    similarity = sum_weight_product / np.sqrt(
        r1['raster_directional_norm']*r2['raster_directional_norm']
    )
    
    return similarity

def calculate_directional_similarities(data, grouper):
    logger.info('Calculating directional similarities...')
    similarities = {}
    counter = 0
    zero_counter = 0
    for member1, member2 in grouper.pairwise_group_iter():
        key = (member1['filename'], member2['filename'])
        if not has_intersection(
                member1,
                member2
        ):
            similarities[key] = 0
            zero_counter += 1
        else:
            similarities[key] = calculate_directional_similarity(
                member1,
                member2
            )
        counter+=1
        if counter % 1000 == 0:
            logger.debug(
                'Calculated %d directional similarities (%d default zero-valued)' % (
                    counter,
                    zero_counter
                )
            )

    return similarities
