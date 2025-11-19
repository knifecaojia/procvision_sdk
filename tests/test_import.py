def test_import():
    from procvision_algorithm_sdk import BaseAlgorithm, Session

    assert Session("s").id == "s"

    class A(BaseAlgorithm):
        def get_info(self):
            return {}

        def pre_execute(self, step_index, session, shared_mem_id, image_meta, user_params):
            return {"status": "OK"}

        def execute(self, step_index, session, shared_mem_id, image_meta, user_params):
            return {"status": "OK"}

    a = A("pid")
    assert a.pid == "pid"