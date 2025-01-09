from dl.utils import data, openai_call_embedding, Doc, parse_docx, write_data, search_chunk, green, init, openai_call_completion, init_faiss
import dl.utils as utils
from dl.http import app, delete_file
import uvicorn
import os


def run_server():
    try:
        init()
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception as e:
        print(f'something went wrong: {e}')
        write_data(data)
        return


def main():
    run_server()
