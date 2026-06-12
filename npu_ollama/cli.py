import argparse
import json
import os
import sys
import threading
import time
import webbrowser
from urllib.request import Request,urlopen

from . import server
from .store import (
    pull_model,
    remove_model,
    installed_models
)

from .networking import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    FALLBACK_PORT,
    env_port,
    resolve_port,
    base_url
)

HOST = DEFAULT_HOST


def url():

     return base_url(HOST)


def candidate_ports(port=None):

    if port is not None:

        return [
            port
        ]

    ports = []
    env = env_port()

    if env is not None:

        ports.append(env)

    ports.extend(
        [
            DEFAULT_PORT,
            FALLBACK_PORT
        ]
    )

    return list(
        dict.fromkeys(ports)
    )


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

    server.serve(
        host=HOST,
        port=None
    )


def is_server_ready(host, port):

    try:

        with urlopen(
            f"http://{host}:{port}/health",
            timeout=.5
        ) as response:

            return response.status == 200

    except Exception:

        return False


def resolve_chat_port(host, port=None):

    for candidate in candidate_ports(port):

        if is_server_ready(
            host,
            candidate
        ):

            return candidate

    return resolve_port(
        host,
        port
    )


def chat(model=None, device="NPU", host=HOST, port=None, open_browser=True):

    os.environ["NPU_DEVICE"] = device

    if model:

        os.environ["NPU_MODEL"] = model

    port = resolve_chat_port(
        host,
        port
    )

    chat_url = f"http://{host}:{port}/chat"

    if model:

        chat_url = f"{chat_url}?model={model}"

    if is_server_ready(host, port):

        if open_browser:

            webbrowser.open(chat_url)

        print(chat_url)
        return 0

    def open_when_ready():

        for _ in range(60):

            if is_server_ready(host, port):

                if open_browser:

                    webbrowser.open(chat_url)

                print(chat_url)
                return

            time.sleep(.25)

    threading.Thread(
        target=open_when_ready,
        daemon=True
    ).start()

    server.serve(
        host=host,
        port=port
    )

    return 0


def main(argv=None):

    p=argparse.ArgumentParser()

    sub=p.add_subparsers(
        dest="cmd"
    )

    serve_parser=sub.add_parser(
        "serve"
    )

    serve_parser.add_argument(
        "--host",
        default=HOST
    )

    serve_parser.add_argument(
        "--port",
        type=int
    )

    start_parser=sub.add_parser(
        "start"
    )

    start_parser.add_argument(
        "--host",
        default=HOST
    )

    start_parser.add_argument(
        "--port",
        type=int
    )

    chat_parser=sub.add_parser(
        "chat"
    )

    chat_parser.add_argument(
        "model",
        nargs="?"
    )

    chat_parser.add_argument(
        "--device",
        default="NPU",
        choices=[
            "NPU",
            "GPU"
        ]
    )

    chat_parser.add_argument(
        "--host",
        default=HOST
    )

    chat_parser.add_argument(
        "--port",
        type=int
    )

    chat_parser.add_argument(
        "--no-browser",
        action="store_true"
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

    args=p.parse_args(argv)

    if args.cmd in {
        "serve",
        "start"
    }:

        server.serve(
            host=args.host,
            port=args.port
        )

        return 0

    elif args.cmd=="chat":

        return chat(
            args.model,
            args.device,
            args.host,
            args.port,
            not args.no_browser
        )

    elif args.cmd=="list":

        for m in installed_models():

            print(
                m["name"]
            )

        return 0

    elif args.cmd=="pull":

        print(
            pull_model(
                args.model
            )
        )

        return 0

    elif args.cmd=="rm":

        remove_model(
            args.model
        )

        return 0

    elif args.cmd=="run":

        run(
            args.model,
            args.prompt,
            args.device
        )

        return 0

    p.print_help()
    return 1


if __name__=="__main__":

    main()
