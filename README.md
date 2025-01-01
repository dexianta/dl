# DocLib
doclib is a simple tool to add docx files (e.g. research papers, etc) and do RAG on it.
- you can add a file or a folder of docx
- once added, the tool chunk it with unstructured lib and send to openai to build embeddings
- provided with you custom prompt, now you can interact with your files

# How to use
`export dl_openai_key=<your key>`
`export dl_data_dir=<custom path> (by default it's ./data)`
