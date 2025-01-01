from dl.utils import openai_call_embedding, Chunk


def test_openai_call_embedding():
    chunks = [Chunk(text="hello", vec=[]), Chunk(text="world", vec=[])]
    ret = openai_call_embedding(chunks)
    print(len(ret[1].vec))
