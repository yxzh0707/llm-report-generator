import asyncio, json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments.system_comparison import assemble_generic,calculate
from autoresearch_agent_core import AgentInput,MessageRecord
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

class ToolFake(FakeMessagesListChatModel):
    def bind_tools(self,tools,**kwargs):return self

def call(name,args,id):return AIMessage(content='',tool_calls=[dict(name=name,args=args,id=id,type='tool_call')])

class GeneralAgentTests(unittest.TestCase):
    def test_decimal_arithmetic_and_no_code(self):
        self.assertEqual(calculate('(0.1+0.2)*100'),'30.0')
        self.assertEqual(calculate('(120-100)/100*100'),'20.0')
        for s in ["__import__('os').system('id')",'2**10000000','x.y','[1][0]']:
            with self.assertRaises(ValueError):calculate(s)

    def test_generic_agent_reads_full_source_and_saves_without_report_gate(self):
        async def go():
            with tempfile.TemporaryDirectory() as d:
                out=Path(d);text='source '*12000+'TAIL_SENTINEL'
                packet={'uploaded':[dict(document_id='sample',title='Sample',source_url='upload://sample',text=text,source_kind='uploaded')],'web':[]}
                report='Unstructured report with an unsupported amount 999 and no citations.'
                model=ToolFake(responses=[call('retrieve_uploaded_documents',{},'r'),call('calculator',{'expression':'0.1+0.2'},'c'),
                    call('count_words',{'content':report},'l'),call('write_file',{'path':'work/outputs/final_report.md','content':report},'w'),AIMessage(content='Done')])
                runtime,sources=assemble_generic(out,packet,model=model)
                result=await runtime.arun(AgentInput(messages=(MessageRecord(role='user',content='Synthetic harness check.'),)))
                await runtime.aclose()
                self.assertEqual(result.status,'succeeded',result.terminal)
                self.assertEqual((out/'raw_report.md').read_text(),report)
                self.assertEqual(sources[0]['text'],text)
                self.assertFalse((out/'validation_checks.json').exists())
                self.assertFalse((out/'length_checks.json').exists())
                self.assertIn('TAIL_SENTINEL',json.dumps(result.model_dump(mode='json')))
                self.assertNotIn('draft_target',(out/'agent/SKILL.md').read_text())
        asyncio.run(go())

if __name__=='__main__':unittest.main()
