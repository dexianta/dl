from dl.utils import data, parse_doc, openai_call_embedding, Doc, parse_docx, set_prompt, write_data, search_chunk, green, init, openai_call_completion, init_faiss, yellow, get_prompt, set_prompt
import dl.utils as utils
from dl.http import app, delete_file
import uvicorn
import os


def list_files():
    global data
    green(f"------ current files ({len(data.data)}) -------")
    for doc in data.data:
        green(f"{doc.id}. {doc.title}")
    print()


def add_folder(path: str):
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".docx"):
                add_file(os.path.join(root, file))
    init_faiss()


def add_file(path: str, build_idx=False):
    global data
    green(f'add file at: {path}')
    name = os.path.splitext(os.path.basename(path))[0]
    if data.exist(name):
        yellow(f'{name} already exist, skipping..')
        return
    chunks = parse_doc(path)

    # Call OpenAI API to get vector embeddings
    chunks = openai_call_embedding(chunks)

    # Create a new document and add to the Docs instance
    doc = Doc(id=0, title=name, chunks=chunks)
    doc_id = data.add_doc(doc)
    if build_idx:
        init_faiss()
    green(f"file '{name}' added successfully with ID {doc_id}.")

    # regenerate faiss


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
