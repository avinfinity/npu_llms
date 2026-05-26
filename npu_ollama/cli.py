import argparse
import json
import os
import socket
import sys
import subprocess
from urllib.request import Request,urlopen

from .store import (
    pull_model,
    remove_model,
    installed_models
)

from .networking import (
    DEFAULT_HOST,
    resolve_port,
    base_url
)

HOST = DEFAULT_HOST
PORT = resolve_port()


def url():

     return base_url(HOST,PORT)


def post(path,payload):

    req=Request(

        url()+path,
        data=json.dumps(payload).encode(),
        headers={

            "Content-Type":
            "application/json"

        }

    )

    with urlopen(req) as r:

        return json.loads(
            r.read()
        )


def run(model,prompt,device):

    os.environ["NPU_MODEL"]=model
    os.environ["NPU_DEVICE"]=device

    if prompt:

        response=post(

            "/api/chat",

            {

                "model":model,

                "messages":[

                    {

                        "role":"user",
                        "content":prompt

                    }

                ]

            }

        )

        print(

            response["message"]["content"]
        )

        return

    print(
        "Enter /bye to exit"
    )

    while True:

        q=input(">>> ")

        if q in {

            "/bye",
            "/exit"
        }:

            return

        response=post(

            "/api/chat",

            {

                "model":model,

                "messages":[

                    {

                        "role":"user",
                        "content":q

                    }

                ]
            }
        )

        print(
            response["message"]["content"]
        )


def serve():

    import uvicorn

    uvicorn.run(

        "npu_ollama.api:app",

        host=HOST,
        port=PORT
    )


def main():

    p=argparse.ArgumentParser()

    sub=p.add_subparsers(
        dest="cmd"
    )

    sub.add_parser(
        "serve"
    )

    l=sub.add_parser(
        "list"
    )

    pull=sub.add_parser(
        "pull"
    )

    pull.add_argument(
        "model"
    )

    rm=sub.add_parser(
        "rm"
    )

    rm.add_argument(
        "model"
    )

    run_parser=sub.add_parser(
        "run"
    )

    run_parser.add_argument(
        "model"
    )

    run_parser.add_argument(
        "prompt",
        nargs="?"
    )

    run_parser.add_argument(
        "--device",
        default="NPU",
        choices=[
            "NPU",
            "GPU"
        ]
    )

    args=p.parse_args()

    if args.cmd=="serve":

        serve()

    elif args.cmd=="list":

        for m in installed_models():

            print(
                m["name"]
            )

    elif args.cmd=="pull":

        print(
            pull_model(
                args.model
            )
        )

    elif args.cmd=="rm":

        remove_model(
            args.model
        )

    elif args.cmd=="run":

        run(
            args.model,
            args.prompt,
            args.device
        )


if __name__=="__main__":

    main()