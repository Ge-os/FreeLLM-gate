#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

import uvicorn
from fastapi.middleware.cors import CORSMiddleware

import logging
from fastapi import FastAPI

log = logging.getLogger("uvicorn")


def main():
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["localhost"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Authorization"],
    )
    from config import get_config
    settings = get_config()
    uvicorn.run("app.main:app", host=settings.BASE_URL, port=settings.PORT, reload=True)


if __name__ == '__main__':
    main()
