# SPDX-License-Identifier: Apache-2.0
'''
Utility to collect all instances of MPIX_REGISTER_[...] and turn it into a list.

This saves from the need to manually maintain lists of operations through the libmpix source and
allow the user to add elements to the list without modifying the libmpix source.
'''

import os
import sys
import re


def add_match(symbols: dict, category: str, line: str) -> None:
    '''
    Append the match found to the symbol table
    '''
    if category not in symbols:
        symbols[category] = []

    p = re.compile('\\(\\s*(\\w+)\\s*[,\\)]')
    m = p.match(line)

    if m is None:
        raise Exception(f'-- Warning: expected "(<id>)" or "(<id>, ...", not {line}')

    symbols[category].append(m.group(1))


def scan_file(symbols: dict, path: str) -> None:
    '''
    Aggregate all the matches found in the path and add them to the symbols table.
    '''
    with open(path) as f:
        p = re.compile('MPIX_REGISTER_(\\w+)')

        for line in f:
            m = p.match(line)

            if m is not None:
                add_match(symbols, m.group(1), line[m.end():])


def generate_list(symbols: dict) -> None:
    '''
    Turn the table of aggregated symbols and categories into C source
    '''
    print(f'/* Generated with {sys.argv[0]} */')
    for category in sorted(symbols.keys()):
        print('')
        print(f'#define MPIX_LIST_{category} \\')

        for symbol in symbols[category]:
            print(f'\t&mpix_{category.lower()}_{symbol}, \\')
        print(f'\tNULL')


def main():
    symbols = {}

    for path in sys.argv[1:]:
        scan_file(symbols, path)

    generate_list(symbols)


if __name__ == '__main__':
    main()
