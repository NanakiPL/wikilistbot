# -*- coding: utf-8  -*-
import sys

def progressBar(percentage, label = 'Progress'):
    bar = ' '* max(20, 70-len(label))

    filled = min(len(bar), int(len(bar) * percentage))

    sys.stdout.write('{}: [{}] {:.1%}\r'.format(label, '#'*filled + bar[filled:], percentage))
    sys.stdout.flush()