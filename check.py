#!/usr/bin/env python3
from config import IGNORED 

from itertools import groupby
import logging
from sys import argv

import icalendar

def main():
    path = argv[1]

    data = None
    with open(path, 'rb') as fo:
        data = fo.read()
    cal = icalendar.Calendar.from_ical(data)

    key = lambda c: str(c['SUMMARY'])
    groups = {}
    for k, g in groupby(sorted(cal.walk('VTODO'), key=key), key=key):
        group = list(g)
        groups[k] = group

    susp = []
    for k, g in sorted(groups.items()):
        if k in IGNORED:
            logging.info(k + " is ignored, skipping...")
            continue

        if len(g) <= 1: # probably not repeating
            continue

        suspicious = 0
        for c in g:
            # TODO how to skip subtasks?
            if 'STATUS' in c and str(c['STATUS']) == 'COMPLETED':
                suspicious += 1
            elif 'DUE' not in c:
                suspicious += 1

        if len(g) == suspicious:
            susp.append('"{}",'.format(k))
            logging.error(k)

    print("Suspicious (for quick add):")
    for s in susp:
        print(s)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        import coloredlogs
        coloredlogs.install(fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s")
        coloredlogs.set_level(logging.INFO)
    except ImportError:
        logging.info("Install coloredlogs for fancy colored logs!")
    logging.basicConfig(level=logging.DEBUG)
    main()
