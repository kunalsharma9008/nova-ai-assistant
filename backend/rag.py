import chromadb
import ollama
from pathlib import Path
from pypdf import PdfReader


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DOCUMENTS_DIR = (
    BASE_DIR /
    "data" /
    "documents"
)

CHROMA_DIR = (
    BASE_DIR /
    "data" /
    "chroma"
)


# ============================================================
# SETTINGS
# ============================================================

EMBEDDING_MODEL = "embeddinggemma"

COLLECTION_NAME = "nova_documents"


# ============================================================
# CREATE DIRECTORIES
# ============================================================

DOCUMENTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CHROMA_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CHROMADB
# ============================================================

client = chromadb.PersistentClient(
    path=str(CHROMA_DIR)
)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text,
    chunk_size=1000,
    overlap=200
):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[
            start:end
        ].strip()

        if chunk:

            chunks.append(
                chunk
            )

        start += (
            chunk_size -
            overlap
        )

    return chunks


# ============================================================
# EXTRACT PDF TEXT
# ============================================================

def extract_pdf_text(
    pdf_path
):

    reader = PdfReader(
        str(pdf_path)
    )

    text = ""

    for page in reader.pages:

        page_text = (
            page.extract_text()
        )

        if page_text:

            text += (
                page_text +
                "\n"
            )

    return text


# ============================================================
# INDEX ONE DOCUMENT
# ============================================================

def index_document(
    pdf_path
):

    pdf_path = Path(
        pdf_path
    )

    print()
    print(
        "========================================"
    )
    print(
        "INDEXING DOCUMENT"
    )
    print(
        "File:",
        pdf_path.name
    )
    print(
        "========================================"
    )


    # --------------------------------------------------------
    # Check file
    # --------------------------------------------------------

    if not pdf_path.exists():

        print(
            "File does not exist."
        )

        return {
            "success": False,
            "filename": pdf_path.name,
            "chunks": 0
        }


    # --------------------------------------------------------
    # Extract text
    # --------------------------------------------------------

    try:

        text = extract_pdf_text(
            pdf_path
        )

    except Exception as error:

        print(
            "PDF ERROR:",
            error
        )

        return {
            "success": False,
            "filename": pdf_path.name,
            "chunks": 0
        }


    if not text.strip():

        print(
            "No readable text found."
        )

        return {
            "success": False,
            "filename": pdf_path.name,
            "chunks": 0
        }


    # --------------------------------------------------------
    # Create chunks
    # --------------------------------------------------------

    chunks = chunk_text(
        text
    )

    print(
        "Created chunks:",
        len(chunks)
    )


    # --------------------------------------------------------
    # Create embeddings
    # --------------------------------------------------------

    for index, chunk in enumerate(
        chunks
    ):

        try:

            embedding_response = (
                ollama.embed(
                    model=EMBEDDING_MODEL,
                    input=chunk
                )
            )

            embedding = (
                embedding_response[
                    "embeddings"
                ][0]
            )


            # ------------------------------------------------
            # Unique document ID
            # ------------------------------------------------

            document_id = (
                f"{pdf_path.stem}_{index}"
            )


            # ------------------------------------------------
            # Store in ChromaDB
            # ------------------------------------------------

            collection.upsert(

                ids=[
                    document_id
                ],

                embeddings=[
                    embedding
                ],

                documents=[
                    chunk
                ],

                metadatas=[
                    {
                        "source": pdf_path.name
                    }
                ]
            )


        except Exception as error:

            print(
                "Embedding error:",
                error
            )


    print()
    print(
        "INDEXING COMPLETE"
    )
    print(
        "Document:",
        pdf_path.name
    )
    print(
        "Chunks:",
        len(chunks)
    )
    print(
        "========================================"
    )


    return {
        "success": True,
        "filename": pdf_path.name,
        "chunks": len(chunks)
    }


# ============================================================
# INDEX ALL DOCUMENTS
# ============================================================

def index_documents():

    pdf_files = list(
        DOCUMENTS_DIR.glob(
            "*.pdf"
        )
    )


    if not pdf_files:

        print(
            "No PDF files found."
        )

        return


    total_chunks = 0


    for pdf_file in pdf_files:

        result = index_document(
            pdf_file
        )

        if result["success"]:

            total_chunks += (
                result["chunks"]
            )


    print()
    print(
        "========================================"
    )
    print(
        "RAG INDEXING COMPLETE"
    )
    print(
        "========================================"
    )
    print(
        "Documents:",
        len(pdf_files)
    )
    print(
        "Chunks indexed:",
        total_chunks
    )


# ============================================================
# SEARCH DOCUMENTS
# ============================================================

def search_documents(
    query,
    n_results=3
):

    # --------------------------------------------------------
    # Create query embedding
    # --------------------------------------------------------

    embedding_response = (
        ollama.embed(
            model=EMBEDDING_MODEL,
            input=query
        )
    )

    query_embedding = (
        embedding_response[
            "embeddings"
        ][0]
    )


    # --------------------------------------------------------
    # Search ChromaDB
    # --------------------------------------------------------

    results = collection.query(

        query_embeddings=[
            query_embedding
        ],

        n_results=n_results
    )


    # --------------------------------------------------------
    # Extract results
    # --------------------------------------------------------

    documents = (
        results["documents"][0]
    )

    metadatas = (
        results["metadatas"][0]
    )


    matches = []


    for document, metadata in zip(
        documents,
        metadatas
    ):

        matches.append({

            "text": document,

            "source": metadata[
                "source"
            ]

        })


    return matches


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    index_documents()