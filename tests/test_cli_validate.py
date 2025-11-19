import json
import os

from procvision_algorithm_sdk.cli import validate


def test_validate_sample_pass():
    here = os.path.dirname(__file__)
    sample = os.path.abspath(os.path.join(here, "..", "..", "sdk_sample"))
    report = validate(project=sample, manifest=None, zip_path=None)
    assert report["summary"]["status"] == "PASS"