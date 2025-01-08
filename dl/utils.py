from dataclasses import dataclass
from typing import Tuple
import faiss
import numpy as np
import os
from openai import OpenAI
from unstructured.partition.docx import partition_docx  # this import is heavy
import json
import io


@dataclass
class ChunkRAG:
    text: str
    doc_title: str

    def str(self) -> str:
        return f'{self.text}\n(from: {self.doc_title})'


@dataclass
class Chunk:
    text: str
    vec: list[float]

    def to_rag(self, title: str) -> ChunkRAG:
        return ChunkRAG(text=self.text, doc_title=title)


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
class Docs:
    data: list[Doc]

    def get(self, id: int) -> Doc:
        for d in self.data:
            if d.id == id:
                return d

    def next_id(self) -> int:
        if len(self.data) == 0:
            return 0
        max_id = max(doc.id for doc in self.data)
        return max_id + 1

    def exist(self, name: str) -> bool:
        for doc in self.data:
            if doc.title == name:
                return True
        return False

    def add_doc(self, doc: Doc) -> int:
        doc.id = self.next_id()
        self.data.append(doc)
        # write to local
        return doc.id

    def set_data(self, data: list[Doc]):
        gray('setting data for docs')
        self.data = data

    def len(self):
        return len(self.data)


docs = Docs(data=[])
client: OpenAI = None
prompt = ''
faiss_vec_idx = None
faiss_meta_idx = []
data_dir = './data'
meta_path = ''
embedding_path = ''
top_n_chunk = 30


def set_prompt(new_prompt: str):
    global prompt
    prompt = new_prompt


def get_prompt() -> str:
    global prompt
    return prompt


def init():
    global docs, data_dir, meta_path, embedding_path, client, prompt, top_n_chunk
    openai_key = os.getenv("dl_openai_key", "")
    if openai_key == "":
        raise Exception("dl_openai_key needs to be set")

    top_n_chunk = int(os.getenv("dl_top_n_chunk", 30))

    default_prompt = """
    you're a helpful assistant that help user do RAG on their uploaded documents, 
    you will be provided a list of chunks of documents along with their question, 
    and answer user's question accurately based on these chunks.

    chunk structure: <text> (from: <document name>)
    """
    prompt = os.getenv("dl_prompt", default_prompt)
    if prompt == "":
        raise Exception("dl_prompt needs to be set")

    client = OpenAI(api_key=openai_key)
    data_dir = f'{os.path.expanduser("~")}/.dl/data'
    meta_path = data_dir + "/meta.json"
    embedding_path = data_dir + "/embeddings.npy"
    doc_list = read_doc_list()
    docs.set_data(doc_list)
    gray(f'init docs, exist {len(docs.data)} files')
    if len(docs.data) == 0:
        return
    init_faiss()


def init_faiss():
    gray('init faiss')
    global docs
    global faiss_vec_idx
    global faiss_meta_idx
    faiss_vec_idx, faiss_meta_idx = build_faiss(docs.data)


def parse_docx(file: bytes) -> list[Chunk]:
    # Partition the PDF into structured elements
    elements = partition_docx(
        file=io.BytesIO(file),
        infer_table_structure=True,
        include_page_breaks=True,
        starting_page_number=1,
        strategy='hi_res'
    )

    new_elements = []
    for elem in elements:
        d = elem.to_dict()
        new_elements.append(Chunk(text=d['text'], vec=[]))
    return new_elements


def read_as_bytes(file_path: str) -> bytes:
    try:
        with open(file_path, 'rb') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file at {file_path} was not found.")
    except Exception as e:
        raise Exception(f"An error occurred while reading the file: {e}")


def parse_doc(path: str) -> list[Chunk]:
    doc_content = read_as_bytes(path)
    return parse_docx(doc_content)


def openai_call_completion(question: str, chunks: list[ChunkRAG]) -> str:
    global prompt
    if len(chunks) == 0:
        return "no data"
    retrieved_context = "\n".join(
        [f'{chunk.text} (from: {chunk.doc_title})' for chunk in chunks])
    gray('calling completion api')
    ret = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{retrieved_context}\n\n"
                    f"Question: {question}"
                ),
            },
        ],)
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


def write_doc_list(docs: list[Doc]):
    global data_dir, meta_path, embedding_path
    print('writing to disk...')
    os.makedirs(data_dir, exist_ok=True)
    metadata = []
    embeddings = []
    for idx, doc in enumerate(docs):
        meta = doc.to_meta()
        for chunk_idx, chunk in enumerate(doc.chunks):
            embeddings.append(chunk.vec)
            meta['chunks'].append(
                {'text': chunk.text, 'vec_idx': len(embeddings) - 1})
        metadata.append(meta)
    # write meta file
    with open(meta_path, 'w') as f:
        json.dump(metadata, f)
    # write embedding
    embeddings_array = np.array(embeddings, dtype=np.float32)
    np.save(embedding_path, embeddings_array)


def read_doc_list() -> list[Doc]:
    gray('reading data from disk...')
    global meta_path, embedding_path
    try:
        with open(meta_path, 'r') as f:
            metas = json.load(f)
        embeddings = np.load(embedding_path)

        docs_list = []
        for meta in metas:
            chunks = []
            for chunk in meta['chunks']:
                vec = embeddings[chunk['vec_idx']].tolist()
                chunks.append(Chunk(text=chunk['text'], vec=vec))
            docs_list.append(Doc(
                id=meta["id"],
                title=meta["title"],
                chunks=chunks
            ))
        return docs_list
    except Exception as e:
        print(f'error loading data from disk...: {e}')
        return []


# meta is (doc_idx, chunk_idx)
def build_faiss(docs: list[Doc]) -> Tuple[faiss.IndexFlatL2, list[Tuple[int, int]]]:
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


def search_vec(idx: faiss.IndexFlatL2, meta: list[Tuple[int, int]], query: list[float], n=30) -> Tuple[int, int, int]:
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


def search_chunk(question: str) -> list[ChunkRAG]:
    global docs
    global faiss_meta_idx
    global faiss_vec_idx
    ret = openai_call_embedding(chunks=[Chunk(text=question, vec=[])])
    question_vec = ret[0].vec
    gray(f"question embedding generated: {len(question_vec)}")
    idxes = search_vec(faiss_vec_idx, faiss_meta_idx, question_vec)
    retrived = []
    for (doc_idx, chunk_idx, _) in idxes:
        doc = docs.get(doc_idx)
        chunk = docs.get(doc_idx).chunks[chunk_idx]
        retrived.append(chunk.to_rag(doc.title))
    gray(f'{len(retrived)} chunks retrived')
    return retrived


def yellow(msg: str):
    print(f"\033[33m{msg}\033[0m")


def gray(msg: str):
    print(f'\033[38;5;240m{msg}\033[0m')


def green(msg: str):
    print(f"\033[32m{msg}\033[0m")

def add_uploaded_file(name: str, content: bytes):
    global docs
    chunks = parse_docx(content)

    # Call OpenAI API to get vector embeddings
    chunks = openai_call_embedding(chunks)

    # Create a new document and add to the Docs instance
    doc = Doc(id=0, title=name, chunks=chunks)
    _ = docs.add_doc(doc)
    init_faiss()

