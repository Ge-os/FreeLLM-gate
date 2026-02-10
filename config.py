# import pydantic
# from pydantic.v1 import BaseSettings
# import os
# from dotenv import load_dotenv


# class Settings(BaseSettings):
#     DATABASE_PORT: int
#     POSTGRES_PASSWORD: str
#     POSTGRES_USER: str
#     POSTGRES_DB: str
#     POSTGRES_HOST: str
#     POSTGRES_HOSTNAME: str

#     JWT_PUBLIC_KEY: str
#     JWT_PRIVATE_KEY: str
#     REFRESH_TOKEN_EXPIRES_IN: int
#     ACCESS_TOKEN_EXPIRES_IN: int
#     JWT_ALGORITHM: str

#     CLIENT_ORIGIN: str
#     OPENAI_API_KEY: str

#     class Config:
#         env_file = r'.env'


# load_dotenv()
# API_KEY = os.environ.get("OPENAI_API_KEY")
# CLIENT_ID = os.environ.get('client-id', None)
# CLIENT_SECRET = os.environ.get('client-secret', None)
# settings = Settings()
