import unittest
from unittest.mock import Mock
from solidworks_mcp.diagnostics.resource_wait import same_live_process


class LiveProcessIdentityTests(unittest.TestCase):
    def test_exited_process_is_not_live_even_if_its_object_still_exists(self):
        created=Mock(return_value=100)
        self.assertFalse(same_live_process('handle',100,wait=lambda h,t:0,created=created))
        created.assert_not_called()

    def test_live_matching_identity(self):
        self.assertTrue(same_live_process('handle',100,wait=lambda h,t:258,created=lambda h:100))

    def test_live_reused_pid_is_not_the_owned_identity(self):
        self.assertFalse(same_live_process('handle',100,wait=lambda h,t:258,created=lambda h:200))

    def test_wait_failure_does_not_claim_process_exited(self):
        with self.assertRaises(RuntimeError):
            same_live_process('handle',100,wait=lambda h,t:0xffffffff,created=lambda h:100)
