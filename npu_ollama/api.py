import os
import time
from datetime import datetime, timezone
from typing import Optional,List,Dict,Any

from fastapi import FastAPI,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field

from .llm import get_llm
from .store import installed_models

app=FastAPI(
    title="NPU Ollama API"
)


class Message(BaseModel):
    role:str
    content:str


class GenerateRequest(BaseModel):
    model:Optional[str]=None
    prompt:str
    stream:bool=False
    options:Dict[str,Any]=Field(default_factory=dict)


class ChatRequest(BaseModel):
    model:Optional[str]=None
    messages:List[Message]
    stream:bool=False
    options:Dict[str,Any]=Field(default_factory=dict)


def now():

    return datetime.now(
        timezone.utc
    ).isoformat()


def generation_options(options):

    allowed={

        "max_new_tokens",
        "temperature",
        "top_p",
        "repetition_penalty"

    }

    return {

        k:v
        for k,v
        in options.items()
        if k in allowed
    }


@app.get("/health")
def health():

    return {

        "status":"ok"

    }


@app.get("/api/tags")
def tags():

    return {

        "models":[

            {

                "name":m["name"],
                "model":m["name"]

            }

            for m in installed_models()
        ]
    }


@app.post("/api/generate")
def generate(request:GenerateRequest):

    device = os.getenv("NPU_DEVICE", "NPU")

    llm=get_llm(
        request.model,
        device
    )

    options=generation_options(
        request.options
    )

    started=time.time_ns()

    if request.stream:

        def stream():

            for token in llm.stream_generate(
                request.prompt,
                **options
            ):

                yield (

                    f'{{"response":"{token}","done":false}}\n'
                )

            yield (

                '{"done":true}\n'
            )

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson"
        )

    response=llm.generate(
        request.prompt,
        **options
    )

    return {

        "model":llm.model_name,
        "created_at":now(),
        "response":response,
        "done":True,
        "total_duration":
            time.time_ns()-started
    }


@app.post("/api/chat")
def chat(request:ChatRequest):

    if not request.messages:

        raise HTTPException(
            400,
            "messages required"
        )

    device = os.getenv("NPU_DEVICE", "NPU")

    llm=get_llm(
        request.model,
        device
    )

    prompt=request.messages[-1].content

    options=generation_options(
        request.options
    )

    if request.stream:

        def stream():

            for token in llm.stream_generate(
                prompt,
                **options
            ):

                yield (

                    f'{{"message":{{"role":"assistant","content":"{token}"}},"done":false}}\n'
                )

            yield (

                '{"done":true}\n'
            )

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson"
        )

    response=llm.generate(
        prompt,
        **options
    )

    return {

        "model":llm.model_name,

        "message":{

            "role":"assistant",
            "content":response
        },

        "done":True
    }