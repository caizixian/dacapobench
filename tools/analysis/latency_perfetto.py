#!/usr/bin/env python3
"""
Visualizing the DaCapo latency CSV dumps using Perfetto UI

Usage: ./tools/analysis/latency_perfetto.py /path/scratch/dacapo-latency-usec-simple-<n>.csv [/path/scratch/dacapo-latency-usec-metered-100ms-smoothing-<n>.csv /path/scratch/dacapo-latency-usec-metered-full-smoothing-<n>.csv]

The output .json.gz file can be visualized on https://ui.perfetto.dev/
Each request is shown as a slice.
The number of finished request for each thread over time is shown as a counter.

positional arguments:
  input            Path to one or more latency CSVs

optional arguments:
  -h, --help       show this help message and exit
  --output OUTPUT  Output path
"""
import json
import gzip
from collections import defaultdict
import argparse


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", help="Output path", default="dacapo-latency.json.gz", type=str
    )
    parser.add_argument("input", nargs="+", help="Path to one or more latency CSVs")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    latency_csv_paths = args.input
    events = []
    for p in latency_csv_paths:
        with open(p) as fd:
            if "simple" in p:
                event_suffix = ""
            elif "metered-100ms-smoothing" in p:
                event_suffix = " 100ms metered"
            elif "metered-full-smoothing" in p:
                event_suffix = " fully metered"
            else:
                raise ValueError("Unsupported latency dump file")
            lines = fd.readlines()
            # Record end timestamps to be sorted later
            # For metered latency, events starting earlier might finish later
            end_timestamps_per_thread = defaultdict(list)
            for line in lines:
                parts = line.split(",")
                start = int(parts[0])
                end = int(parts[1])
                tid = int(parts[2])

                end_timestamps_per_thread[tid].append(end)

                if start == 0 and end == 0:
                    continue
                # Request as slices
                # Skip metered latencies as slices would overlap
                if "simple" in p:
                    events.append(
                        {
                            "name": "Req{}".format(event_suffix),
                            "ph": "X",
                            "ts": start,
                            "dur": end - start,
                            "pid": 0,
                            "tid": tid,
                        }
                    )
            for tid, end_timestamps in end_timestamps_per_thread.items():
                sorted_end_timestamps = sorted(end_timestamps)
                for smooth in [1, 16, 256]:
                    i = 0
                    while i < len(sorted_end_timestamps):
                        events.append(
                            {
                                "name": "t{}".format(tid, smooth),
                                "ph": "C",
                                "ts": sorted_end_timestamps[i],
                                "pid": 0,
                                "args": {
                                    "requests{} smooth {}".format(
                                        event_suffix, smooth
                                    ): i
                                },
                            }
                        )
                        i += smooth

    events.append(
        {"name": "Process Start", "ph": "i", "ts": 0, "pid": 0, "tid": 0, "s": "p"}
    )
    with gzip.open(args.output, "wt") as fd:
        json.dump(events, fd)


if __name__ == "__main__":
    main()
