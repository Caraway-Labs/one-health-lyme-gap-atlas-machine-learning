"""Run the fixed four-request public CDC research probe, without source extracts."""

import argparse
import json

from lyme_gap_atlas_ml.alternative_label_sources import research_alternative
from lyme_gap_atlas_ml.label_feasibility import research, research_pa

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pa", action="store_true", help="One bounded official PA workbook probe")
    parser.add_argument("--alternative", choices=("wi", "eisen"))
    args = parser.parse_args()
    result = (
        research_alternative(args.alternative)
        if args.alternative
        else (research_pa() if args.pa else research())
    )
    print(json.dumps(result, indent=2))
