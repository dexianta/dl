from dl.utils import openai_call_embedding, Chunk, build_faiss2, search_vec2, Doc
import faiss
import numpy as np


def test_openai_call_embedding():
    chunks = [Chunk(text="hello", vec=[], title=''),
              Chunk(text="world", title='', vec=[])]
    ret = openai_call_embedding(chunks)
    print(len(ret[1].vec))


def test_faiss():
    vectors = np.array([
        [1, 1],
        [2, 2],
        [3, 3],
    ], dtype='float32')

    idx = faiss.IndexFlatL2(2)
    idx.add(vectors)
    query = np.array([[2, 2]], dtype='float32')

    dist, ind = idx.search(query, 3)
    print(dist)
    print(ind)


def test_build_search():
    indexes = build_faiss2([
        Doc(
            id=1,
            title='doc1',
            chunks=[
                Chunk(title='', text='1', vec=[1, 1]),
                Chunk(title='', text='2', vec=[2, 2]),
                Chunk(title='', text='3', vec=[3, 3]),
            ]
        ),
        Doc(
            id=2,
            title='doc2',
            chunks=[
                Chunk(title='', text='1.5', vec=[1.5, 1.5]),
                Chunk(title='', text='2.5', vec=[2.5, 2.5]),
                Chunk(title='', text='3.5', vec=[3.5, 3.5]),
            ]
        ),
    ])

    query = np.array([[1, 1]], dtype='float32')
    ret = search_vec2(indexes, query, 2)
    print(ret)
