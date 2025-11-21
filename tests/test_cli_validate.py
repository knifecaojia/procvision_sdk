import json
import os

from procvision_algorithm_sdk.cli import validate


def test_validate_handles_missing_manifest():
    tmp = os.path.abspath("non_existing_project_dir")
    report = validate(project=tmp, manifest=None, zip_path=None)
    assert report["summary"]["status"] == "FAIL"
