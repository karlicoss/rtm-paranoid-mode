#!/usr/bin/env python3
from config import IGNORED, BACKUPS_PATH

import logging
import os
import re
from sys import argv

from kython import *

import icalendar # type: ignore
from icalendar.cal import Todo # type: ignore

# TODO extract in a module to parse RTM's ical?
class MyTodo:
    def __init__(self, todo: Todo) -> None:
        self.todo = todo
        self.notes = None
        self.tags = None

    def _init_notes(self):
        desc = self.todo['DESCRIPTION']
        self.notes = re.findall(r'---\n\n(.*?)\n\nUpdated:', desc, flags=re.DOTALL)

    def _init_tags(self):
        desc = self.todo['DESCRIPTION']
        [tags_str] = re.findall(r'\nTags:(.*?)\n', desc, flags=re.DOTALL)
        self.tags = [t.strip() for t in tags_str.split(',')] # TODO handle none?

    def get_notes(self) -> List[str]:
        if self.notes is None:
            self._init_notes()
        return self.notes

    def get_tags(self) -> List[str]:
        if self.tags is None:
            self._init_tags()
        return self.tags

    def get_uid(self) -> str:
        return str(self.todo['UID'])

    def get_title(self) -> str:
        return str(self.todo['SUMMARY'])

    def get_status(self) -> str:
        if 'STATUS' not in self.todo:
            return None # TODO 'COMPLETED'?
        return str(self.todo['STATUS'])

    def get_time(self):
        t1 = self.todo['DTSTAMP'].dt
        t2 = self.todo['LAST-MODIFIED'].dt
        assert t1 == t2 # TODO not sure which one is correct
        return t1

    def is_completed(self) -> bool:
        return self.get_status() == 'COMPLETED'

    def __repr__(self):
        return repr(self.todo)

    def __str__(self):
        return str(self.todo)

    @staticmethod
    def alala_key(mtodo):
        return (mtodo.is_completed(), mtodo.get_time())


class RtmBackup:
    def __init__(self, data: bytes) -> None:
        self.cal = icalendar.Calendar.from_ical(data)

    @staticmethod
    def from_path(path: str) -> 'RtmBackup':
        with open(path, 'rb') as fo:
            data = fo.read()
            return RtmBackup(data)

    def get_all_todos(self) -> List[MyTodo]:
        return [MyTodo(t) for t in self.cal.walk('VTODO')]

    def get_todos_by_uid(self) -> Dict[str, MyTodo]:
        todos = self.get_all_todos()
        res = {todo.get_uid(): todo for todo in todos}
        assert len(res) == len(todos) # hope uid is unique, but just in case
        return res

    def get_todos_by_title(self) -> Dict[str, List[MyTodo]]:
        todos = self.get_all_todos()
        return group_by_key(todos, lambda todo: todo.get_title())


def check_wiped_notes(backups: List[str]):
    def filter_same_alala(todos: List[MyTodo]) -> List[MyTodo]:
        notes = [len(todo.get_notes()) for todo in todos]
        # grouped = group_by_key(todos, lambda n: len(todo.get_notes()))
        if len(notes) > 1:
            if all(notes[0] == i for i in notes):
                todos = [todos[0]]
        return todos

    all_todos = []
    for b in backups:
        backup = RtmBackup.from_path(b)
        all_todos.extend(backup.get_all_todos())

    # first, let tasks with same titles or uids be in the same class. (if we rename a task, it retains UID)
    cur_key = 0
    uid_key = {}
    title_key = {}
    kk_map = {} # type: Dict[int, List[MyTodo]]
    for todo in all_todos:
        uid = todo.get_uid()
        title = todo.get_title()
        kk = None
        if uid in uid_key:
            kk = uid_key.get(uid)
        elif title in title_key:
            kk = title_key.get(title)
        else:
            kk = cur_key
            cur_key += 1
            uid_key[uid] = kk
            title_key[title] = kk
        # ok, kk is set
        ll = kk_map.get(kk, [])
        ll.append(todo)
        kk_map[kk] = ll

    kk2_map = {}
    for kk, todos in sorted(kk_map.items()):
        # within each group, notes that have same number of notes, are equivalent
        todos = filter_same_alala(todos)
        todos = [t for t in todos if not t.is_completed()] # TODO FIXME THIS IS ONLY TEMPORARY?
        kk2_map[kk] = todos

    kk_map = kk2_map

    def has_safe_note(todo: MyTodo) -> bool:
        notes = todo.get_notes()
        for note in notes:
            if 'is_safe' in note:
                return True
        return False

    def has_safe_tag(todos: List[MyTodo]) -> bool:
        all_tags = set.union(*(set(todo.get_tags) for todo in todos))
        return 'z_dn_safe' in all_tags

    def boring(todos: List[MyTodo]) -> bool:
        if len(todos) <= 1:
            return True

        counts = [len(todo.get_notes()) for todo in todos]

        if counts.count(counts[0]) == len(counts):
            return True

        if all(a <= b for a, b in zip(counts, counts[1:])):
            # increasing
            return True

        for tags in [todo.get_tags() for todo in todos]:
            if 'routine' in tags: # TODO FIXME 'safe' tag. If a task has it in ANY of the backups, it is considered safe. tag is better for completed
                return True

        # good thing about safe note is if it disappears, we'll notice it! 
        if has_safe_note(todos[-1]):
            return True

        return False

    for kk, todos in sorted(kk_map.items()):
        # TODO sorts by 1) competion 2) modified date
        todos = sorted(todos, key = MyTodo.alala_key)
        if not boring(todos):
            for todo in todos:
                logging.error("{} {} {}".format(todo.get_title(), todo.get_uid(), todo.get_notes()))


def are_suspicious(l: List[MyTodo]) -> bool:
    if len(l) <= 1: # probably not repeating
        return False

    all_tags = set.union(*(set(todo.get_tags()) for todo in l))
    if 'z_ac_safe' in all_tags:
        return False

    suspicious = 0
    for c in l:
        if c.is_completed():
            suspicious += 1
        elif 'DUE' not in c.todo:
            suspicious += 1

    return len(l) == suspicious

def check_accidentally_completed(path: str):
    backup = RtmBackup.from_path(path)

    groups = backup.get_todos_by_title()

    susp = []
    for k, g in sorted(groups.items()):
        if k in IGNORED:
            logging.info(k + " is ignored, skipping...")
            continue

        if are_suspicious(g):
            susp.append('"{}",'.format(k))
            logging.error(k)

    if len(susp) > 0:
        print("Suspicious:")
        for s in susp:
            print(s)
    else:
        print("Nothing suspicious!")


def main():
    def extract_date(s: str):
        s = s[len(BACKUPS_PATH + "/rtm_"):-4]
        s = s.replace('_', '-')
        return parse_date(s)

    backups = sorted([os.path.join(BACKUPS_PATH, p) for p in os.listdir(BACKUPS_PATH) if p.endswith('ical')], key=extract_date)
    last_backup = backups[-1]

    check_accidentally_completed(last_backup)
    logging.info("Using " + last_backup + " for checking for accidentally completed notes")

    backups = backups[:-1:5] + [backups[-1]] # always include last # TODO FIXME USE ALL?
    logging.info("Using {} for checking for wiped notes".format(backups))

    check_wiped_notes(backups)


if __name__ == '__main__':
    setup_logging()
    main()
