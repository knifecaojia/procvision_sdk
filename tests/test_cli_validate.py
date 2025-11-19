import json
import os

from procvision_algorithm_sdk.cli import validate


def test_validate_sample_pass():
    """Test that validates the sdk_sample algorithm correctly"""
    sample = os.path.abspath("sdk_sample")
    report = validate(project=sample, manifest=None, zip_path=None)
    assert report["summary"]["status"] == "PASS", f"Validation failed with: {json.dumps(report, indent=2)}"
