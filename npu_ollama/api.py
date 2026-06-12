import os
import json
import time
from importlib.resources import files
from datetime import datetime, timezone
from typing import Optional,List,Dict,Any

from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse,RedirectResponse,StreamingResponse
from pydantic import BaseModel,Field

from .llm import get_llm
from .store import installed_models

app=FastAPI(
    title="NPU Ollama API"
)


def static_file(name):

    return files(
        "npu_ollama.static"
    ).joinpath(
        name
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

    normalized = dict(options)

    if "num_predict" in normalized:

        normalized[
            "max_new_tokens"
        ] = normalized.pop(
            "num_predict"
        )

    return {

        k:v
        for k,v
        in normalized.items()
        if k in allowed
    }


def chat_prompt(messages):

    lines = [
        f"{message.role}: {message.content}"
        for message in messages
    ]

    lines.append(
        "assistant:"
    )

    return "\n".join(
        lines
    )


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

                yield json.dumps(
                    {
                        "response":token,
                        "done":False
                    }
                ) + "\n"

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

    prompt=chat_prompt(
        request.messages
    )

    options=generation_options(
        request.options
    )

    if request.stream:

        def stream():

            for token in llm.stream_generate(
                prompt,
                **options
            ):

                yield json.dumps(
                    {
                        "message":{
                            "role":"assistant",
                            "content":token
                        },
                        "done":False
                    }
                ) + "\n"

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


@app.get("/")
def index():

    return RedirectResponse(
        "/chat"
    )


@app.get("/chat")
def chat_ui():

    return FileResponse(
        static_file("chat.html")
    )
