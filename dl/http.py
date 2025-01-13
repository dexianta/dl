from fastapi import FastAPI, Form, File, UploadFile, Query, HTTPException
from .utils import data, write_data
import dl.utils as utils
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import signal

app = FastAPI()

# Middleware to log requests


@app.get("/", response_class=HTMLResponse)
async def login():
    return html_template("", """
        <h1>Welcome to DocLib</h1>
        <form action="/auth" method="post">
        <label for="secret_key">Enter Your Token:</label><br>
        <input type="text" id="token" name="token" size="20" required><br>
        <button type="submit">Login</button>
        </form>
    """)


@app.post("/auth", response_class=HTMLResponse)
async def auth(token: str = Form(...)):
    check(token)
    return redirect("/menu", token)


@app.get("/menu", response_class=HTMLResponse)
async def main_menu(token: str = Query(...)):
    check(token)
    return html_template(token, f"""
        <h1>DocLib</h1>
        <ul>
            <li><a href="/files?token={token}">Manage Files</a></li>
            <li><a href="/set-prompt?token={token}">Set Prompt</a></li>
            <li><a href="/chunk-search?token={token}">Search Chunk</a></li>
            <li><a href="/ask-question?token={token}">Ask Question</a></li>
        </ul>
    """)


def file_list():
    li = "".join(
        f"""<li>
        <span style="font-weight: bold;">{doc.id}</span>.
        <span style="font-weight: bold;color=green">{doc.tag}</span>.
        <span style="font-weight: bold;">{doc.title}</span>
    </li>"""
        for doc in data.docs
    )
    return f"<ul>{li}</ul>"


@app.get("/files", response_class=HTMLResponse)
async def manage_files(token: str = Query(...)):
    check(token)
    global data
    docs_html = "".join(
        f"""<li>
        <form style="display: inline;" action="/delete-file?token={token}" method="post">
            <input type="hidden" name="id" value="{doc.id}">
            <button type="submit">x</button>
        </form>
        <span style="font-weight: bold;">{doc.id}</span>.
        <span style="font-weight: bold; color:green;">[{doc.tag}]</span>
        <span style="font-weight: bold;">{doc.title}</span>
        <form style="display: inline;" action="/add-tag?token={token}" method="post">
            <input type="hidden" name="id" value="{doc.id}">
            <input type="text" name="tag" placeholder="add tag" size="10" required>
        <button type="submit">Tag</button>
    </form>
    </li>"""
        for doc in data.docs
    )
    return html_template(token, f"""
        <h1> Manage Files</h1>
        <ul> {docs_html} </ul>
         <form id="uploadForm" action="/add-file?token={token}" method="post" enctype="multipart/form-data">
            <label for="file">Add File (Select File):</label><br>
            <input type="file" id="file" name="files" multiple><br>
            <button id="submitButton" type="submit">Add</button>
        </form>
        """)


@app.post("/add-tag")
async def add_tag(id: str = Form(...), token=Query(...), tag: str = Form(...)):
    check(token)
    global data
    print('add-tag', id, tag)
    data.add_doc_tag(int(id), tag)
    return redirect("/files", token)


@app.post("/delete-file")
async def delete_file(id: int = Form(...), token=Query(...)):
    check(token)
    utils.delete_file(id)
    return redirect("/files", token)


@app.post("/add-file")
async def add_file(token=Query(...), files: list[UploadFile] = File(...)):
    check(token)
    # Get the file name
    for file in files:
        file_name = file.filename

        # Read the file content as bytes
        file_content = await file.read()

        print('adding file..', 'name: ', file_name,
              'bytes: ', len(file_content))

        if file_name is None or file_content is None:
            return redirect("/files", token)

        utils.add_uploaded_file(file_name, file_content)
    return redirect("/files", token)


@app.get("/set-prompt", response_class=HTMLResponse)
async def set_prompt(token: str = Query(...)):
    check(token)
    global data
    return html_template(token,
                         f"""
        <h1>Set Prompt</h1>
        <h3> Current Prompt: </h3>
        <p> {data.state.prompt.get(data.get_user(token))} </p>
        <form action="/set-prompt-do?token={token}" method="post">
            <label for="query">Set your new prompt:</label>
            <textarea id="query" name="prompt" rows="5" cols="40"></textarea>
            <button type="submit">Set</button>
        </form>
        <form action="/reset-prompt?token={token}" method="post">
            <button type="submit">Reset</button>
        </form>
    """
    )


@app.post("/reset-chat", response_class=HTMLResponse)
async def reset_chat(token: str = Query(...)):
    check(token)
    global data
    data.reset_chat(token)
    return redirect("/ask-question", token)


@app.post("/reset-prompt", response_class=HTMLResponse)
async def reset_prompt(token: str = Query(...)):
    check(token)
    global data
    data.reset_prompt(token)
    return redirect("/set-prompt", token)


@app.post("/set-prompt-do", response_class=HTMLResponse)
async def set_prompt_do(prompt: str = Form(...), token: str = Query(...)):
    check(token)
    global data
    data.set_prompt(token, prompt)
    return redirect("/set-prompt", token)


@app.get("/chunk-search", response_class=HTMLResponse)
async def search_chunk(token: str = Query(...)):
    check(token)
    return html_template(token,
                         f"""
        <h1>Search Chunk</h1>
        <form id="uploadForm" action="/search-results?token={token}" method="post">
            <label for="query">Enter Search Query:</label>
            <textarea id="query" name="query" rows="5" cols="40"></textarea>

            <div class="form-row">
                <label for="number">Chunk size:</label>
                <input id="number" name="chunk_size" type="number" value="30" required />

                <label for="doc_ids">Doc IDs:</label>
                <input id="doc_ids" name="doc_ids" type="text" placeholder="e.g. 1,2,3"/>

                <label for="doc_ids">Doc Tags:</label>
                <input id="doc_tags" name="doc_tags" type="text" placeholder="e.g. tag1,tag2"/>
            </div>

            <button id="submitButton" type="submit">Submit</button>
        </form>
        <p> --- Available files --- </p>
        {file_list()}
    """
    )


@app.post("/search-results", response_class=HTMLResponse)
async def search_results(
        doc_ids: str = Form(...),
        doc_tags: str = Form(...),
        token: str = Query(...),
        query: str = Form(...),
        chunk_size: int = Form(...)):
    check(token)
    doc_ids_num = parse_comma_separated_ints(doc_ids)
    doc_tags = [x.strip() for x in doc_tags.split(",") if x.strip()]

    ret = utils.search_chunk2(query, doc_tags, doc_ids_num, chunk_size)
    results = [f"{r.text} [{r.tag}] ({r.title})" for r in ret]
    results_html = "".join(
        f"<li>{result}</li>" for result in results)
    return html_template(token, f"""
        <h1> Search Results </h1>
        <ul style="list-style-type:disc;margin-left: 20px"> {results_html} </ul>
    """)


@app.get("/ask-question", response_class=HTMLResponse)
async def ask_question(token: str = Query(...)):
    user = check(token)
    chat_html = "".join(f"<p>{msg}</p>" if msg.startswith('sys:') else f'<p style="color: gray;">{msg}</p>'
                        for msg in utils.data.state.chat_history.get(user, []))
    return html_template(token, f"""
    <h1> Ask a Question </h1>
    <div> {chat_html} </div>
    <form id="uploadForm" action="{r("/submit-question", token)}" method="post">
        <label for="query">Enter your question:</label>
        <textarea id="query" name="query" rows="5" cols="40"></textarea>

        <div class="form-row">
            <label for="number">Chunk size:</label>
            <input id="number" name="chunk_size" type="number" value="30" required />

            <label for="doc_ids">Doc IDs:</label>
            <input id="doc_ids" name="doc_ids" type="text" placeholder="e.g. 1,2,3"/>

            <label for="doc_ids">Doc Tags:</label>
            <input id="doc_tags" name="doc_tags" type="text" placeholder="e.g. tag1,tag2"/>
        </div>
        <button id="submitButton" type="submit">Submit</button>
    </form>
    <form action="{r("/reset-chat", token)}" method="post">
        <button type="submit">reset</button>
    </form>
    <p> --- Available files --- </p>
    {file_list()}
""")


@app.post("/submit-question", response_class=HTMLResponse)
async def submit_question(
        query: str = Form(...),
        token: str = Query(...),
        chunk_size: int = Form(...),
        doc_ids: str = Form(...),
        doc_tags: str = Form(...)):
    doc_ids_num = parse_comma_separated_ints(doc_ids)
    doc_tags = [x.strip() for x in doc_tags.split(",") if x.strip()]
    answer = utils.ask_question(
        check(token), query, doc_ids_num, doc_tags, chunk_size)
    utils.data.add_chat(token, "usr: " + query)
    utils.data.add_chat(token, "sys: " + answer)
    return redirect("/ask-question", token)


@app.on_event("shutdown")
def shutdown_event():
    print('saving data..')
    write_data(data)


@app.post("/shutdown")
async def shutdown():
    os.kill(os.getpid(), signal.SIGINT)  # Gracefully shut down


def authed(key:
           str) -> str:
    global data
    return data.state.users[key]


def r(path:
      str, token: str) -> str:
    return f"{path}?token={token}"


def check(token):
    global data
    user = data.get_user(token)
    if user == "":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def redirect(path, token):
    return RedirectResponse(r(path, token), status_code=303)


def html_template(token, content):
    top_menu = f"""<a href="/menu?token={token}">Top Menu</a>"""
    ret = f"""
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

                .form-row {{
                    display: flex; /* Arrange items in a row */
                    align-items: center; /* Align vertically */
                    gap: 10px; /* Space between items */
                    margin-bottom: 15px; /* Spacing between rows */
                }}

                .form-row input[type="number"],
                .form-row input[type="text"] {{
                    width: 150px; /* Set a fixed width for inputs */
                }}

                .form-row label {{
                    white-space: nowrap; /* Prevent label text wrapping */
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
                input {{
                    font-family: 'Roboto', sans-serif;
                    padding: 10px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    margin-bottom: 10px;
                }}
                textarea {{
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
        #top-menu#
    </html>
    """
    if token != "":
        ret = ret.replace("#top-menu#", top_menu)
    else:
        ret = ret.replace("#top-menu#", "")
    return ret


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


def parse_comma_separated_ints(input_string: str) -> list[int]:
    try:
        return [int(num.strip()) for num in input_string.split(",") if num.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad doc id")
