def test_import():
    from procvision_algorithm_sdk import BaseAlgorithm, Session

    assert Session("s").id == "s"

    class A(BaseAlgorithm):
        def get_info(self):
            return {}
        def pre_execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
            return {"status": "OK", "message": "准备就绪"}
        def execute(self, step_index, pid, session, user_params, shared_mem_id, image_meta):
            return {"status": "OK", "data": {"result_status": "OK"}}

    a = A()
    assert isinstance(a, BaseAlgorithm)