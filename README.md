# DocLib
doclib is a simple tool to add docx files (e.g. research papers, etc) and do RAG on it.
- you can add a file or a folder of docx
- once added, the tool chunk it with unstructured lib and send to openai to build embeddings
- provided with you custom prompt, now you can interact with your files

# How it works
docx files are chunked and embeddings are generated. Then an in-memory faiss L2 index are created
for vector search. When a question is asked, we will search the faiss vector index to find the most
relevant materials to do the RAG.

# How to use
- clone the repo
- `pip install -r requirements.txt`
- `pip install -e .`
- go to another window, run `dl`

### The following env are required/optional to be set
- `export dl_openai_key=<your key>` required
- `export dl_prompt=<your system prompt for all your questions>` required
- `export dl_data_dir=<custom path> (by default it's ./data)` optional
- `export dl_top_n_chunk=<the number to retrive the top n chunks>` optional
