import constants as c
from collections import Counter
import json
import numpy as np
from utility import Clogger

logger = Clogger('group_clusters.log')

def bbox_intersection(
        d1,
        d2,
):
    try:
        bbox1 = d1['bbox']
        bbox2 = d2['bbox']
    except TypeError as e:
        logger.debug(d1)
        logger.debug(d2)
        logger.error('TYPE ERROR')
        raise e

    return not (
        (bbox1['lat'][1] < bbox2['lat'][0]) or
        (bbox1['lat'][0] > bbox2['lat'][1]) or
        (bbox1['long'][1] < bbox2['long'][0]) or
        (bbox1['long'][0] > bbox2['long'][1])
    )

class Group:
    def __init__(
            self,
            members
    ):
        self.members = members
        self.attributes = None

    def add_member(self, member):
        #logger.debug('Adding member to group: %a' % member)
        self.members.append(member)

    def set_attributes(self):
        self.attributes = self.summary()


    def __add__(self, y):
        self.members += y.members
        return self

    def intersect(self, y):
        """
        takes either a member dict containing "bbox"
        object or another Group, determines if there's an 
        intersection
        """
        if isinstance(y, Group):
            for member in self.members:
                for ymember in y.members:
                    if bbox_intersection(member, ymember):
                        return True
        else:
            for member in self.members:
                if bbox_intersection(member, y):
                    return True
        return False

    def match_dict_ids(self, d):
        #filter dict by IDS
        ids = {member['id'] for member in self.members}
        return {
            k:v
            for k, v in d.items()
            if k in ids
        }

    def summary(self):
        return {
            'n_members': len(self.members),
            'total_distance': np.sum([
                m['distance'] for m in self.members
            ]),
            'median_lat': np.median([
                np.mean(m['bbox']['lat'])
                for m in self.members
            ]),
            'median_long': np.median([
                np.mean(m['bbox']['long'])
                for m in self.members
            ]),
            'n_duplicates': np.sum([
                v-1 for v in
                Counter([m['filename'] for m in self.members]).values()
            ]),
            'long_raster_size': c.RASTER_SIZE_LAT * np.cos(
                np.median([
                    np.mean(m['bbox']['lat'])
                    for m in self.members
                ])
            ),
        }

    def pairwise_iter(self):
        n_groups = len(self.members)
        for i in range(n_groups-1):
            for j in range(i, n_groups):
                yield (self.members[i], self.members[j])

    def print_summary(self):
        try:
            print(json.dumps(self.summary(), indent=2))
        except:
            print((self.summary()))

## TODO: FIGURE OUT WHY FIRST ATTEMPTED MATCH HAS A
## STRING AS THE FIRST MEMBER ARGUMENT (WHICH IS A RANDOM
## KEY FROM THE METADATA SUBDICTIONARIES, E.G., "bbox",
## "distance"
class GroupProcessor:
    def __init__(
            self,
            groups=None,
            metadata=None,
            debug=False
    ):
        self.debug = debug
        if groups is None:
            self.groups = []
        else:
            self.groups = groups

        if metadata is not None:
            logger.info('Initializing GroupProcessor from metadata')
            for v in metadata.values():
                self.add_member(v)
                
            while self.merge_groups():
                pass

    def pairwise_group_iter(self):
        for group in self.groups:
            for member1, member2 in group.pairwise_iter():
                yield member1, member2

    def set_group_attributes(self):
        for group in self.groups:
            group.set_attributes()
            

    def add_group(self, group):
        #logger.debug('Adding group to processor')
        self.groups.append(group)

    def add_member(self, member):
        if member is None:
            logger.error('MEMBER IS NONE')
            raise ValueError('MEMBER IS NONE')
        if self.debug:
            logger.debug(member['filename'])
        #logger.debug('Adding member to processor')
        added=False
        for group in self.groups:
            if group.intersect(member):
                group.add_member(member)
                added=True
                break
        if not added:
            self.add_group(Group([member]))

    def merge_groups(self):
        """
        iteratively merges groups together until no more merges
        can be made
        """
        if len(self.groups) <= 1:
            return 0
        halt = False
        n_groups = len(self.groups)
        group_idx = 0
        n_merges = 0
        merge_iter = 0
        logger.debug('Merging groups')
        while not halt:
            merge_iter += 1
            main_group = self.groups[group_idx]
            loop_change = False
            for i in range(n_groups - 1, group_idx, -1):
                try:
                    if main_group.intersect(self.groups[i]):
                        main_group += self.groups.pop(i)
                        n_groups -= 1
                        loop_change=True
                        n_merges += 1
                except AttributeError as e:
                    #print(self.groups)
                    logger.error(
                        'ATTRIBUTE ERROR: (g_idx, n_g, i, n_merges) '
                        '(%s, %s, %s, %s)' % (
                            n_groups,
                            group_idx,
                            i,
                            n_merges
                        )
                    )
                    raise e
            
            if n_groups == 1:
                logger.debug('Halting because n_groups = 1')
                halt=True
            elif group_idx == n_groups - 1:
                logger.debug('Halting because group index has reached max')
                halt=True
            elif not loop_change:
                group_idx += 1
            if self.debug:
                logger.debug('Merge iter %d' % merge_iter)

        if self.debug:
            logger.debug('Made %d merges' % n_merges)

        self.set_group_attributes()

        return n_merges

    def print_group_sizes(self):
        logger.info(
            [len(g.members) for g in self.groups]
        )

    def overall_group_summary(self):
        group_summaries = [
            g.summary() for g in self.groups
        ]
        return {
            'n_groups': len(self.groups),
            'n_duplicates': sum(
                [
                    s['n_duplicates'] for s in group_summaries
                ]
            )
        }
        
                
def test():
    eps = 1e-6
    TEST_DATA = {
        'a': {
            'bbox': {'lat': (0,1), 'long': (0,1)},
            'distance': 3,
            'filename': 'a',
        },
        'b': {
            'bbox': {'lat': (0.1,0.9), 'long': (0.1,0.9)},
            'distance': 4,
            'filename': 'b'
        },
        'c': {
            'bbox': {'lat': (2,3), 'long': (4,5)},
            'distance': 100,
            'filename':'c',
        },
        'd': {
            'bbox': {'lat': (-1,2),'long': (6,7)},
            'distance': 20,
            'filename': 'd',
        },
        'e': {
            'bbox': {'lat': (2,3), 'long': (2,3)},
            'distance': 50,
            'filename': 'e',
        },
        'f': {
            'bbox': {'lat': (0.5, 4), 'long': (0.5, 4)},
            'distance': 200,
            'filename':'f',
        },
    }

    logger.info('TEST MODE')
    gp = GroupProcessor(metadata=TEST_DATA, debug=True)

    gp.print_group_sizes()
    logger.debug(gp.overall_group_summary())
    

            
    

if __name__ == '__main__':
    test()
                
