from devboard.agents.system_message_tags import (
    SystemMessageBlock,
    extract_system_messages,
    wrap_system_message,
)


class TestWrapSystemMessage:
    def test_basic_wrap(self):
        result = wrap_system_message("hello world", "initial_context")
        assert result == '<system_message type="initial_context">\nhello world\n</system_message>'

    def test_empty_content(self):
        result = wrap_system_message("", "initial_context")
        assert result == '<system_message type="initial_context">\n\n</system_message>'

    def test_multiline_content(self):
        content = "line one\nline two\nline three"
        result = wrap_system_message(content, "my_type")
        assert result == f'<system_message type="my_type">\n{content}\n</system_message>'


class TestExtractSystemMessages:
    def test_no_blocks(self):
        blocks, remaining = extract_system_messages("just plain text")
        assert blocks == []
        assert remaining == "just plain text"

    def test_single_block(self):
        text = '<system_message type="initial_context">\nsome context\n</system_message>'
        blocks, remaining = extract_system_messages(text)
        assert len(blocks) == 1
        assert blocks[0] == SystemMessageBlock(message_type="initial_context", content="some context")
        assert remaining == ""

    def test_block_with_remaining_text(self):
        text = '<system_message type="initial_context">\ncontext here\n</system_message>\n\nActual user message'
        blocks, remaining = extract_system_messages(text)
        assert len(blocks) == 1
        assert blocks[0].content == "context here"
        assert remaining == "Actual user message"

    def test_multiple_blocks(self):
        text = (
            '<system_message type="initial_context">\nfirst\n</system_message>\n'
            '<system_message type="task_spec_updated">\nsecond\n</system_message>'
        )
        blocks, remaining = extract_system_messages(text)
        assert len(blocks) == 2
        assert blocks[0] == SystemMessageBlock(message_type="initial_context", content="first")
        assert blocks[1] == SystemMessageBlock(message_type="task_spec_updated", content="second")
        assert remaining == ""

    def test_block_with_nested_xml(self):
        content = "<some_tag>value</some_tag>\n<another>stuff</another>"
        text = f'<system_message type="initial_context">\n{content}\n</system_message>'
        blocks, _ = extract_system_messages(text)
        assert len(blocks) == 1
        assert blocks[0].content == content

    def test_empty_content_block(self):
        text = '<system_message type="initial_context"></system_message>'
        blocks, _ = extract_system_messages(text)
        assert len(blocks) == 1
        assert blocks[0].content == ""

    def test_roundtrip_wrap_and_extract(self):
        content = "some important context\nwith multiple lines"
        wrapped = wrap_system_message(content, "initial_context")
        blocks, remaining = extract_system_messages(wrapped)
        assert len(blocks) == 1
        assert blocks[0].message_type == "initial_context"
        assert blocks[0].content == content
        assert remaining == ""

    def test_block_with_remaining_user_message(self):
        context = wrap_system_message("project context", "initial_context")
        full_text = f"{context}\n\nWhat is the status of this project?"
        blocks, remaining = extract_system_messages(full_text)
        assert len(blocks) == 1
        assert blocks[0].content == "project context"
        assert remaining == "What is the status of this project?"
