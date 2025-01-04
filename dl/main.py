from dl.utils import docs, parse_doc, openai_call_embedding, Doc, set_prompt, write_doc_list, search_chunk, green, init, openai_call_completion, init_faiss, yellow, get_prompt, set_prompt
import os


def list_files():
    global docs
    green(f"------ current files ({len(docs.data)}) -------")
    for doc in docs.data:
        green(f"{doc.id}. {doc.title}")
    print()


def add_folder(path: str):
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".docx"):
                add_file(os.path.join(root, file))
    init_faiss()


def add_file(path: str, build_idx=False):
    global docs
    green(f'add file at: {path}')
    name = os.path.splitext(os.path.basename(path))[0]
    if docs.exist(name):
        yellow(f'{name} already exist, skipping..')
        return
    chunks = parse_doc(path)

    # Call OpenAI API to get vector embeddings
    chunks = openai_call_embedding(chunks)

    # Create a new document and add to the Docs instance
    doc = Doc(id=0, title=name, chunks=chunks)
    doc_id = docs.add_doc(doc)
    if build_idx:
        init_faiss()
    green(f"file '{name}' added successfully with ID {doc_id}.")


def delete_file(idx: int):
    global docs
    change = False
    for i, doc in enumerate(docs.data):
        if doc.id == idx:
            del docs.data[i]
            change = True
    if change:
        init_faiss()
    # regenerate faiss


def ask_question(question: str):
    chunks = search_chunk(question)
    green(openai_call_completion(question, chunks))


def main_menu():
    try:
        init()
    except Exception as e:
        print(f'something went wrong: {e}')
        return
    state = "out"
    while True:
        try:
            while True:
                print("------------- Choices -----------")
                green(
                    "1.Add folder 2.Delete file 3.Ask question 4.Search chunk 5.Set Prompt")
                print('-  -  -  -  -  -  -  -  -  -  -  -')
                print("required: export dl_openai_key=<key>")
                print(
                    "optional: export dl_data_dir=<desired location (./data by default)> for internal data")
                print("optional: export dl_top_n_chunk=<integer> (default is 30)")

                list_files()

                choice = input("Enter your choice: ").strip()
                print("===================")
                match choice:
                    case '1':
                        state = 'in'
                        path = input(
                            "Enter the folder path (duplicate files won't be added): ").strip()
                        add_folder(path)
                    case '2':
                        state = 'in'
                        idx = input("Enter idx to delete: ").strip()
                        delete_file(int(idx))
                    case '3':
                        state = 'in'
                        question = input("Enter question: ").strip()
                        ask_question(question)
                    case '4':
                        state = 'in'
                        question = input("Enter question: ").strip()
                        for i, chunk in enumerate(search_chunk(question)):
                            green(f'{i}: {chunk.str()}\n-----')
                    case '5':
                        state = 'in'
                        green('---- current prompt ----')
                        green(get_prompt())
                        question = input("Enter new prompt: ").strip()
                        set_prompt(question)
                    case _:
                        print("pick again")
        except (KeyboardInterrupt, EOFError) as e:
            print(f'exiting ... {e}')
            if state == 'out':
                write_doc_list(docs.data)
                break
            else:
                state = 'out'
                continue

        except Exception as e:
            print(f'something went wrong: {e}')
            write_doc_list(docs.data)
            break


def main():
    main_menu()
# if __name__ == "__main__":
#    main_menu()
