#! /usr/bin/env python
"""
Use this file to strip the list of DVM parameters read by the package when
connecting to the control system plugin.

Usage:
    ./strip_csv.py DVM-Parameter_v2.10.0-HIT.csv >hit_csys/DVM-Parameter.csv


WHITELIST = (
    'kl_',
    'ax_',
    'ay_',
    'dax_',
    'dax_',
    'axgeo_',
    'aygeo_',
    'e_',
    'a0_',
    'a_',
    'z_',
    'q_',
)


def is_whitelisted(p):
    return any(map(p.startswith, WHITELIST))


def main(csv_file):
    with open(csv_file, 'rb') as f:
        lines = f.read().decode('utf-8').splitlines()

    lines = [line for line in lines
             if is_whitelisted(line.split(';')[1].lower())]

    print("\n".join(lines))


if __name__ == '__main__':
    import sys; sys.exit(main(*sys.argv[1:]))
