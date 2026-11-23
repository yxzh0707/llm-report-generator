"""Persist a fake-model run through the actual runtime, never a quality result."""
import asyncio
import json
from pathlib import Path
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from phase1_request_policy import required_headings
from run_report import run
from runtime_adapter import REPORT_PATH


class ToolFake(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def call(name, args, identity):
    return AIMessage(content='', tool_calls=[{'name': name, 'args': args, 'id': identity, 'type': 'tool_call'}])


async def main():
    config = {'purpose': 'offline_contract_only', 'request': {'task': 'Summarise fixture data center revenue'},
              'corpus_root': str(Path('tests/fixtures/documents').resolve()),
              'document_ids': ['a', 'b'], 'queries': ['data center revenue risks']}
    report = '\n\n'.join('## '+h+'\n\nFixture data center revenue [S1] [S2].'
                         for h in required_headings('standard_analysis'))
    model = ToolFake(responses=[call('retrieve_uploaded_documents', {}, 'r'),
        call('write_file', {'path': REPORT_PATH, 'content': report}, 'w'),
        AIMessage(content=report, response_metadata={'finish_reason': 'stop'})])
    return await run(config, fake_model=model)


if __name__ == '__main__':
    asyncio.run(main())
