from dataclasses import dataclass, asdict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from docx import Document
from io import BytesIO
from typing import Tuple
import faiss
import numpy as np
import os
from openai import OpenAI
import json


@dataclass
class Chunk:
    title: str  # optional
    text: str
    vec: list[float]


@dataclass
class Doc:
    id: int
    title: str
    chunks: list[Chunk]

    def to_meta(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            'chunks': [],
        }


@dataclass
class State:
    users: dict[str, str]  # key -> username
    prompt: dict[str, str]  # username -> prompt
    chat_history: dict[str, list]  # username -> chat history


@dataclass
class Data:
    state: State
    docs: list[Doc]

    def get_user(self, key: str):
        return self.state.users.get(key, "")

    def add_chat(self, key, msg: str):
        user = self.get_user(key)
        if user == "":
            return
        self.state.chat_history.setdefault(user, []).append(msg)

    def reset_chat(self, key: str):
        user = self.get_user(key)
        if user == "":
            return
        self.state.chat_history[user] = []

    def set_prompt(self, key, prompt: str):
        user = self.get_user(key)
        if user == "":
            return
        self.state.prompt[user] = prompt

    def reset_prompt(self, key):
        self.set_prompt(key, default_prompt)

    def get(self, doc_id: int) -> Doc:
        for d in self.docs:
            if d.id == doc_id:
                return d
        return Doc(0, "", [])

    def next_id(self) -> int:
        if len(self.docs) == 0:
            return 0
        max_id = max(doc.id for doc in self.docs)
        return max_id + 1

    def exist(self, name: str) -> bool:
        for doc in self.docs:
            if doc.title == name:
                return True
        return False

    def add_doc(self, doc: Doc) -> int:
        doc.id = self.next_id()
        self.docs.append(doc)
        # write to local
        return doc.id

    def set_data(self, docs: list[Doc], state: State):
        gray('setting data for docs')
        self.docs = docs
        self.state = state


default_prompt = """
you're a helpful assistant that help user do RAG on their uploaded documents,
you will be provided a list of chunks of documents along with their question,
and answer user's question accurately based on these chunks.

chunk structure: text (from: document_name)
"""


data = Data(docs=[], state=State(
    users={}, prompt={}, chat_history={}))
client: OpenAI = None
prompt = {}
faiss_vec_idx = None
faiss_vec_by_doc_id = None
faiss_meta_idx = []
data_dir = ''
state_path = ''
meta_path = ''
embedding_path = ''
top_n_chunk = 30


def init():
    global data, data_dir, meta_path, embedding_path, state_path, client, prompt, top_n_chunk
    openai_key = os.getenv("dl_openai_key", "")
    if openai_key == "":
        raise Exception("dl_openai_key needs to be set")

    top_n_chunk = int(os.getenv("dl_top_n_chunk", 30))

    prompt = os.getenv("dl_prompt", default_prompt)
    if prompt == "":
        raise Exception("dl_prompt needs to be set")

    client = OpenAI(api_key=openai_key)
    data_dir = f'{os.path.expanduser("~")}/.dl/data'
    meta_path = data_dir + "/meta.json"
    embedding_path = data_dir + "/embeddings.npy"
    state_path = data_dir + "/state.json"
    doc_list, state = read_data()
    data.set_data(doc_list, state)
    gray(f'init docs, exist {len(data.docs)} files')
    if len(data.docs) == 0:
        return
    init_faiss()


def init_faiss():
    gray('init faiss')
    # global faiss_vec_idx
    # global faiss_meta_idx
    global faiss_vec_by_doc_id
    if len(data.docs) == 0:
        return
    # faiss_vec_idx, faiss_meta_idx = build_faiss(data.docs)
    faiss_vec_by_doc_id = build_faiss2(data.docs)


text_splitter = RecursiveCharacterTextSplitter(
    # Set a really small chunk size, just to show.
    chunk_size=400,
    chunk_overlap=50,
    length_function=len,
    is_separator_regex=False,
)


def parse_docx(file: bytes) -> list[Chunk]:
    # Partition the PDF into structured elements
    doc_str = BytesIO(file)

    text = [p.text for p in Document(doc_str).paragraphs if p.text != '']

    chunks = [
        chunk.page_content for chunk in text_splitter.create_documents(text)
    ]

    ret = []
    for chunk in chunks:
        ret.append(Chunk(text=chunk, vec=[], title=''))
    return ret


def read_as_bytes(file_path: str) -> bytes:
    try:
        with open(file_path, 'rb') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file at {file_path} was not found.")
    except Exception as e:
        raise Exception(f"An error occurred while reading the file: {e}")


def openai_call_completion(username, question: str, chunks: list[Chunk]) -> str:
    global data
    if len(chunks) == 0:
        return "no data"
    retrieved_context = "\n".join(
        [f'{chunk.text} ({chunk.title})' for chunk in chunks])
    gray('calling completion api')
    msgs = [
        {"role": "user", "content": msg[4:]} if msg.startswith('usr:') else {
            "role": "assistant", "content": msg[4:]}
        for msg in data.state.chat_history.get(username, [])
    ]
    msgs.insert(
        0, {
            "role": "system",
            "content": data.state.prompt.get(username, default_prompt) +
            " (never format response, just plain text)"})
    msgs = msgs + [{"role": "user",
                   "content": f"Context:\n{retrieved_context}\nQuestion:{question}",
                    }]
    ret = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=msgs)
    return ret.choices[0].message.content


def openai_call_embedding(chunks: list[Chunk], batch_size=50) -> list[Chunk]:
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [chunk.text for chunk in batch]

        # Call the OpenAI Embedding API for the batch
        response = client.embeddings.create(
            input=texts,
            model="text-embedding-3-small"
        )

        # Assign embeddings to the corresponding Chunk objects
        for chunk, embedding_data in zip(batch, response.data):
            chunk.vec = embedding_data.embedding

    return chunks


def write_data(data: Data):
    global data_dir, meta_path, embedding_path
    print('writing to disk...')
    os.makedirs(data_dir, exist_ok=True)
    metadata = []
    embeddings = []
    for idx, doc in enumerate(data.docs):
        meta = doc.to_meta()
        for chunk_idx, chunk in enumerate(doc.chunks):
            embeddings.append(chunk.vec)
            meta['chunks'].append(
                {'text': chunk.text, 'vec_idx': len(embeddings) - 1})
        metadata.append(meta)
    with open(state_path, 'w') as f:
        json.dump(asdict(data.state), f)
    # write meta file
    with open(meta_path, 'w') as f:
        json.dump(metadata, f)
    # write embedding
    embeddings_array = np.array(embeddings, dtype=np.float32)
    np.save(embedding_path, embeddings_array)


def read_data() -> Tuple[list[Doc], State]:
    gray('reading data from disk...')
    global meta_path, embedding_path, state_path
    metas = []
    state = State(prompt={}, chat_history={}, users={})
    try:
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                metas = json.load(f)
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                tmp = json.load(f)
                state = State(**tmp)
        embeddings = np.load(embedding_path)

        for k, v in state.users.items():
            if state.prompt.get(k, "") == "":
                state.prompt[k] = default_prompt

        docs_list = []
        for meta in metas:
            chunks = []
            for chunk in meta['chunks']:
                vec = embeddings[chunk['vec_idx']].tolist()
                chunks.append(Chunk(text=chunk['text'], vec=vec, title=''))
            docs_list.append(Doc(
                id=meta["id"],
                title=meta["title"],
                chunks=chunks
            ))
        return docs_list, state
    except Exception as e:
        print(f'error loading data from disk...: {e}')
        return [], state

# meta is (doc_idx, chunk_idx)


def search_vec2(
        idx: dict[int, faiss.IndexFlatL2],
        query: list[float],
        n=50) -> dict[str, list[int]]:
    gray('search_vec2')
    if idx is None:
        raise Exception('faiss index not initialize')
    query = np.array(query, dtype=np.float32).reshape(1, -1)

    tmp = {}
    for doc_id, index in idx.items():
        dist, indices = index.search(query, n)
        tmp[doc_id] = list(zip(indices[0], dist[0]))

    tmp_list = []
    # find the combined top n
    for doc_id, t in tmp.items():
        for idx, dist in t:
            tmp_list.append((doc_id, idx, dist))

    sorted_data = sorted(tmp_list, key=lambda x: x[2])

    ret = {}
    for doc_id, i, dist in sorted_data[:n]:
        if doc_id not in ret:
            ret[doc_id] = []
        ret[doc_id].append(i)

    return ret


def build_faiss2(
    docs: list[Doc]
) -> dict[int, faiss.IndexFlatL2]:
    indexes = {}
    for doc in docs:
        embeddings = []
        for chunk_idx, chunk in enumerate(doc.chunks):
            embeddings.append(chunk.vec)
            # meta.append((doc.id, chunk_idx))
        # embeddings for one docs
        embeddings_np = np.array(embeddings, dtype=np.float32)
        dimension = embeddings_np.shape[1]
        idx = faiss.IndexFlatL2(dimension)
        idx.add(embeddings_np)
        indexes[doc.id] = idx

    gray('faiss index built')
    return indexes


# meta is (doc_idx, chunk_idx)
def build_faiss(
    docs: list[Doc]
) -> Tuple[faiss.IndexFlatL2, list[Tuple[int, int]]]:
    embeddings = []
    meta = []
    for doc in docs:
        for chunk_idx, chunk in enumerate(doc.chunks):
            embeddings.append(chunk.vec)
            meta.append((doc.id, chunk_idx))
    embeddings_np = np.array(embeddings, dtype=np.float32)
    dimension = embeddings_np.shape[1]
    idx = faiss.IndexFlatL2(dimension)
    idx.add(embeddings_np)
    gray('faiss index built')
    return idx, meta


def search_vec(
        idx: faiss.IndexFlatL2,
        meta: list[Tuple[int, int]],
        query: list[float],
        n=50) -> list[Tuple[int, int, int]]:
    gray('search_vec')
    if idx is None:
        raise Exception('faiss index not initialize')
    query = np.array(query, dtype=np.float32).reshape(1, -1)
    distances, indices = idx.search(query, n)

    ret = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx != -1:
            doc_idx, chunk_idx = meta[idx]
            ret.append((doc_idx, chunk_idx, dist))
    return ret


def search_chunk2(question: str, doc_ids: list[int], chunk_size: int) -> list[Chunk]:
    global data
    ret = openai_call_embedding(
        chunks=[Chunk(text=question, vec=[], title='')])
    question_vec = ret[0].vec
    gray(f"question embedding generated: {len(question_vec)}")
    idxes = search_vec2(filter_vec(doc_ids), question_vec, chunk_size)
    retrived = []
    for doc_id, idx in idxes.items():
        doc = data.get(doc_id)
        for chunk_idx in idx:
            chunk = data.get(doc_id).chunks[chunk_idx]
            chunk.title = doc.title
            retrived.append(chunk)
    gray(f'{len(retrived)} chunks retrived')
    return retrived


def search_chunk(question: str, chunk_size: int) -> list[Chunk]:
    global data
    global faiss_meta_idx
    global faiss_vec_idx
    ret = openai_call_embedding(
        chunks=[Chunk(text=question, vec=[], title='')])
    question_vec = ret[0].vec
    gray(f"question embedding generated: {len(question_vec)}")
    idxes = search_vec(faiss_vec_idx, faiss_meta_idx, question_vec, chunk_size)
    retrived = []
    for (doc_idx, chunk_idx, _) in idxes:
        doc = data.get(doc_idx)
        chunk = data.get(doc_idx).chunks[chunk_idx]
        chunk.title = doc.title
        retrived.append(chunk)
    gray(f'{len(retrived)} chunks retrived')
    return retrived


def yellow(msg: str):
    print(f"\033[33m{msg}\033[0m")


def gray(msg: str):
    print(f'\033[38;5;240m{msg}\033[0m')


def green(msg: str):
    print(f"\033[32m{msg}\033[0m")


def add_uploaded_file(name: str, content: bytes):
    chunks = parse_docx(content)

    # _name = name.removesuffix(".docx")
    for chunk in chunks:
        chunk.text = chunk.text  # add title into the chunk

    # Call OpenAI API to get vector embeddings
    chunks = openai_call_embedding(chunks)

    # Create a new document and add to the Docs instance
    doc = Doc(id=0, title=name, chunks=chunks)
    _ = data.add_doc(doc)
    init_faiss()


def delete_file(idx: int):
    change = False
    for i, doc in enumerate(data.docs):
        if doc.id == idx:
            del data.docs[i]
            change = True
    if change:
        init_faiss()


def ask_question(username, question: str, doc_ids: list[int], chunk_size=50) -> str:
    chunks = search_chunk2(question, doc_ids, chunk_size)
    return openai_call_completion(username, question, chunks)


def filter_vec(doc_ids: list[int]) -> dict[int, faiss.IndexFlatL2]:
    gray(f'filter by docs {doc_ids}')
    if doc_ids is None or len(doc_ids) == 0:
        return faiss_vec_by_doc_id

    ret = {}
    for k, v in faiss_vec_by_doc_id.items():
        if k in doc_ids:
            ret[k] = v

    gray(f'filtered: {ret.keys()}')
    return ret
