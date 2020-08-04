import logging
import random

#used for processing these intervals
def urand(tup):
    return random.uniform(tup[0],tup[1])


class CStreamHandler(logging.StreamHandler):
    
    def format(self, record):
        msg = super().format(record)
        color_prefix = {
            10: '0',
            20: '1;36',
            30: '1;33',
            40: '1;31',
            50: '1;37;41',
        }[record.levelno]

        msg = '\x1b[%sm%s\x1b[0m' % (color_prefix, msg)
        
        return msg
        
    


class Clogger(object):
    idx = 0
    def __init__(
            self,
            filename='default.log'
        ):
        Clogger.idx+=1
        self.filename=filename

        self.logger = logging.getLogger('logger_%d' % Clogger.idx)
        self.logger.setLevel(logging.DEBUG)
        sh = CStreamHandler()
        fh = logging.FileHandler(filename)
        formatter = logging.Formatter(
            '[%(levelname)s] %(asctime)s - %(message)s',
            '%Y-%m-%d %H:%M:%S',
        )

        sh.setFormatter(formatter)
        fh.setFormatter(formatter)

        self.logger.addHandler(sh)
        self.logger.addHandler(fh)
        

    def __getattr__(self, *args, **kwargs):
        return getattr(self.logger, *args, **kwargs)


def diamond_generator(n):
    return {
         (c1*(n-i), i*c2) for i in range(n+1)
        for c1 in [1,-1]
        for c2 in [1,-1]
    }
