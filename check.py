#!/usr/bin/env python3
from config import IGNORED 

from itertools import groupby
import logging

import icalendar

def main():
    # TODO get last
    data = None
    # TODO get ical which was latest?
    with open('rtm_2017-06-05.ical', 'rb') as fo:
        data = fo.read()
    cal = icalendar.Calendar.from_ical(data)

    key = lambda c: str(c['SUMMARY'])
    groups = {}
    for k, g in groupby(sorted(cal.walk('VTODO'), key=key), key=key):
        group = list(g)
        groups[k] = group

    for k, g in sorted(groups.items(), key=lambda p: len(p[1])):
        statuses = []
        for c in g:
            status = "???" if ('STATUS' not in c) else str(c['STATUS'])
            statuses.append(status)

        if k in IGNORED:
            # TODO log
            logging.info(k + " is ignored, skipping...")
            continue
    
        if len(statuses) <= 1: # probably not repeating
            continue
    
        if all([s == 'COMPLETED' for s in statuses]):
            print(k, statuses)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
