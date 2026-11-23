"""Check the original gate hook used by the frozen report adapter."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from langchain_core.messages import ToolMessage
from autoresearch_agent_langchain.middleware import InvocationContext
from runtime_adapter import UploadedReportGate


class ReportStateTests(unittest.TestCase):
    def test_new_evidence_invalidates_saved_report_in_gate_hook(self):
        # The normal runtime disables tools after a saved report. Inject a late
        # successful evidence result directly into the actual gate hook to test
        # its stale-state behavior independently of that closeout boundary.
        async def check():
            gate=UploadedReportGate()
            context=InvocationContext(run_id='fixture',thread_id='fixture',model_calls=2,metadata={})
            state=gate._state(context);state['report_content']='Saved prior report'
            request=SimpleNamespace(runtime=SimpleNamespace(context=context),state={'messages':[]},
                tool_call={'name':'retrieve_uploaded_documents','id':'late-source','args':{}})
            async def handler(_):
                return ToolMessage(content='New retrieved evidence',tool_call_id='late-source',
                                   name='retrieve_uploaded_documents',status='success')
            await gate.awrap_tool_call(request,handler)
            self.assertIsNone(state['report_content'])
            self.assertTrue(state['report_invalidated'])
            self.assertTrue(any(e.get('action')=='report_gate_report_invalidated' for e in context.observations))
        asyncio.run(check())


if __name__=='__main__':unittest.main()
