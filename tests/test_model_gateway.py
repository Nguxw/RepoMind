import pytest

from packages.model_gateway import MockModelClient, create_model_client


@pytest.mark.asyncio
async def test_mock_model_client_generates_text_and_json():
    client = MockModelClient()

    text = await client.generate_text([{"role": "user", "content": "question: where is main?"}])
    payload = await client.generate_json([{"role": "user", "content": "page: Overview"}], schema={})

    assert "citations" in text.lower()
    assert payload["title"] == "Overview"
    assert payload["sections"]
    assert client.usage_since(0).input_tokens > 0


def test_model_factory_defaults_to_mock():
    client = create_model_client("mock")

    assert isinstance(client, MockModelClient)
