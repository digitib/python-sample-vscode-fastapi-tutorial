import os

import redis
from fastapi import FastAPI, HTTPException, Request

from models import DocumentPayload

app = FastAPI()

redis_client = redis.StrictRedis(host="0.0.0.0", port=6379, db=0, decode_responses=True)


@app.get("/")
def home(request: Request) -> dict[str, str]:
    url: str = (
        f"https://{os.getenv('CODESPACE_NAME')}-8000.{os.getenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN')}/"
        if os.getenv("CODESPACE_NAME")
        else str(request.base_url)
    )
    return {
        "message": f"Navigate to the following URL to access the Swagger UI: {url}docs"
    }


# Route to add a document
@app.post("/documents/{document_id}/{quantity}")
def add_document(document_name: str, quantity: int) -> dict[str, DocumentPayload]:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0.")

    # Check if document already exists
    document_id_str: str | None = redis_client.hget("document_name_to_id", document_name)

    if document_id_str is not None:
        document_id = int(document_id_str)
        quantity = redis_client.hincrby(f"document_id:{document_id}", "quantity", quantity)
    else:
        # Generate an id for the document
        document_id: int = redis_client.incr("document_ids")
        redis_client.hset(
            f"document_id:{document_id}",
            mapping={
                "document_id": document_id,
                "document_name": document_name,
                "quantity": quantity,
            },
        )
        # Create a set so we can search by name too
        redis_client.hset("document_name_to_id", document_name, document_id)

    return {
        "document": DocumentPayload(document_id=document_id, document_name=document_name, quantity=quantity)
    }


# Route to list a specific document by id but using Redis
@app.get("/documents/{document_id}")
def list_document(document_id: int) -> dict[str, dict[str, str]]:
    if not redis_client.hexists(f"document_id:{document_id}", "document_id"):
        raise HTTPException(status_code=404, detail="Document not found.")
    else:
        return {"document": redis_client.hgetall(f"document_id:{document_id}")}


@app.get("/documents")
def list_documents() -> dict[str, list[DocumentPayload]]:
    documents: list[DocumentPayload] = []
    stored_documents: dict[str, str] = redis_client.hgetall("document_name_to_id")

    for name, id_str in stored_documents.items():
        document_id: int = int(id_str)

        document_name_str: str | None = redis_client.hget(f"document_id:{document_id}", "document_name")
        if document_name_str is not None:
            document_name: str = document_name_str
        else:
            continue  # skip this item if it has no name

        document_quantity_str: str | None = redis_client.hget(
            f"document_id:{document_id}", "quantity"
        )
        if document_quantity_str is not None:
            document_quantity: int = int(document_quantity_str)
        else:
            document_quantity = 0

        documents.append(
            DocumentPayload(document_id=document_id, document_name=document_name, quantity=document_quantity)
        )

    return {"documents": documents}


# Route to delete a specific document by id but using Redis
@app.delete("/documents/{document_id}")
def delete_document(document_id: int) -> dict[str, str]:
    if not redis_client.hexists(f"document_id:{document_id}", "document_id"):
        raise HTTPException(status_code=404, detail="Document not found.")
    else:
        document_name: str | None = redis_client.hget(f"document_id:{document_id}", "document_name")
        redis_client.hdel("document_name_to_id", f"{document_name}")
        redis_client.delete(f"document_id:{document_id}")
        return {"result": "document deleted."}


# Route to remove some quantity of a specific document by id but using Redis
@app.delete("/documents/{document_id}/{quantity}")
def remove_quantity(document_id: int, quantity: int) -> dict[str, str]:
    if not redis_client.hexists(f"document_id:{document_id}", "document_id"):
        raise HTTPException(status_code=404, detail="Document not found.")

    document_quantity: str | None = redis_client.hget(f"document_id:{document_id}", "quantity")

    # if quantity to be removed is higher or equal to document's quantity, delete the document
    if document_quantity is None:
        existing_quantity: int = 0
    else:
        existing_quantity: int = int(document_quantity)
    if existing_quantity <= quantity:
        document_name: str | None = redis_client.hget(f"document_id:{document_id}", "document_name")
        redis_client.hdel("document_name_to_id", f"{document_name}")
        redis_client.delete(f"document_id:{document_id}")
        return {"result": "document deleted."}
    else:
        redis_client.hincrby(f"document_id:{document_id}", "quantity", -quantity)
        return {"result": f"{quantity} documents removed."}
