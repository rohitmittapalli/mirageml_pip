import os
import sys
from io import StringIO

import requests

from ...constants import (
    LLM_GPT_ENDPOINT,
    get_headers,
)

PACKAGE_DIR = os.path.dirname(__file__)
os.environ["TRANSFORMERS_CACHE"] = os.path.join(PACKAGE_DIR, "models")


def _chunk_data(data, metadata):
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2048, chunk_overlap=80)
    docs = text_splitter.create_documents([data])
    chunks = [x.page_content for x in docs]
    meta = [{"data": curr_chunk, "source": metadata["source"]} for curr_chunk in chunks]
    vector_data = local_get_embedding(chunks)

    return chunks, meta, vector_data


def local_get_embedding(text_list, embedding_model_id="BAAI/bge-base-en-v1.5"):
    from sentence_transformers import SentenceTransformer

    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    model_dir = os.path.join(PACKAGE_DIR, "models", embedding_model_id)
    if not os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)
        print("Downloading model to:", model_dir)
        print("This will take a few minutes and only happen once!")

    # TODO: Suppress stdout/stderr
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()

    model = SentenceTransformer(embedding_model_id, cache_folder=model_dir)
    embeddings = model.encode(text_list, normalize_embeddings=False)

    # Restore stdout/stderr
    sys.stdout, sys.stderr = original_stdout, original_stderr

    # Convert the embeddings to a list
    embeddings = embeddings.tolist()  # size = 768
    return embeddings


def local_llm_call(messages, llm_model_id="TheBloke/Llama-2-7b-Chat-GGUF", stream=False):
    from ctransformers import AutoModelForCausalLM

    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    model_dir = os.path.join(PACKAGE_DIR, "models", llm_model_id)
    if not os.path.exists(model_dir):
        os.makedirs(model_dir, exist_ok=True)
        print("Downloading model to:", model_dir)
        print("This will take a few minutes and only happen once!")

    # Suppress stdout/stderr
    original_stdout, original_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()

    llm = AutoModelForCausalLM.from_pretrained(
        "TheBloke/Llama-2-7b-Chat-GGUF",
        model_file="llama-2-7b-chat.Q4_K_M.gguf",
        model_type="llama",
    )

    # Restore stdout/stderr
    sys.stdout, sys.stderr = original_stdout, original_stderr
    formatted_messages = "\n".join([x["content"] for x in messages])

    if stream:
        return llm(formatted_messages, stream=True)
    else:
        return llm(formatted_messages)


def get_embedding(text_list, model="BAAI/bge-small-en-v1.5"):
    raise NotImplementedError


def llm_call(messages, model="gpt-3.5-turbo", stream=False, local=False):
    if local:
        return local_llm_call(messages, stream=stream)
    json_data = {"model": model, "messages": messages, "stream": stream}
    return requests.post(LLM_GPT_ENDPOINT, json=json_data, headers=get_headers(), stream=stream)
