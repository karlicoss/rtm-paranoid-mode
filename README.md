Has it ever occured to you that you accidentally messed up a due date or deleted a repeating task in RTM, and ended up forgeting about this piece of routine forever? Well, no more! This script tracks the tasks which stopped repeating so you can review them carefully and explicitly mark as stopped.

The only thing you're gonna need is an RTM .ical export file.

# Usage
    
    cp config.py.example config.py
    python3 check.py path_to_rtm_export.ical

Then, update `config.py` with ignored tasks occasionally.

# Prerequisites
See `requirements.txt`
