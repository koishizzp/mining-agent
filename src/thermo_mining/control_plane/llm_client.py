def _load_openai_client():
    from openai import OpenAI

    return OpenAI


class OpenAIPlannerClient:
    def __init__(self, model: str, api_key: str | None, base_url: str | None) -> None:
        openai_client = _load_openai_client()
        self.client = openai_client(api_key=api_key, base_url=base_url)
        self.model = model

    def plan(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.output[0].content[0].json
