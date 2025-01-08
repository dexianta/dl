from fastapi import FastAPI, Form, File, UploadFile
from dl.utils import data, write_data
import dl.utils as utils
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import signal

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def main_menu():
    return html_template(f"""
        <h1>File RAG, yooo</h1>
        <ul>
            <li><a href="/files">Manage Files</a></li>
            <li><a href="/set-prompt">Set Prompt</a></li>
            <li><a href="/chunk-search">Search Chunk</a></li>
            <li><a href="/ask-question">Ask Question</a></li>
        </ul>
        <form action="/shutdown" method="post">
            <button type="submit">Close Server</button>
        </form>
    """)


@app.get("/files", response_class=HTMLResponse)
async def manage_files():
    global data
    docs_html = "".join(
        f"""<li>
        <form style="display: inline;" action="/delete-file" method="post">
            <input type="hidden" name="id" value="{doc.id}">
            <button type="submit">x</button>
        </form>
        <span style="font-weight: bold;">{doc.id}</span>.
        <span style="font-weight: bold;">{doc.title}</span>
    </li>"""
        for doc in data.docs
    )
    return html_template(f"""
            <h1> Manage Files</h1>
            <ul> {docs_html} </ul>
             <form id="uploadForm" action="/add-file" method="post" enctype="multipart/form-data">
                <label for="file">Add File (Select File):</label><br>
                <input type="file" id="file" name="file" style=""><br>
                <button id="submitButton" type="submit">Add</button>
            </form>
            """)


@app.post("/delete-file")
async def delete_file(id: int = Form(...)):
    utils.delete_file(id)
    return RedirectResponse("/files", status_code=303)


@app.post("/add-file")
async def add_file(file: UploadFile = File(...)):
    # Get the file name
    file_name = file.filename

    # Read the file content as bytes
    file_content = await file.read()

    print('adding file..', 'name: ', file_name, 'bytes: ', len(file_content))

    utils.add_uploaded_file(file_name, file_content)

    return RedirectResponse("/files", status_code=303)


@app.get("/set-prompt", response_class=HTMLResponse)
async def set_prompt():
    global data
    return html_template(
        f"""
        <h1>Set Prompt</h1>
        <h3> Current Prompt: </h3>
        <p> {data.state.prompt} </p>
        <form action="/set-prompt-do" method="post">
            <label for="query">Set your new prompt:</label>
            <textarea id="query" name="prompt" rows="5" cols="40"></textarea>
            <button type="submit">Set</button>
        </form>
        <form action="/reset-prompt" method="post">
            <button type="submit">Reset</button>
        </form>
    """
    )


@app.post("/reset-chat", response_class=HTMLResponse)
async def reset_chat():
    global data
    data.state.chat_history = []
    return RedirectResponse("/ask-question", status_code=303)


@app.post("/reset-prompt", response_class=HTMLResponse)
async def reset_prompt():
    global data
    data.state.prompt = utils.default_prompt
    return RedirectResponse("/set-prompt", status_code=303)


@app.post("/set-prompt-do", response_class=HTMLResponse)
async def set_prompt_return(prompt: str = Form(...)):
    global data
    data.state.prompt = prompt
    return RedirectResponse("/set-prompt", status_code=303)


@app.get("/chunk-search", response_class=HTMLResponse)
async def search_chunk():
    return html_template(
        """
        <h1>Search Chunk</h1>
        <form id="uploadForm" action="/search-results" method="post">
            <label for="query">Enter Search Query:</label>
            <textarea id="query" name="query" rows="5" cols="40"></textarea>
            <button id="submitButton" type="submit">Search</button>
        </form>
    """
    )


@app.post("/search-results", response_class=HTMLResponse)
async def search_results(query: str = Form(...)):
    ret = utils.search_chunk(query)
    results = [r.str() for r in ret]
    results_html = "".join(f"<li>{result}</li>" for result in results)
    return html_template(f"""
        <h1> Search Results </h1>
        <ul style="list-style-type:disc;margin-left: 20px"> {results_html} </ul>
    """)


@app.get("/ask-question", response_class=HTMLResponse)
async def ask_question():
    chat_html = "".join(
        f"<p>{
            msg}</p>" if msg.startswith('sys:') else f'<p style="color: gray;">{msg}</p>'
        for msg in utils.data.state.chat_history)
    return html_template(f"""
        <h1> Ask a Question </h1>
        <div> {chat_html} </div>
        <form id="uploadForm" action="/submit-question" method="post">
            <label for="query">Enter your question:</label>
            <textarea id="query" name="query" rows="5" cols="40"></textarea>
            <button id="submitButton" type="submit">Search</button>
        </form>
        <form action="/reset-chat" method="post">
            <button type="submit">reset</button>
        </form>
    """)


@app.post("/submit-question", response_class=HTMLResponse)
async def submit_question(query: str = Form(...)):
    answer = utils.ask_question(query)
    utils.data.state.chat_history.append("usr: " + query)
    utils.data.state.chat_history.append("sys: " + answer)
    return RedirectResponse("/ask-question", status_code=303)


@app.on_event("shutdown")
def shutdown_event():
    print('saving data..')
    write_data(data)


@app.post("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGINT)  # Gracefully shut down


def html_template(content):
    return f"""
    <html>
        <head>
            <title>DocLib</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Roboto', sans-serif;
                    font-size: 24px;
                    line-height: 1.6;
                    margin: 20px;
                    color: #333;
                }}
                h1 {{
                    color: #2c3e50;
                }}
                a, button {{
                    font-weight: bold;
                    color: #2980b9;
                    text-decoration: none;
                    cursor: pointer;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                ul {{
                    list-style: none;
                    padding: 0;
                }}
                ul li {{
                    margin: 10px 0;
                }}
                button {{
                    background-color: #2980b9;
                    border: none;
                    padding: 10px 15px;
                    color: white;
                    border-radius: 5px;
                    cursor: pointer;
                }}
                button:disabled {{
                background-color: #ccc;
                    color: #666;
                    cursor: not-allowed;
                    opacity: 0.7;
                }}
                button:hover {{
                    background-color: #3498db;
                }}
                form {{
                    margin-top: 20px;
                }}
                input, textarea {{
                    font-family: 'Roboto', sans-serif;
                    padding: 10px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    width: 100%;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            {content}
            {script}
        </body>
        <a href="/">Go Back</a>
    </html>
    """


script = """
    <script>
        const query = document.getElementById("query");
        if (query) {
            query.addEventListener('keydown', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault()
                    const start = this.selectionStart
                    const end = this.selectionEnd
                    this.value = this.value.substring(0, start) + "\\n" + this.value.substring(end)
                    this.selectionStart = this.selectionEnd = start + 1
                }
            });
        }

        const form = document.getElementById('uploadForm');
        const submitButton = document.getElementById('submitButton');

        if (form && submitButton) {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                submitButton.disabled = true;
                form.submit()
            });
        }
    </script>
"""

upload_script = """
<script>
    </script>
    """
