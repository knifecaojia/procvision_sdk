def test_import():
    from procvision_algorithm_sdk import BaseAlgorithm, Session

    assert Session("s").id == "s"

    class A(BaseAlgorithm):
        def execute(self, step_index, step_desc, cur_image, guide_image, guide_info):
            return {"status": "OK", "data": {"result_status": "OK", "defect_rects": []}}

    a = A()
    assert isinstance(a, BaseAlgorithm)
